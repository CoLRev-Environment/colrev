#! /usr/bin/env python
"""Importer"""
from pathlib import Path
from typing import Any
from typing import Optional

import inquirer
import pandas as pd
import questionary
from bib_dedupe.bib_dedupe import block
from bib_dedupe.bib_dedupe import cluster
from bib_dedupe.bib_dedupe import match
from bib_dedupe.bib_dedupe import merge
from bib_dedupe.bib_dedupe import prep

import colrev.loader.load_utils
import colrev.ops.check
import colrev.ops.search_api_feed
import colrev.record.record
import colrev.review_manager
import colrev.search_file
from colrev.constants import Colors
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
        input("TODO: use ops.load.import_record()??")
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


def extract_matches(matched_df: pd.DataFrame, import_records_df: pd.DataFrame):
    m = matched_df.copy()

    # Ensure string dtype and handle missing IDs
    for c in ["ID_1", "ID_2", "duplicate_label"]:
        if c in m:
            m[c] = m[c].astype("string")

    def pairs_with_label(label: str):
        s = (
            m.loc[m["duplicate_label"].eq(label), ["ID_1", "ID_2"]]
            .dropna()
            .astype("string")
        )
        # drop self-pairs just in case
        s = s[s["ID_1"] != s["ID_2"]]
        # normalize order to avoid A–B and B–A duplicates
        pairs = {tuple(sorted(pair)) for pair in s.to_numpy()}
        return sorted(pairs)

    duplicate_pairs = pairs_with_label("duplicate")
    maybe_pairs = pairs_with_label("maybe")

    # IDs from import_records_df that never appear in ID_1 or ID_2
    ids1 = (
        m["ID_1"].dropna().astype("string")
        if "ID_1" in m
        else pd.Series(dtype="string")
    )
    ids2 = (
        m["ID_2"].dropna().astype("string")
        if "ID_2" in m
        else pd.Series(dtype="string")
    )
    all_matched_ids = pd.Index(ids1).union(pd.Index(ids2))

    import_ids = import_records_df["ID"].dropna().astype("string")
    not_in_matches = import_ids[~import_ids.isin(all_matched_ids)].tolist()

    return duplicate_pairs, maybe_pairs, not_in_matches


def pick_record_ids_checkbox(not_in_matches, import_records):
    candidate_ids = [rid for rid in not_in_matches if rid in import_records]
    choices = []
    for rid in candidate_ids:
        rec = import_records.get(rid, {})
        title = rec.get("title", "—")
        year = rec.get("year", "—")
        author = rec.get("author", rec.get("authors", "—"))
        label = f"{title} ({year}) — {author}  [{rid}]"
        choices.append(questionary.Choice(title=label, value=rid))  # returns ID(s)

    selected = questionary.checkbox(
        "Select one or more records:",
        choices=choices,
        qmark="",  # quieter UI
        instruction="",
    ).ask()
    return selected or []  # -> List[str] of IDs


def pick_record_id_radio(not_in_matches, import_records):
    candidate_ids = [rid for rid in not_in_matches if rid in import_records]
    choices = []
    for rid in candidate_ids:
        rec = import_records.get(rid, {})
        title = rec.get("title", "—")
        year = rec.get("year", "—")
        author = rec.get("author", rec.get("authors", "—"))
        label = f"{title} ({year}) — {author}  [{rid}]"
        choices.append(
            questionary.Choice(title=label, value=rid)
        )  # returns a single ID

    selected = questionary.select(
        "Select a record:", choices=choices, qmark="", instruction=""
    ).ask()
    return selected  # -> str or None


def select_source(review_manager: Any) -> Optional[Any]:
    sources = (
        getattr(getattr(review_manager, "settings", object()), "sources", []) or []
    )
    if not sources:
        print("No sources found in review_manager.settings.sources")
        return None

    def g(obj, attr, default=None):
        return getattr(obj, attr, default)

    def label(src, idx: int) -> str:
        name = (
            g(src, "name")
            or g(src, "source_name")
            or g(src, "endpoint")
            or f"source_{idx+1}"
        )
        query = g(src, "search") or g(src, "query") or ""
        path = g(src, "search_results_path") or "—"
        parts = [str(name)]
        if query:
            parts.append(f"[{query}]")
        parts.append(f"→ {path}")
        return " ".join(parts)

    choice_list = [
        questionary.Choice(title=label(src, i), value=src)
        for i, src in enumerate(sources)
    ]

    picked = questionary.select(
        "Select a source:", choices=choice_list, qmark="", instruction=""
    ).ask()

    if picked is None:
        return None

    print(f"search_results_path = {getattr(picked, 'search_results_path', None)}")
    return picked


def import_file(
    import_path: Path, review_manager: colrev.review_manager.ReviewManager
) -> None:

    print(f"Import records from {import_path}")
    import_records = colrev.loader.load_utils.load(filename=import_path)
    colrev.ops.check.CheckOperation(review_manager)
    records = review_manager.dataset.load_records_dict()

    from bib_dedupe.bib_dedupe import prep, block, match

    records_df = pd.DataFrame.from_dict(records, orient="index")
    records_df["search_set"] = "original"

    from bib_dedupe import verbose_print

    verbose_print.verbosity_level = -1

    import_records_df = pd.DataFrame.from_dict(import_records, orient="index")
    import_records_df["ID"] = "import_" + import_records_df["ID"].astype("string")
    import_records_df["search_set"] = "import"
    combined_df = pd.concat([records_df, import_records_df])

    # TODO : offer as bib-dedupe built-in method:
    # map_datasets(d1, d2)
    # -> returns: pairs of IDs with label,
    # ID_d1, ID_d2, label
    # 0001,  00002, duplicate
    # 0002,  NA,    unique
    # 0003, 0005,   maybe

    combined_df = prep(combined_df)
    blocked_df = block(combined_df)
    matched_df = match(blocked_df)

    verbose_print.verbosity_level = 1

    duplicate_pairs, maybe_pairs, not_in_matches = extract_matches(
        matched_df, import_records_df
    )
    # compute the width of the left ID across both lists
    left_width = max(
        max((len(str(a)) for a, _ in duplicate_pairs), default=0),
        max((len(str(a)) for a, _ in maybe_pairs), default=0),
    )

    for a, b in duplicate_pairs:
        print(f"{Colors.GREEN}{str(a):<{left_width}} <->  {b}{Colors.END}")
    print()

    for a, b in maybe_pairs:
        print(f"{Colors.ORANGE}{str(a):<{left_width}} <?> {b}{Colors.END}")

    print()
    print("To import")
    not_in_matches = [n.replace("import_", "") for n in not_in_matches]
    for ref in not_in_matches:
        print(f"- {ref}")

    rec_ids = pick_record_ids_checkbox(not_in_matches, import_records)

    # TODO : allow for "new source"
    # TODO : TB:D how to set source_identifier for exploratory-searches
    search_source = select_source(review_manager)
    target_files_dir_feed = colrev.ops.search_api_feed.SearchAPIFeed(
        source_identifier="ID",
        search_source=search_source,
        update_only=False,
        logger=review_manager.logger,
        verbose_mode=False,
    )
    load_operation = review_manager.get_load_operation()
    for rec_id in rec_ids:
        record_dict = import_records[rec_id]

        target_files_dir_feed.add_update_record(
            colrev.record.record.Record(record_dict)
        )

        record_origin = (
            target_files_dir_feed.source.get_origin_prefix()
            + "/"
            + record_dict[Fields.ID]
        )
        record_dict[Fields.ORIGIN] = [record_origin]

        record_dict[Fields.STATUS] = RecordState.md_retrieved

        # TODO : compy pdfs?

        load_operation.import_record(
            record_dict=record_dict, records=records, set_id=True
        )

        record_dict[Fields.STATUS] = RecordState.rev_included

    target_files_dir_feed.save()
    review_manager.dataset.save_records_dict(records)


def main() -> None:
    """Main function for import"""
    review_manager = colrev.review_manager.ReviewManager()
    # import_path = _get_import_path()
    print("For testing purposes, using hardcoded path")
    import_path = Path(
        "/home/gerit/ownCloud/data/literature_reviews/BibDedupe/bib-dedupe_paper/references.bib"
    )

    # import_type = 'prescreening decisions'
    # import_path = Path("...")

    if import_path.is_file():
        import_file(import_path, review_manager)
        return

    import_type = _get_import_type()

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
