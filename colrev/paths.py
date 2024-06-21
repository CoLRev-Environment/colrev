#!/usr/bin/env python3
"""The CoLRev review manager (main entrypoint)."""
from __future__ import annotations

from pathlib import Path


# pylint: disable=too-few-public-methods
# pylint: disable=too-many-instance-attributes
class PathManager:
    """Paths for the CoLRev review project (repository)"""

    SEARCH_DIR = Path("data/search")
    PREP_DIR = Path("data/prep")
    DEDUPE_DIR = Path("data/dedupe")
    PRESCREEN_DIR = Path("data/prescreen")
    PDF_DIR = Path("data/pdfs")
    SCREEN_DIR = Path("data/screen")
    DATA_DIR = Path("data/data")
    CORRECTIONS_DIR = Path(".corrections")
    OUTPUT_DIR = Path("output")
    RECORDS_FILE = Path("data/records.bib")
    SETTINGS_FILE = Path("settings.json")
    STATUS_FILE = Path("status.yaml")
    README_FILE = Path("readme.md")
    REPORT_FILE = Path(".report.log")
    GIT_IGNORE_FILE = Path(".gitignore")
    PRE_COMMIT_CONFIG = Path(".pre-commit-config.yaml")

    # Ensure the path uses forward slashes, which is compatible with Git's path handling
    RECORDS_FILE_GIT = str(RECORDS_FILE).replace("\\", "/")

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path

        self.search = base_path / self.SEARCH_DIR
        self.prep = base_path / self.PREP_DIR
        self.dedupe = base_path / self.DEDUPE_DIR
        self.prescreen = base_path / self.PRESCREEN_DIR
        self.pdf = base_path / self.PDF_DIR
        self.screen = base_path / self.SCREEN_DIR
        self.data = base_path / self.DATA_DIR
        self.corrections = base_path / self.CORRECTIONS_DIR
        self.output = base_path / self.OUTPUT_DIR
        self.records = base_path / self.RECORDS_FILE
        self.settings = base_path / self.SETTINGS_FILE
        self.status = base_path / self.STATUS_FILE
        self.readme = base_path / self.README_FILE
        self.report = base_path / self.REPORT_FILE
        self.git_ignore = base_path / self.GIT_IGNORE_FILE
        self.pre_commit_config = base_path / self.PRE_COMMIT_CONFIG
