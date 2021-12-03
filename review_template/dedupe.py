#! /usr/bin/env python
import csv
import itertools
import logging
import multiprocessing as mp
import os
import pprint
import re
import unicodedata

import pandas as pd
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from thefuzz import fuzz

from review_template import prepare
from review_template.review_manager import RecordState

nr_records_added, nr_current_records = 0, 0

logger = logging.getLogger("review_template")

MERGING_NON_DUP_THRESHOLD, MERGING_DUP_THRESHOLD, BATCH_SIZE = -1, -1, -1
MAIN_REFERENCES = "NA"

pp = pprint.PrettyPrinter(indent=4, width=140)

pd.options.mode.chained_assignment = None  # default='warn'

current_batch_counter = mp.Value("i", 0)


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

    author_similarity = fuzz.partial_ratio(df_a["author"], df_b["author"]) / 100

    title_similarity = (
        fuzz.partial_ratio(df_a["title"].lower(), df_b["title"].lower()) / 100
    )

    # partial ratio (catching 2010-10 or 2001-2002)
    year_similarity = fuzz.partial_ratio(df_a["year"], df_b["year"]) / 100

    outlet_similarity = (
        fuzz.partial_ratio(df_a["container_title"], df_b["container_title"]) / 100
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

    return {"score": round(weighted_average, 4), "details": details}


def get_similarity(df_a: pd.DataFrame, df_b: pd.DataFrame) -> float:
    details = get_similarity_detailed(df_a, df_b)
    return details["score"]


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
            .str.replace(r"[^A-Za-z0-9, ]+", "", regex=True)
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


def calculate_similarities_record(references: pd.DataFrame) -> list:
    # Note: per definition, similarities are needed relative to the first row.
    references = prep_references(references)
    # references.to_csv('preped_references.csv')
    references["similarity"] = 0
    references["details"] = 0
    sim_col = references.columns.get_loc("similarity")
    details_col = references.columns.get_loc("details")
    for base_record_i in range(1, references.shape[0]):
        sim_details = get_similarity_detailed(
            references.iloc[base_record_i], references.iloc[0]
        )
        references.iloc[base_record_i, sim_col] = sim_details["score"]
        references.iloc[base_record_i, details_col] = sim_details["details"]
    # Note: return all other records (not the comparison record/first row)
    # and restrict it to the ID, similarity and details
    ck_col = references.columns.get_loc("ID")
    sim_col = references.columns.get_loc("similarity")
    details_col = references.columns.get_loc("details")
    return references.iloc[1:, [ck_col, sim_col, details_col]]


def get_prev_queue(queue_order: list, origin: str) -> list:
    # Note: Because we only introduce individual (non-merged records),
    # there should be no semicolons in origin!
    prev_records = []
    for idx, el in enumerate(queue_order):
        if origin == el:
            prev_records = queue_order[:idx]
            break
    return prev_records


def append_merges(record: dict) -> None:
    global current_batch_counter
    logger.debug(f'append_merges {record["ID"]}: \n{pp.pformat(record)}\n\n')

    if RecordState.md_prepared != record["status"]:
        return

    with current_batch_counter.get_lock():
        if current_batch_counter.value >= BATCH_SIZE:
            return
        else:
            current_batch_counter.value += 1

    with open(MAIN_REFERENCES) as target_db:
        bib_db = BibTexParser(
            customization=convert_to_unicode,
            ignore_nonstandard_types=False,
            common_strings=True,
        ).parse_file(target_db, partial=True)

    # add all processed records to the queue order before first (re)run
    if not os.path.exists("queue_order.csv"):
        with open("queue_order.csv", "a") as fd:
            for x in bib_db.entries:
                if RecordState.md_processed == x["status"]:
                    fd.write(x["origin"] + "\n")

    # the order matters for the incremental merging (make sure that each
    # additional record is compared to/merged with all prior records in
    # the queue)
    with open("queue_order.csv", "a") as fd:
        fd.write(record["origin"] + "\n")
    queue_order = pd.read_csv("queue_order.csv", header=None)
    queue_order = queue_order[queue_order.columns[0]].tolist()
    required_prior_record_links = get_prev_queue(queue_order, record["origin"])

    record_links_in_prepared_file = []
    # note: no need to wait for completion of preparation
    record_links_in_prepared_file = [
        record["origin"].split(";") for record in bib_db.entries if "origin" in record
    ]
    record_links_in_prepared_file = list(
        itertools.chain(*record_links_in_prepared_file)
    )

    # if the record is the first one added to the bib_db
    # (in a preceding processing step), it can be propagated
    if len(required_prior_record_links) < 2:
        if not os.path.exists("non_duplicates.csv"):
            with open("non_duplicates.csv", "a") as fd:
                fd.write('"ID"\n')
        with open("non_duplicates.csv", "a") as fd:
            fd.write('"' + record["ID"] + '"\n')
        return

    merge_ignore_status = [
        RecordState.md_needs_manual_preparation,
        RecordState.md_needs_manual_deduplication,
    ]

    prior_records = [
        x for x in bib_db.entries if x["status"] not in merge_ignore_status
    ]

    prior_records = [
        x
        for x in prior_records
        if any(
            record_link in x["origin"].split(",")
            for record_link in required_prior_record_links
        )
    ]

    if len(prior_records) < 1:
        # Note: the first record is a non_duplicate (by definition)
        if not os.path.exists("non_duplicates.csv"):
            with open("non_duplicates.csv", "a") as fd:
                fd.write('"ID"\n')
        with open("non_duplicates.csv", "a") as fd:
            fd.write('"' + record["ID"] + '"\n')
        return

    # df to get_similarities for each other record
    record["status"] = str(record["status"])
    for pr in prior_records:
        pr["status"] = str(pr["status"])
    references = pd.DataFrame.from_dict([record] + prior_records)

    # drop the same ID record
    # Note: the record is simply added as the first row.
    # references = references[~(references['ID'] == record['ID'])]
    # dropping them before calculating similarities prevents errors
    # caused by unavailable fields!
    # Note: ignore records that need manual preparation in the merging
    # (until they have been prepared!)
    references = references[
        ~references["status"].str.contains(
            "|".join([str(x) for x in merge_ignore_status]), na=False
        )
    ]

    # means that all prior records are tagged as md_needs_manual_preparation
    if references.shape[0] == 0:
        if not os.path.exists("non_duplicates.csv"):
            with open("non_duplicates.csv", "a") as fd:
                fd.write('"ID"\n')
        with open("non_duplicates.csv", "a") as fd:
            fd.write('"' + record["ID"] + '"\n')
        return
    references = calculate_similarities_record(references)

    max_similarity = references.similarity.max()
    ID = references.loc[references["similarity"].idxmax()]["ID"]
    details = references.loc[references["similarity"].idxmax()]["details"]
    logger.debug(f"max_similarity ({max_similarity}): {ID}")
    if max_similarity <= MERGING_NON_DUP_THRESHOLD:
        # Note: if no other record has a similarity exceeding the threshold,
        # it is considered a non-duplicate (in relation to all other records)
        if not os.path.exists("non_duplicates.csv"):
            with open("non_duplicates.csv", "a") as fd:
                fd.write('"ID"\n')
        with open("non_duplicates.csv", "a") as fd:
            fd.write('"' + record["ID"] + '"\n')
    if (
        max_similarity > MERGING_NON_DUP_THRESHOLD
        and max_similarity < MERGING_DUP_THRESHOLD
    ):
        # The md_needs_manual_deduplication status is only set
        # for one element of the tuple!
        if not os.path.exists("potential_duplicate_tuples.csv"):
            with open("potential_duplicate_tuples.csv", "a") as fd:
                fd.write('"ID1","ID2","max_similarity"\n')
        with open("potential_duplicate_tuples.csv", "a") as fd:
            # to ensure a consistent order
            record_a, record_b = sorted([ID, record["ID"]])
            line = (
                '"' + record_a + '","' + record_b + '","' + str(max_similarity) + '"\n'
            )
            fd.write(line)
        logger.info(
            f'{ID} - {record["ID"]}'.ljust(35, " ")
            + f"  - potential duplicate (similarity: {max_similarity})"
        )

    if max_similarity >= MERGING_DUP_THRESHOLD:
        # note: the following status will not be saved in the bib file but
        # in the duplicate_tuples.csv (which will be applied to the bib file
        # in the end)
        if not os.path.exists("duplicate_tuples.csv"):
            with open("duplicate_tuples.csv", "a") as fd:
                fd.write('"ID1","ID2"\n')
        with open("duplicate_tuples.csv", "a") as fd:
            fd.write('"' + ID + '","' + record["ID"] + '"\n')
        logger.info(
            f'Dropped duplicate: {ID} <- {record["ID"]}'
            f" (similarity: {max_similarity})\nDetails: {details}"
        )

    return


def apply_merges(bib_db: BibDatabase) -> BibDatabase:

    # The merging also needs to consider whether IDs are propagated
    # Completeness of comparisons should be ensured by the
    # append_merges procedure (which ensures that all prior records
    # in global queue_order are considered before completing
    # the comparison/adding records ot the csvs)

    try:
        os.remove("queue_order.csv")
    except FileNotFoundError:
        pass

    merge_details = ""
    # Always merge clear duplicates: row[0] <- row[1]
    if os.path.exists("duplicate_tuples.csv"):
        with open("duplicate_tuples.csv") as read_obj:
            csv_reader = csv.reader(read_obj)
            for row in csv_reader:
                el_to_merge = []
                file_to_merge = "NA"
                for record in bib_db.entries:
                    if record["ID"] == row[1]:
                        el_to_merge = record["origin"].split(";")
                        file_to_merge = record.get("file", "NA")
                        # Drop the duplicated record
                        bib_db.entries = [
                            i for i in bib_db.entries if not (i["ID"] == record["ID"])
                        ]
                        break
                for record in bib_db.entries:
                    if record["ID"] == row[0]:
                        els = el_to_merge + record["origin"].split(";")
                        els = list(set(els))
                        if "NA" != file_to_merge:
                            if "file" in record:
                                record["file"] = (
                                    record.get("file", "") + ";" + file_to_merge
                                )
                            else:
                                record["file"] = file_to_merge
                        record.update(origin=str(";".join(els)))
                        if RecordState.md_prepared == record["status"]:
                            record.update(status=RecordState.md_processed)
                        merge_details += row[0] + " < " + row[1] + "\n"
                        break

    # Set clear non-duplicates to completely processed
    if os.path.exists("non_duplicates.csv"):
        with open("non_duplicates.csv") as read_obj:
            csv_reader = csv.reader(read_obj)
            for row in csv_reader:
                for record in bib_db.entries:
                    if record["ID"] == row[0]:
                        if RecordState.md_prepared == record["status"]:
                            record.update(status=RecordState.md_processed)
        os.remove("non_duplicates.csv")

    # note: potential_duplicate_tuples need to be processed manually but we
    # tag the second record (row[1]) as "md_needs_mual_deduplication"
    if os.path.exists("potential_duplicate_tuples.csv"):
        with open("potential_duplicate_tuples.csv") as read_obj:
            csv_reader = csv.reader(read_obj)
            for row in csv_reader:
                for record in bib_db.entries:
                    if (record["ID"] == row[0]) or (record["ID"] == row[1]):
                        record.update(status=RecordState.md_needs_manual_deduplication)
        potential_duplicates = pd.read_csv("potential_duplicate_tuples.csv", dtype=str)
        potential_duplicates.sort_values(
            by=["max_similarity", "ID1", "ID2"], ascending=False, inplace=True
        )
        potential_duplicates.to_csv(
            "potential_duplicate_tuples.csv",
            index=False,
            quoting=csv.QUOTE_ALL,
            na_rep="NA",
        )

    return bib_db


def main(REVIEW_MANAGER) -> None:

    saved_args = locals()
    global MERGING_NON_DUP_THRESHOLD
    global MERGING_DUP_THRESHOLD
    global MAIN_REFERENCES
    global BATCH_SIZE

    MERGING_NON_DUP_THRESHOLD = REVIEW_MANAGER.config["MERGING_NON_DUP_THRESHOLD"]
    MERGING_DUP_THRESHOLD = REVIEW_MANAGER.config["MERGING_DUP_THRESHOLD"]
    MAIN_REFERENCES = REVIEW_MANAGER.paths["MAIN_REFERENCES"]
    BATCH_SIZE = REVIEW_MANAGER.config["BATCH_SIZE"]
    bib_db = REVIEW_MANAGER.load_main_refs()
    git_repo = REVIEW_MANAGER.get_repo()

    logger.info("Process duplicates")

    for record in bib_db.entries:
        if "crossref" in record:
            crossref_rec = prepare.get_crossref_record(record)
            if crossref_rec is None:
                continue

            if not os.path.exists("duplicate_tuples.csv"):
                with open("duplicate_tuples.csv", "a") as fd:
                    fd.write('"ID1","ID2"\n')
            with open("duplicate_tuples.csv", "a") as fd:
                fd.write('"' + record["ID"] + '","' + crossref_rec["ID"] + '"\n')
            logger.info(
                f'Resolved crossref link: {record["ID"]} <- {crossref_rec["ID"]}'
            )

    in_process = True
    batch_start, batch_end = 1, 0
    while in_process:
        with current_batch_counter.get_lock():
            batch_start += current_batch_counter.value
            current_batch_counter.value = 0  # start new batch
        if batch_start > 1:
            logger.info("Continuing batch duplicate processing started earlier")

        pool = mp.Pool(REVIEW_MANAGER.config["CPUS"])
        pool.map(append_merges, bib_db.entries)
        pool.close()
        pool.join()

        bib_db = apply_merges(bib_db)

        with current_batch_counter.get_lock():
            batch_end = current_batch_counter.value + batch_start - 1

        if batch_end > 0:
            logger.info(
                "Completed duplicate processing batch "
                f"(records {batch_start} to {batch_end})"
            )

            REVIEW_MANAGER.save_bib_file(bib_db)
            if os.path.exists("potential_duplicate_tuples.csv"):
                git_repo.index.add(["potential_duplicate_tuples.csv"])
            if os.path.exists("duplicate_tuples.csv"):
                os.remove("duplicate_tuples.csv")
            git_repo.index.add([MAIN_REFERENCES])

            in_process = REVIEW_MANAGER.create_commit("Process duplicates", saved_args)
            if not in_process:
                logger.info("No duplicates merged/potential duplicates identified")

        if batch_end < BATCH_SIZE or batch_end == 0:
            if batch_end == 0:
                logger.info("No records to check for duplicates")
            break

    return
