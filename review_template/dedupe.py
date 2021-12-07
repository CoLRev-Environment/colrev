#! /usr/bin/env python
import itertools
import logging
import pprint
import re
import unicodedata

import pandas as pd
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from thefuzz import fuzz
from tqdm.contrib.concurrent import process_map

from review_template.review_manager import RecordState

logger = logging.getLogger("review_template")

MERGING_NON_DUP_THRESHOLD, MERGING_DUP_THRESHOLD = -1, -1
MAIN_REFERENCES = "NA"

pp = pprint.PrettyPrinter(indent=4, width=140)

pd.options.mode.chained_assignment = None  # default='warn'


def remove_accents(input_str: str) -> str:
    try:
        nfkd_form = unicodedata.normalize("NFKD", input_str)
        wo_ac = [rmdiacritics(c) for c in nfkd_form if not unicodedata.combining(c)]
        wo_ac = "".join(wo_ac)
    except ValueError:
        wo_ac = input_str
        pass
    return wo_ac


def rmdiacritics(char: str) -> str:
    """
    Return the base character of char, by "removing" any
    diacritics like accents or curls and strokes and the like.
    """
    desc = unicodedata.name(char)
    cutoff = desc.find(" WITH ")
    if cutoff != -1:
        desc = desc[:cutoff]
        try:
            char = unicodedata.lookup(desc)
        except KeyError:
            pass  # removing "WITH ..." produced an invalid name
    return char


def format_authors_string(authors: str) -> str:
    authors = str(authors).lower()
    authors_string = ""
    authors = remove_accents(authors)

    # abbreviate first names
    # "Webster, Jane" -> "Webster, J"
    # also remove all special characters and do not include separators (and)
    for author in authors.split(" and "):
        if "," in author:
            last_names = [
                word[0] for word in author.split(",")[1].split(" ") if len(word) > 0
            ]
            authors_string = (
                authors_string + author.split(",")[0] + " " + " ".join(last_names) + " "
            )
        else:
            authors_string = authors_string + author + " "
    authors_string = re.sub(r"[^A-Za-z0-9, ]+", "", authors_string.rstrip())
    return authors_string


def year_similarity(y1: int, y2: int) -> float:
    sim = 0
    if int(y1) == int(y2):
        sim = 1
    elif int(y1) in [int(y1) - 1, int(y1) + 1]:
        sim = 0.8
    elif int(y1) in [int(y1) - 2, int(y1) + 2]:
        sim = 0.5
    return sim


def get_record_similarity(record_a: dict, record_b: dict) -> float:
    if "title" not in record_a:
        record_a["title"] = ""
    if "author" not in record_a:
        record_a["author"] = ""
    if "year" not in record_a:
        record_a["year"] = ""
    if "journal" not in record_a:
        record_a["journal"] = ""
    if "volume" not in record_a:
        record_a["volume"] = ""
    if "number" not in record_a:
        record_a["number"] = ""
    if "pages" not in record_a:
        record_a["pages"] = ""
    if "booktitle" not in record_a:
        record_a["booktitle"] = ""
    if "title" not in record_b:
        record_b["title"] = ""
    if "author" not in record_b:
        record_b["author"] = ""
    if "year" not in record_b:
        record_b["year"] = ""
    if "journal" not in record_b:
        record_b["journal"] = ""
    if "volume" not in record_b:
        record_b["volume"] = ""
    if "number" not in record_b:
        record_b["number"] = ""
    if "pages" not in record_b:
        record_b["pages"] = ""
    if "booktitle" not in record_b:
        record_b["booktitle"] = ""

    if "container_title" not in record_a:
        record_a["container_title"] = (
            record_a.get("journal", "")
            + record_a.get("booktitle", "")
            + record_a.get("series", "")
        )

    if "container_title" not in record_b:
        record_b["container_title"] = (
            record_b.get("journal", "")
            + record_b.get("booktitle", "")
            + record_b.get("series", "")
        )

    df_a = pd.DataFrame.from_dict([record_a])
    df_b = pd.DataFrame.from_dict([record_b])

    return get_similarity(df_a.iloc[0], df_b.iloc[0])


def get_similarity_detailed(df_a: pd.DataFrame, df_b: pd.DataFrame) -> float:

    author_similarity = fuzz.ratio(df_a["author"], df_b["author"]) / 100

    title_similarity = fuzz.ratio(df_a["title"].lower(), df_b["title"].lower()) / 100

    # partial ratio (catching 2010-10 or 2001-2002)
    year_similarity = fuzz.ratio(df_a["year"], df_b["year"]) / 100

    outlet_similarity = (
        fuzz.ratio(df_a["container_title"], df_b["container_title"]) / 100
    )

    if str(df_a["journal"]) != "nan":
        # Note: for journals papers, we expect more details
        if df_a["volume"] == df_b["volume"]:
            volume_similarity = 1
        else:
            volume_similarity = 0
        if df_a["number"] == df_b["number"]:
            number_similarity = 1
        else:
            number_similarity = 0
        # sometimes, only the first page is provided.
        if str(df_a["pages"]) == "nan" or str(df_b["pages"]) == "nan":
            pages_similarity = 1
        else:
            if df_a["pages"] == df_b["pages"]:
                pages_similarity = 1
            else:
                if df_a["pages"].split("-")[0] == df_b["pages"].split("-")[0]:
                    pages_similarity = 1
                else:
                    pages_similarity = 0

        # Put more weithe on other fields if the title is very common
        # ie., non-distinctive
        # The list is based on a large export of distinct papers, tabulated
        # according to titles and sorted by frequency
        if [df_a["title"], df_b["title"]] in [
            ["editorial", "editorial"],
            ["editorial introduction", "editorial introduction"],
            ["editorial notes", "editorial notes"],
            ["editor's comments", "editor's comments"],
            ["book reviews", "book reviews"],
            ["editorial note", "editorial note"],
            ["reviewer ackowledgment", "reviewer ackowledgment"],
        ]:
            weights = [0.175, 0, 0.175, 0.175, 0.175, 0.175, 0.125]
        else:
            weights = [0.25, 0.3, 0.13, 0.2, 0.05, 0.05, 0.02]

        sim_names = [
            "authors",
            "title",
            "year",
            "outlet",
            "volume",
            "number",
            "pages",
        ]
        similarities = [
            author_similarity,
            title_similarity,
            year_similarity,
            outlet_similarity,
            volume_similarity,
            number_similarity,
            pages_similarity,
        ]

    else:

        weights = [0.15, 0.75, 0.05, 0.05]
        sim_names = [
            "author",
            "title",
            "year",
            "outlet",
        ]
        similarities = [
            author_similarity,
            title_similarity,
            year_similarity,
            outlet_similarity,
        ]

    weighted_average = sum(
        similarities[g] * weights[g] for g in range(len(similarities))
    )

    details = (
        "["
        + ",".join([sim_names[g] for g in range(len(similarities))])
        + "]"
        + "*weights_vecor^T = "
        + "["
        + ",".join([str(similarities[g]) for g in range(len(similarities))])
        + "]"
        + "["
        + ",".join([str(weights[g]) for g in range(len(similarities))])
        + "]^T"
    )
    logger.debug(details)

    return {"score": round(weighted_average, 4), "details": details}


def get_similarity(df_a: pd.DataFrame, df_b: pd.DataFrame) -> float:
    details = get_similarity_detailed(df_a, df_b)
    return details["score"]


def calculate_similarities_record(references: pd.DataFrame) -> list:
    # Note: per definition, similarities are needed relative to the last row.
    references["similarity"] = 0
    references["details"] = 0
    sim_col = references.columns.get_loc("similarity")
    details_col = references.columns.get_loc("details")
    for base_record_i in range(0, references.shape[0] - 1):
        sim_details = get_similarity_detailed(
            references.iloc[base_record_i], references.iloc[-1]
        )
        references.iloc[base_record_i, sim_col] = sim_details["score"]
        references.iloc[base_record_i, details_col] = sim_details["details"]
    # Note: return all other records (not the comparison record/first row)
    # and restrict it to the ID, similarity and details
    ck_col = references.columns.get_loc("ID")
    sim_col = references.columns.get_loc("similarity")
    details_col = references.columns.get_loc("details")
    return references.iloc[:-1, [ck_col, sim_col, details_col]]


def append_merges(batch_item: dict) -> list:

    logger.debug(f'append_merges {batch_item["record"]}')

    references = batch_item["queue"]

    # if the record is the first one added to the bib_db
    # (in a preceding processing step), it can be propagated
    # if len(batch_item["queue"]) < 2:
    if len(references.index) < 2:
        return [
            {
                "ID1": batch_item["record"],
                "ID2": "NA",
                "similarity": 1,
                "decision": "no_duplicate",
            }
        ]

    # df to get_similarities for each other record
    references = calculate_similarities_record(references)
    # if batch_item['record'] == 'AdamsNelsonTodd1992':
    #     references.to_csv('last_similarities.csv')

    max_similarity = references.similarity.max()

    # TODO: it may not be sufficient to consider the record with the highest similarity

    if max_similarity <= MERGING_NON_DUP_THRESHOLD:
        # Note: if no other record has a similarity exceeding the threshold,
        # it is considered a non-duplicate (in relation to all other records)
        logger.debug(f"max_similarity ({max_similarity})")
        return [
            {
                "ID1": batch_item["record"],
                "ID2": "NA",
                "similarity": max_similarity,
                "decision": "no_duplicate",
            }
        ]

    ID = references.loc[references["similarity"].idxmax()]["ID"]
    logger.debug(f"max_similarity ({max_similarity}): {batch_item['record']} {ID}")
    details = references.loc[references["similarity"].idxmax()]["details"]
    logger.debug(details)
    if (
        max_similarity > MERGING_NON_DUP_THRESHOLD
        and max_similarity < MERGING_DUP_THRESHOLD
    ):

        # record_a, record_b = sorted([ID, record["ID"]])
        logger.info(
            f'{batch_item["record"]} - {ID}'.ljust(35, " ")
            + f"  - potential duplicate (similarity: {max_similarity})"
        )
        return [
            {
                "ID1": batch_item["record"],
                "ID2": ID,
                "similarity": max_similarity,
                "decision": "potential_duplicate",
            }
        ]

    if max_similarity >= MERGING_DUP_THRESHOLD:
        # note: the following status will not be saved in the bib file but
        # in the duplicate_tuples.csv (which will be applied to the bib file
        # in the end)

        logger.info(
            f'Dropped duplicate: {batch_item["record"]} (duplicate of {ID})'
            f" (similarity: {max_similarity})\nDetails: {details}"
        )
        return [
            {
                "ID1": batch_item["record"],
                "ID2": ID,
                "similarity": max_similarity,
                "decision": "duplicate",
            }
        ]


def apply_merges(REVIEW_MANAGER, results: list) -> BibDatabase:

    # The merging also needs to consider whether IDs are propagated
    # Completeness of comparisons should be ensured by the
    # append_merges procedure (which ensures that all prior records
    # in global queue_order are considered before completing
    # the comparison/adding records ot the csvs)

    results = list(itertools.chain(*results))

    non_dupes = [x["ID1"] for x in results if "no_duplicate" == x["decision"]]
    REVIEW_MANAGER.replace_field(
        non_dupes,
        "status",
        str(RecordState.md_processed),
    )

    bib_db = REVIEW_MANAGER.load_main_refs()

    for dupe in [x for x in results if "duplicate" == x["decision"]]:
        try:
            main_record = [x for x in bib_db.entries if x["ID"] == dupe["ID1"]]
            if len(main_record) == 0:
                continue
            main_record = main_record[0]
            dupe_record = [x for x in bib_db.entries if x["ID"] == dupe["ID2"]]
            if len(dupe_record) == 0:
                continue
            dupe_record = dupe_record[0]
            origins = main_record["origin"].split(";") + dupe_record["origin"].split(
                ";"
            )
            main_record["origin"] = ";".join(list(set(origins)))
            if "file" in main_record:
                main_record["file"] = (
                    main_record["file"] + ";" + dupe_record.get("file", "")
                )
                main_record["file"].rstrip(";")
            main_record["status"] = str(RecordState.md_processed)
            bib_db.entries = [x for x in bib_db.entries if x["ID"] != dupe_record["ID"]]
            # REVIEW_MANAGER.update_record_by_ID(main_record)
            # REVIEW_MANAGER.update_record_by_ID(dupe_record, delete=True)
        except StopIteration:
            # TODO : check whether this is valid.
            pass
    REVIEW_MANAGER.save_bib_file(bib_db)

    potential_duplicate_ids = []
    for item in [x for x in results if "potential_duplicate" == x["decision"]]:
        # Note: set set needs_manual_dedupliation without IDs of the potential duplicate
        # because new papers may be added to md_processed
        # (becoming additional potential duplicates)
        potential_duplicate_ids.append(item["ID1"])

    REVIEW_MANAGER.replace_field(
        potential_duplicate_ids,
        "status",
        str(RecordState.md_needs_manual_deduplication),
    )

    # pd_record = next(
    #     REVIEW_MANAGER.read_next_record(conditions={"ID": item["ID1"]})
    # )
    # pd_record["potential_dupes"] = (
    #     pd_record.get("potential_dupes", "") + ";" + item["ID2"]
    # )
    # pd_record["potential_dupes"] = pd_record["potential_dupes"].lstrip(";")
    # pd_record["status"] = str(RecordState.md_needs_manual_deduplication)
    # REVIEW_MANAGER.update_record_by_ID(pd_record)

    # pd_record = next(
    #     REVIEW_MANAGER.read_next_record(conditions={"ID": item["ID2"]})
    # )
    # pd_record["potential_dupes"] = (
    #     pd_record.get("potential_dupes", "") + ";" + item["ID1"]
    # )
    # pd_record["potential_dupes"] = pd_record["potential_dupes"].lstrip(";")
    # pd_record["status"] = str(RecordState.md_needs_manual_deduplication)
    # REVIEW_MANAGER.update_record_by_ID(pd_record)

    # REVIEW_MANAGER.save_record_list_by_ID

    git_repo = REVIEW_MANAGER.get_repo()
    git_repo.index.add([MAIN_REFERENCES])

    return


def prep_references(references: pd.DataFrame) -> pd.DataFrame:
    if "volume" not in references:
        references["volume"] = "nan"
    if "number" not in references:
        references["number"] = "nan"
    if "pages" not in references:
        references["pages"] = "nan"
    if "year" not in references:
        references["year"] = "nan"
    else:
        references["year"] = references["year"].astype(str)
    if "author" not in references:
        references["author"] = "nan"
    else:
        references["author"] = references["author"].apply(
            lambda x: format_authors_string(x)
        )
    if "title" not in references:
        references["title"] = "nan"
    else:
        references["title"] = (
            references["title"]
            .str.replace(r"[^A-Za-z0-9, ]+", " ", regex=True)
            .str.lower()
        )
        if "chapter" in references:
            references.loc[references["title"].isnull(), "title"] = references[
                "chapter"
            ]
        else:
            references.loc[references["title"].isnull(), "title"] = "nan"

    if "journal" not in references:
        references["journal"] = ""
    else:
        references["journal"] = (
            references["journal"]
            .str.replace(r"[^A-Za-z0-9, ]+", "", regex=True)
            .str.lower()
        )
    if "booktitle" not in references:
        references["booktitle"] = ""
    else:
        references["booktitle"] = (
            references["booktitle"]
            .str.replace(r"[^A-Za-z0-9, ]+", "", regex=True)
            .str.lower()
        )
        # possibly for @proceedings{ ... records
        # if 'address' in references:
        #     references['booktitle'] = references["booktitle"] + references["address"]
        #     print(references['address'])
    if "series" not in references:
        references["series"] = ""
    else:
        references["series"] = (
            references["series"]
            .str.replace(r"[^A-Za-z0-9, ]+", "", regex=True)
            .str.lower()
        )

    references["container_title"] = (
        references["journal"].fillna("")
        + references["booktitle"].fillna("")
        + references["series"].fillna("")
    )

    references.drop(
        references.columns.difference(
            [
                "ID",
                "author",
                "title",
                "year",
                "journal",
                "container_title",
                "volume",
                "number",
                "pages",
            ]
        ),
        1,
        inplace=True,
    )
    references[["author", "title", "journal", "container_title", "pages"]] = references[
        ["author", "title", "journal", "container_title", "pages"]
    ].astype(str)

    return references


def get_data(REVIEW_MANAGER):
    from review_template.review_manager import RecordState

    # Note: this would also be a place to set records as "no-duplicate" by definition
    # (e.g., for non-duplicated sources marked in the search_details)

    get_record_state_list = REVIEW_MANAGER.get_record_state_list()
    IDs_to_dedupe = [
        x[0] for x in get_record_state_list if x[1] == str(RecordState.md_prepared)
    ]
    processed_IDs = [
        x[0]
        for x in get_record_state_list
        if x[1]
        not in [
            str(RecordState.md_imported),
            str(RecordState.md_prepared),
            str(RecordState.md_needs_manual_preparation),
            str(RecordState.md_needs_manual_deduplication),
        ]
    ]

    nr_tasks = len(IDs_to_dedupe)
    dedupe_data = {
        "nr_tasks": nr_tasks,
        "queue": processed_IDs + IDs_to_dedupe,
        "items_start": len(processed_IDs),
    }
    logger.debug(pp.pformat(dedupe_data))

    return dedupe_data


def batch(data, n=1):
    # the queue (order) matters for the incremental merging (make sure that each
    # additional record is compared to/merged with all prior records in
    # the queue)

    with open(MAIN_REFERENCES) as target_db:
        bib_db = BibTexParser(
            customization=convert_to_unicode,
            ignore_nonstandard_types=False,
            common_strings=True,
        ).parse_file(target_db, partial=True)
    # Note: Because we only introduce individual (non-merged records),
    # there should be no semicolons in origin!
    records_queue = [x for x in bib_db.entries if x["ID"] in data["queue"]]

    references = pd.DataFrame.from_dict(records_queue)
    references["author"] = references["author"].str[:60]
    references = prep_references(references)

    items_start = data["items_start"]
    it_len = len(data["queue"])
    batch_data = []
    for ndx in range(items_start // n, it_len, n):
        for i in range(ndx, min(ndx + n, it_len)):
            batch_data.append(
                {
                    "record": data["queue"][i],
                    "queue": references.iloc[: i + 1],
                }
            )

    for ndx in range(0, it_len, n):
        yield batch_data[ndx : min(ndx + n, it_len)]


def merge_crossref_linked_records(REVIEW_MANAGER) -> None:
    from review_template import prepare

    bib_db = REVIEW_MANAGER.load_main_refs()
    git_repo = REVIEW_MANAGER.get_repo()
    for record in bib_db.entries:
        if "crossref" in record:
            crossref_rec = prepare.get_crossref_record(record)
            if crossref_rec is None:
                continue

            logger.info(
                f'Resolved crossref link: {record["ID"]} <- {crossref_rec["ID"]}'
            )
            apply_merges(
                REVIEW_MANAGER,
                [
                    {
                        "ID1": record["ID"],
                        "ID2": crossref_rec["ID"],
                        "similarity": 1,
                        "decision": "duplicate",
                    }
                ],
            )
            git_repo.index.add([MAIN_REFERENCES])
    return


def main(REVIEW_MANAGER) -> None:

    saved_args = locals()

    global MERGING_NON_DUP_THRESHOLD
    MERGING_NON_DUP_THRESHOLD = REVIEW_MANAGER.config["MERGING_NON_DUP_THRESHOLD"]

    global MERGING_DUP_THRESHOLD
    MERGING_DUP_THRESHOLD = REVIEW_MANAGER.config["MERGING_DUP_THRESHOLD"]

    global MAIN_REFERENCES
    MAIN_REFERENCES = REVIEW_MANAGER.paths["MAIN_REFERENCES"]

    logger.info("Process duplicates")

    merge_crossref_linked_records(REVIEW_MANAGER)

    dedupe_data = get_data(REVIEW_MANAGER)

    i = 1
    for dedupe_batch in batch(dedupe_data, REVIEW_MANAGER.config["BATCH_SIZE"]):

        print(f"Batch {i}")
        i += 1

        dedupe_batch_results = process_map(
            append_merges, dedupe_batch, max_workers=REVIEW_MANAGER.config["CPUS"]
        )

        # dedupe_batch[-1]['queue'].to_csv('last_references.csv')

        apply_merges(REVIEW_MANAGER, dedupe_batch_results)

        REVIEW_MANAGER.create_commit("Process duplicates", saved_args=saved_args)

    if 1 == i:
        logger.info("No records to check for duplicates")

    return
