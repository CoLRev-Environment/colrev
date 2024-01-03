#! /usr/bin/env python
"""Connector for pandas"""
from __future__ import annotations

from pathlib import Path
from typing import List
from typing import Optional

import pandas as pd

import colrev.review_manager
from colrev.constants import Fields


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

    if add_abstracts_from_pdfs:
        raise NotImplementedError

    if not include_provenance:
        raise NotImplementedError

    if notify != "":
        raise NotImplementedError

    review_manager = colrev.review_manager.ReviewManager(
        path_str=project_path, force_mode=True
    )
    colrev.operation.CheckOperation(review_manager=review_manager)
    records = review_manager.dataset.load_records_dict()
    df = pd.DataFrame.from_dict(records, orient="index")
    return df


def add_from_tei(
    records_df: pd.DataFrame,
    *,
    project_path: str = "",
    fields: Optional[List[str]] = None,
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

    review_manager = colrev.review_manager.ReviewManager(
        path_str=project_path, force_mode=True
    )

    def extract_abstract(record: pd.Series) -> str:
        if Fields.ABSTRACT in record and not pd.isnull(record[Fields.ABSTRACT]):
            return record[Fields.ABSTRACT]

        try:
            tei_filename = colrev.record.Record(data=record).get_tei_filename()
            tei = review_manager.get_tei(tei_path=tei_filename)
            return tei.get_abstract()
        except FileNotFoundError:
            return ""

    def extract_keywords(record: pd.Series) -> str:
        if Fields.KEYWORDS in record and not pd.isnull(record[Fields.KEYWORDS]):
            return record[Fields.KEYWORDS]
        try:
            tei_filename = colrev.record.Record(data=record).get_tei_filename()
            tei = review_manager.get_tei(tei_path=tei_filename)
            return ", ".join(tei.get_paper_keywords())
        except FileNotFoundError:
            return ""

    if Fields.ABSTRACT in fields:
        records_df[Fields.ABSTRACT] = records_df.apply(extract_abstract, axis=1)
    if Fields.KEYWORDS in fields:
        records_df[Fields.KEYWORDS] = records_df.apply(extract_keywords, axis=1)


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

    review_manager.dataset.save_records_dict(records=records)
