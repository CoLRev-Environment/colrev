#! /usr/bin/env python
"""Completion of metadata based on year-volume-issue dependency as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass

import requests
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.search_sources.crossref as crossref_connector
import colrev.ops.search_sources
import colrev.record

# pylint: disable=duplicate-code
if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class YearVolIssPrep(JsonSchemaMixin):
    """Prepares records based on year-volume-issue dependency"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = (
        "ask the publisher to correct the metadata"
        + " (see https://www.crossref.org/blog/"
        + "metadata-corrections-updates-and-additions-in-metadata-manager/"
    )
    always_apply_changes = True

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

        self.local_index = prep_operation.review_manager.get_local_index()

        vol_nr_dict: dict = {}
        if hasattr(prep_operation.review_manager, "dataset"):
            records = prep_operation.review_manager.dataset.load_records_dict()
            for record in records.values():
                # pylint: disable=duplicate-code
                if record[
                    "colrev_status"
                ] not in colrev.record.RecordState.get_post_x_states(
                    state=colrev.record.RecordState.md_processed
                ):
                    continue
                if not record.get("year", "NA").isdigit():
                    continue

                if "journal" not in record or "volume" not in record:
                    continue

                if record["journal"] not in vol_nr_dict:
                    vol_nr_dict[record["journal"]] = {}

                if record["volume"] not in vol_nr_dict[record["journal"]]:
                    vol_nr_dict[record["journal"]][record["volume"]] = {}

                if "number" not in record:
                    vol_nr_dict[record["journal"]][record["volume"]] = record["year"]
                else:
                    if isinstance(
                        vol_nr_dict[record["journal"]][record["volume"]], dict
                    ):
                        vol_nr_dict[record["journal"]][record["volume"]][
                            record["number"]
                        ] = record["year"]
                    else:
                        # do not use inconsistent data (has/has no number)
                        del vol_nr_dict[record["journal"]][record["volume"]]

        self.vol_nr_dict = vol_nr_dict

    def __get_year_from_toc(self, *, record: colrev.record.Record) -> None:
        # TBD: maybe extract the following three lines as a separate script...
        try:
            year = self.local_index.get_year_from_toc(record_dict=record.get_data())
            record.update_field(
                key="year",
                value=year,
                source="LocalIndexPrep",
                note="",
                keep_source_if_equal=True,
            )
        except colrev_exceptions.TOCNotAvailableException:
            pass

    def __get_year_from_vol_nr_dict(self, *, record: colrev.record.Record) -> None:
        if "journal" not in record.data or "volume" not in record.data:
            return

        if record.data["journal"] not in self.vol_nr_dict:
            return

        if record.data["volume"] not in self.vol_nr_dict[record.data["journal"]]:
            return

        if "number" in record.data:
            if (
                record.data["number"]
                in self.vol_nr_dict[record.data["journal"]][record.data["volume"]]
            ):
                record.update_field(
                    key="year",
                    value=self.vol_nr_dict[record.data["journal"]][
                        record.data["volume"]
                    ][record.data["number"]],
                    source="year_vol_iss_prep",
                    note="",
                )
                record.update_masterdata_provenance()
        else:
            if isinstance(
                self.vol_nr_dict[record.data["journal"]][record.data["volume"]],
                (str, int),
            ):
                record.update_field(
                    key="year",
                    value=self.vol_nr_dict[record.data["journal"]][
                        record.data["volume"]
                    ],
                    source="year_vol_iss_prep",
                    note="",
                )
                record.update_masterdata_provenance()

    def __get_year_from_crossref(
        self, *, record: colrev.record.Record, prep_operation: colrev.ops.prep.Prep
    ) -> None:
        try:
            crossref_source = crossref_connector.CrossrefSearchSource(
                source_operation=prep_operation
            )
            retrieved_records = crossref_source.crossref_query(
                review_manager=prep_operation.review_manager,
                record_input=record,
                jour_vol_iss_list=True,
                timeout=prep_operation.timeout,
            )
            retries = 0
            while (
                not retrieved_records and retries < prep_operation.max_retries_on_error
            ):
                retries += 1
                retrieved_records = crossref_source.crossref_query(
                    review_manager=prep_operation.review_manager,
                    record_input=record,
                    jour_vol_iss_list=True,
                    timeout=prep_operation.timeout,
                )
            if 0 == len(retrieved_records):
                return

            retrieved_records = [
                retrieved_record
                for retrieved_record in retrieved_records
                if retrieved_record.data.get("volume", "NA")
                == record.data.get("volume", "NA")
                and retrieved_record.data.get("journal", "NA")
                == record.data.get("journal", "NA")
                and retrieved_record.data.get("number", "NA")
                == record.data.get("number", "NA")
            ]

            years = [r.data["year"] for r in retrieved_records]
            if len(years) == 0:
                return
            most_common = max(years, key=years.count)
            if years.count(most_common) > 3:
                record.update_field(
                    key="year", value=most_common, source="CROSSREF(average)", note=""
                )
        except requests.exceptions.RequestException:
            pass

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare a record based on year-volume-issue dependency"""

        if record.data.get("year", "NA").isdigit() or record.masterdata_is_curated():
            return record

        self.__get_year_from_toc(record=record)

        if "year" in record.data:
            return record

        self.__get_year_from_vol_nr_dict(record=record)

        if "year" in record.data:
            return record

        self.__get_year_from_crossref(record=record, prep_operation=prep_operation)

        return record


if __name__ == "__main__":
    pass
