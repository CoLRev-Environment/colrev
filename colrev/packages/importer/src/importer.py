#! /usr/bin/env python
"""Importer"""
from pathlib import Path

import inquirer
import pandas as pd
from bib_dedupe.bib_dedupe import block
from bib_dedupe.bib_dedupe import cluster
from bib_dedupe.bib_dedupe import match
from bib_dedupe.bib_dedupe import merge
from bib_dedupe.bib_dedupe import prep

import colrev.ops.check
import colrev.ops.search_api_feed
import colrev.record.record
import colrev.review_manager
import colrev.search_file
from colrev.constants import Fields
from colrev.constants import RecordState
from colrev.constants import SearchType

# TODO : clarify difference between the different imports of merge:
# TODO : bib_dedupe docs: not mentioning merge_functions !?
# from bib_dedupe.merge import merge
# from bib_dedupe.bib_dedupe import merge


def _get_import_type() -> str:
    questions = [
        inquirer.List(
            "decision",
            message="Select",
            choices=["records", "prescreening decisions", "screening decisions"],
        ),
    ]

    answers = inquirer.prompt(questions)
    import_type = answers["decision"]
    return import_type


def _get_import_path() -> Path:
    def validate_path(_, path: str) -> bool:  # type: ignore
        # pylint: disable=broad-exception-caught
        if not Path(path).is_dir() and not Path(path).is_symlink():
            print("No directory found at the specified path.")
            return False

        try:
            colrev.review_manager.ReviewManager(path_str=path)
        except Exception as e:
            print(e)
            return False

        return True

    path_question = [
        inquirer.Path(
            "path",
            message="Enter the path to import data from",
            validate=validate_path,
        ),
    ]

    path_answer = inquirer.prompt(path_question)
    return Path(path_answer["path"])


def _get_mapping(records: dict, *, other_records: dict) -> dict:

    records_df = pd.DataFrame(records.values())
    other_records_df = pd.DataFrame(other_records.values())

    other_records_df[Fields.ID] = "other_" + other_records_df[Fields.ID].astype(str)

    # set search_set column to prevent duplicates within sets
    records_df["search_set"] = "original"
    other_records_df["search_set"] = "other"

    combined_records_df = pd.concat([records_df, other_records_df], ignore_index=True)

    merged_df = merge(combined_records_df)
    merged_df = merged_df[merged_df["origin"].str.contains(";")]
    origins = merged_df["origin"].tolist()

    # id: other_id
    mapping = {}
    for origin in origins:
        if origin.count(";") != 1:
            print(origin)
            continue
        o_1, o_2 = origin.split(";")
        if o_1.startswith("other_") and not o_2.startswith("other_"):
            mapping[o_2] = o_1.replace("other_", "")
        elif o_2.startswith("other_") and not o_1.startswith("other_"):
            mapping[o_1] = o_2.replace("other_", "")
        else:
            print(origin)
    return mapping


def _import_prescreening_decisions(
    review_manager: colrev.review_manager.ReviewManager,
    *,
    other_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    colrev.ops.check.CheckOperation(other_review_manager)
    other_records = other_review_manager.dataset.load_records_dict()
    review_manager.get_prescreen_operation()
    records = review_manager.dataset.load_records_dict()

    print(f"Records in current repository: {len(records)}")

    print("Matching strategy: bib-dedupe match")

    # TODO : allow strategies: same include/exclude decisions, only include / only exclude

    mapping = _get_mapping(records, other_records=other_records)
    for original_id, other_id in mapping.items():
        other_prescreen_included = other_records[other_id][Fields.STATUS] not in [
            RecordState.rev_prescreen_excluded,
            RecordState.md_retrieved,
            RecordState.md_imported,
            RecordState.md_needs_manual_preparation,
            RecordState.md_prepared,
            RecordState.md_processed,
        ]
        if other_prescreen_included:
            records[original_id][Fields.STATUS] = RecordState.rev_prescreen_included
        else:
            records[original_id][Fields.STATUS] = RecordState.rev_prescreen_excluded

    print(f"Import from {len(other_records)} records")
    print(f"Prescreening decisions available: {len(mapping)}")
    print(f"Matching rate: {len(mapping)/len(records)}")

    review_manager.dataset.save_records_dict(records)
    review_manager.create_commit(
        msg=f"Import prescreening decisions from repository ({other_review_manager.path.name})",
        manual_author=False,
    )


def _import_records(
    review_manager: colrev.review_manager.ReviewManager,
    *,
    other_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    print("Importing records")
    print(f"From {other_review_manager.path}")
    print(f"To   {review_manager.path}")

    if (
        "y"
        != input(
            "This will import all records (including PDFs and origins) "
            "from the other repository. Proceed? [yN] "
        ).lower()
    ):
        print("Aborting")
        return

    colrev.ops.check.CheckOperation(review_manager)
    colrev.ops.check.CheckOperation(other_review_manager)

    other_records = other_review_manager.dataset.load_records_dict()
    records = review_manager.dataset.load_records_dict()

    other_records_df = pd.DataFrame(other_records.values())
    # prefix IDs with "other_" to avoid collisions
    other_records_df[Fields.ID] = "other_" + other_records_df[Fields.ID].astype(str)
    records_df = pd.DataFrame(records.values())
    records_df["search_set"] = "old_set"

    combined_records_df = pd.concat([records_df, other_records_df], ignore_index=True)
    combined_records_df["prev_ID"] = combined_records_df[Fields.ID]

    records_df = prep(combined_records_df, verbosity_level=0)

    # Block records
    blocked_df = block(records_df, verbosity_level=0)

    target_files_search_source = None
    for search_source in review_manager.settings.sources:
        if search_source.search_type == SearchType.FILES:
            target_files_search_source = search_source
    if not target_files_search_source:
        print("No Files source found -- creating one")
        target_files_search_source = colrev.search_file.ExtendedSearchFile(
            search_string="",
            platform="colrev.files_dir",
            search_type=SearchType.FILES,
            search_results_path=Path("data/search/files.bib"),
            version="1.0.0",
        )
        review_manager.settings.sources.append(target_files_search_source)
        review_manager.settings.save_settings_file()

    target_files_dir_feed = colrev.ops.search_api_feed.SearchAPIFeed(
        source_identifier=Fields.FILE,
        search_source=target_files_search_source,
        update_only=False,
        logger=review_manager.logger,
        verbose_mode=False,
    )

    origin_files_search_source = None
    for search_source in other_review_manager.settings.sources:
        if search_source.search_type == SearchType.FILES:
            origin_files_search_source = search_source
    if not origin_files_search_source:
        print("No Files source found in origin repository -- cannot proceed")
        return

    origin_files_search_source.search_results_path = (
        other_review_manager.path / origin_files_search_source.search_results_path
    )
    origin_files_dir_feed = colrev.ops.search_api_feed.SearchAPIFeed(
        source_identifier=Fields.FILE,
        search_source=origin_files_search_source,
        update_only=False,
        logger=other_review_manager.logger,
        verbose_mode=False,
    )

    print()

    matched_df = match(blocked_df, verbosity_level=0)
    # TODO : mechanism in bib-dedupe to make sure that the cluster function is called?! (data structure!)
    duplicate_id_sets = cluster(matched_df, verbosity_level=0)

    for duplicate_id_set in duplicate_id_sets:
        if len(duplicate_id_set) != 2:
            print(f"Problem (duplicates != 2): {duplicate_id_set}")
            continue
        original_id = duplicate_id_set[0]
        other_id = duplicate_id_set[1]
        assert other_id.startswith("other_")
        print(f"{original_id} <-- {other_id}")

        # merge
        other_record = other_records[other_id.replace("other_", "")]
        if Fields.FILE in other_record and Fields.FILE not in records[original_id]:
            print(f" - Copying file {other_record[Fields.FILE]}")
            records[original_id][Fields.FILE] = other_record[Fields.FILE]
            # TODO : copy PDF file
            original_path = other_review_manager.path / Path(other_record[Fields.FILE])
            if original_path.is_file():
                target_path = review_manager.path / Path(other_record[Fields.FILE])
                if not target_path.parent.is_dir():
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                if not target_path.is_file():
                    import shutil

                    shutil.copyfile(original_path, target_path)
                else:
                    print(f" - PDF {target_path} already exists -- not copying")

            other_origins = other_record.get(Fields.ORIGIN, [])
            file_origin = [
                o for o in other_origins if o.startswith("file") or o.startswith("pdf")
            ].pop()
            origin_record = origin_files_dir_feed.feed_records[
                file_origin.split("/")[1]
            ]

            # Fix filename
            origin_record[Fields.FILE] = other_record[Fields.FILE]
            target_files_dir_feed.add_update_record(
                colrev.record.record.Record(origin_record)
            )

        # TODO : other fields?
        other_records.pop(other_id.replace("other_", ""))

    if "y" != input("Proceed with merge? [yN] ").lower():
        print("Aborting")  # discarding in-mem changes
        return

    # Import non-duplicated records
    for other_record in other_records.values():
        if other_record[Fields.ID] in records:
            # TODO : increment ID to avoid collisions
            print(f"Duplicate ID {other_record[Fields.ID]} -- skipping")
            continue

        # print(f"Importing {other_record[Fields.ID]}")
        records[other_record[Fields.ID]] = other_record

        other_origins = other_record.get(Fields.ORIGIN, [])
        file_origin = [
            o for o in other_origins if o.startswith("file") or o.startswith("pdf")
        ].pop()

        origin_record = origin_files_dir_feed.feed_records[file_origin.split("/")[1]]

        # Fix filename
        origin_record[Fields.FILE] = other_record[Fields.FILE]

        target_files_dir_feed.add_update_record(
            colrev.record.record.Record(origin_record)
        )
        updated_file_origin = (
            target_files_dir_feed.source.get_origin_prefix()
            + "/"
            + origin_record[Fields.ID]
        )

        records[other_record[Fields.ID]][Fields.ORIGIN] = [updated_file_origin]

    target_files_dir_feed.save()

    review_manager.dataset.save_records_dict(records)
    review_manager.dataset.git_repo.add_changes(target_files_dir_feed.feed_file)


def main() -> None:
    """Main function for import"""
    review_manager = colrev.review_manager.ReviewManager()
    import_type = _get_import_type()
    # import_path = _get_import_path()
    print("For testing purposes, using hardcoded path")
    import_path = Path("/home/gerit/ownCloud/inbox/colrev-importer/origin/data")

    # import_type = 'prescreening decisions'
    # import_path = Path("...")

    other_review_manager = colrev.review_manager.ReviewManager(
        path_str=import_path.as_posix()
    )

    print(f"Import {import_type} from {import_path}")

    if import_type == "prescreening decisions":
        _import_prescreening_decisions(
            review_manager, other_review_manager=other_review_manager
        )

    elif import_type == "records":
        _import_records(review_manager, other_review_manager=other_review_manager)
    else:
        raise NotImplementedError
