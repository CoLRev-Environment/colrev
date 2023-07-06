#! /usr/bin/env python
"""Checker for inconsistent-with-url-metadata."""
from __future__ import annotations

from thefuzz import fuzz

import colrev.ops.built_in.search_sources.website as website_connector
import colrev.qm.quality_model

# pylint: disable=too-few-public-methods


class InconsistentWithURLMetadataChecker:
    """The InconsistentWithURLMetadataChecker"""

    msg = "inconsistent-with-url-metadata"
    __fields_to_check = ["author", "title", "journal", "year", "volume", "number"]

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

        self.__url_connector = website_connector.WebsiteConnector(
            review_manager=quality_model.review_manager
        )

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the inconsistent-with-url-metadata checks"""

        if "url" not in record.data:
            return
        if any(x in record.data["url"] for x in ["search.ebscohost.com/login"]):
            return
        if "md_curated.bib" in record.data["colrev_data_provenance"]["url"]["source"]:
            return

        if self.__url_metadata_conflicts(record=record):
            record.add_masterdata_provenance_note(key="url", note=self.msg)
        else:
            record.remove_masterdata_provenance_note(key="url", note=self.msg)

    def __url_metadata_conflicts(self, *, record: colrev.record.Record) -> bool:
        url_record = record.copy_prep_rec()
        self.__url_connector.retrieve_md_from_website(record=url_record)
        for key, value in url_record.data.items():
            if key not in self.__fields_to_check:
                continue
            if not isinstance(value, str):
                continue
            if key in record.data:
                if len(url_record.data[key]) < 5 or len(record.data[key]) < 5:
                    continue
                if (
                    fuzz.partial_ratio(
                        record.data[key].lower(), url_record.data[key].lower()
                    )
                    < 70
                ):
                    return True

        return False


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(InconsistentWithURLMetadataChecker(quality_model))
