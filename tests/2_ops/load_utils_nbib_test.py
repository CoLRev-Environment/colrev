#!/usr/bin/env python
"""Tests of the load utils for nbib files"""
import logging
import os
from pathlib import Path

import pytest

import colrev.exceptions as colrev_exceptions
from colrev.ops.load_utils_nbib import NBIBLoader


def test_load_nbib_entries(tmp_path, helpers):  # type: ignore
    os.chdir(tmp_path)

    # only supports nbib
    with pytest.raises(colrev_exceptions.ImportException):
        nbib_loader = NBIBLoader(
            source_file=Path("table.ptvc"),
            list_fields={"AU": " and ", "OT": ", ", "PT": ", "},
            unique_id_field="doi",
            force_mode=False,
            logger=logging.getLogger(__name__),
        )

    # file must exist
    with pytest.raises(colrev_exceptions.ImportException):
        nbib_loader = NBIBLoader(
            source_file=Path("non-existent.nbib"),
            list_fields={"AU": " and ", "OT": ", ", "PT": ", "},
            unique_id_field="doi",
            force_mode=False,
            logger=logging.getLogger(__name__),
        )

    helpers.retrieve_test_file(
        source=Path("load_utils/nbib_test.nbib"),
        target=Path("test.nbib"),
    )

    nbib_loader = NBIBLoader(
        source_file=Path("test.nbib"),
        list_fields={"AU": " and ", "OT": ", ", "PT": ", "},
        unique_id_field="doi",
        force_mode=False,
        logger=logging.getLogger(__name__),
    )

    entries = nbib_loader.load_nbib_entries()

    assert len(entries) == 1
    assert entries["000001"]["TI"] == "Paper title"
    assert entries["000001"]["AU"] == "Smith, Tom and Hunter, Shawn"
    assert entries["000001"]["OT"] == "Keyword 1, Keyword 2"
    assert entries["000001"]["JT"] == "Journal Name"
    assert entries["000001"]["SO"] == "v10 n1 p1-10 2000"
    assert entries["000001"]["AID"] == "http://dx.doi.org/10.1000/123456789"
    assert entries["000001"]["OID"] == "EJ1131633"
    assert entries["000001"]["VI"] == "10"
    assert entries["000001"]["IP"] == "1"
    assert entries["000001"]["PG"] == "1-9"
    assert entries["000001"]["DP"] == "2000"
    assert entries["000001"]["LID"] == "http://eric.ed.gov/?id=EJ1131633"
    assert entries["000001"]["AB"] == "Abstract ..."
    assert entries["000001"]["ISSN"] == "ISSN-1234-4567"
    assert entries["000001"]["LA"] == "English"
    assert entries["000001"]["PT"] == "Journal Articles, Reports - Research"

    entrymap = {"Journal Articles, Reports - Research": "article"}

    nbib_loader.apply_entrytype_mapping(
        record_dict=entries["000001"], entrytype_map=entrymap
    )
    key_map = {"article": {"TI": "title", "OID": "doi"}}
    nbib_loader.map_keys(record_dict=entries["000001"], key_map=key_map)
    assert entries["000001"]["title"] == "Paper title"

    entries["000001"]["PT"] = "unknown"

    with pytest.raises(NotImplementedError):
        nbib_loader.apply_entrytype_mapping(
            record_dict=entries["000001"], entrytype_map=entrymap
        )

    nbib_loader.force_mode = True
    nbib_loader.apply_entrytype_mapping(
        record_dict=entries["000001"], entrytype_map=entrymap
    )
    # No error is raised
