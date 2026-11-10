#! /usr/bin/env python
"""CustomName"""
import logging
import typing

from pathlib import Path
import colrev.search_file
from colrev.package_manager.package_base_classes import SearchSourcePackageBaseClass

class CustomName(SearchSourcePackageBaseClass):

    def __init__(self, *, search_file: 'colrev.search_file.ExtendedSearchFile', logger: 'typing.Optional[logging.Logger]' = None, verbose_mode: 'bool' = False) -> 'None':
        """Initialize the instance."""

    def prep_link_md(self, prep_operation: 'colrev.ops.prep.Prep', record: 'colrev.record.record.Record', save_feed: 'bool' = True, timeout: 'int' = 10) -> 'colrev.record.record.Record':
        """Retrieve masterdata from the SearchSource."""

    def prepare(self, record: 'colrev.record.record_prep.PrepRecord') -> 'colrev.record.record.Record':
        """Run the custom source-prep operation."""

    def search(self, rerun: 'bool') -> 'None':
        """Run a search of the SearchSource."""

    @classmethod
    def preprocess(
        cls, text: str, *, format: str, source_version: typing.Optional[str]
    ) -> str:
        """Preprocess source text before parsing, when needed."""
        return text

    @classmethod
    def preprocess_file(
        cls,
        path: Path,
        *,
        format: str,
        source_version: typing.Optional[str],
        output_dir: Path,
    ) -> Path:
        """Preprocess a source file before parsing, when needed."""
        return path

    @classmethod
    def normalize(
        cls,
        records: list[dict],
        *,
        format: str,
        source_version: typing.Optional[str],
    ) -> dict[str, dict]:
        """Normalize parsed records, when needed."""
        return super().normalize(
            records, format=format, source_version=source_version
        )
