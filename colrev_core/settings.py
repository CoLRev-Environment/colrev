#!/usr/bin/env python3
import typing
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Note : to avoid performance issues on startup (ReviewManager, parsing settings)
# the settings dataclasses should be in one file (13s compared to 0.3s)


# Project


class IDPpattern(Enum):
    first_author_year = "FIRST_AUTHOR_YEAR"
    three_authors_year = "THREE_AUTHORS_YEAR"


@dataclass
class ProjectConfiguration:
    id_pattern: IDPpattern
    review_type: str
    share_stat_req: str
    delay_automated_processing: str  # TODO: should be bool
    curated_fields: typing.List[str]


# Search


class SearchType(Enum):
    DB = "DB"
    TOC = "TOC"
    BACK_CIT = "BACK_CIT"
    FORW_CIT = "FORW_CIT"
    PDFS = "PDFS"
    OTHER = "OTHER"
    FEED = "FEED"
    COLREV_REPO = "COLREV_REPO"

    def __str__(self):
        return f"{self.name}"


@dataclass
class SearchSource:
    filename: Path
    search_type: SearchType
    source_identifier: str
    search_parameters: str
    comment: typing.Optional[str]


@dataclass
class SearchConfiguration:
    sources: typing.List[SearchSource]


# Load


@dataclass
class LoadConfiguration:
    pass


# Prep


@dataclass
class PrepRound:
    """The scripts are either in Prepare.prep_scripts, in a custom project script
    (the script in settings.json must have the same name), or otherwise in a
    python package (locally installed)."""

    name: str
    similarity: float
    scripts: typing.List[str]


@dataclass
class PrepConfiguration:
    fields_to_keep: typing.List[str]
    prep_rounds: typing.List[PrepRound]


# Dedupe


@dataclass
class DedupeConfiguration:
    merge_threshold: float
    partition_threshold: float


# Prescreen


@dataclass
class PrescreenConfiguration:
    plugin: typing.Optional[str]
    mode: typing.Optional[str]


# PDF get


@dataclass
class PDFGetConfiguration:
    pdf_path_type: str  # TODO : "symlink" or "copy"


# PDF prep


@dataclass
class PDFPrepConfiguration:
    pass


# Screen


@dataclass
class ScreenCriterion:
    name: str
    explanation: str


@dataclass
class ScreeningProcessConfig:
    overlapp: typing.Optional[int]
    mode: typing.Optional[str]
    parallel_independent: typing.Optional[str]


@dataclass
class ScreenConfiguration:
    process: ScreeningProcessConfig
    criteria: typing.List[ScreenCriterion]


# Data


@dataclass
class DataField:
    name: str
    explanation: str
    data_type: str


@dataclass
class DataStructuredFormat:
    fields: typing.Optional[typing.List[DataField]] = None


@dataclass
class DataPaperFormat:
    endpoint: str
    word_template: typing.Optional[str] = None
    csl_style: typing.Optional[str] = None


@dataclass
class DataConfiguration:
    data_format: typing.List[typing.Union[DataPaperFormat, DataStructuredFormat]]


@dataclass
class Configuration:
    project: ProjectConfiguration
    search: SearchConfiguration
    load: LoadConfiguration
    prep: PrepConfiguration
    dedupe: DedupeConfiguration
    prescreen: PrescreenConfiguration
    pdf_get: PDFGetConfiguration
    pdf_prep: PDFPrepConfiguration
    screen: ScreenConfiguration
    data: DataConfiguration
