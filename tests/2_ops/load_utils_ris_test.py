#!/usr/bin/env python
"""Tests of the load utils for ris files"""
import logging
import os
from pathlib import Path

import pytest

from colrev.ops.load_utils_ris import RISLoader


def test_load_ris_entries(tmp_path, helpers):  # type: ignore
    os.chdir(tmp_path)

    helpers.retrieve_test_file(
        source=Path("load_utils/ris_test.ris"),
        target=Path("test.ris"),
    )

    ris_loader = RISLoader(
        source_file=Path("test.ris"),
        list_fields={"AU": " and ", "OT": ", ", "PT": ", "},
        unique_id_field="doi",
        force_mode=False,
        logger=logging.getLogger(__name__),
    )

    ris_loader.apply_ris_fixes()

    entries = ris_loader.load_ris_records()

    assert len(entries) == 2
    assert entries["00001"]["TI"] == "Title of a conference paper"
    assert (
        entries["00001"]["AU"]
        == "A. Author-One and B. Author-Two and C. Author-Three and D. Author-Four and E. Author-Five"
    )
    assert entries["00001"]["T2"] == "Secondary Title (booktitle title, if applicable)"
    assert entries["00001"]["SP"] == "183--186"
    assert entries["00001"]["PY"] == "2020"
    assert entries["00001"]["DO"] == "10.1234/Random-name55555.2020.00050"
    assert entries["00001"]["SN"] == "1111-3333"
    assert entries["00001"]["Y1"] == "4-8 Aug. 2020"

    assert entries["00002"]["TY"] == "JOUR"
    assert entries["00002"]["TI"] == "Title of a journal paper"
    assert entries["00002"]["T2"] == "Secondary Title (journal title, if applicable)"
    assert entries["00002"]["SP"] == "14--25"
    assert (
        entries["00002"]["AU"] == "A. Author-One and B. Author-Two and C. Author-Three"
    )
    assert entries["00002"]["PY"] == "2017"
    assert entries["00002"]["DO"] == "10.1111/MC.2017.66"
    assert entries["00002"]["JO"] == "Secondary Title (journal title, if applicable)"
    assert entries["00002"]["IS"] == "3"
    assert entries["00002"]["SN"] == "1111-2222"
    assert entries["00002"]["VO"] == "50"
    assert entries["00002"]["VL"] == "50"
    assert entries["00002"]["JA"] == "Secondary Title (journal title, if applicable)"
    assert entries["00002"]["Y1"] == "Mar. 2017"
    assert entries["00002"]["ER"] == ""

    entrymap = {"JOUR": "article", "CONF": "inproceedings"}

    ris_loader.apply_entrytype_mapping(
        record_dict=entries["00001"], entrytype_map=entrymap
    )
    key_map = {
        "article": {"TI": "title", "OID": "doi"},
        "inproceedings": {"TI": "title", "OID": "doi"},
    }
    ris_loader.map_keys(record_dict=entries["00001"], key_map=key_map)
    assert entries["00001"]["title"] == "Title of a conference paper"

    entries["00001"]["TY"] = "unknown"

    with pytest.raises(NotImplementedError):
        ris_loader.apply_entrytype_mapping(
            record_dict=entries["00001"], entrytype_map=entrymap
        )

    ris_loader.force_mode = True
    ris_loader.apply_entrytype_mapping(
        record_dict=entries["00001"], entrytype_map=entrymap
    )
    # No error is raised
