#! /usr/bin/env python
"""Package interfaces."""
from __future__ import annotations

import abc
import typing
from abc import ABC
from abc import abstractmethod
from pathlib import Path
from typing import Type

import colrev.package_manager.package_settings
from colrev.constants import EndpointType
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType

if typing.TYPE_CHECKING:  # pragma: no cover
    import logging
    import colrev.record.record
    import colrev.settings
    import colrev.ops


# pylint: disable=too-few-public-methods


class ReviewTypePackageBaseClass(abc.ABC):
    """The base class for ReviewType packages

    The following cli command calls the initialize method of a ReviewType package:

    ``colrev init --type package_name`` -> calls ``package.initialize()``

    """

    ci_supported: bool

    @abstractmethod
    def __init__(
        self, *, operation: colrev.process.operation.Operation, settings: dict
    ) -> None:
        pass

    @abstractmethod
    def initialize(self, settings: colrev.settings.Settings) -> dict:
        """Initialize the review type"""


class SearchSourcePackageBaseClass(ABC):
    """The base class for SearchSource packages

    The following cli commands call specific methods of a SearchSource package:

    ``colrev search --add package_name`` -> calls ``package.add_endpoint()``

    ``colrev search`` -> calls ``search`` operation -> calls ``package.search()``

    ``colrev load`` -> calls ``load`` operation -> calls ``package.load()``

    ``colrev prep`` -> calls ``prep`` operation -> calls ``package.prep()``

    """

    ci_supported: bool
    settings_class: Type[colrev.package_manager.package_settings.DefaultSourceSettings]
    source_identifier: str
    search_types: list[SearchType]
    heuristic_status: SearchSourceHeuristicStatus
    search_source: colrev.package_manager.package_settings.DefaultSourceSettings

    @abstractmethod
    def __init__(
        self,
        *,
        source_operation: colrev.process.operation.Operation,
        settings: typing.Optional[dict] = None,
    ) -> None:
        pass

    @classmethod
    @abstractmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Heuristic to identify which SearchSource a search file belongs to."""

    @classmethod
    @abstractmethod
    def add_endpoint(
        cls, operation: colrev.ops.search.Search, params: str
    ) -> colrev.settings.SearchSource:
        """Add the SearchSource as an endpoint."""

    @abstractmethod
    def search(self, rerun: bool) -> None:
        """Run a search of the SearchSource."""

    @abstractmethod
    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        """Retrieve masterdata from the SearchSource."""

    # pylint: disable=unused-argument
    @classmethod
    def ensure_append_only(cls, filename: Path) -> bool:
        """Ensure that the SearchSource is append-only."""
        return False

    @classmethod
    @abstractmethod
    def load(cls, *, filename: Path, logger: logging.Logger) -> dict:
        """Load records from the SearchSource."""

    @abstractmethod
    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        source: colrev.settings.SearchSource,
    ) -> colrev.record.record.Record:
        """Run the custom source-prep operation."""


class PrepPackageBaseClass(ABC):
    """The base class for Prep packages.

    The following cli command calls the prepare method of a Prep package:

    ``colrev prep`` -> calls ``package.prepare()``
    """

    ci_supported: bool

    settings_class: Type[colrev.package_manager.package_settings.DefaultSettings]
    source_correction_hint: str
    always_apply_changes: bool

    @abstractmethod
    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,
        settings: dict,
    ) -> None:
        pass

    @abstractmethod
    def prepare(
        self, record: colrev.record.record_prep.PrepRecord
    ) -> colrev.record.record.Record:
        """Run the prep operation."""


class PrepManPackageBaseClass(ABC):
    """The base class for PrepMan packages.

    The following cli command calls the prepare_manual method of a PrepMan package:

    ``colrev prep-man`` -> calls ``package.prepare_manual()``

    """

    ci_supported: bool

    settings_class: Type[colrev.package_manager.package_settings.DefaultSettings]

    @abstractmethod
    def __init__(
        self, *, prep_man_operation: colrev.ops.prep_man.PrepMan, settings: dict
    ) -> None:
        pass

    @abstractmethod
    def prepare_manual(self, records: dict) -> dict:
        """Run the prep-man operation."""


class DedupePackageBaseClass(ABC):
    """The base class for Dedupe packages.

    The following cli command calls the dedupe method of a Dedupe package:

    ``colrev dedupe`` -> calls ``package.run_dedupe()``
    """

    ci_supported: bool

    settings_class: Type[colrev.package_manager.package_settings.DefaultSettings]

    @abstractmethod
    def __init__(
        self,
        *,
        dedupe_operation: colrev.ops.dedupe.Dedupe,
        settings: dict,
    ):
        pass

    @abstractmethod
    def run_dedupe(self) -> None:
        """Run the dedupe operation."""


class PrescreenPackageBaseClass(ABC):
    """The base class for Prescreen packages.

    The following cli command calls the run_prescreen method of a Prescreen package:

    ``colrev prescreen`` -> calls ``package.run_prescreen()``"""

    ci_supported: bool

    settings_class: Type[colrev.package_manager.package_settings.DefaultSettings]
    settings: colrev.package_manager.package_settings.DefaultSettings

    @abstractmethod
    def __init__(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        settings: dict,
    ) -> None:
        pass

    @abstractmethod
    def run_prescreen(self, records: dict, split: list) -> dict:
        """Run the prescreen operation."""


class PDFGetPackageBaseClass(ABC):
    """The base class for PDFGet packages.

    The following cli command calls the pdf_get method of a PDFGet package:

    ``colrev pdf-get`` -> calls ``package.get_pdf()``
    """

    ci_supported: bool

    settings_class: Type[colrev.package_manager.package_settings.DefaultSettings]

    @abstractmethod
    def __init__(
        self,
        *,
        pdf_get_operation: colrev.ops.pdf_get.PDFGet,
        settings: dict,
    ) -> None:
        pass

    @abstractmethod
    def get_pdf(
        self, record: colrev.record.record.Record
    ) -> colrev.record.record.Record:
        """Run the pdf-get operation."""


class PDFGetManPackageBaseClass(ABC):
    """The base class for PDFGetMan packages.

    The following cli command calls the pdf_get_man method of a PDFGetMan package:

    ``colrev pdf-get-man`` -> calls ``package.pdf_get_man()``"""

    ci_supported: bool

    settings_class: Type[colrev.package_manager.package_settings.DefaultSettings]

    @abstractmethod
    def __init__(
        self,
        *,
        pdf_get_man_operation: colrev.ops.pdf_get_man.PDFGetMan,
        settings: dict,
    ) -> None:
        pass

    @abstractmethod
    def pdf_get_man(self, records: dict) -> dict:
        """Run the pdf-get-man operation."""


class PDFPrepPackageBaseClass(ABC):
    """The base class for PDFPrep packages.

    The following cli command calls the prep_pdf method of a PDFPrep package:

    ``colrev pdf-prep`` -> calls ``package.prep_pdf()``
    """

    ci_supported: bool

    settings_class: Type[colrev.package_manager.package_settings.DefaultSettings]

    @abstractmethod
    def __init__(
        self,
        *,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        settings: dict,
    ) -> None:
        pass

    @abstractmethod
    def prep_pdf(
        self, record: colrev.record.record_pdf.PDFRecord, pad: int
    ) -> colrev.record.record.Record:
        """Run the prep-pdf operation."""


class PDFPrepManPackageBaseClass(ABC):
    """The base class for PDFPrepMan packages.

    The following cli command calls the pdf_prep_man method of a PDFPrepMan package:

    ``colrev pdf-prep-man`` -> calls ``package.pdf_prep_man()``
    """

    ci_supported: bool

    settings_class: Type[colrev.package_manager.package_settings.DefaultSettings]

    @abstractmethod
    def __init__(
        self,
        *,
        pdf_prep_man_operation: colrev.ops.pdf_prep_man.PDFPrepMan,
        settings: dict,
    ) -> None:
        pass

    @abstractmethod
    def pdf_prep_man(self, records: dict) -> dict:
        """Run the pdf-prep-man operation."""


class ScreenPackageBaseClass(ABC):
    """The base class for Screen packages.

    The following cli command calls the run_screen method of a Screen package:

    ``colrev screen`` -> calls ``package.run_screen()``

    """

    ci_supported: bool

    settings_class: Type[colrev.package_manager.package_settings.DefaultSettings]

    @abstractmethod
    def __init__(
        self,
        *,
        screen_operation: colrev.ops.screen.Screen,
        settings: dict,
    ) -> None:
        pass

    @abstractmethod
    def run_screen(self, records: dict, split: list) -> dict:
        """Run the screen operation."""


class DataPackageBaseClass(ABC):
    """The base class for Data packages.

    The following cli command calls the update_data method of a Data package:

    ``colrev data`` -> calls ``package.update_data()``
    """

    ci_supported: bool

    settings_class: Type[colrev.package_manager.package_settings.DefaultSettings]

    @abstractmethod
    def __init__(
        self,
        *,
        data_operation: colrev.ops.data.Data,
        settings: dict,
    ) -> None:
        pass

    @abstractmethod
    def update_data(
        self, records: dict, synthesized_record_status_matrix: dict, silent_mode: bool
    ) -> None:
        """Update the data by running the data operation."""

    @abstractmethod
    def update_record_status_matrix(
        self, synthesized_record_status_matrix: dict, endpoint_identifier: str
    ) -> None:
        """Update the record status matrix."""

    @abstractmethod
    def get_advice(self) -> dict:
        """Get advice on how to operate the data package endpoint."""


BASECLASS_OVERVIEW = {
    EndpointType.review_type: {
        "import_name": ReviewTypePackageBaseClass,
        "custom_class": "CustomReviewType",
        "operation_name": "operation",
    },
    EndpointType.search_source: {
        "import_name": SearchSourcePackageBaseClass,
        "custom_class": "CustomSearchSource",
        "operation_name": "source_operation",
    },
    EndpointType.prep: {
        "import_name": PrepPackageBaseClass,
        "custom_class": "CustomPrep",
        "operation_name": "prep_operation",
    },
    EndpointType.prep_man: {
        "import_name": PrepManPackageBaseClass,
        "custom_class": "CustomPrepMan",
        "operation_name": "prep_man_operation",
    },
    EndpointType.dedupe: {
        "import_name": DedupePackageBaseClass,
        "custom_class": "CustomDedupe",
        "operation_name": "dedupe_operation",
    },
    EndpointType.prescreen: {
        "import_name": PrescreenPackageBaseClass,
        "custom_class": "CustomPrescreen",
        "operation_name": "prescreen_operation",
    },
    EndpointType.pdf_get: {
        "import_name": PDFGetPackageBaseClass,
        "custom_class": "CustomPDFGet",
        "operation_name": "pdf_get_operation",
    },
    EndpointType.pdf_get_man: {
        "import_name": PDFGetManPackageBaseClass,
        "custom_class": "CustomPDFGetMan",
        "operation_name": "pdf_get_man_operation",
    },
    EndpointType.pdf_prep: {
        "import_name": PDFPrepPackageBaseClass,
        "custom_class": "CustomPDFPrep",
        "operation_name": "pdf_prep_operation",
    },
    EndpointType.pdf_prep_man: {
        "import_name": PDFPrepManPackageBaseClass,
        "custom_class": "CustomPDFPrepMan",
        "operation_name": "pdf_prep_man_operation",
    },
    EndpointType.screen: {
        "import_name": ScreenPackageBaseClass,
        "custom_class": "CustomScreen",
        "operation_name": "screen_operation",
    },
    EndpointType.data: {
        "import_name": DataPackageBaseClass,
        "custom_class": "CustomData",
        "operation_name": "data_operation",
    },
}


BASECLASS_MAP = {}
for endpoint_type, endpoint_data in BASECLASS_OVERVIEW.items():
    import_name = endpoint_data["import_name"].__name__  # type: ignore
    BASECLASS_MAP[endpoint_type.name] = import_name
