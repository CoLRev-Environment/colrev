#!/usr/bin/env python
"""Tests of the record similarity functionality"""
import pytest

import colrev.record.record_prep
import colrev.record.record_similarity
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields

# flake8: noqa


@pytest.mark.parametrize(
    "input_dict, expected",
    [
        ({Fields.CONTAINER_TITLE: "MIS Quarterly"}, False),
        ({Fields.CONTAINER_TITLE: "MISQ"}, True),
        ({Fields.CONTAINER_TITLE: "J. of Inf. Syst. Tech."}, True),
        ({Fields.CONTAINER_TITLE: "ICIS"}, True),
        (
            {Fields.CONTAINER_TITLE: "International Conference on Information Systems"},
            False,
        ),
        ({Fields.CONTAINER_TITLE: "Int. Conf. on Inf. Sys."}, True),
    ],
)
def test_container_is_abbreviated(input_dict: dict, expected: bool) -> None:
    record = colrev.record.record_prep.PrepRecord(input_dict)
    assert expected == colrev.record.record_similarity.container_is_abbreviated(record)


@pytest.mark.parametrize(
    "input_dict_1, input_dict_2, matches",
    [
        (
            {
                Fields.ID: "001",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.AUTHOR: "Rai, Arun",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "1",
            },
            {
                Fields.ID: "002",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.AUTHOR: "Rai, Arun",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "1",
            },
            True,
        ),
        (
            {
                Fields.ID: "001",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.AUTHOR: "Rai, Arun",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "2",
            },
            {
                Fields.ID: "002",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.AUTHOR: "Rai, Arun",
                Fields.YEAR: "2020",
                Fields.TITLE: "Editorial",
                Fields.VOLUME: "45",
                Fields.NUMBER: "1",
            },
            False,
        ),
    ],
)
def test_matches(input_dict_1: dict, input_dict_2: dict, matches: bool) -> None:
    record1 = colrev.record.record_prep.PrepRecord(input_dict_1)
    record2 = colrev.record.record_prep.PrepRecord(input_dict_2)
    assert colrev.record.record_similarity.matches(record1, record2) == matches
