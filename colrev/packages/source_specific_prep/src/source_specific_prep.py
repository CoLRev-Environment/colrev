#! /usr/bin/env python
"""Source-specific preparation as a prep operation"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

from pydantic import Field

import colrev.exceptions as colrev_exceptions
import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.record.record
from colrev.constants import EndpointType
from colrev.constants import Fields
from colrev.package_manager.package_manager import PackageManager

# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods


class SourceSpecificPrep(base_classes.PrepPackageBaseClass):
    """Prepares records based on the prepare scripts specified by the SearchSource"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    source_correction_hint = "check with the developer"
    ci_supported: bool = Field(default=True)

    always_apply_changes = True

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,
        settings: dict,
        logger: typing.Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.settings = self.settings_class(**settings)
        self.review_manager = prep_operation.review_manager
        self.package_manager = PackageManager()

    # pylint: disable=unused-argument
    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Prepare the record by applying source-specific fixes"""
        # Note : we take the first origin (ie., the source-specific prep should
        # be one of the first in the prep-list)
        origin_source = record.data[Fields.ORIGIN][0].split("/")[0]

        sources = [
            s
            for s in self.review_manager.settings.sources
            if s.search_results_path == Path("data/search") / Path(origin_source)
        ]

        for source in sources:
            try:
                # if source.platform not in self.search_sources.packages:
                #     continue
                # endpoint = self.search_sources.packages[source.platform]
                search_source_class = self.package_manager.get_package_endpoint_class(
                    package_type=EndpointType.search_source,
                    package_identifier=source.platform,
                )
                endpoint = search_source_class(search_file=source)

                if callable(endpoint.prepare):
                    record = endpoint.prepare(record)  # source
                else:
                    print(f"error: {source.platform}")
            except colrev_exceptions.MissingDependencyError as exc:
                self.logger.warn(exc)

        if "howpublished" in record.data and Fields.URL not in record.data:
            if Fields.URL in record.data["howpublished"]:
                record.rename_field(key="howpublished", new_key=Fields.URL)
                record.update_field(
                    key=Fields.URL,
                    value=record.data[Fields.URL].replace("\\url{", "").rstrip("}"),
                    source="source_specific_prep",
                )

        if "webpage" == record.data[Fields.ENTRYTYPE].lower() or (
            "misc" == record.data[Fields.ENTRYTYPE].lower()
            and Fields.URL in record.data
        ):
            record.update_field(
                key=Fields.ENTRYTYPE, value="online", source="source_specific_prep"
            )

        return record
