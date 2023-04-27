#! /usr/bin/env python
"""Checks of consistency between global IDs a prep operation"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from thefuzz import fuzz

import colrev.env.package_manager
import colrev.ops.built_in.search_sources.crossref as crossref_connector
import colrev.ops.built_in.search_sources.website as website_connector
import colrev.ops.search_sources
import colrev.record

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.prep

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class GlobalIDConsistencyPrep(JsonSchemaMixin):
    """Prepares records by removing IDs (DOIs/URLs) that do not match with the metadata"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    __fields_to_check = ["author", "title", "journal", "year", "volume", "number"]

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

        self.url_connector = website_connector.WebsiteConnector(
            source_operation=prep_operation
        )
        self.prep_operation = prep_operation

    def __validate_against_doi_metadata(self, *, record: colrev.record.Record) -> None:
        # pylint: disable=too-many-branches

        if "doi" not in record.data:
            return
        if "doi" in record.data["colrev_data_provenance"]:
            if (
                "md_curated.bib"
                in record.data["colrev_data_provenance"]["doi"]["source"]
            ):
                return

        record_copy = record.copy_prep_rec()

        crossref_search_source = crossref_connector.CrossrefSearchSource(
            source_operation=self.prep_operation
        )
        crossref_md = crossref_search_source.get_masterdata(
            prep_operation=self.prep_operation, record=record_copy, save_feed=False
        )

        for key, value in crossref_md.data.items():
            if key not in self.__fields_to_check:
                continue
            if not isinstance(value, str):
                continue
            if key in record.data:
                if record.data[key] == "UNKNOWN":
                    continue
                if key in ["author", "title", "journal"]:
                    if len(crossref_md.data[key]) < 5 or len(record.data[key]) < 5:
                        continue
                if (
                    fuzz.partial_ratio(
                        record.data[key].lower(), crossref_md.data[key].lower()
                    )
                    < 70
                ):
                    if record.masterdata_is_curated():
                        record.remove_field(key="doi")
                    else:
                        record.set_status(
                            target_state=colrev.record.RecordState.md_needs_manual_preparation
                        )
                        record.add_masterdata_provenance_note(
                            key=key, note="disagreement with doi metadata"
                        )

    def __validate_against_url_metadata(self, *, record: colrev.record.Record) -> None:
        if "url" not in record.data:
            return

        if any(x in record.data["url"] for x in ["search.ebscohost.com/login"]):
            return

        if "md_curated.bib" in record.data["colrev_data_provenance"]["url"]["source"]:
            return

        try:
            url_record = record.copy_prep_rec()
            self.url_connector.retrieve_md_from_website(
                record=url_record, prep_operation=self.prep_operation
            )
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
                        if record.masterdata_is_curated():
                            record.remove_field(key="url")
                        else:
                            record.set_status(
                                target_state=colrev.record.RecordState.md_needs_manual_preparation
                            )
                            record.add_masterdata_provenance_note(
                                key=key,
                                note=f"disagreement with website metadata ({value})",
                            )
        except AttributeError:
            pass

    def prepare(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.PrepRecord,
    ) -> colrev.record.Record:
        """Prepare records by removing IDs (DOIs/URLs) that do not match with the metadata

        When metadata provided by DOI/crossref or on the website (url) differs from
        the RECORD: set status to md_needs_manual_preparation."""

        if prep_operation.polish and not prep_operation.force_mode:
            return record

        self.__validate_against_doi_metadata(record=record)

        self.__validate_against_url_metadata(record=record)

        return record


if __name__ == "__main__":
    pass
