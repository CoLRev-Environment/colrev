#! /usr/bin/env python
import logging
import pprint
import re
import unicodedata
from pathlib import Path

import git
import pandas as pd
from thefuzz import fuzz
from tqdm.contrib.concurrent import process_map

from colrev_core.review_manager import RecordState

report_logger = logging.getLogger("colrev_core_report")
logger = logging.getLogger("colrev_core")


pp = pprint.PrettyPrinter(indent=4, width=140)

pd.options.mode.chained_assignment = None  # default='warn'


###########################################################################

# Active-learning deduplication

# Note: code based on
# https://github.com/dedupeio/dedupe-examples/blob/master/csv_example/csv_example.py


# - If the results list does not contain a 'score' value, it is generated
#   manually and we cannot set the 'status' to md_processed
# - If the results list contains a 'score value'

# IMPORTANT: manual_duplicate/manual_non_duplicate fields:
# ID in the (same) deduplication commit
# the same ID may be used for other records in following commits!


def remove_accents(input_str: str) -> str:
    try:
        nfkd_form = unicodedata.normalize("NFKD", input_str)
        wo_ac_str = [rmdiacritics(c) for c in nfkd_form if not unicodedata.combining(c)]
        wo_ac = "".join(wo_ac_str)
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


def prep_references(references: pd.DataFrame) -> dict:

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
    references["author"] = references["author"].str[:60]

    references.loc[
        references.ENTRYTYPE == "inbook", "container_title"
    ] = references.loc[references.ENTRYTYPE == "inbook", "title"]
    if "chapter" in references:
        references.loc[references.ENTRYTYPE == "inbook", "title"] = references.loc[
            references.ENTRYTYPE == "inbook", "chapter"
        ]

    if "title" not in references:
        references["title"] = "nan"
    else:
        references["title"] = (
            references["title"]
            .str.replace(r"[^A-Za-z0-9, ]+", " ", regex=True)
            .str.lower()
        )
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

    # To validate/improve preparation in jupyter notebook:
    # return references
    # Copy to notebook:
    # from colrev_core.review_manager import ReviewManager
    # from colrev_core import dedupe
    # from colrev_core.review_manager import Process, ProcessType
    # REVIEW_MANAGER = ReviewManager()
    # REVIEW_MANAGER.notify(Process(ProcessType.dedupe))
    # df = dedupe.readData(REVIEW_MANAGER)
    # EDITS
    # df.to_csv('export.csv', index=False)

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

    references_dict = references.to_dict("records")
    logger.debug(pp.pformat(references_dict))

    data_d = {}

    for row in references_dict:
        # Note: we need the ID to identify/remove duplicates in the MAIN_REFERENCES.
        # It is ignored in the field-definitions by the deduper!
        # clean_row = [(k, preProcess(k, v)) for (k, v) in row.items() if k != "ID"]
        clean_row = [(k, preProcess(k, v)) for (k, v) in row.items()]
        data_d[row["ID"]] = dict(clean_row)

    return data_d


def preProcess(k, column):
    # From dedupe (TODO : integrate)
    """
    Do a little bit of data cleaning with the help of Unidecode and Regex.
    Things like casing, extra spaces, quotes and new lines can be ignored.
    """
    if k in ["ID", "ENTRYTYPE", "status"]:
        return column

    column = str(column)
    if any(
        column == x for x in ["no issue", "no volume", "no pages", "no author", "nan"]
    ):
        column = None
        return column

    # TODO : compare whether unidecode or rmdiacritics/remove_accents works better.
    # column = unidecode(column)
    column = re.sub("  +", " ", column)
    column = re.sub("\n", " ", column)
    column = column.strip().strip('"').strip("'").lower().strip()
    # If data is missing, indicate that by setting the value to `None`
    if not column:
        column = None
    return column


def readData(REVIEW_MANAGER):

    records = REVIEW_MANAGER.load_records()

    # Note: Because we only introduce individual (non-merged records),
    # there should be no semicolons in origin!
    records_queue = [
        x
        for x in records
        if x["status"]
        not in [RecordState.md_imported, RecordState.md_needs_manual_preparation]
    ]

    # TODO : do not consider md_prescreen_excluded (non-latin alphabets)

    references = pd.DataFrame.from_dict(records_queue)
    references = prep_references(references)

    return references


def setup_active_learning_dedupe(REVIEW_MANAGER, retrain: bool):

    from colrev_core.review_manager import Process, ProcessType
    import dedupe
    from pathlib import Path

    REVIEW_MANAGER.notify(Process(ProcessType.dedupe))

    logging.getLogger("dedupe.training").setLevel(logging.WARNING)
    logging.getLogger("dedupe.api").setLevel(logging.WARNING)

    training_file = Path(".references_dedupe_training.json")
    settings_file = Path(".references_learned_settings")
    if retrain:
        training_file.unlink(missing_ok=True)
        settings_file.unlink(missing_ok=True)

    logger.info("Importing data ...")

    ret_dict = {}

    # TODO : in the readData, we may want to append the status
    # to use Gazetteer (dedupe_io) if applicable

    # TODO  We need to calculate the training data (and prepare it)
    #       from colrev-history
    # -> feed the "old training data", pre-calculated indices into the
    #    active-learning
    # -> see dedupe.py/setup_active_learning_dedupe (end of function)

    # TODO TBD do we assume that MAIN_REFERENCES/post-md_processed
    # does not have duplicates?

    data_d = readData(REVIEW_MANAGER)
    if len(data_d) < 50:
        ret_dict["status"] = "not_enough_data"

    else:

        logger.debug(pp.pformat(data_d))

        def title_corpus():
            for record in data_d.values():
                yield record["title"]

        def container_corpus():
            for record in data_d.values():
                yield record["container_title"]

        def author_corpus():
            for record in data_d.values():
                yield record["author"]

        # Training

        # Define the fields dedupe will pay attention to
        fields = [
            {
                "field": "author",
                "type": "Text",
                "corpus": author_corpus(),
                "has missing": True,
            },
            {"field": "title", "type": "Text", "corpus": title_corpus()},
            {"field": "container_title", "type": "Text", "corpus": container_corpus()},
            {"field": "year", "type": "DateTime"},
            {"field": "volume", "type": "Text", "has missing": True},
            {"field": "number", "type": "Text", "has missing": True},
            {"field": "pages", "type": "String", "has missing": True},
        ]

        # Create a new deduper object and pass our data model to it.
        deduper = dedupe.Dedupe(fields)

        # If we have training data saved from a previous run of dedupe,
        # look for it and load it in.
        # __Note:__ if you want to train from scratch, delete the training_file
        if training_file.is_file():
            logger.info(f"Reading pre-labeled training data from {training_file.name}")
            with open(training_file, "rb") as f:
                deduper.prepare_training(data_d, f)
        else:
            deduper.prepare_training(data_d)

        ret_dict["status"] = "ok"
        ret_dict["deduper"] = deduper

    return ret_dict


def apply_merges(REVIEW_MANAGER, results: list):
    """Apply automated deduplication decisions

    Level: IDs (not origins), requiring IDs to be immutable after md_prepared

    record['status'] can only be set to md_processed after running the
    active-learning classifier and checking whether the record is not part of
    any other duplicate-cluster
    - If the results list does not contain a 'score' value, it is generated
      manually and we cannot set the 'status' to md_processed
    - If the results list contains a 'score value'

    """

    # The merging also needs to consider whether IDs are propagated
    # Completeness of comparisons should be ensured by the
    # append_merges procedure (which ensures that all prior records
    # in global queue_order are considered before completing
    # the comparison/adding records ot the csvs)

    # results = list(itertools.chain(*results))

    records = REVIEW_MANAGER.load_()

    for non_dupe in [x["ID1"] for x in results if "no_duplicate" == x["decision"]]:
        non_dupe_record_list = [x for x in records if x["ID"] == non_dupe]
        if len(non_dupe_record_list) == 0:
            continue
        non_dupe_record = non_dupe_record_list.pop()
        non_dupe_record.update(status=RecordState.md_processed)

    for dupe in [x for x in results if "duplicate" == x["decision"]]:
        try:
            main_record_list = [x for x in records if x["ID"] == dupe["ID1"]]
            if len(main_record_list) == 0:
                continue
            main_record = main_record_list.pop()
            dupe_record_list = [x for x in records if x["ID"] == dupe["ID2"]]
            if len(dupe_record_list) == 0:
                continue
            dupe_record = dupe_record_list.pop()
            origins = main_record["origin"].split(";") + dupe_record["origin"].split(
                ";"
            )
            main_record["origin"] = ";".join(list(set(origins)))
            if "file" in main_record and "file" in dupe_record:
                main_record["file"] = (
                    main_record["file"] + ";" + dupe_record.get("file", "")
                )
            if "score" in dupe:
                conf_details = f"(confidence: {str(round(dupe['score'], 3))})"
            else:
                conf_details = ""
            report_logger.info(
                f"Removed duplicate{conf_details}: "
                + f'{main_record["ID"]} <- {dupe_record["ID"]}'
            )
            # main_record["status"] = str(RecordState.md_processed)
            records = [x for x in records if x["ID"] != dupe_record["ID"]]
            # REVIEW_MANAGER.update_record_by_ID(main_record)
            # REVIEW_MANAGER.update_record_by_ID(dupe_record, delete=True)
        except StopIteration:
            # TODO : check whether this is valid.
            pass

    # Set remaining records to md_processed (not duplicate) because all records
    # have been considered by dedupe
    for record in records:
        if record["status"] == RecordState.md_prepared:
            record["status"] = RecordState.md_processed

    REVIEW_MANAGER.save_records(records)

    git_repo = REVIEW_MANAGER.get_repo()
    git_repo.index.add([str(REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"])])

    return


def apply_manual_deduplication_decisions(REVIEW_MANAGER, results: list):
    """Apply manual deduplication decisions

    Level: IDs (not origins), requiring IDs to be immutable after md_prepared

    Note : record['status'] can only be set to md_processed after running the
    active-learning classifier and checking whether the record is not part of
    any other duplicate-cluster
    """

    # The merging also needs to consider whether IDs are propagated

    records = REVIEW_MANAGER.load_records()

    non_dupe_list = []
    dupe_list = []
    for x in results:
        if "no_duplicate" == x["decision"]:
            non_dupe_list.append([x["ID1"], x["ID2"]])
        if "duplicate" == x["decision"]:
            dupe_list.append([x["ID1"], x["ID2"]])

    for non_dupe_1, non_dupe_2 in non_dupe_list:
        record = [x for x in records if x["ID"] == non_dupe_1].pop()
        if "manual_non_duplicate" in record:
            record["manual_non_duplicate"] = (
                record["manual_non_duplicate"] + ";" + non_dupe_2
            )
        else:
            record["manual_non_duplicate"] = non_dupe_2

        record = [x for x in records if x["ID"] == non_dupe_2].pop()
        if "manual_non_duplicate" in record:
            record["manual_non_duplicate"] = (
                record["manual_non_duplicate"] + ";" + non_dupe_1
            )
        else:
            record["manual_non_duplicate"] = non_dupe_1

        # Note : no need to consider "manual_duplicate" (it stays the same)

    for main_rec_id, dupe_rec_id in dupe_list:
        main_record = [x for x in records if x["ID"] == main_rec_id].pop()
        # Simple way of implementing the closure
        # cases where the main_record has already been merged into another record
        if "MOVED_DUPE" in main_record:
            main_record = [
                x for x in records if x["ID"] == main_record["MOVED_DUPE"]
            ].pop()

        dupe_record = [x for x in records if x["ID"] == dupe_rec_id].pop()

        dupe_record["MOVED_DUPE"] = main_rec_id

        origins = main_record["origin"].split(";") + dupe_record["origin"].split(";")
        main_record["origin"] = ";".join(list(set(origins)))

        if "file" in main_record and "file" in dupe_record:
            main_record["file"] = ";".join([main_record["file"], dupe_record["file"]])
        if "file" in dupe_record and "file" not in main_record:
            main_record["file"] = dupe_record["file"]

        if "manual_duplicate" in main_record:
            main_record["manual_duplicate"] = (
                main_record["manual_duplicate"] + ";" + dupe_rec_id
            )
        else:
            main_record["manual_duplicate"] = dupe_rec_id

        # Note: no need to change "manual_non_duplicate" or "manual_duplicate"
        # in dupe_record because dupe_record will be dropped anyway

        if (
            "manual_non_duplicate" in main_record
            and "manual_non_duplicate" in dupe_record
        ):
            main_record["manual_non_duplicate"] = (
                main_record["manual_non_duplicate"]
                + ";"
                + dupe_record["manual_non_duplicate"]
            )

        # Note : we add the "manual_duplicate" from dedupe record to keep all
        # manual_duplicate classification decisions
        if "manual_duplicate" in dupe_record:
            if "manual_duplicate" in main_record:
                main_record["manual_duplicate"] = (
                    main_record["manual_duplicate"]
                    + ";"
                    + dupe_record["manual_duplicate"]
                )
            else:
                main_record["manual_duplicate"] = dupe_record["manual_duplicate"]

        report_logger.info(
            f"Removed duplicate: {dupe_rec_id} (duplicate of {main_rec_id})"
        )

    records = [x for x in records if x["ID"] not in [d[1] for d in dupe_list]]

    records = [{k: v for k, v in r.items() if k != "MOVED_DUPE"} for r in records]

    REVIEW_MANAGER.save_records(records)

    git_repo = REVIEW_MANAGER.get_repo()
    git_repo.index.add([str(REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"])])

    return


def fix_errors(REVIEW_MANAGER) -> None:
    """Errors are highlighted in the Excel files"""

    from colrev_core.review_manager import Process, ProcessType
    import bibtexparser

    report_logger = logging.getLogger("colrev_core_report")
    logger = logging.getLogger("colrev_core")

    report_logger.info("Dedupe: fix errors")
    logger.info("Dedupe: fix errors")
    REVIEW_MANAGER.notify(Process(ProcessType.dedupe))
    saved_args = locals()

    dupe_file = Path("duplicates_to_validate.xlsx")
    non_dupe_file = Path("non_duplicates_to_validate.xlsx")
    git_repo = git.Repo(str(REVIEW_MANAGER.paths["REPO_DIR"]))
    if dupe_file.is_file():
        dupes = pd.read_excel(dupe_file)
        dupes.fillna("", inplace=True)
        c_to_correct = dupes.loc[dupes["error"] != "", "cluster_id"].to_list()
        dupes = dupes[dupes["cluster_id"].isin(c_to_correct)]
        IDs_to_unmerge = dupes.groupby(["cluster_id"])["ID"].apply(list).tolist()

        if len(IDs_to_unmerge) > 0:
            records = REVIEW_MANAGER.load_records()

            MAIN_REFERENCES_RELATIVE = REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]
            revlist = (
                ((commit.tree / str(MAIN_REFERENCES_RELATIVE)).data_stream.read())
                for commit in git_repo.iter_commits(paths=str(MAIN_REFERENCES_RELATIVE))
            )

            # Note : there could be more than two IDs in the list
            while len(IDs_to_unmerge) > 0:
                filecontents = next(revlist)
                prior_db = bibtexparser.loads(filecontents)
                prior_records = prior_db.entries

                unmerged = []
                for ID_list_to_unmerge in IDs_to_unmerge:
                    report_logger.info(f'Undo merge: {",".join(ID_list_to_unmerge)}')

                    # delete new record, add previous records (from history) to records
                    records = [r for r in records if r["ID"] not in ID_list_to_unmerge]

                    if all(
                        [
                            ID in [r["ID"] for r in prior_records]
                            for ID in ID_list_to_unmerge
                        ]
                    ):
                        for r in prior_records:
                            if r["ID"] in ID_list_to_unmerge:
                                # add the manual_dedupe/non_dupe decision to the records
                                manual_non_duplicates = ID_list_to_unmerge.copy()
                                manual_non_duplicates.remove(r["ID"])

                                if "manual_non_duplicate" in r:
                                    r["manual_non_duplicate"] = (
                                        r["manual_non_duplicate"]
                                        + ";"
                                        + ";".join(manual_non_duplicates)
                                    )
                                else:
                                    r["manual_non_duplicate"] = ";".join(
                                        manual_non_duplicates
                                    )
                                r["status"] = RecordState.md_processed
                                records.append(r)
                                logger.info(f'Restored {r["ID"]}')
                    else:
                        unmerged.append(ID_list_to_unmerge)

                IDs_to_unmerge = unmerged

            records = sorted(records, key=lambda d: d["ID"])
            REVIEW_MANAGER.save_records(records)
            git_repo.index.add([str(REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"])])

    if non_dupe_file.is_file():
        non_dupes = pd.read_excel(non_dupe_file)
        non_dupes.fillna("", inplace=True)
        c_to_correct = non_dupes.loc[non_dupes["error"] != "", "cluster_id"].to_list()
        non_dupes = non_dupes[non_dupes["cluster_id"].isin(c_to_correct)]
        IDs_to_merge = non_dupes.groupby(["cluster_id"])["ID"].apply(list).tolist()

        # TODO : there could be more than two IDs in the list!
        # change the apply_manual_deduplication_decisions() to accept a list of IDs
        if len(IDs_to_merge) > 0:
            auto_dedupe = []
            for ID1, ID2 in IDs_to_merge:
                auto_dedupe.append(
                    {
                        "ID1": ID1,
                        "ID2": ID2,
                        "decision": "duplicate",
                    }
                )
            apply_manual_deduplication_decisions(REVIEW_MANAGER, auto_dedupe)

    if dupe_file.is_file() or non_dupe_file.is_file():
        REVIEW_MANAGER.create_commit(
            "Validate and correct duplicates",
            manual_author=True,
            saved_args=saved_args,
        )
    else:
        logger.error("No file with potential errors found.")
    return


###############################################################################

# Deprecated version of similarity-based, partially-automated matching

# Note : we use some of the functionality in other scripts
# e.g., for checking similarity with curated records in the preparation


def year_similarity(y1: int, y2: int) -> float:
    sim = 0.0
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


def get_similarity_detailed(df_a: pd.DataFrame, df_b: pd.DataFrame) -> dict:

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
        + "]*"
        + "["
        + ",".join([str(weights[g]) for g in range(len(similarities))])
        + "]^T"
    )
    report_logger.debug(f"Similarity score: {round(weighted_average, 4)}")
    report_logger.debug(details)

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
    for base_record_i in range(0, references.shape[0]):
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
    return references.iloc[:, [ck_col, sim_col, details_col]]


def append_merges(batch_item: dict) -> list:

    logger.debug(f'append_merges {batch_item["record"]}')

    references = batch_item["queue"]

    # if the record is the first one added to the records
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
    # drop the first row (similarities are calculated relative to the last row)
    references = references.iloc[:-1, :]
    # if batch_item['record'] == 'AdamsNelsonTodd1992':
    #     references.to_csv('last_similarities.csv')

    max_similarity = references.similarity.max()

    # TODO: it may not be sufficient to consider the record with the highest similarity

    if max_similarity <= batch_item["MERGING_NON_DUP_THRESHOLD"]:
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

    elif (
        max_similarity > batch_item["MERGING_NON_DUP_THRESHOLD"]
        and max_similarity < batch_item["MERGING_DUP_THRESHOLD"]
    ):

        ID = references.loc[references["similarity"].idxmax()]["ID"]
        logger.debug(f"max_similarity ({max_similarity}): {batch_item['record']} {ID}")
        details = references.loc[references["similarity"].idxmax()]["details"]
        logger.debug(details)
        # record_a, record_b = sorted([ID, record["ID"]])
        msg = (
            f'{batch_item["record"]} - {ID}'.ljust(35, " ")
            + f"  - potential duplicate (similarity: {max_similarity})"
        )
        report_logger.info(msg)
        logger.info(msg)
        return [
            {
                "ID1": batch_item["record"],
                "ID2": ID,
                "similarity": max_similarity,
                "decision": "potential_duplicate",
            }
        ]

    else:  # max_similarity >= batch_item["MERGING_DUP_THRESHOLD"]:
        # note: the following status will not be saved in the bib file but
        # in the duplicate_tuples.csv (which will be applied to the bib file
        # in the end)
        ID = references.loc[references["similarity"].idxmax()]["ID"]
        logger.debug(f"max_similarity ({max_similarity}): {batch_item['record']} {ID}")
        details = references.loc[references["similarity"].idxmax()]["details"]
        logger.debug(details)
        msg = (
            f'Dropped duplicate: {batch_item["record"]} (duplicate of {ID})'
            + f" (similarity: {max_similarity})\nDetails: {details}"
        )
        report_logger.info(msg)
        logger.info(msg)
        return [
            {
                "ID1": batch_item["record"],
                "ID2": ID,
                "similarity": max_similarity,
                "decision": "duplicate",
            }
        ]


def get_data(REVIEW_MANAGER):
    from colrev_core.review_manager import RecordState

    # Note: this would also be a place to set records as "no-duplicate" by definition
    # (e.g., for non-duplicated sources marked in the sources)

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


def merge_crossref_linked_records(REVIEW_MANAGER) -> None:
    from colrev_core import prep

    records = REVIEW_MANAGER.load_records()
    git_repo = REVIEW_MANAGER.get_repo()
    for record in records:
        if "crossref" in record:
            crossref_rec = prep.get_crossref_record(record)
            if crossref_rec is None:
                continue

            report_logger.info(
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
            git_repo.index.add([str(REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"])])
    return


def batch(data, REVIEW_MANAGER):
    # the queue (order) matters for the incremental merging (make sure that each
    # additional record is compared to/merged with all prior records in
    # the queue)

    records = REVIEW_MANAGER.load_records()

    # Note: Because we only introduce individual (non-merged records),
    # there should be no semicolons in origin!
    records_queue = [x for x in records if x["ID"] in data["queue"]]

    references = pd.DataFrame.from_dict(records_queue)
    references = prep_references(references)

    n = REVIEW_MANAGER.config["BATCH_SIZE"]
    items_start = data["items_start"]
    it_len = len(data["queue"])
    batch_data = []
    for ndx in range(items_start // n, it_len, n):
        for i in range(ndx, min(ndx + n, it_len)):
            batch_data.append(
                {
                    "record": data["queue"][i],
                    "queue": references.iloc[: i + 1],
                    "MERGING_NON_DUP_THRESHOLD": 0.7,
                    "MERGING_DUP_THRESHOLD": 0.95,
                }
            )

    for ndx in range(0, it_len, n):
        yield batch_data[ndx : min(ndx + n, it_len)]


def main(REVIEW_MANAGER) -> None:

    saved_args = locals()

    logger.info("Process duplicates")

    merge_crossref_linked_records(REVIEW_MANAGER)

    dedupe_data = get_data(REVIEW_MANAGER)

    i = 1
    for dedupe_batch in batch(dedupe_data, REVIEW_MANAGER):

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
