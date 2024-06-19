#!/usr/bin/env python
"""Tests of record merger functionality"""
import pytest

import colrev.record.record_merger
import colrev.record.record_prep
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import RecordState


@pytest.mark.parametrize(
    "input_dict_1, input_dict_2, preferred_masterdata_source_prefixes, result_dict",
    [
        (
            {
                Fields.ID: "001",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.ORIGIN: ["md_crossref.bib/001"],
                Fields.AUTHOR: "Rai, Arun",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "1",
            },
            {
                Fields.ID: "002",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.ORIGIN: ["md_dblp.bib/001"],
                Fields.AUTHOR: "Rai, Arun",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "1",
            },
            ["md_dblp.bib"],
            {
                Fields.ID: "001",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.ORIGIN: ["md_crossref.bib/001", "md_dblp.bib/001"],
                Fields.AUTHOR: "Rai, Arun",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "1",
            },
        ),
        # Prefer curated (despite author all-caps)
        (
            {
                Fields.ID: "001",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.MD_PROV: {FieldValues.CURATED: {"source": "www...", "note": ""}},
                Fields.ORIGIN: ["md_curated.bib/001"],
                Fields.AUTHOR: "RAI, ARUN",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "1",
            },
            {
                Fields.ID: "002",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.ORIGIN: ["md_crossref.bib/001"],
                Fields.AUTHOR: "Rai, Arun",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "1",
            },
            [],
            {
                Fields.ID: "001",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.MD_PROV: {FieldValues.CURATED: {"source": "www...", "note": ""}},
                Fields.ORIGIN: ["md_crossref.bib/001", "md_curated.bib/001"],
                Fields.AUTHOR: "RAI, ARUN",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "1",
            },
        ),
        # Prefer curated incoming (despite author all-caps)
        (
            {
                Fields.ID: "001",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.MD_PROV: {Fields.AUTHOR: {"source": "www...", "note": ""}},
                Fields.ORIGIN: ["md_crossref.bib/001"],
                Fields.AUTHOR: "RAI, ARUN",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "1",
            },
            {
                Fields.ID: "002",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.MD_PROV: {FieldValues.CURATED: {"source": "www...", "note": ""}},
                Fields.ORIGIN: ["md_curated.bib/001"],
                Fields.AUTHOR: "Rai, Arun",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "1",
            },
            [],
            {
                Fields.ID: "001",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.MD_PROV: {FieldValues.CURATED: {"source": "www...", "note": ""}},
                Fields.ORIGIN: ["md_crossref.bib/001", "md_curated.bib/001"],
                Fields.AUTHOR: "Rai, Arun",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "1",
            },
        ),
        # Prefer preferred_masterdata_source_prefixes
        (
            {
                Fields.ID: "001",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.ORIGIN: ["pubmed.bib/001"],
                Fields.AUTHOR: "RAI, ARUN",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "1",
            },
            {
                Fields.ID: "002",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.ORIGIN: ["md_crossref.bib/001"],
                Fields.AUTHOR: "Rai, Arun and Coauthor, Second",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "1",
            },
            ["md_crossref.bib"],
            {
                Fields.ID: "001",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.MD_PROV: {Fields.AUTHOR: {"source": "ORIGINAL", "note": ""}},
                Fields.D_PROV: {},
                Fields.ORIGIN: ["md_crossref.bib/001", "pubmed.bib/001"],
                Fields.AUTHOR: "Rai, Arun and Coauthor, Second",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "1",
            },
        ),
        # Merge other ifelds
        (
            {
                Fields.ID: "001",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.ORIGIN: ["md_crossref.bib/001"],
                Fields.AUTHOR: "Rai, Arun",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "1",
            },
            {
                Fields.ID: "002",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.ORIGIN: ["md_dblp.bib/001"],
                Fields.AUTHOR: "Rai, Arun",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "1",
                "literature_review": "yes",
            },
            [],
            {
                Fields.ID: "001",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.MD_PROV: {
                    Fields.TITLE: {"note": "language-unknown", "source": "ORIGINAL"}
                },
                Fields.D_PROV: {
                    "literature_review": {"source": "ORIGINAL", "note": ""}
                },
                Fields.ORIGIN: ["md_crossref.bib/001", "md_dblp.bib/001"],
                Fields.AUTHOR: "Rai, Arun",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "1",
                "literature_review": "yes",
            },
        ),
    ],
)
def test_merger(
    input_dict_1: dict,
    input_dict_2: dict,
    preferred_masterdata_source_prefixes: list,
    result_dict: dict,
) -> None:

    actual_record = colrev.record.record.Record(input_dict_1)
    colrev.record.record_merger.merge(
        actual_record,
        colrev.record.record.Record(input_dict_2),
        default_source="ORIGINAL",
        preferred_masterdata_source_prefixes=preferred_masterdata_source_prefixes,
    )
    assert actual_record.data == result_dict


@pytest.mark.parametrize(
    "main_record_dict, merging_record_dict, key, expected_dict",
    [
        (
            {
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
            },
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE, Fields.AUTHOR: "Rai, Arun"},
            Fields.AUTHOR,
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE, Fields.AUTHOR: "Rai, Arun"},
        ),
        (
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE, Fields.AUTHOR: "RAI, ARUN"},
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE, Fields.AUTHOR: "Rai, Arun"},
            Fields.AUTHOR,
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE, Fields.AUTHOR: "Rai, Arun"},
        ),
        (
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE, Fields.YEAR: FieldValues.UNKNOWN},
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE, Fields.YEAR: "2015"},
            Fields.YEAR,
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE, Fields.YEAR: "2015"},
        ),
        (
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE, Fields.FILE: "file_a"},
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE, Fields.FILE: "file_b"},
            Fields.FILE,
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE, Fields.FILE: "file_a;file_b"},
        ),
        (
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE},
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE, Fields.FILE: "file_a"},
            Fields.FILE,
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE, Fields.FILE: "file_a"},
        ),
        (
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE, Fields.PAGES: "no page given"},
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE, Fields.PAGES: "1--23"},
            Fields.PAGES,
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE, Fields.PAGES: "1--23"},
        ),
        (
            {
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.URL: "http://www.publisher.com",
            },
            {
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.URL: "https://www.publisher.com",
            },
            Fields.URL,
            {
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.URL: "https://www.publisher.com",
            },
        ),
        (
            {},
            {
                Fields.NUMBER: "1",
            },
            Fields.NUMBER,
            {
                Fields.NUMBER: "1",
            },
        ),
        (
            {
                Fields.MD_PROV: {
                    Fields.NUMBER: {
                        "source": "source_identifier",
                        "note": "IGNORE:missing",
                    }
                }
            },
            {
                Fields.NUMBER: "1",
            },
            Fields.NUMBER,
            {},
        ),
    ],
)
def test__fuse_fields(
    main_record_dict: dict,
    merging_record_dict: dict,
    key: str,
    expected_dict: dict,
) -> None:
    print(main_record_dict)
    main_record = colrev.record.record.Record(main_record_dict)

    colrev.record.record_merger._fuse_fields(
        main_record,
        merging_record=colrev.record.record.Record(merging_record_dict),
        key=key,
    )
    print(main_record_dict)
    print(merging_record_dict)
    print(expected_dict)

    if key in expected_dict:
        assert main_record.data[key] == expected_dict[key]
    else:
        assert key not in main_record.data


@pytest.mark.parametrize(
    "main_record_dict, merging_record_dict, expected_status",
    [
        (
            {
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.STATUS: RecordState.md_retrieved,
            },
            {
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.STATUS: RecordState.pdf_imported,
            },
            RecordState.pdf_imported,
        ),
    ],
)
def test_merge_status(
    main_record_dict: dict,
    merging_record_dict: dict,
    expected_status: RecordState,
) -> None:
    main_record = colrev.record.record.Record(main_record_dict)

    colrev.record.record_merger._merge_status(
        main_record,
        merging_record=colrev.record.record.Record(merging_record_dict),
    )
    assert main_record.data[Fields.STATUS] == expected_status


@pytest.mark.parametrize(
    "main_record_dict, merging_record_dict, expected_pages",
    [
        (
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE, Fields.PAGES: "10-20"},
            {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE, Fields.PAGES: "NA"},
            "10-20",
        ),
    ],
)
def test_select_pages(
    main_record_dict: dict,
    merging_record_dict: dict,
    expected_pages: str,
) -> None:
    main_record = colrev.record.record.Record(main_record_dict)

    actual = colrev.record.record_merger._select_pages(
        main_record,
        merging_record=colrev.record.record.Record(merging_record_dict),
    )
    assert actual == expected_pages


@pytest.mark.parametrize(
    "default, candidate, expected",
    [
        ("NA", "Journal of Science", "Journal of Science"),
        (
            "J. MIS",
            "Journal of Management Information Systems",
            "Journal of Management Information Systems",
        ),
    ],
)
def test_select_container_title(default: str, candidate: str, expected: str) -> None:

    actual = colrev.record.record_merger._select_container_title(default, candidate)
    assert actual == expected
