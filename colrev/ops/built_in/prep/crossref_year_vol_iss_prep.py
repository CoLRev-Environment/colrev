#! /usr/bin/env python
"""Completion of metadata based on Crossref API as a prep operation"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

import requests
import timeout_decorator
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search_sources
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep
    import colrev.env.local_index

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class CrossrefYearVolIssPrep(JsonSchemaMixin):
    """Prepares records by adding missing years based on crossref.org metadata"""

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
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare a record by adding missing years based on journal/volume/number from Crossref"""

        # The year depends on journal x volume x issue
        if (
            "journal" in record.data
            and "volume" in record.data
            and "number" in record.data
        ) and "UNKNOWN" == record.data.get("year", "UNKNOWN"):
            pass
        else:
            return record

        CrossrefConnector = colrev.ops.built_in.database_connectors.CrossrefConnector
        try:

            retrieved_records = CrossrefConnector.crossref_query(
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
                retrieved_records = CrossrefConnector.crossref_query(
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
            # prep_operation.review_manager.logger.debug(most_common)
            # prep_operation.review_manager.logger.debug(years.count(most_common))
            if years.count(most_common) > 3:
                record.update_field(
                    key="year", value=most_common, source="CROSSREF(average)"
                )
        except requests.exceptions.RequestException:
            pass
        except KeyboardInterrupt:
            sys.exit()

        return record


if __name__ == "__main__":
    pass
