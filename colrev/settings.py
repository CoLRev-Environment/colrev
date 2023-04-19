#!/usr/bin/env python3
"""Settings of the CoLRev project."""
from __future__ import annotations

import dataclasses
import json
import typing
import warnings
from dataclasses import asdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import dacite
from dacite import from_dict
from dacite.exceptions import MissingValueError
from dacite.exceptions import WrongTypeError
from dataclasses_jsonschema import FieldEncoder
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.utils
import colrev.exceptions as colrev_exceptions

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.review_manager


# Note : to avoid performance issues on startup (ReviewManager, parsing settings)
# the settings dataclasses should be in one file (13s compared to 0.3s)


# Project


class IDPattern(Enum):
    """The pattern for generating record IDs"""

    # pylint: disable=invalid-name
    first_author_year = "first_author_year"
    three_authors_year = "three_authors_year"

    @classmethod
    def get_options(cls) -> typing.List[str]:
        """Get the options"""
        # pylint: disable=no-member
        return cls._member_names_

    @classmethod
    def get_field_details(cls) -> typing.Dict:
        """Get the field details"""
        # pylint: disable=no-member
        return {"options": cls._member_names_, "type": "selection"}


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
    def get_field_details(cls) -> typing.Dict:
        """Get the field details"""
        # pylint: disable=no-member
        return {"options": cls._member_names_, "type": "selection"}

    @classmethod
    def get_options(cls) -> typing.List[str]:
        """Get the options"""
        # pylint: disable=no-member
        return cls._member_names_


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
    colrev_version: str
    auto_upgrade: bool

    def __str__(self) -> str:
        project_str = f"Review ({self.review_type}):"
        if self.title:
            project_str += f" {self.title}"
        return project_str


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
    def get_field_details(cls) -> typing.Dict:
        """Get the field details"""
        # pylint: disable=no-member
        return {"options": cls._member_names_, "type": "selection"}

    @classmethod
    def get_options(cls) -> typing.List[str]:
        """Get the options"""
        # pylint: disable=no-member
        return cls._member_names_

    def __str__(self) -> str:
        return f"{self.name}"


@dataclass
class SearchSource(JsonSchemaMixin):
    """Search source settings"""

    # pylint: disable=too-many-instance-attributes

    endpoint: str
    filename: Path
    search_type: SearchType
    search_parameters: dict
    load_conversion_package_endpoint: dict
    comment: typing.Optional[str]

    def get_corresponding_bib_file(self) -> Path:
        """Get the corresponding bib file"""

        return self.filename.with_suffix(".bib")

    def setup_for_load(
        self,
        *,
        record_list: typing.List[typing.Dict],
        imported_origins: typing.List[str],
    ) -> None:
        """Set the SearchSource up for the load process (initialize statistics)"""
        # pylint: disable=attribute-defined-outside-init
        # Note : define outside init because the following
        # attributes are temporary. They should not be
        # saved to settings.json.

        self.to_import = len(record_list)
        self.imported_origins: typing.List[str] = imported_origins
        self.len_before = len(imported_origins)
        self.source_records_list: typing.List[typing.Dict] = record_list

    def get_origin_prefix(self) -> str:
        """Get the corresponding origin prefix"""
        return (
            str(self.get_corresponding_bib_file().name)
            .replace(str(colrev.review_manager.ReviewManager.SEARCHDIR_RELATIVE), "")
            .lstrip("/")
        )

    def is_md_source(self) -> bool:
        """Check whether the source is a metadata source (for preparation)"""

        return str(self.filename.name).startswith("md_")

    def is_quasi_md_source(self) -> bool:
        """Check whether the source is a quasi-metadata source
        (when search files are added without search_parameters/queries)"""

        return not bool(self.search_parameters)

    def get_dict(self) -> dict:
        """Get the dict of SearchSources (for endpoint initalization)"""

        exported_dict = asdict(
            self, dict_factory=colrev.env.utils.custom_asdict_factory
        )

        exported_dict["search_type"] = colrev.settings.SearchType[
            exported_dict["search_type"]
        ]
        exported_dict["filename"] = Path(exported_dict["filename"])

        return exported_dict

    def get_feed(
        self,
        review_manager: colrev.review_manager.ReviewManager,
        source_identifier: str,
        update_only: bool,
    ) -> colrev.ops.search.GeneralOriginFeed:
        """Get a feed to add and update records"""
        # pylint: disable=import-outside-toplevel
        # pylint: disable=cyclic-import
        import colrev.ops.search

        return colrev.ops.search.GeneralOriginFeed(
            review_manager=review_manager,
            search_source=self,
            source_identifier=source_identifier,
            update_only=update_only,
        )

    def __str__(self) -> str:
        optional_comment = ""
        if self.comment:
            optional_comment = f"\n   comment:             {self.comment}"
        return (
            f"{self.endpoint} (type: {self.search_type}, "
            + f"filename: {self.filename})\n"
            + f"   search parameters:   {self.search_parameters}"
            # + "   load_conversion_package_endpoint:   "
            # + f"{self.load_conversion_package_endpoint['endpoint']}"
            + optional_comment
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
    prep_package_endpoints: list

    def __str__(self) -> str:
        short_list = [script["endpoint"] for script in self.prep_package_endpoints][:3]
        if len(self.prep_package_endpoints) > 3:
            short_list.append("...")
        return f"{self.name} (" + ",".join(short_list) + ")"


@dataclass
class PrepSettings(JsonSchemaMixin):
    """Prep settings"""

    fields_to_keep: typing.List[str]
    prep_rounds: typing.List[PrepRound]

    prep_man_package_endpoints: list

    def __str__(self) -> str:
        return (
            " - prep_rounds:\n   - "
            + "\n   - ".join([str(prep_round) for prep_round in self.prep_rounds])
            + f"\n - fields_to_keep: {self.fields_to_keep}"
        )


# Dedupe


class SameSourceMergePolicy(Enum):
    """Policy for applying merges within the same search source"""

    # pylint: disable=invalid-name
    prevent = "prevent"
    warn = "warn"
    apply = "apply"

    @classmethod
    def get_field_details(cls) -> typing.Dict:
        """Get the field details"""
        # pylint: disable=no-member
        return {"options": cls._member_names_, "type": "selection"}

    @classmethod
    def get_options(cls) -> typing.List[str]:
        """Get the options"""
        # pylint: disable=no-member
        return cls._member_names_


@dataclass
class DedupeSettings(JsonSchemaMixin):
    """Dedupe settings"""

    same_source_merges: SameSourceMergePolicy
    dedupe_package_endpoints: list

    def __str__(self) -> str:
        return (
            f" - same_source_merges: {self.same_source_merges}\n"
            + " - "
            + ",".join([s["endpoint"] for s in self.dedupe_package_endpoints])
        )


# Prescreen


@dataclass
class PrescreenSettings(JsonSchemaMixin):
    """Prescreen settings"""

    explanation: str
    prescreen_package_endpoints: list

    def __str__(self) -> str:
        return "- " + ",".join(
            [s["endpoint"] for s in self.prescreen_package_endpoints]
        )


# PDF get


class PDFPathType(Enum):
    """Policy for handling PDFs (create symlinks or copy files)"""

    # pylint: disable=invalid-name
    symlink = "symlink"
    copy = "copy"

    @classmethod
    def get_field_details(cls) -> typing.Dict:
        """Get the field details"""
        # pylint: disable=no-member
        return {"options": cls._member_names_, "type": "selection"}

    @classmethod
    def get_options(cls) -> typing.List[str]:
        """Get the options"""
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
    pdf_get_package_endpoints: list

    pdf_get_man_package_endpoints: list

    def __str__(self) -> str:
        return (
            f" - pdf_path_type: {self.pdf_path_type}"
            + "\n - "
            + ",".join([s["endpoint"] for s in self.pdf_get_package_endpoints])
        )


# PDF prep


@dataclass
class PDFPrepSettings(JsonSchemaMixin):
    """PDF prep settings"""

    keep_backup_of_pdfs: bool

    pdf_prep_package_endpoints: list

    pdf_prep_man_package_endpoints: list

    def __str__(self) -> str:
        return "- " + "\n- ".join(
            [s["endpoint"] for s in self.pdf_prep_package_endpoints]
        )


# Screen


class ScreenCriterionType(Enum):
    """Type of screening criterion"""

    # pylint: disable=invalid-name
    inclusion_criterion = "inclusion_criterion"
    exclusion_criterion = "exclusion_criterion"

    @classmethod
    def get_field_details(cls) -> typing.Dict:
        """Get the field details"""
        # pylint: disable=no-member
        return {"options": cls._member_names_, "type": "selection"}

    @classmethod
    def get_options(cls) -> typing.List[str]:
        """Get the options"""
        # pylint: disable=no-member
        return cls._member_names_

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
    screen_package_endpoints: list

    def __str__(self) -> str:
        if self.criteria:
            return " - " + "\n - ".join([str(c) for c in self.criteria])
        return " -"


# Data


@dataclass
class DataSettings(JsonSchemaMixin):
    """Data settings"""

    data_package_endpoints: list

    def __str__(self) -> str:
        return " - " + "\n- ".join([s["endpoint"] for s in self.data_package_endpoints])


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

    def is_curated_repo(self) -> bool:
        """Check whether data is curated in this repository"""

        curation_endpoints = [
            x
            for x in self.data.data_package_endpoints
            if x["endpoint"] == "colrev.colrev_curation"
        ]
        return bool(curation_endpoints)

    def is_curated_masterdata_repo(self) -> bool:
        """Check whether the masterdata is curated in this repository"""

        curation_endpoints = [
            x
            for x in self.data.data_package_endpoints
            if x["endpoint"] == "colrev.colrev_curation"
        ]
        if curation_endpoints:
            curation_endpoint = curation_endpoints[0]
            if curation_endpoint["curated_masterdata"]:
                return True
        return False

    def __str__(self) -> str:
        return (
            str(self.project)
            + "\nSearch\n"
            + str(self.search)
            + "\nSources\n- "
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
    def get_settings_schema(cls) -> dict:
        """Get the json-schema for the settings"""

        class PathField(FieldEncoder):
            """JsonSchemaMixin encoder for Path fields"""

            @property
            def json_schema(self) -> dict:
                return {"type": "path"}

        JsonSchemaMixin.register_field_encoders({Path: PathField()})

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            schema = cls.json_schema()

        sdefs = schema["definitions"]
        sdefs["SearchSource"]["properties"]["load_conversion_package_endpoint"] = {  # type: ignore
            "package_endpoint_type": "load_conversion",
            "type": "package_endpoint",
        }

        # pylint: disable=unused-variable
        sdefs["PrepRound"]["properties"]["prep_package_endpoints"] = {  # type: ignore # noqa: F841
            "package_endpoint_type": "prep",
            "type": "package_endpoint_array",
        }
        sdefs["PrepSettings"]["properties"]["prep_man_package_endpoints"] = {  # type: ignore
            "package_endpoint_type": "prep_man",
            "type": "package_endpoint_array",
        }
        sdefs["DedupeSettings"]["properties"]["dedupe_package_endpoints"] = {  # type: ignore
            "package_endpoint_type": "dedupe",
            "type": "package_endpoint_array",
        }
        sdefs["PrescreenSettings"]["properties"]["prescreen_package_endpoints"] = {  # type: ignore
            "package_endpoint_type": "prescreen",
            "type": "package_endpoint_array",
        }
        sdefs["PDFGetSettings"]["properties"]["pdf_get_package_endpoints"] = {  # type: ignore
            "package_endpoint_type": "pdf_get",
            "type": "package_endpoint_array",
        }
        sdefs["PDFGetSettings"]["properties"]["pdf_get_man_package_endpoints"] = {  # type: ignore
            "package_endpoint_type": "pdf_get_man",
            "type": "package_endpoint_array",
        }
        sdefs["PDFPrepSettings"]["properties"]["pdf_prep_package_endpoints"] = {  # type: ignore
            "package_endpoint_type": "pdf_prep",
            "type": "package_endpoint_array",
        }
        sdefs["PDFPrepSettings"]["properties"]["pdf_prep_man_package_endpoints"] = {  # type: ignore
            "package_endpoint_type": "pdf_prep_man",
            "type": "package_endpoint_array",
        }
        sdefs["ScreenSettings"]["properties"]["screen_package_endpoints"] = {  # type: ignore
            "package_endpoint_type": "screen",
            "type": "package_endpoint_array",
        }
        sdefs["DataSettings"]["properties"]["data_package_endpoints"] = {  # type: ignore
            "package_endpoint_type": "data",
            "type": "package_endpoint_array",
        }

        return schema


def __load_settings_from_dict(*, loaded_dict: dict) -> Settings:
    try:
        converters = {Path: Path, Enum: Enum}
        settings = from_dict(
            data_class=Settings,
            data=loaded_dict,
            config=dacite.Config(type_hooks=converters, cast=[Enum]),  # type: ignore
        )
        for source in settings.sources:
            if not str(source.filename).replace("\\", "/").startswith("data/search"):
                msg = f"Source filename does not start with data/search: {source.filename}"
                raise colrev_exceptions.InvalidSettingsError(msg=msg)

        filenames = [x.filename for x in settings.sources]
        if not len(filenames) == len(set(filenames)):
            non_unique = list({str(x) for x in filenames if filenames.count(x) > 1})
            msg = f"Non-unique source filename(s): {', '.join(non_unique)}"
            raise colrev_exceptions.InvalidSettingsError(msg=msg, fix_per_upgrade=False)

    except (ValueError, MissingValueError, WrongTypeError, AssertionError) as exc:
        raise colrev_exceptions.InvalidSettingsError(
            msg=str(exc)
        ) from exc  # pragma: no cover

    return settings


def load_settings(*, settings_path: Path) -> Settings:
    """Load the settings from file"""

    if not settings_path.is_file():
        raise colrev_exceptions.RepoSetupError()

    with open(settings_path, encoding="utf-8") as file:
        loaded_dict = json.load(file)

    return __load_settings_from_dict(loaded_dict=loaded_dict)


def save_settings(*, review_manager: colrev.review_manager.ReviewManager) -> None:
    """Save the settings"""

    exported_dict = asdict(
        review_manager.settings, dict_factory=colrev.env.utils.custom_asdict_factory
    )

    with open("settings.json", "w", encoding="utf-8") as outfile:
        json.dump(exported_dict, outfile, indent=4)
    review_manager.dataset.add_changes(path=Path("settings.json"))


if __name__ == "__main__":
    pass
