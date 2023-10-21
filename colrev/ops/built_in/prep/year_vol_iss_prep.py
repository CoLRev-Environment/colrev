#! /usr/bin/env python
"""Completion of metadata based on year-volume-issue dependency as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import requests
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.search_sources.crossref as crossref_connector
import colrev.ops.search_sources
import colrev.record
from colrev.constants import Fields

# pylint: disable=duplicate-code

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
        self.review_manager = prep_operation.review_manager
        self.local_index = prep_operation.review_manager.get_local_index()
        self.vol_nr_dict = self.__get_vol_nr_dict()
        self.quality_model = self.review_manager.get_qm()

    def __get_vol_nr_dict(self) -> dict:
        vol_nr_dict: dict = {}
        if not hasattr(self.review_manager, "dataset"):
            return vol_nr_dict
        records = self.review_manager.dataset.load_records_dict()
        for record in records.values():
            # pylint: disable=duplicate-code
            if record[Fields.STATUS] not in colrev.record.RecordState.get_post_x_states(
                state=colrev.record.RecordState.md_processed
            ):
                continue
            if not record.get(Fields.YEAR, "NA").isdigit():
                continue

            if Fields.JOURNAL not in record or Fields.VOLUME not in record:
                continue

            if record[Fields.JOURNAL] not in vol_nr_dict:
                vol_nr_dict[record[Fields.JOURNAL]] = {}

            if record[Fields.VOLUME] not in vol_nr_dict[record[Fields.JOURNAL]]:
                vol_nr_dict[record[Fields.JOURNAL]][record[Fields.VOLUME]] = {}

            if Fields.NUMBER not in record:
                vol_nr_dict[record[Fields.JOURNAL]][record[Fields.VOLUME]] = record[
                    Fields.YEAR
                ]
            else:
                if isinstance(
                    vol_nr_dict[record[Fields.JOURNAL]][record[Fields.VOLUME]], dict
                ):
                    vol_nr_dict[record[Fields.JOURNAL]][record[Fields.VOLUME]][
                        record[Fields.NUMBER]
                    ] = record[Fields.YEAR]
                else:
                    # do not use inconsistent data (has/has no number)
                    del vol_nr_dict[record[Fields.JOURNAL]][record[Fields.VOLUME]]

        return vol_nr_dict

    def __get_year_from_toc(self, *, record: colrev.record.Record) -> None:
        # TBD: maybe extract the following three lines as a separate script...
        try:
            year = self.local_index.get_year_from_toc(record_dict=record.get_data())
            record.update_field(
                key=Fields.YEAR,
                value=year,
                source="LocalIndexPrep",
                note="",
                keep_source_if_equal=True,
            )
        except colrev_exceptions.TOCNotAvailableException:
            pass

    def __get_year_from_vol_nr_dict(self, *, record: colrev.record.Record) -> None:
        if Fields.JOURNAL not in record.data or Fields.VOLUME not in record.data:
            return

        if record.data[Fields.JOURNAL] not in self.vol_nr_dict:
            return

        if (
            record.data[Fields.VOLUME]
            not in self.vol_nr_dict[record.data[Fields.JOURNAL]]
        ):
            return

        if Fields.NUMBER in record.data:
            if (
                record.data[Fields.NUMBER]
                in self.vol_nr_dict[record.data[Fields.JOURNAL]][
                    record.data[Fields.VOLUME]
                ]
            ):
                record.update_field(
                    key=Fields.YEAR,
                    value=self.vol_nr_dict[record.data[Fields.JOURNAL]][
                        record.data[Fields.VOLUME]
                    ][record.data[Fields.NUMBER]],
                    source="year_vol_iss_prep",
                    note="",
                )
                record.run_quality_model(qm=self.quality_model)
        else:
            if isinstance(
                self.vol_nr_dict[record.data[Fields.JOURNAL]][
                    record.data[Fields.VOLUME]
                ],
                (str, int),
            ):
                record.update_field(
                    key=Fields.YEAR,
                    value=self.vol_nr_dict[record.data[Fields.JOURNAL]][
                        record.data[Fields.VOLUME]
                    ],
                    source="year_vol_iss_prep",
                    note="",
                )
                record.run_quality_model(qm=self.quality_model)

    def __get_year_from_crossref(
        self, *, record: colrev.record.Record, prep_operation: colrev.ops.prep.Prep
    ) -> None:
        try:
            crossref_source = crossref_connector.CrossrefSearchSource(
                source_operation=prep_operation
            )
            retrieved_records = crossref_source.crossref_query(
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
                    record_input=record,
                    jour_vol_iss_list=True,
                    timeout=prep_operation.timeout,
                )
            if 0 == len(retrieved_records):
                return

            retrieved_records = [
                retrieved_record
                for retrieved_record in retrieved_records
                if retrieved_record.data.get(Fields.VOLUME, "NA")
                == record.data.get(Fields.VOLUME, "NA")
                and retrieved_record.data.get(Fields.JOURNAL, "NA")
                == record.data.get(Fields.JOURNAL, "NA")
                and retrieved_record.data.get(Fields.NUMBER, "NA")
                == record.data.get(Fields.NUMBER, "NA")
            ]

            years = [r.data[Fields.YEAR] for r in retrieved_records]
            if len(years) == 0:
                return
            most_common = max(years, key=years.count)
            if years.count(most_common) > 3:
                record.update_field(
                    key=Fields.YEAR,
                    value=most_common,
                    source="CROSSREF(average)",
                    note="",
                )
        except requests.exceptions.RequestException:
            pass

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare a record based on year-volume-issue dependency"""

        if (
            record.data.get(Fields.YEAR, "NA").isdigit()
            or record.masterdata_is_curated()
        ):
            return record

        self.__get_year_from_toc(record=record)

        if Fields.YEAR in record.data:
            return record

        self.__get_year_from_vol_nr_dict(record=record)

        if Fields.YEAR in record.data:
            return record

        self.__get_year_from_crossref(record=record, prep_operation=prep_operation)

        return record
