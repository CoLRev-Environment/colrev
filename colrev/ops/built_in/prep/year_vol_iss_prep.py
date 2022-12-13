#! /usr/bin/env python
"""Completion of metadata based on year-volume-issue dependency as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import requests
import timeout_decorator
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.search_sources.crossref as crossref_connector
import colrev.ops.search_sources
import colrev.record


if TYPE_CHECKING:
    import colrev.ops.prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class YearVolIssPrep(JsonSchemaMixin):
    """Prepares records based on year-volume-issue dependency"""

    settings_class = colrev.env.package_manager.DefaultSettings

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
                if isinstance(vol_nr_dict[record["journal"]][record["volume"]], dict):
                    vol_nr_dict[record["journal"]][record["volume"]][
                        record["number"]
                    ] = record["year"]
                else:
                    # do not use inconsistent data (has/has no number)
                    del vol_nr_dict[record["journal"]][record["volume"]]

        self.vol_nr_dict = vol_nr_dict

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare a record based on year-volume-issue dependency"""

        # pylint: disable=too-many-nested-blocks
        # pylint: disable=too-many-return-statements
        # pylint: disable=too-many-branches

        if record.data.get("year", "NA").isdigit() or record.masterdata_is_curated():
            return record

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
            return record
        except colrev_exceptions.TOCNotAvailableException:
            pass

        if "journal" in record.data:
            if record.data["journal"] in self.vol_nr_dict:
                if "volume" in record.data:
                    if (
                        record.data["volume"]
                        in self.vol_nr_dict[record.data["journal"]]
                    ):
                        if "number" in record.data:
                            if (
                                record.data["number"]
                                in self.vol_nr_dict[record.data["journal"]][
                                    record.data["volume"]
                                ]
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
                                return record
                        else:
                            if isinstance(
                                self.vol_nr_dict[record.data["journal"]][
                                    record.data["volume"]
                                ],
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
                                return record

        # The year depends on journal x volume x issue
        if (
            "journal" in record.data
            and "volume" in record.data
            and "number" in record.data
        ) and "UNKNOWN" == record.data.get("year", "UNKNOWN"):
            pass
        else:
            return record

        crossref_source = crossref_connector.CrossrefSearchSource(
            source_operation=prep_operation
        )
        try:

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
                return record

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
                return record
            most_common = max(years, key=years.count)
            if years.count(most_common) > 3:
                record.update_field(
                    key="year", value=most_common, source="CROSSREF(average)", note=""
                )
        except requests.exceptions.RequestException:
            pass

        return record


if __name__ == "__main__":
    pass
