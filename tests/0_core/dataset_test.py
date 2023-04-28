#!/usr/bin/env python
"""Tests for the dataset"""
from copy import deepcopy

import colrev.env.utils
import colrev.review_manager
import colrev.settings


def test_get_applicable_restrictions(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Get the applicable masterdata restrictions"""
    pe_before = deepcopy(base_repo_review_manager.settings.data.data_package_endpoints)
    base_repo_review_manager.settings.data.data_package_endpoints.append(
        {
            "endpoint": "colrev.colrev_curation",
            "curation_url": "https://github.com/CoLRev-curations/decision-support-systems",
            "curated_masterdata": True,
            "masterdata_restrictions": {
                "1985": {
                    "ENTRYTYPE": "article",
                    "volume": True,
                    "number": True,
                    "journal": "Decision Support Systems",
                },
                "2013": {
                    "ENTRYTYPE": "article",
                    "volume": True,
                    "journal": "Decision Support Systems",
                },
                "2014": {
                    "ENTRYTYPE": "article",
                    "volume": True,
                    "number": False,
                    "journal": "Decision Support Systems",
                },
            },
            "curated_fields": ["doi", "url", "dblp_key"],
        }
    )
    base_repo_review_manager.dataset = colrev.dataset.Dataset(
        review_manager=base_repo_review_manager
    )
    actual = base_repo_review_manager.dataset.get_applicable_restrictions(
        record_dict={"year": 1986}
    )
    expected = {
        "ENTRYTYPE": "article",
        "volume": True,
        "number": True,
        "journal": "Decision Support Systems",
    }
    assert expected == actual
    base_repo_review_manager.settings.data.data_package_endpoints = pe_before
