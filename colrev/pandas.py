#! /usr/bin/env python
"""Connector for pandas"""
from __future__ import annotations

import pandas as pd
import colrev.review_manager

def load_df(project_path: str) -> pd.DataFrame:
    """Get a pandas dataframe from a CoLRev project"""

    # TODO : option: add_abstracts_from_pdfs

    # TODO :colrev.pandas.load("path-to-repo", include_provenance=True, notify="prep/...")

    # TODO : extract this function to colrev at some point
    review_manager = colrev.review_manager.ReviewManager(path_str=project_path)
    colrev.operation.CheckOperation(review_manager=review_manager)
    records = review_manager.dataset.load_records_dict()
    df = pd.DataFrame.from_dict(records, orient="index")
    return df