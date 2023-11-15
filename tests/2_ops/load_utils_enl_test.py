#!/usr/bin/env python
"""Tests of the enl load utils"""
from pathlib import Path

import colrev.ops.load_utils_enl
import colrev.review_manager
import colrev.settings
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields


def test_load(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the enl load utils"""

    helpers.reset_commit(review_manager=base_repo_review_manager, commit="load_commit")

    search_source = colrev.settings.SearchSource(
        endpoint="colrev.unknown_source",
        filename=Path("data/search/ais.txt"),
        search_type=colrev.settings.SearchType.OTHER,
        search_parameters={"scope": {"path": "test"}},
        comment="",
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
        target=Path("data/search/") / Path("ais.txt"),
    )
    load_operation = base_repo_review_manager.get_load_operation()

    enl_loader = colrev.ops.load_utils_enl.ENLLoader(
        load_operation=load_operation,
        source=search_source,
        list_fields={"A": " and "},
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

    actual = base_repo_review_manager.dataset.parse_bibtex_str(recs_dict_in=records)
    print(actual)
    assert actual == expected
