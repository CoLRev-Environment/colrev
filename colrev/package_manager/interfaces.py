#! /usr/bin/env python
"""Package interfaces."""
from __future__ import annotations

import abc
import typing
from abc import ABC
from abc import abstractmethod
from pathlib import Path

import colrev
from colrev.constants import EndpointType

if typing.TYPE_CHECKING:  # pragma: no cover
    import colrev.process.operation
    import colrev.record.record
    import colrev.settings

# pylint: disable=too-many-ancestors

# TODO: ci_supported
# # pylint: disable=too-few-public-methods
# class GeneralInterface(zope.interface.Interface):  # pylint: disable=inherit-non-class
#     """The General Interface for all package endpoints

#     Each package endpoint must implement the following attributes (methods)"""

#     ci_supported = zope.interface.Attribute(
#         """Flag indicating whether the package can be run in
#         continuous integration environments (e.g. GitHub Actions)"""
#     )


class ReviewType(abc.ABC):
    """The ReviewType interface for ReviewTypes"""

    @abc.abstractmethod
    def __init__(self, ci_supported: bool):
        """Initialize the review type"""

    @abc.abstractmethod
    def initialize(self, settings: colrev.settings.Settings) -> dict:
        """Initialize the review type"""


# TODO: query-parsing interface?
# class... .parse(query_str) -> Query ; serialize(query) -> str;


class APISearchInterface(abc.ABC):  # pylint: disable=inherit-non-class

    query = ""
    # TODO : depends on "last_updated" in crossref. -> maybe use a "run_since ..." field?
    # Flag indicating whether to rerun the query
    rerun = False

    # pylint: disable=no-self-argument
    def search() -> dict:  # type: ignore
        """Run the API-search"""


class SearchSourceInterface(ABC):
    """The PackageEndpoint abstract base class for SearchSources"""

    settings_class = None
    source_identifier = None
    search_types = None
    heuristic_status = None  # TODO : colrev.SearchSourceHeuristicStatus

    @abstractmethod
    def heuristic(self, filename: Path, data: str):
        """Heuristic to identify which SearchSource a search file belongs to."""

    @abstractmethod
    def add_endpoint(
        self, operation: colrev.process.operation.Operation, params: str
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
    ):
        """Retrieve masterdata from the SearchSource."""

    @abstractmethod
    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load records from the SearchSource."""

    @abstractmethod
    def prepare(self, record: dict, source: colrev.settings.SearchSource) -> None:
        """Run the custom source-prep operation."""


class PrepInterface(ABC):
    """The PackageEndpoint abstract base class for prep operations."""

    settings_class = None
    source_correction_hint = None
    always_apply_changes = None

    @abstractmethod
    def prepare(self, prep_record: dict) -> dict:
        """Run the prep operation."""


class PrepManInterface(ABC):
    """The PackageEndpoint abstract base class for prep-man operations."""

    settings_class = None

    @abstractmethod
    def prepare_manual(self, records: dict) -> dict:
        """Run the prep-man operation."""


class DedupeInterface(ABC):
    """The PackageEndpoint abstract base class for dedupe operations."""

    settings_class = None

    @abstractmethod
    def run_dedupe(self) -> None:
        """Run the dedupe operation."""


class PrescreenInterface(ABC):
    """The PackageEndpoint abstract base class for prescreen operations."""

    settings_class = None

    @abstractmethod
    def run_prescreen(self, records: dict, split: list) -> dict:
        """Run the prescreen operation."""


class PDFGetInterface(ABC):
    """The PackageEndpoint abstract base class for pdf-get operations."""

    settings_class = None

    @abstractmethod
    def get_pdf(self, record: dict) -> dict:
        """Run the pdf-get operation."""


class PDFGetManInterface(ABC):
    """The PackageEndpoint abstract base class for pdf-get-man operations."""

    settings_class = None

    @abstractmethod
    def pdf_get_man(self, records: dict) -> dict:
        """Run the pdf-get-man operation."""


class PDFPrepInterface(ABC):
    """The PackageEndpoint abstract base class for pdf-prep operations."""

    settings_class = None

    @abstractmethod
    def prep_pdf(self, record: colrev.record.record_pdf.PDFRecord, pad: int) -> dict:
        """Run the prep-pdf operation."""


class PDFPrepManInterface(ABC):
    """The PackageEndpoint abstract base class for pdf-prep-man operations."""

    settings_class = None

    @abstractmethod
    def pdf_prep_man(self, records: dict) -> dict:
        """Run the pdf-prep-man operation."""


class ScreenInterface(ABC):
    """The PackageEndpoint abstract base class for screen operations."""

    settings_class = None

    @abstractmethod
    def run_screen(self, records: dict, split: list) -> dict:
        """Run the screen operation."""


class DataInterface(ABC):
    """The PackageEndpoint abstract base class for data operations."""

    settings_class = None

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
        "import_name": ReviewType,
        "custom_class": "CustomReviewType",
        "operation_name": "operation",
    },
    EndpointType.search_source: {
        "import_name": SearchSourceInterface,
        "custom_class": "CustomSearchSource",
        "operation_name": "source_operation",
    },
    EndpointType.prep: {
        "import_name": PrepInterface,
        "custom_class": "CustomPrep",
        "operation_name": "prep_operation",
    },
    EndpointType.prep_man: {
        "import_name": PrepManInterface,
        "custom_class": "CustomPrepMan",
        "operation_name": "prep_man_operation",
    },
    EndpointType.dedupe: {
        "import_name": DedupeInterface,
        "custom_class": "CustomDedupe",
        "operation_name": "dedupe_operation",
    },
    EndpointType.prescreen: {
        "import_name": PrescreenInterface,
        "custom_class": "CustomPrescreen",
        "operation_name": "prescreen_operation",
    },
    EndpointType.pdf_get: {
        "import_name": PDFGetInterface,
        "custom_class": "CustomPDFGet",
        "operation_name": "pdf_get_operation",
    },
    EndpointType.pdf_get_man: {
        "import_name": PDFGetManInterface,
        "custom_class": "CustomPDFGetMan",
        "operation_name": "pdf_get_man_operation",
    },
    EndpointType.pdf_prep: {
        "import_name": PDFPrepInterface,
        "custom_class": "CustomPDFPrep",
        "operation_name": "pdf_prep_operation",
    },
    EndpointType.pdf_prep_man: {
        "import_name": PDFPrepManInterface,
        "custom_class": "CustomPDFPrepMan",
        "operation_name": "pdf_prep_man_operation",
    },
    EndpointType.screen: {
        "import_name": ScreenInterface,
        "custom_class": "CustomScreen",
        "operation_name": "screen_operation",
    },
    EndpointType.data: {
        "import_name": DataInterface,
        "custom_class": "CustomData",
        "operation_name": "data_operation",
    },
}


BASECLASS_MAP = {}
for endpoint_type, endpoint_data in BASECLASS_OVERVIEW.items():
    import_name = endpoint_data["import_name"].__name__  # type: ignore
    BASECLASS_MAP[endpoint_type.name] = import_name
