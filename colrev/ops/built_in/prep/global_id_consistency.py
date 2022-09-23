#! /usr/bin/env python
"""Checks of consistency between global IDs a prep operation"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import timeout_decorator
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from thefuzz import fuzz

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search_sources
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepPackageInterface)
@dataclass
class GlobalIDConsistencyPrep(JsonSchemaMixin):
    """Prepares records by removing IDs (DOIs/URLs) that do not match with the metadata"""

    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """When metadata provided by DOI/crossref or on the website (url) differs from
        the RECORD: set status to md_needs_manual_preparation."""

        # pylint: disable=too-many-branches

        fields_to_check = ["author", "title", "journal", "year", "volume", "number"]

        if "doi" in record.data:
            record_copy = record.copy_prep_rec()
            crossref_connector = (
                colrev.ops.built_in.database_connectors.CrossrefConnector
            )
            crossref_md = crossref_connector.get_masterdata_from_crossref(
                prep_operation=prep_operation, record=record_copy
            )
            for key, value in crossref_md.data.items():
                if key not in fields_to_check:
                    continue
                if not isinstance(value, str):
                    continue
                if key in record.data:
                    if len(crossref_md.data[key]) < 5 or len(record.data[key]) < 5:
                        continue
                    if (
                        fuzz.partial_ratio(
                            record.data[key].lower(), crossref_md.data[key].lower()
                        )
                        < 70
                    ):
                        record.data[
                            "colrev_status"
                        ] = colrev.record.RecordState.md_needs_manual_preparation
                        record.add_masterdata_provenance_note(
                            key=key, note=f"disagreement with doi metadata ({value})"
                        )

        if "url" in record.data:
            try:
                url_connector = colrev.ops.built_in.database_connectors.URLConnector()
                url_record = record.copy_prep_rec()
                url_connector.retrieve_md_from_url(
                    record=url_record, prep_operation=prep_operation
                )
                for key, value in url_record.data.items():
                    if key not in fields_to_check:
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
                            record.data[
                                "colrev_status"
                            ] = colrev.record.RecordState.md_needs_manual_preparation
                            record.add_masterdata_provenance_note(
                                key=key,
                                note=f"disagreement with website metadata ({value})",
                            )
            except AttributeError:
                pass

        return record


if __name__ == "__main__":
    pass
