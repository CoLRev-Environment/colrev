#!/usr/bin/env python3
import dataclasses
import typing
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from dataclasses_jsonschema import JsonSchemaMixin

# Note : to avoid performance issues on startup (ReviewManager, parsing settings)
# the settings dataclasses should be in one file (13s compared to 0.3s)

# https://stackoverflow.com/questions/66807878/pretty-print-dataclasses-prettier

# Project


class IDPattern(Enum):
    """The pattern for generating record IDs"""

    # pylint: disable=invalid-name
    first_author_year = "first_author_year"
    three_authors_year = "three_authors_year"

    @classmethod
    def get_field_details(cls) -> typing.Dict:
        # pylint: disable=no-member
        return {"options": cls._member_names_, "type": "selection"}

    @classmethod
    def get_options(cls) -> typing.List[str]:
        # pylint: disable=no-member
        return cls._member_names_


@dataclass
class Author(JsonSchemaMixin):
    """Author of the review"""

    # pylint: disable=too-many-instance-attributes

    name: str
    initials: str
    email: str
    orcid: typing.Optional[str] = None
    contributions: typing.List[str] = dataclasses.field(default_factory=list)
    affiliations: typing.Optional[str] = None
    funding: typing.List[str] = dataclasses.field(default_factory=list)
    identifiers: typing.List[str] = dataclasses.field(default_factory=list)


@dataclass
class Protocol(JsonSchemaMixin):
    """Review protocol"""

    url: str


class ShareStatReq(Enum):
    """Record status requirements for sharing"""

    # pylint: disable=invalid-name
    none = "none"
    processed = "processed"
    screened = "screened"
    completed = "completed"

    @classmethod
    def get_options(cls) -> typing.List[str]:
        # pylint: disable=no-member
        return cls._member_names_

    @classmethod
    def get_field_details(cls) -> typing.Dict:
        # pylint: disable=no-member
        return {"options": cls._member_names_, "type": "selection"}


@dataclass
class ProjectSettings(JsonSchemaMixin):
    """Project settings"""

    # pylint: disable=too-many-instance-attributes

    title: str
    __doc_title__ = "The title of the review"
    authors: typing.List[Author]
    keywords: typing.List[str]
    # status ? (development/published?)
    protocol: typing.Optional[Protocol]
    # publication: ... (reference, link, ....)
    review_type: str
    id_pattern: IDPattern
    share_stat_req: ShareStatReq
    delay_automated_processing: bool
    curation_url: typing.Optional[str]
    curated_masterdata: bool
    curated_fields: typing.List[str]
    colrev_version: str

    def __str__(self) -> str:
        # TODO : add more
        return f"Review ({self.review_type})"


# Search


class SearchType(Enum):
    """Type of search source"""

    DB = "DB"
    TOC = "TOC"
    BACKWARD_SEARCH = "BACKWARD_SEARCH"
    FORWARD_SEARCH = "FORWARD_SEARCH"
    PDFS = "PDFS"
    OTHER = "OTHER"

    @classmethod
    def get_options(cls) -> typing.List[str]:
        # pylint: disable=no-member
        return cls._member_names_

    @classmethod
    def get_field_details(cls) -> typing.Dict:
        # pylint: disable=no-member
        return {"options": cls._member_names_, "type": "selection"}

    def __str__(self):
        return f"{self.name}"


@dataclass
class SearchSource(JsonSchemaMixin):
    """Search source settings"""

    # pylint: disable=too-many-instance-attributes

    filename: Path
    search_type: SearchType
    source_name: str
    source_identifier: str
    search_parameters: dict
    load_conversion_script: dict
    comment: typing.Optional[str]

    def get_corresponding_bib_file(self) -> Path:
        return self.filename.with_suffix(".bib")

    def setup_for_load(
        self,
        *,
        record_list: typing.List[typing.Dict],
        imported_origins: typing.List[str],
    ) -> None:
        # pylint: disable=attribute-defined-outside-init
        # Note : define outside init because the following
        # attributes are temporary. They should not be
        # saved to settings.json.

        self.to_import = len(record_list)
        self.imported_origins: typing.List[str] = imported_origins
        self.len_before = len(imported_origins)
        self.source_records_list: typing.List[typing.Dict] = record_list

    def __str__(self) -> str:
        return (
            f"{self.source_name} (type: {self.search_type}, "
            + f"filename: {self.filename})\n"
            + f"   source identifier:   {self.source_identifier}\n"
            + f"   search parameters:   {self.search_parameters}\n"
            + f"   load_conversion_script:   {self.load_conversion_script['endpoint']}\n"
            + f"   comment:             {self.comment}"
        )


@dataclass
class SearchSettings(JsonSchemaMixin):
    """Search settings"""

    retrieve_forthcoming: bool

    def __str__(self) -> str:
        return f" - retrieve_forthcoming: {self.retrieve_forthcoming}"


# Load


@dataclass
class LoadSettings(JsonSchemaMixin):
    """Load settings"""

    def __str__(self) -> str:
        return " - TODO"


# Prep


@dataclass
class PrepRound(JsonSchemaMixin):
    """Prep round settings"""

    name: str
    similarity: float
    scripts: list

    def __str__(self) -> str:
        short_list = [script["endpoint"] for script in self.scripts][:3]
        if len(self.scripts) > 3:
            short_list.append("...")
        return f"{self.name} (" + ",".join(short_list) + ")"


@dataclass
class PrepSettings(JsonSchemaMixin):
    """Prep settings"""

    fields_to_keep: typing.List[str]
    prep_rounds: typing.List[PrepRound]

    man_prep_scripts: list

    def __str__(self) -> str:
        return (
            " - prep_rounds: \n   - "
            + "\n   - ".join([str(prep_round) for prep_round in self.prep_rounds])
            + f"\n - fields_to_keep: {self.fields_to_keep}"
        )


# Dedupe


class SameSourceMergePolicy(Enum):
    """Policy for applying merges within the same search source"""

    # pylint: disable=invalid-name
    prevent = "prevent"
    apply = "apply"
    warn = "warn"

    @classmethod
    def get_options(cls) -> typing.List[str]:
        # pylint: disable=no-member
        return cls._member_names_

    @classmethod
    def get_field_details(cls) -> typing.Dict:
        # pylint: disable=no-member
        return {"options": cls._member_names_, "type": "selection"}


@dataclass
class DedupeSettings(JsonSchemaMixin):
    """Dedupe settings"""

    same_source_merges: SameSourceMergePolicy
    scripts: list

    def __str__(self) -> str:
        return (
            f" - same_source_merges: {self.same_source_merges}\n"
            + " - "
            + ",".join([s["endpoint"] for s in self.scripts])
        )


# Prescreen


@dataclass
class PrescreenSettings(JsonSchemaMixin):
    """Prescreen settings"""

    explanation: str
    scripts: list

    def __str__(self) -> str:
        return "Scripts: " + ",".join([s["endpoint"] for s in self.scripts])


# PDF get


class PDFPathType(Enum):
    """Policy for handling PDFs (create symlinks or copy files)"""

    # pylint: disable=invalid-name
    symlink = "symlink"
    copy = "copy"

    @classmethod
    def get_field_details(cls) -> typing.Dict:
        # pylint: disable=no-member
        return {"options": cls._member_names_, "type": "selection"}

    @classmethod
    def get_options(cls) -> typing.List[str]:
        # pylint: disable=no-member
        return cls._member_names_


@dataclass
class PDFGetSettings(JsonSchemaMixin):
    """PDF get settings"""

    pdf_path_type: PDFPathType
    pdf_required_for_screen_and_synthesis: bool
    """With the pdf_required_for_screen_and_synthesis flag, the PDF retrieval
    can be specified as mandatory (true) or optional (false) for the following steps"""
    rename_pdfs: bool
    scripts: list

    man_pdf_get_scripts: list

    def __str__(self) -> str:
        return (
            f" - pdf_path_type: {self.pdf_path_type}"
            + " - "
            + ",".join([s["endpoint"] for s in self.scripts])
        )


# PDF prep


@dataclass
class PDFPrepSettings(JsonSchemaMixin):
    """PDF prep settings"""

    scripts: list

    man_pdf_prep_scripts: list

    def __str__(self) -> str:
        return " - " + ",".join([s["endpoint"] for s in self.scripts])


# Screen


class ScreenCriterionType(Enum):
    """Type of screening criterion"""

    # pylint: disable=invalid-name
    inclusion_criterion = "inclusion_criterion"
    exclusion_criterion = "exclusion_criterion"

    @classmethod
    def get_options(cls) -> typing.List[str]:
        # pylint: disable=no-member
        return cls._member_names_

    @classmethod
    def get_field_details(cls) -> typing.Dict:
        # pylint: disable=no-member
        return {"options": cls._member_names_, "type": "selection"}

    def __str__(self) -> str:
        return self.name


@dataclass
class ScreenCriterion(JsonSchemaMixin):
    """Screen criterion"""

    explanation: str
    comment: typing.Optional[str]
    criterion_type: ScreenCriterionType

    def __str__(self) -> str:
        return f"{self.criterion_type} {self.explanation} ({self.explanation})"


@dataclass
class ScreenSettings(JsonSchemaMixin):
    """Screen settings"""

    explanation: typing.Optional[str]
    criteria: typing.Dict[str, ScreenCriterion]
    scripts: list

    def __str__(self) -> str:
        return " - " + "\n - ".join([str(c) for c in self.criteria])


# Data


@dataclass
class DataSettings(JsonSchemaMixin):
    """Data settings"""

    scripts: list

    def __str__(self) -> str:
        return " - " + "\n- ".join([s["endpoint"] for s in self.scripts])


@dataclass
class Settings(JsonSchemaMixin):
    """CoLRev project settings"""

    # pylint: disable=too-many-instance-attributes

    project: ProjectSettings
    sources: typing.List[SearchSource]
    search: SearchSettings
    load: LoadSettings
    prep: PrepSettings
    dedupe: DedupeSettings
    prescreen: PrescreenSettings
    pdf_get: PDFGetSettings
    pdf_prep: PDFPrepSettings
    screen: ScreenSettings
    data: DataSettings

    def __str__(self) -> str:
        return (
            str(self.project)
            + "\nSearch\n"
            + str(self.search)
            + "\nSources\n"
            + "\n- ".join([str(s) for s in self.sources])
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

    @classmethod
    def get_settings_schema(cls):

        schema = cls.json_schema()
        sdefs = schema["definitions"]
        sdefs["SearchSource"]["properties"]["conversion_script"] = {  # type: ignore
            "script_type": "conversion",
            "type": "script_item",
        }

        sdefs["SearchSource"]["properties"]["search_script"] = {  # type: ignore
            "script_type": "search",
            "type": "script_item",
        }

        sdefs["SearchSource"]["properties"]["source_prep_scripts"] = {  # type: ignore
            "script_type": "source_prep_script",
            "type": "script_array",
        }

        # pylint: disable=unused-variable
        prep_rounds = sdefs["PrepRound"]["properties"]["scripts"]
        prep_rounds = {  # type: ignore # noqa: F841
            "script_type": "prep",
            "type": "script_array",
        }
        sdefs["PrepSettings"]["properties"]["PrepSettings"] = {  # type: ignore
            "script_type": "prep_man",
            "type": "script_array",
        }
        sdefs["DedupeSettings"]["properties"]["scripts"] = {  # type: ignore
            "script_type": "dedupe",
            "type": "script_array",
        }
        sdefs["PrescreenSettings"]["properties"]["scripts"] = {  # type: ignore
            "script_type": "prescreen",
            "type": "script_array",
        }
        sdefs["PDFGetSettings"]["properties"]["scripts"] = {  # type: ignore
            "script_type": "pdf_get",
            "type": "script_array",
        }
        sdefs["PDFGetSettings"]["properties"]["man_pdf_get_scripts"] = {  # type: ignore
            "script_type": "pdf_get_man",
            "type": "script_array",
        }
        sdefs["PDFPrepSettings"]["properties"]["scripts"] = {  # type: ignore
            "script_type": "pdf_prep",
            "type": "script_array",
        }
        sdefs["PDFPrepSettings"]["properties"]["man_pdf_prep_scripts"] = {  # type: ignore
            "script_type": "pdf_prep_man",
            "type": "script_array",
        }
        sdefs["ScreenSettings"]["properties"]["scripts"] = {  # type: ignore
            "script_type": "screen",
            "type": "script_array",
        }
        sdefs["DataSettings"]["properties"]["scripts"] = {  # type: ignore
            "script_type": "data",
            "type": "script_array",
        }

        return schema


if __name__ == "__main__":
    pass
