#!/usr/bin/env python
"""Tests of the enl load utils"""
import logging
import os
from pathlib import Path

import pytest

import colrev.exceptions as colrev_exceptions
import colrev.review_manager
import colrev.settings
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.ops.load_utils_enl import ENLLoader
from colrev.ops.write_utils_bib import to_string


def test_load(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, tmp_path, helpers
) -> None:
    """Test the enl load utils"""
    os.chdir(tmp_path)

    # only supports enl
    with pytest.raises(colrev_exceptions.ImportException):
        enl_loader = ENLLoader(
            source_file=Path("table.ptvc"),
            list_fields={"A": " and ", "O": ", ", "P": ", "},
            force_mode=False,
            logger=logging.getLogger(__name__),
        )

    # file must exist
    with pytest.raises(colrev_exceptions.ImportException):
        enl_loader = ENLLoader(
            source_file=Path("non-existent.enl"),
            list_fields={"A": " and ", "O": ", ", "P": ", "},
            force_mode=False,
            logger=logging.getLogger(__name__),
        )

    enl_mapping = {
        ENTRYTYPES.ARTICLE: {
            "T": Fields.TITLE,
            "A": Fields.AUTHOR,
            "D": Fields.YEAR,
            "B": Fields.JOURNAL,
            "V": Fields.VOLUME,
            "N": Fields.NUMBER,
            "P": Fields.PAGES,
            "X": Fields.ABSTRACT,
            "U": Fields.URL,
            "8": "date",
            "0": "type",
        },
        ENTRYTYPES.INPROCEEDINGS: {
            "T": Fields.TITLE,
            "A": Fields.AUTHOR,
            "D": Fields.YEAR,
            "B": Fields.JOURNAL,
            "V": Fields.VOLUME,
            "N": Fields.NUMBER,
            "P": Fields.PAGES,
            "X": Fields.ABSTRACT,
            "U": Fields.URL,
            "8": "date",
            "0": "type",
        },
    }
    entrytype_map = {
        "Journal Article": ENTRYTYPES.ARTICLE,
        "HICSS": ENTRYTYPES.INPROCEEDINGS,
        "ICIS": ENTRYTYPES.INPROCEEDINGS,
        "ECIS": ENTRYTYPES.INPROCEEDINGS,
        "AMCIS": ENTRYTYPES.INPROCEEDINGS,
        "Proceedings": ENTRYTYPES.INPROCEEDINGS,
        "Inproceedings": ENTRYTYPES.INPROCEEDINGS,
        "All Sprouts Content": ENTRYTYPES.INPROCEEDINGS,
    }

    helpers.retrieve_test_file(
        source=Path("load_utils/") / Path("ais.txt"),
        target=Path("ais.txt"),
    )

    enl_loader = ENLLoader(
        source_file=Path("ais.txt"),
        list_fields={"A": " and "},
        force_mode=False,
        logger=logging.getLogger(__name__),
    )
    records = enl_loader.load_enl_entries()

    for record_dict in records.values():
        if "0" not in record_dict:
            keys_to_check = ["V", "N"]
            if any([k in record_dict for k in keys_to_check]):
                record_dict["0"] = "Journal Article"
            else:
                record_dict["0"] = "Inproceedings"
        enl_loader.apply_entrytype_mapping(
            record_dict=record_dict, entrytype_map=entrytype_map
        )
        enl_loader.map_keys(record_dict=record_dict, key_map=enl_mapping)
        record_dict["ID"] = record_dict[Fields.URL].replace(
            "https://aisel.aisnet.org/", ""
        )

    expected = (
        helpers.test_data_path / Path("load_utils/") / Path("ais_expected.bib")
    ).read_text(encoding="utf-8")

    actual = to_string(records_dict=records)
    assert actual == expected

    records = enl_loader.load_enl_entries()
    records["000001"]["0"] = "unknown"

    with pytest.raises(NotImplementedError):
        enl_loader.apply_entrytype_mapping(
            record_dict=records["000001"], entrytype_map=entrytype_map
        )

    enl_loader.force_mode = True
    enl_loader.apply_entrytype_mapping(
        record_dict=records["000001"], entrytype_map=entrytype_map
    )

    records["000001"]["ENTRYTYPE"] = "article"
    enl_loader.map_keys(
        record_dict=records["000001"], key_map={ENTRYTYPES.ARTICLE: {"T": "title"}}
    )
    assert records["000001"].keys() == {"ID", "ENTRYTYPE", "title"}
