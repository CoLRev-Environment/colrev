#! /usr/bin/env python
"""Conslidation of metadata based on LocalIndex as a prep operation"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.packages.local_index.src.local_index as local_index_connector
import colrev.record.record
import colrev.search_file
from colrev.constants import Fields
from colrev.constants import SearchType

# pylint: disable=duplicate-code


# pylint: disable=too-few-public-methods


class LocalIndexPrep(base_classes.PrepPackageBaseClass):
    """Prepares records based on LocalIndex metadata"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings

    ci_supported: bool = Field(default=True)

    source_correction_hint = (
        "correct the metadata in the source "
        + "repository (as linked in the provenance field)"
    )
    always_apply_changes = True
    _local_index_md_filename = Path("data/search/md_curated.bib")

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,
        settings: dict,
        logger: typing.Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.settings = self.settings_class(**settings)

        # LocalIndex as an md-prep source
        li_md_source_l = [
            s
            for s in prep_operation.review_manager.settings.sources
            if s.search_results_path == self._local_index_md_filename
        ]
        if li_md_source_l:
            search_file = li_md_source_l[0]
        else:
            search_file = colrev.search_file.ExtendedSearchFile(
                platform="colrev.local_index",
                search_results_path=self._local_index_md_filename,
                search_type=SearchType.MD,
                search_string="",
                comment="",
                version="0.1.0",
            )

        self.local_index_source = local_index_connector.LocalIndexSearchSource(
            search_file=search_file,
        )
        self.prep_operation = prep_operation

    # pylint: disable=unused-argument
    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Prepare the record metadata based on local-index"""

        # don't move to  jour_iss_number_year prep
        # because toc-retrieval relies on adequate toc items!
        if (
            Fields.VOLUME in record.data
            and Fields.NUMBER in record.data
            and not record.masterdata_is_curated()
        ):
            # Note : cannot use local_index as an attribute of PrepProcess
            # because it creates problems with multiprocessing
            fields_to_remove = self.local_index_source.local_index.get_fields_to_remove(
                record.get_data()
            )
            for field_to_remove in fields_to_remove:
                if field_to_remove in record.data:
                    record.remove_field(
                        key=field_to_remove,
                        not_missing_note=True,
                        source="local_index",
                    )

        self.local_index_source.prep_link_md(
            prep_operation=self.prep_operation, record=record
        )

        return record
