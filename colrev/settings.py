#!/usr/bin/env python3
"""Settings of the project"""
from __future__ import annotations

import json
import typing
from pathlib import Path

from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.ops.search_api_feed
from colrev.constants import IDPattern
from colrev.constants import PDFPathType
from colrev.constants import ScreenCriterionType
from colrev.constants import SearchType
from colrev.constants import ShareStatReq

if typing.TYPE_CHECKING:
    import colrev.review_manager

# Note : to avoid performance issues on startup (ReviewManager, parsing settings)
# the settings dataclasses should be in one file (13s compared to 0.3s)


# Project


class Author(BaseModel):
    """Author of the review"""

    # pylint: disable=too-many-instance-attributes

    name: str
    initials: str
    email: str
    orcid: typing.Optional[str] = None
    contributions: typing.List[str] = Field(default_factory=list)
    affiliations: typing.Optional[str] = None
    funding: typing.List[str] = Field(default_factory=list)
    identifiers: typing.List[str] = Field(default_factory=list)


class Protocol(BaseModel):
    """Review protocol"""

    url: str


class ProjectSettings(BaseModel):
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
        project_str = f"- review ({self.review_type}):"
        project_str += f"\n- title: {self.title}"
        return project_str


# Search


class SearchSource(BaseModel):
    """Search source settings"""

    # pylint: disable=too-many-instance-attributes
    endpoint: str
    filename: Path
    search_type: SearchType
    search_parameters: dict
    comment: typing.Optional[str]

    to_import: int = 0
    imported_origins: typing.List[str] = []
    len_before: int = 0
    source_records_list: typing.List[typing.Dict] = []

    # pylint: disable=no-self-argument
    @model_validator(mode="before")
    def validate_filename(cls, values):  # type: ignore
        """Validate the filename"""
        filename = values.get("filename")
        if filename and not str(filename).replace("\\", "/").startswith("data/search"):
            raise colrev_exceptions.InvalidSettingsError(
                msg=f"Source filename does not start with data/search: {filename}"
            )
        return values

    def model_dump(self, **kwargs) -> dict:  # type: ignore
        exclude = set(kwargs.pop("exclude", set()))
        exclude.add("to_import")
        exclude.add("imported_origins")
        exclude.add("len_before")
        exclude.add("source_records_list")
        return super().model_dump(exclude=exclude, **kwargs)

    def setup_for_load(
        self,
        *,
        source_records_list: typing.List[typing.Dict],
        imported_origins: typing.List[str],
    ) -> None:
        """Set the SearchSource up for the load process (initialize statistics)"""
        # pylint: disable=attribute-defined-outside-init
        # Note : define outside init because the following
        # attributes are temporary. They should not be
        # saved to SETTINGS_FILE.

        self.to_import = len(source_records_list)
        self.imported_origins: typing.List[str] = imported_origins
        self.len_before = len(imported_origins)
        self.source_records_list: typing.List[typing.Dict] = source_records_list

    def get_origin_prefix(self) -> str:
        """Get the corresponding origin prefix"""
        assert not any(x in str(self.filename.name) for x in [";", "/"])
        return str(self.filename.name).lstrip("/")

    def is_md_source(self) -> bool:
        """Check whether the source is a metadata source (for preparation)"""

        return str(self.filename.name).startswith("md_")

    def is_curated_source(self) -> bool:
        """Check whether the source is a curated source (for preparation)"""

        return self.get_origin_prefix() == "md_curated.bib"

    def get_query(self) -> str:
        """Get the query filepath"""
        assert self.search_type == SearchType.DB
        # Note : save API queries in SETTINGS_FILE
        if "query_file" not in self.search_parameters:
            raise KeyError
        if not Path(self.search_parameters["query_file"]).is_file():
            raise FileNotFoundError
        return Path(self.search_parameters["query_file"]).read_text(encoding="utf-8")

    def get_api_feed(
        self,
        review_manager: colrev.review_manager.ReviewManager,
        source_identifier: str,
        update_only: bool,
        prep_mode: bool = False,
    ) -> colrev.ops.search_api_feed.SearchAPIFeed:
        """Get a feed to add and update records"""

        return colrev.ops.search_api_feed.SearchAPIFeed(
            review_manager=review_manager,
            source_identifier=source_identifier,
            search_source=self,
            update_only=update_only,
            prep_mode=prep_mode,
        )

    def __str__(self) -> str:
        formatted_str = (
            f"{str(self.search_type).lower()}: {self.endpoint} >> {self.filename}"
        )
        if self.search_parameters:
            formatted_str += f"\n   search parameters:   {self.search_parameters}"
        if self.comment:
            formatted_str += f"\n   comment:             {self.comment}"

        return formatted_str


class SearchSettings(BaseModel):
    """Search settings"""

    retrieve_forthcoming: bool

    def __str__(self) -> str:
        return f"- retrieve_forthcoming: {self.retrieve_forthcoming}"


# Prep


class PrepRound(BaseModel):
    """Prep round settings"""

    name: str
    prep_package_endpoints: list

    def __str__(self) -> str:
        short_list = [script["endpoint"] for script in self.prep_package_endpoints][:3]
        if len(self.prep_package_endpoints) > 3:
            short_list.append("...")
        return f"{self.name} (" + ",".join(short_list) + ")"


class PrepSettings(BaseModel):
    """Prep settings"""

    fields_to_keep: typing.List[str]
    prep_rounds: typing.List[PrepRound]

    prep_man_package_endpoints: list

    defects_to_ignore: list

    def __str__(self) -> str:
        return (
            f"- fields_to_keep: {self.fields_to_keep}\n"
            + "- prep_rounds:\n - endpoints:\n   - "
            + "\n   - ".join([str(prep_round) for prep_round in self.prep_rounds])
        )


# Dedupe


class DedupeSettings(BaseModel):
    """Dedupe settings"""

    dedupe_package_endpoints: list

    def __str__(self) -> str:
        endpoints_str = "- endpoints: []\n"
        if self.dedupe_package_endpoints:
            endpoints_str = "- endpoints:\n - " + "\n - ".join(
                [s["endpoint"] for s in self.dedupe_package_endpoints]
            )
        return endpoints_str


# Prescreen


class PrescreenSettings(BaseModel):
    """Prescreen settings"""

    explanation: str
    prescreen_package_endpoints: list

    def __str__(self) -> str:
        endpoints_str = "- endpoints: []\n"
        if self.prescreen_package_endpoints:
            endpoints_str = "- endpoints:\n - " + "\n - ".join(
                [s["endpoint"] for s in self.prescreen_package_endpoints]
            )
        return endpoints_str


# PDF get


class PDFGetSettings(BaseModel):
    """PDF get settings"""

    pdf_path_type: PDFPathType
    pdf_required_for_screen_and_synthesis: bool
    """With the pdf_required_for_screen_and_synthesis flag, the PDF retrieval
    can be specified as mandatory (true) or optional (false) for the following steps"""
    rename_pdfs: bool
    pdf_get_package_endpoints: list

    pdf_get_man_package_endpoints: list

    defects_to_ignore: list

    def __str__(self) -> str:
        endpoints_str = "- endpoints: []\n"
        if self.pdf_get_man_package_endpoints:
            endpoints_str = "- endpoints:\n - " + "\n - ".join(
                [s["endpoint"] for s in self.pdf_get_package_endpoints]
            )
        return f"- pdf_path_type: {self.pdf_path_type.value}\n" + endpoints_str


# PDF prep


class PDFPrepSettings(BaseModel):
    """PDF prep settings"""

    keep_backup_of_pdfs: bool

    pdf_prep_package_endpoints: list

    pdf_prep_man_package_endpoints: list

    def __str__(self) -> str:
        endpoints_str = "- endpoints: []\n"
        if self.pdf_prep_package_endpoints:
            endpoints_str = "- endpoints:\n - " + "\n - ".join(
                [s["endpoint"] for s in self.pdf_prep_package_endpoints]
            )
        return endpoints_str


# Screen


class ScreenCriterion(BaseModel):
    """Screen criterion"""

    explanation: str
    comment: typing.Optional[str]
    criterion_type: ScreenCriterionType

    def __str__(self) -> str:
        return f"{self.explanation} ({self.criterion_type}, {self.comment})"


class ScreenSettings(BaseModel):
    """Screen settings"""

    explanation: typing.Optional[str] = None
    criteria: typing.Dict[str, ScreenCriterion]
    screen_package_endpoints: list

    def __str__(self) -> str:
        endpoints_str = "- endpoints: []\n"
        if self.screen_package_endpoints:
            endpoints_str = "- endpoints:\n - " + "\n - ".join(
                [s["endpoint"] for s in self.screen_package_endpoints]
            )
        criteria_str = "- Criteria: []"
        if self.criteria:
            criteria_str = "- Criteria:\n - " + "\n - ".join(
                [
                    f"{short_name}: " + str(criterion)
                    for short_name, criterion in self.criteria.items()
                ]
            )
        return criteria_str + "\n" + endpoints_str


# Data


class DataSettings(BaseModel):
    """Data settings"""

    data_package_endpoints: list

    def __str__(self) -> str:
        endpoints_str = "- endpoints: []\n"
        if self.data_package_endpoints:
            endpoints_str = "- endpoints:\n - " + "\n - ".join(
                [s["endpoint"] for s in self.data_package_endpoints]
            )
        return endpoints_str


class Settings(BaseModel):
    """CoLRev project settings"""

    # pylint: disable=too-many-instance-attributes

    project: ProjectSettings
    sources: typing.List[SearchSource]
    search: SearchSettings
    prep: PrepSettings
    dedupe: DedupeSettings
    prescreen: PrescreenSettings
    pdf_get: PDFGetSettings
    pdf_prep: PDFPrepSettings
    screen: ScreenSettings
    data: DataSettings

    def model_dump(self, **kwargs) -> dict:  # type: ignore
        """Dump the settings model with recursive handling of SearchSource."""

        sources_dump = [source.model_dump(**kwargs) for source in self.sources]
        data = super().model_dump(**kwargs)
        data["sources"] = sources_dump
        return data

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
        sources_str = "\n- " + "\n- ".join(
            [str(s) for s in self.sources if s.is_md_source()]
            + [str(s) for s in self.sources if not s.is_md_source()]
        )

        return (
            str(self.project)
            + "\nSearch\n"
            + str(self.search)
            + "\nSources"
            + sources_str
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

    def get_packages(self) -> typing.List[str]:
        """Get the list of all package names"""

        def extract_endpoints(package_endpoints: list) -> list:
            return [
                e for pe in package_endpoints for k, e in pe.items() if k == "endpoint"
            ]

        all_packages = (
            [self.project.review_type]
            + [s.endpoint for s in self.sources]
            + extract_endpoints(self.prep.prep_man_package_endpoints)
            + extract_endpoints(self.dedupe.dedupe_package_endpoints)
            + extract_endpoints(self.prescreen.prescreen_package_endpoints)
            + extract_endpoints(self.pdf_get.pdf_get_package_endpoints)
            + extract_endpoints(self.pdf_get.pdf_get_man_package_endpoints)
            + extract_endpoints(self.pdf_prep.pdf_prep_package_endpoints)
            + extract_endpoints(self.pdf_prep.pdf_prep_man_package_endpoints)
            + extract_endpoints(self.screen.screen_package_endpoints)
            + extract_endpoints(self.data.data_package_endpoints)
        )
        for p_round in self.prep.prep_rounds:
            all_packages.extend(extract_endpoints(p_round.prep_package_endpoints))

        return all_packages


def _add_missing_attributes(loaded_dict: dict) -> None:  # pragma: no cover
    # replace dict with defaults if values are missing (to avoid exceptions)
    if "defects_to_ignore" not in loaded_dict["pdf_get"]:
        loaded_dict["pdf_get"]["defects_to_ignore"] = []


def _load_settings_from_dict(loaded_dict: dict) -> Settings:
    try:
        _add_missing_attributes(loaded_dict)
        settings = Settings(**loaded_dict)
        filenames = [x.filename for x in settings.sources]
        if not len(filenames) == len(set(filenames)):
            non_unique = list({str(x) for x in filenames if filenames.count(x) > 1})
            msg = f"Non-unique source filename(s): {', '.join(non_unique)}"
            raise colrev_exceptions.InvalidSettingsError(msg=msg, fix_per_upgrade=False)

    except (Exception,) as exc:  # pragma: no cover
        raise colrev_exceptions.InvalidSettingsError(msg=str(exc)) from exc

    return settings


def load_settings(*, settings_path: Path) -> Settings:
    """Load the settings from file"""

    if not settings_path.is_file():
        raise colrev_exceptions.RepoSetupError()

    try:
        with open(settings_path, encoding="utf-8") as file:
            loaded_dict = json.load(file)

    except json.decoder.JSONDecodeError as exc:
        raise colrev_exceptions.RepoSetupError(
            f"Failed to load settings: {exc}"
        ) from exc

    return _load_settings_from_dict(loaded_dict)


def save_settings(*, review_manager: colrev.review_manager.ReviewManager) -> None:
    """Save the settings"""

    exported_dict = review_manager.settings.model_dump()
    exported_dict = colrev.env.utils.custom_asdict_factory(exported_dict)

    with open(review_manager.paths.settings, "w", encoding="utf-8") as outfile:
        json.dump(exported_dict, outfile, indent=4)
    review_manager.dataset.add_changes(review_manager.paths.settings)
