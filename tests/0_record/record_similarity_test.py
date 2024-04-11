#!/usr/bin/env python
"""Tests of the record similarity functionality"""
import pytest

import colrev.exceptions as colrev_exceptions
import colrev.record.record
import colrev.record.record_prep
import colrev.record.record_similarity
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import RecordState

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
