#! /usr/bin/env python
"""Connector for pandas"""
from __future__ import annotations

import os
import shutil
import typing
from pathlib import Path

import pandas as pd
from bib_dedupe.bib_dedupe import block
from bib_dedupe.bib_dedupe import match
from bib_dedupe.bib_dedupe import prep

import colrev.env.tei_parser
import colrev.ops.check
import colrev.review_manager
from colrev.constants import Fields
from colrev.constants import RecordState


def load_df(
    *,
    project_path: str = "",
    add_abstracts_from_pdfs: bool = False,
    include_provenance: bool = True,
    notify: str = "",
) -> pd.DataFrame:
    """Get a pandas dataframe from a CoLRev project"""

    if project_path == "":
        project_path = str(Path.cwd())

    os.chdir(project_path)

    if add_abstracts_from_pdfs:
        raise NotImplementedError

    if not include_provenance:
        raise NotImplementedError

    if notify != "":
        raise NotImplementedError

    review_manager = colrev.review_manager.ReviewManager(path_str=project_path)
    colrev.ops.check.CheckOperation(review_manager)
    records = review_manager.dataset.load_records_dict()
    loaded_df = pd.DataFrame.from_dict(records, orient="index")
    return loaded_df


def load_resolved_papers(other_project_path: str) -> pd.DataFrame:
    """Loads records from the other project, matches them with the current project,
    and returns a DataFrame of the other records with the corresponding IDs in the current project.

    This is useful when integrating datasets and reusing screening decisions or coding.

    Example:

    Current project record(s):

    @Webster2002{
        title = "Analyzing the past to prepare for the future",
        author = "Webser, Jane and Watson, Rick",
        ...
    }

    Other project record(s):

    @ID1{
        title = "ANALYZING THE PAST TO PREPARE FOR THE FUTURE",
        author = "WEBSTER; WATSON",
        colrev_status = "rev_included",
        methods = "literature_review",
        ...
    }

    Returns:

    @Webster2002{
        title = "ANALYZING THE PAST TO PREPARE FOR THE FUTURE",
        author = "WEBSTER; WATSON",
        colrev_status = "rev_included",
        methods = "literature_review",
        OTHER_ID = "ID1",
        ...
    }

    Data can easily be assigned to the current project
    by accessing other records based on corresponding current IDs.

    """

    other_review_manager = colrev.review_manager.ReviewManager(
        path_str=other_project_path, force_mode=True
    )
    colrev.ops.check.CheckOperation(other_review_manager)
    # pylint: disable=colrev-records-variable-naming-convention
    other_records = other_review_manager.dataset.load_records_dict()
    project_path = str(Path.cwd())
    review_manager = colrev.review_manager.ReviewManager(
        path_str=project_path, force_mode=True
    )
    colrev.ops.check.CheckOperation(review_manager)
    records = review_manager.dataset.load_records_dict()

    # identify duplicates with dedupe

    records_df = pd.DataFrame.from_dict(records, orient="index")
    records_df["search_set"] = "ORIGINAL"
    records_df[Fields.ID] = "ORIGINAL_" + records_df[Fields.ID].astype(str)
    other_records_df = pd.DataFrame.from_dict(other_records, orient="index")
    other_records_df["search_set"] = "OTHER"
    other_records_df.reset_index(inplace=True)

    combined_df = pd.concat([records_df, other_records_df], ignore_index=True)

    selected_columns = [
        Fields.ID,
        "search_set",
        Fields.AUTHOR,
        Fields.TITLE,
        Fields.YEAR,
        Fields.JOURNAL,
        Fields.BOOKTITLE,
        Fields.VOLUME,
        Fields.NUMBER,
        Fields.PAGES,
        Fields.DOI,
        Fields.ENTRYTYPE,
        Fields.ABSTRACT,
    ]
    combined_df = combined_df[selected_columns]

    combined_df = prep(records_df=combined_df)

    deduplication_pairs = block(combined_df)
    matched_df = match(deduplication_pairs)

    matched_df.rename(columns={"ID_2": "ID"}, inplace=True)
    matched_df = matched_df[matched_df["duplicate_label"] == "duplicate"]

    merged_df = pd.merge(other_records_df, matched_df, on="ID", how="inner")

    merged_df["other_ID"] = merged_df["ID"]
    merged_df[Fields.ID] = merged_df["ID_1"].str.replace("ORIGINAL_", "")
    merged_df.drop(columns=["ID_1"], inplace=True)
    merged_df.drop(columns=["search_set", "duplicate_label", "index"], inplace=True)

    return merged_df


def add_from_tei(
    records_df: pd.DataFrame,
    *,
    project_path: str = "",
    fields: typing.Optional[typing.List[str]] = None,
) -> None:
    """
    This function adds data from TEI files to the given DataFrame.

    Parameters:
    records_df (pd.DataFrame): The DataFrame to which the data will be added.
    project_path (str, optional): The path to the project. Defaults to the
                                  current working directory.
    fields (Optional[List[str]], optional): The fields to be added from the TEI
                                            files. Defaults to [Fields.ABSTRACT,
                                            Fields.KEYWORDS].

    Returns:
    None
    """
    if project_path == "":
        project_path = str(Path.cwd())
    if fields is None:
        fields = [Fields.ABSTRACT, Fields.KEYWORDS]

    def extract_abstract(record: pd.Series) -> str:
        if Fields.ABSTRACT in record and not pd.isnull(record[Fields.ABSTRACT]):
            return record[Fields.ABSTRACT]

        try:
            tei_filename = colrev.record.record.Record(record).get_tei_filename()
            tei = colrev.env.tei_parser.TEIParser(tei_path=tei_filename)
            return tei.get_abstract()
        except FileNotFoundError:
            return ""

    def extract_keywords(record: pd.Series) -> str:
        if Fields.KEYWORDS in record and not pd.isnull(record[Fields.KEYWORDS]):
            return record[Fields.KEYWORDS]
        try:
            tei_filename = colrev.record.record.Record(record).get_tei_filename()
            tei = colrev.env.tei_parser.TEIParser(tei_path=tei_filename)
            return ", ".join(tei.get_paper_keywords())
        except FileNotFoundError:
            return ""

    if Fields.ABSTRACT in fields:
        records_df[Fields.ABSTRACT] = records_df.apply(extract_abstract, axis=1)
    if Fields.KEYWORDS in fields:
        records_df[Fields.KEYWORDS] = records_df.apply(extract_keywords, axis=1)


def extract_pdfs_for_data_extraction(
    records_df: pd.DataFrame, directory: str, copy_files: bool = False
) -> None:
    """
    This function creates symlinks or copies the PDFs to the given directory
    based on the copy_files parameter.

    Parameters:
    records_df (pd.DataFrame): The DataFrame containing the records.
    directory (str): The directory where the symlinks or copies will be created.
    copy_files (bool, optional): If True, copies the PDFs instead of creating
                                 symlinks. Defaults to False.

    Returns:
    None
    """
    project_path = str(Path.cwd())
    review_manager = colrev.review_manager.ReviewManager(
        path_str=project_path, force_mode=True
    )

    directory_path = Path(directory)
    directory_path.mkdir(parents=True, exist_ok=True)
    for _, record in records_df.iterrows():
        if record[Fields.STATUS] not in [
            RecordState.rev_included,
            RecordState.rev_synthesized,
        ]:
            continue
        if Fields.FILE in record and not pd.isnull(record[Fields.FILE]):
            pdf_path = review_manager.path / Path(record[Fields.FILE])
            target_path = directory_path / pdf_path.name
            if copy_files:
                if not target_path.exists():
                    shutil.copy(pdf_path, target_path)
            else:
                if not target_path.exists():
                    target_path.symlink_to(pdf_path)


def save(records_df: pd.DataFrame) -> None:
    """
    This function saves the records from a DataFrame to a dataset.

    Parameters:
    records_df (pd.DataFrame): The DataFrame containing the records to be saved.

    Returns:
    None
    """
    project_path = str(Path.cwd())
    review_manager = colrev.review_manager.ReviewManager(
        path_str=project_path, force_mode=True
    )
    records = records_df.to_dict(orient="index")
    for rec_id, record in records.items():
        for key in list(record.keys()):
            if isinstance(record[key], (list, dict)):
                continue
            if pd.isnull(record[key]) or record[key] == "":
                records[rec_id].pop(key)

    review_manager.dataset.save_records_dict(records)
