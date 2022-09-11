#!/usr/bin/env python3
import dataclasses
import inspect
import typing
from dataclasses import dataclass
from enum import Enum
from enum import EnumMeta
from pathlib import Path

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


class ReviewType(Enum):
    """The type of review"""

    # pylint: disable=invalid-name
    curated_masterdata = "curated_masterdata"
    realtime = "realtime"
    literature_review = "literature_review"
    narrative_review = "narrative_review"
    descriptive_review = "descriptive_review"
    scoping_review = "scoping_review"
    critical_review = "critical_review"
    theoretical_review = "theoretical_review"
    conceptual_review = "conceptual_review"
    qualitative_systematic_review = "qualitative_systematic_review"
    meta_analysis = "meta_analysis"
    scientometric = "scientometric"
    peer_review = "peer_review"

    @classmethod
    def get_field_details(cls) -> typing.Dict:
        # pylint: disable=E1101
        return {"options": cls._member_names_, "type": "selection"}

    @classmethod
    def get_options(cls) -> typing.List[str]:
        # pylint: disable=no-member
        return cls._member_names_

    def __str__(self) -> str:
        return (
            f"{self.name.replace('_', ' ').replace('meta analysis', 'meta-analysis')}"
        )


@dataclass
class Author:
    name: str
    initials: str
    email: str
    orcid: typing.Optional[str] = None
    contributions: typing.List[str] = dataclasses.field(default_factory=list)
    affiliations: typing.Optional[str] = None
    funding: typing.List[str] = dataclasses.field(default_factory=list)
    identifiers: typing.List[str] = dataclasses.field(default_factory=list)


@dataclass
class Protocol:
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
class ProjectConfiguration:
    """Project settings"""

    title: str
    __doc_title__ = "The title of the review"
    authors: typing.List[Author]
    keywords: typing.List[str]
    # status ? (development/published?)
    protocol: typing.Optional[Protocol]
    # publication: ... (reference, link, ....)
    review_type: ReviewType
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
class SearchSource:
    filename: Path
    search_type: SearchType
    source_name: str
    source_identifier: str
    search_parameters: str
    search_script: dict
    conversion_script: dict
    source_prep_scripts: list
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
        source_prep_scripts_string = ",".join(
            s["endpoint"] for s in self.source_prep_scripts
        )
        return (
            f"{self.source_name} (type: {self.search_type}, "
            + f"filename: {self.filename})\n"
            + f"   source identifier:   {self.source_identifier}\n"
            + f"   search parameters:   {self.search_parameters}\n"
            + f"   search_script:       {self.search_script.get('endpoint', '')}\n"
            + f"   conversion_script:   {self.conversion_script['endpoint']}\n"
            + f"   source_prep_script:  {source_prep_scripts_string}\n"
            + f"   comment:             {self.comment}"
        )


@dataclass
class SearchConfiguration:
    retrieve_forthcoming: bool

    def __str__(self) -> str:
        return f" - retrieve_forthcoming: {self.retrieve_forthcoming}"


# Load


@dataclass
class LoadConfiguration:
    def __str__(self) -> str:
        return " - TODO"


# Prep


@dataclass
class PrepRound:
    """The scripts are either in Prepare.prep_scripts, in a custom project script
    (the script in settings.json must have the same name), or otherwise in a
    python package (locally installed)."""

    name: str
    similarity: float
    scripts: list

    def __str__(self) -> str:
        short_list = [script["endpoint"] for script in self.scripts][:3]
        if len(self.scripts) > 3:
            short_list.append("...")
        return f"{self.name} (" + ",".join(short_list) + ")"


@dataclass
class PrepConfiguration:
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
class DedupeConfiguration:
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
class PrescreenConfiguration:
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
class PDFGetConfiguration:
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
class PDFPrepConfiguration:
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
class ScreenCriterion:
    explanation: str
    comment: typing.Optional[str]
    criterion_type: ScreenCriterionType

    def __str__(self) -> str:
        return f"{self.criterion_type} {self.explanation} ({self.explanation})"


@dataclass
class ScreenConfiguration:
    explanation: typing.Optional[str]
    criteria: typing.Dict[str, ScreenCriterion]
    scripts: list

    def __str__(self) -> str:
        return " - " + "\n - ".join([str(c) for c in self.criteria])


# Data


@dataclass
class DataConfiguration:
    scripts: list

    def __str__(self) -> str:
        return " - " + "\n- ".join([s["endpoint"] for s in self.scripts])


@dataclass
class Configuration:

    project: ProjectConfiguration
    sources: typing.List[SearchSource]
    search: SearchConfiguration
    load: LoadConfiguration
    prep: PrepConfiguration
    dedupe: DedupeConfiguration
    prescreen: PrescreenConfiguration
    pdf_get: PDFGetConfiguration
    pdf_prep: PDFPrepConfiguration
    screen: ScreenConfiguration
    data: DataConfiguration

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

        # https://json-schema.org/learn/getting-started-step-by-step

        def get_configuration_options(conf_input):
            conf_options_dict = {}
            conf_cls = conf_input

            # https://stackoverflow.com/questions/50563546/validating-detailed-types-in-python-dataclasses
            if hasattr(conf_cls, "__dict__"):

                if typing.get_origin(conf_cls) == list:
                    # example: SearchSource
                    properties = get_configuration_options(typing.get_args(conf_cls)[0])
                    return {"list": True, "type": "object", "properties": properties}

                if "__dataclass_fields__" in conf_cls.__dict__:
                    for key, value in conf_cls.__dict__["__dataclass_fields__"].items():

                        conf_options_dict[key] = {}

                        if value.type in (str, int, float, bool):
                            if hasattr(conf_cls, f"__doc_{key}__"):
                                conf_options_dict[key]["tooltip"] = getattr(
                                    conf_cls, f"__doc_{key}__"
                                )

                        elif isinstance(value.type, EnumMeta):
                            conf_options_dict[key]["tooltip"] = value.type.__doc__
                            conf_options_dict[key]["type"] = "selection"
                            conf_options_dict[key]["options"] = value.type.get_options()
                            continue
                        # elif inspect.isclass(value.type):
                        #     conf_options_dict[key]["tooltip"] = get_configuration_tooltips(value)

                        # Add tooltips
                        # conf_options_dict[key]["tooltips"] = get_configuration_tooltips(value)

                        # Add type/required
                        if value.type in (int, str, float, bool):
                            conf_options_dict[key]["type"] = value.type.__name__
                            continue

                        if typing.get_origin(value.type) == list:
                            conf_options_dict[key]["list"] = True

                            rets = [
                                get_configuration_options(element)
                                for element in typing.get_args(value.type)
                            ]
                            if str == type(rets[0]):  # noqa: E721
                                conf_options_dict[key]["type"] = rets[0]

                            if dict == type(rets[0]):  # noqa: E721
                                conf_options_dict[key]["type"] = "object"
                                conf_options_dict[key]["properties"] = rets[0]

                            if value.type in (int, str, float, bool):
                                conf_options_dict[key]["type"] = value.type.__name__

                        # Note : typing.Optional occurs as "typing.Union[str, NoneType]"
                        elif typing.get_origin(value.type) == typing.Union:
                            for element in typing.get_args(value.type):
                                ret = get_configuration_options(element)

                                if "optional" != ret:
                                    conf_options_dict[key]["type"] = ret
                                # else:
                                #     conf_options_dict[key]["required"] = False

                        elif typing.get_origin(value.type) in [dict]:
                            conf_options_dict[key] = {}
                            _, dict_value = typing.get_args(value.type)
                            conf_options_dict[key][
                                "custom_dict_key"
                            ] = get_configuration_options(dict_value)

                        elif inspect.isclass(value.type):
                            if "Path" == value.type.__name__:
                                conf_options_dict[key]["type"] = "Path"
                            else:
                                conf_options_dict[key][
                                    "properties"
                                ] = get_configuration_options(value.type)
                        else:
                            print(f"Error 2: {conf_cls}")

                else:
                    if conf_cls == type(None):  # noqa: E721
                        return "optional"

                    if conf_cls in (int, str, float, bool):
                        return conf_cls.__name__

                    if conf_cls == list:
                        return "List"

                    print(f"Error 1: {conf_cls}")

            else:
                print(f"not hasattr __dict_: {conf_cls}")

            return conf_options_dict

        options_dict = {}
        for key, value in cls.__dict__["__dataclass_fields__"].items():
            options_dict[key] = {"type": "object"}
            options_dict[key]["properties"] = get_configuration_options(value.type)

        options_dict["sources"]["properties"]["conversion_script"] = {  # type: ignore
            "type": "script_selector",
            "script_type": "conversion",
            "list": False,
        }

        options_dict["sources"]["properties"]["search_script"] = {  # type: ignore
            "type": "script_selector",
            "script_type": "search",
            "list": False,
        }

        options_dict["sources"]["properties"]["source_prep_scripts"] = {  # type: ignore
            "type": "script_multiple_selector",
            "script_type": "source_prep_script",
            "list": True,
        }

        # pylint: disable=unused-variable
        prep_rounds = options_dict["prep"]["properties"]["prep_rounds"]["properties"][
            "scripts"
        ]
        prep_rounds = {  # type: ignore # noqa: F841
            "type": "script_multiple_selector",
            "script_type": "prep",
            "list": True,
        }
        options_dict["prep"]["properties"]["man_prep_scripts"] = {  # type: ignore
            "type": "script_multiple_selector",
            "script_type": "prep_man",
            "list": True,
        }
        options_dict["dedupe"]["properties"]["scripts"] = {  # type: ignore
            "type": "script_multiple_selector",
            "script_type": "dedupe",
            "list": True,
        }
        options_dict["prescreen"]["properties"]["scripts"] = {  # type: ignore
            "type": "script_multiple_selector",
            "script_type": "prescreen",
            "list": True,
        }
        options_dict["pdf_get"]["properties"]["scripts"] = {  # type: ignore
            "type": "script_multiple_selector",
            "script_type": "pdf_get",
            "list": True,
        }
        options_dict["pdf_get"]["properties"]["man_pdf_get_scripts"] = {  # type: ignore
            "type": "script_multiple_selector",
            "script_type": "pdf_get_man",
            "list": True,
        }
        options_dict["pdf_prep"]["properties"]["scripts"] = {  # type: ignore
            "type": "script_multiple_selector",
            "script_type": "pdf_prep",
            "list": True,
        }
        options_dict["pdf_prep"]["properties"]["man_pdf_prep_scripts"] = {  # type: ignore
            "type": "script_multiple_selector",
            "script_type": "pdf_prep_man",
            "list": True,
        }
        options_dict["screen"]["properties"]["scripts"] = {  # type: ignore
            "type": "script_multiple_selector",
            "script_type": "screen",
            "list": True,
        }
        options_dict["data"]["properties"]["scripts"] = {  # type: ignore
            "type": "script_multiple_selector",
            "script_type": "data",
            "list": True,
        }

        return options_dict


if __name__ == "__main__":
    pass
