#!/usr/bin/env python
"""Test the local_index"""
import pytest

from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import LocalIndexFields
from colrev.constants import RecordState
from colrev.env.local_index_prep import prepare_record_for_indexing
from colrev.env.local_index_prep import prepare_record_for_return

# pylint: disable=line-too-long
# flake8: noqa: E501


@pytest.mark.parametrize(
    "record_dict, expected",
    [
        (
            {
                Fields.ID: "AbbasZhouDengEtAl2018",
                Fields.STATUS: RecordState.md_processed,
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.METADATA_SOURCE_REPOSITORY_PATHS: "/path/to/selected_repo",
                Fields.YEAR: "2014",
                "literature_review": "yes",
                Fields.JOURNAL: "MIS Quarterly",
                Fields.AUTHOR: "Abbas, Ahmed and Zhou, Yilu and Deng, Shasha and Zhang, Pengzhu",
                Fields.TITLE: "Text Analytics to Support Sense-Making in Social Media: A Language-Action Perspective",
            },
            {
                LocalIndexFields.ID: "e44d8844c3d815a912040065ae5b9f051084b5633f110e88927094a1e331f79c",
                LocalIndexFields.CITATION_KEY: "AbbasZhouDengEtAl2018",
                Fields.COLREV_ID: "colrev_id1:|a|mis-quarterly|-|-|2014|abbas-zhou-deng-zhang|text-analytics-to-support-sense-making-in-social-media-a-language-action-perspective",
                Fields.ID: "AbbasZhouDengEtAl2018",
                Fields.STATUS: RecordState.md_processed,
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.D_PROV: {
                    "literature_review": {
                        "note": "",
                        "source": "/path/to/selected_repo",
                    },
                },
                Fields.MD_PROV: {
                    Fields.YEAR: {"note": "", "source": "/path/to/selected_repo"},
                    Fields.JOURNAL: {"note": "", "source": "/path/to/selected_repo"},
                    Fields.AUTHOR: {"note": "", "source": "/path/to/selected_repo"},
                    Fields.TITLE: {"note": "", "source": "/path/to/selected_repo"},
                },
                Fields.YEAR: 2014,
                "literature_review": "yes",
                Fields.JOURNAL: "MIS Quarterly",
                Fields.AUTHOR: "Abbas, Ahmed and Zhou, Yilu and Deng, Shasha and Zhang, Pengzhu",
                Fields.TITLE: "Text Analytics to Support Sense-Making in Social Media: A Language-Action Perspective",
            },
        ),
    ],
)
def test_prepare_record_for_indexing(record_dict: dict, expected: dict) -> None:  # type: ignore

    prepare_record_for_indexing(record_dict)
    assert record_dict == expected


@pytest.mark.parametrize(
    "record_dict, expected",
    [
        (
            {
                Fields.ID: "AbbasZhouDengEtAl2018",
                Fields.STATUS: RecordState.md_processed,
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.METADATA_SOURCE_REPOSITORY_PATHS: "/path/to/selected_repo",
                Fields.YEAR: "2014",
                "literature_review": "yes",
                Fields.JOURNAL: "MIS Quarterly",
                Fields.AUTHOR: "Abbas, Ahmed and Zhou, Yilu and Deng, Shasha and Zhang, Pengzhu",
                Fields.TITLE: "Text Analytics to Support Sense-Making in Social Media: A Language-Action Perspective",
                Fields.FULLTEXT: "https://wiley.com/doi/10.25300/MISQ/2018/13239",
                Fields.FILE: "data/pdfs/non-existing.pdf",
                Fields.COLREV_ID: "colrev_id1:|a|mis-quarterly|-|-|2014|abbas-zhou-deng-zhang|text-analytics-to-support-sense-making-in-social-media-a-language-action-perspective",
            },
            {
                Fields.ID: "AbbasZhouDengEtAl2018",
                Fields.STATUS: RecordState.md_prepared,
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.YEAR: "2014",
                "literature_review": "yes",
                Fields.JOURNAL: "MIS Quarterly",
                Fields.AUTHOR: "Abbas, Ahmed and Zhou, Yilu and Deng, Shasha and Zhang, Pengzhu",
                Fields.TITLE: "Text Analytics to Support Sense-Making in Social Media: A Language-Action Perspective",
                # Fields.FULLTEXT: "https://wiley.com/doi/10.25300/MISQ/2018/13239",
            },
        ),
    ],
)
def test_prepare_record_for_return(record_dict: dict, expected: dict) -> None:

    # TODO : include_file?!
    prepare_record_for_return(record_dict, include_file=True)
    assert record_dict == expected
