#!/usr/bin/env python3
import typing
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Note : to avoid performance issues on startup (ReviewManager, parsing settings)
# the settings dataclasses should be in one file (13s compared to 0.3s)

# https://stackoverflow.com/questions/66807878/pretty-print-dataclasses-prettier

# Project


class IDPpattern(Enum):
    first_author_year = "FIRST_AUTHOR_YEAR"
    three_authors_year = "THREE_AUTHORS_YEAR"


@dataclass
class ProjectConfiguration:
    id_pattern: IDPpattern
    review_type: str
    share_stat_req: str
    delay_automated_processing: bool
    curation_url: typing.Optional[str]
    curated_masterdata: bool
    curated_fields: typing.List[str]

    def __str__(self):
        # TODO : add more
        return f"Review ({self.review_type})"


# Search


class SearchType(Enum):
    DB = "DB"
    TOC = "TOC"
    BACKWARD_SEARCH = "BACKWARD_SEARCH"
    FORWARD_SEARCH = "FORWARD_SEARCH"
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
    source_name: str
    source_identifier: str
    search_parameters: str
    comment: typing.Optional[str]

    def __str__(self):
        return (
            f"{self.source_name} (type: {self.search_type}, "
            + f"filename: {self.filename})\n"
            + f"   source identifier:   {self.source_identifier}\n"
            + f"   search parameters:   {self.search_parameters}\n"
            + f"   comment:             {self.comment}"
        )


@dataclass
class SearchConfiguration:
    sources: typing.List[SearchSource]

    def __str__(self):
        return " - " + "\n - ".join([str(s) for s in self.sources])


# Load


@dataclass
class LoadConfiguration:
    pass

    def __str__(self):
        return " - TODO"


# Prep


@dataclass
class PrepRound:
    """The scripts are either in Prepare.prep_scripts, in a custom project script
    (the script in settings.json must have the same name), or otherwise in a
    python package (locally installed)."""

    name: str
    similarity: float
    scripts: typing.List[str]

    def __str__(self):
        short_list = [script for script in self.scripts][:3]
        if len(self.scripts) > 3:
            short_list.append("...")
        return f"{self.name} (" + ",".join(short_list) + ")"


@dataclass
class PrepConfiguration:
    fields_to_keep: typing.List[str]
    prep_rounds: typing.List[PrepRound]

    def __str__(self):
        return (
            " - prep_rounds: \n   - "
            + "\n   - ".join([str(prep_round) for prep_round in self.prep_rounds])
            + f"\n - fields_to_keep: {self.fields_to_keep}"
        )


# Dedupe


@dataclass
class DedupeConfiguration:
    merge_threshold: float
    partition_threshold: float
    same_source_merges: str  # TODO : "prevent" or "apply"

    def __str__(self):
        return (
            f" - merge_threshold: {self.merge_threshold}\n"
            + f" - partition_threshold: {self.partition_threshold}\n"
            + f" - same_source_merges: {self.same_source_merges}"
        )


# Prescreen


@dataclass
class TimeScopeFrom:
    TimeScopeFrom: int

    def __str__(self):
        return "TimeScopeFrom"


@dataclass
class TimeScopeTo:
    TimeScopeTo: int

    def __str__(self):
        return "TimeScopeTo"


@dataclass
class LanguageScope:
    LanguageScope: list

    def __str__(self):
        return "LanguageScope"


@dataclass
class ComplementaryMaterialsScope:
    ComplementaryMaterialsScope: bool

    def __str__(self):
        return "ComplementaryMaterialsScope"


@dataclass
class OutletInclusionScope:
    OutletInclusionScope: dict

    def __str__(self):
        return "OutletInclusionScope"


@dataclass
class OutletExclusionScope:
    OutletExclusionScope: dict

    def __str__(self):
        return "OutletExclusionScope"


@dataclass
class ENTRYTYPEScope:
    ENTRYTYPEScope: list

    def __str__(self):
        return "ENTRYTYPEScope"


@dataclass
class PrescreenConfiguration:
    plugin: typing.Optional[str]
    mode: typing.Optional[str]
    scope: typing.List[
        typing.Union[
            TimeScopeFrom,
            TimeScopeTo,
            LanguageScope,
            ComplementaryMaterialsScope,
            OutletInclusionScope,
            OutletExclusionScope,
            ENTRYTYPEScope,
        ]
    ]

    def __str__(self):
        return f" - mode: {self.mode}"


# PDF get


@dataclass
class PDFGetConfiguration:
    pdf_path_type: str  # TODO : "symlink" or "copy"

    def __str__(self):
        return f" - pdf_path_type: {self.pdf_path_type}"


# PDF prep


@dataclass
class PDFPrepConfiguration:
    pass

    def __str__(self):
        return " - TODO"


# Screen


@dataclass
class ScreenCriterion:
    name: str
    explanation: str

    def __str__(self):
        return f"{self.name} ({self.explanation})"


@dataclass
class ScreeningProcessConfig:
    overlapp: typing.Optional[int]
    mode: typing.Optional[str]
    parallel_independent: typing.Optional[str]


@dataclass
class ScreenConfiguration:
    process: ScreeningProcessConfig
    criteria: typing.List[ScreenCriterion]

    def __str__(self):
        return " - " + "\n - ".join([str(c) for c in self.criteria])


# Data


@dataclass
class DataField:
    name: str
    explanation: str
    data_type: str


@dataclass
class DataStructuredFormat:
    endpoint: str
    structured_data_endpoint_version: str
    fields: typing.List[DataField]

    def __str__(self):
        return "DataStructuredFormat"


@dataclass
class ManuscriptFormat:
    endpoint: str
    paper_endpoint_version: str
    word_template: typing.Optional[str] = None
    csl_style: typing.Optional[str] = None

    def __str__(self):
        return "ManuscriptFormat"


@dataclass
class PRISMAFormat:
    endpoint: str
    prisma_data_endpoint_version: str

    def __str__(self):
        return "PRISMAFormat"


@dataclass
class ZettlrFormat:
    endpoint: str
    zettlr_endpoint_version: str
    config: dict

    def __str__(self):
        return "ZettlrFormat"


@dataclass
class EndnoteFormat:
    endpoint: str
    endnote_data_endpoint_version: str
    config: dict

    def __str__(self):
        return "EndnoteFormat"


@dataclass
class CustomDataFormat:
    endpoint: str
    custom_data_format_version: str
    config: dict

    def __str__(self):
        return "customFormat"


# Note: data_format endpoints should have unique keys (e.g., paper_endpoint_version)
# to enable strict union matching by dacite.


@dataclass
class DataConfiguration:
    data_format: typing.List[
        typing.Union[
            ManuscriptFormat,
            DataStructuredFormat,
            PRISMAFormat,
            ZettlrFormat,
            EndnoteFormat,
            CustomDataFormat,
        ]
    ]

    def __str__(self):
        return " - " + "\n- ".join([str(c) for c in self.data_format])


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

    def __str__(self):
        return (
            str(self.project)
            + "\nSearch\n"
            + str(self.search)
            + "\nLoad\n"
            + str(self.load)
            + "\nPreparation\n"
            + str(self.prep)
            + "\nDedupe\n"
            + str(self.dedupe)
            + "\nPrescreen\n"
            + str(self.prescreen)
            + "\nPDF get\n"
            + str(self.pdf_get)
            + "\nPDF prep\n"
            + str(self.pdf_prep)
            + "\nScreen\n"
            + str(self.screen)
            + "\nData\n"
            + str(self.data)
        )


if __name__ == "__main__":
    pass
