#!/usr/bin/env python
"""Tests for the colrev package manager"""
import importlib.util
import os
from pathlib import Path

import pytest

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.review_manager
import colrev.settings
from colrev.constants import PackageEndpointType
from colrev.constants import SearchType


@pytest.fixture
def settings() -> colrev.settings.Settings:
    """Fixture returning a settings object"""
    return colrev.settings.load_settings(
        settings_path=Path(colrev.__file__).parents[0] / Path("ops/init/settings.json")
    )


def test_review_type_interfaces(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the review_type_interfaces"""

    package_manager = base_repo_review_manager.get_package_manager()
    load_operation = base_repo_review_manager.get_load_operation()

    review_type_identifiers = package_manager.discover_packages(
        package_type=PackageEndpointType.review_type,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=PackageEndpointType.review_type,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in review_type_identifiers
        ],
        operation=load_operation,
        instantiate_objects=True,
    )


def test_search_source_interfaces(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the search_source_interfaces"""

    package_manager = base_repo_review_manager.get_package_manager()
    load_operation = base_repo_review_manager.get_load_operation(
        notify_state_transition_operation=False
    )

    search_source_identifiers = package_manager.discover_packages(
        package_type=PackageEndpointType.search_source,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=PackageEndpointType.search_source,
        selected_packages=[
            {
                "endpoint": p,
                "filename": Path("test.bib"),
                "search_type": SearchType.DB,
                "search_parameters": {"scope": {"path": "test"}},
                "comment": "",
                "interface_test": True,
            }
            for p in search_source_identifiers
        ],
        operation=load_operation,
        instantiate_objects=True,
    )


def test_prep_package_interfaces(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the prep_package_interfaces"""

    package_manager = base_repo_review_manager.get_package_manager()
    prep_operation = base_repo_review_manager.get_prep_operation(
        notify_state_transition_operation=False
    )

    prep_identifiers = package_manager.discover_packages(
        package_type=PackageEndpointType.prep,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=PackageEndpointType.prep,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in prep_identifiers
        ],
        operation=prep_operation,
        instantiate_objects=True,
    )


def test_prep_man_package_interfaces(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the prep_man_package_interfaces"""

    package_manager = base_repo_review_manager.get_package_manager()
    prep_man_operation = base_repo_review_manager.get_prep_man_operation(
        notify_state_transition_operation=False
    )

    prep_man_identifiers = package_manager.discover_packages(
        package_type=PackageEndpointType.prep_man,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=PackageEndpointType.prep_man,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in prep_man_identifiers
        ],
        operation=prep_man_operation,
        instantiate_objects=True,
    )


def test_dedupe_package_interfaces(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the dedupe_package_interfaces"""

    package_manager = base_repo_review_manager.get_package_manager()
    dedupe_operation = base_repo_review_manager.get_dedupe_operation(
        notify_state_transition_operation=False
    )

    dedupe_identifiers = package_manager.discover_packages(
        package_type=PackageEndpointType.dedupe,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=PackageEndpointType.dedupe,
        selected_packages=[
            {"endpoint": p}
            for p in dedupe_identifiers
            if p not in ["colrev.curation_full_outlet_dedupe"]
        ]
        + [
            {
                "endpoint": "colrev.curation_full_outlet_dedupe",
                "selected_source": "test",
            },
        ],
        operation=dedupe_operation,
        instantiate_objects=True,
    )


def test_prescreen_package_interfaces(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the prescreen_package_interfaces"""

    package_manager = base_repo_review_manager.get_package_manager()
    prescreen_operation = base_repo_review_manager.get_prescreen_operation(
        notify_state_transition_operation=False
    )

    prescreen_identifiers = package_manager.discover_packages(
        package_type=PackageEndpointType.prescreen,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=PackageEndpointType.prescreen,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in prescreen_identifiers
            # Note : asreview dependency fails on gh actions
            if p not in ["colrev_asreview.colrev_asreview"]
        ],
        operation=prescreen_operation,
        instantiate_objects=True,
    )


def test_pdf_get_package_interfaces(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the pdf_get_package_interfaces"""

    package_manager = base_repo_review_manager.get_package_manager()
    pdf_get_operation = base_repo_review_manager.get_pdf_get_operation(
        notify_state_transition_operation=False
    )

    pdf_get_identifiers = package_manager.discover_packages(
        package_type=PackageEndpointType.pdf_get,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=PackageEndpointType.pdf_get,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in pdf_get_identifiers
        ],
        operation=pdf_get_operation,
        instantiate_objects=True,
    )


def test_pdf_get_man_package_interfaces(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the pdf_get_man_package_interfaces"""

    package_manager = base_repo_review_manager.get_package_manager()
    pdf_get_man_operation = base_repo_review_manager.get_pdf_get_man_operation(
        notify_state_transition_operation=False
    )

    pdf_get_man_identifiers = package_manager.discover_packages(
        package_type=PackageEndpointType.pdf_get_man,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=PackageEndpointType.pdf_get_man,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in pdf_get_man_identifiers
        ],
        operation=pdf_get_man_operation,
        instantiate_objects=True,
    )


def test_pdf_prep_package_interfaces(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the pdf_prep_package_interfaces"""
    package_manager = base_repo_review_manager.get_package_manager()
    pdf_prep_operation = base_repo_review_manager.get_pdf_prep_operation(
        notify_state_transition_operation=False
    )

    pdf_prep_identifiers = package_manager.discover_packages(
        package_type=PackageEndpointType.pdf_prep,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=PackageEndpointType.pdf_prep,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in pdf_prep_identifiers
        ],
        operation=pdf_prep_operation,
        instantiate_objects=True,
    )


def test_pdf_prep_man_package_interfaces(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the pdf_prep_man_package_interfaces"""
    package_manager = base_repo_review_manager.get_package_manager()
    pdf_prep_man_operation = base_repo_review_manager.get_pdf_prep_man_operation(
        notify_state_transition_operation=False
    )

    pdf_prep_man_identifiers = package_manager.discover_packages(
        package_type=PackageEndpointType.pdf_prep_man,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=PackageEndpointType.pdf_prep_man,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in pdf_prep_man_identifiers
        ],
        operation=pdf_prep_man_operation,
        instantiate_objects=True,
    )


def test_screen_package_interfaces(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the screen_package_interfaces"""

    package_manager = base_repo_review_manager.get_package_manager()
    screen_operation = base_repo_review_manager.get_screen_operation(
        notify_state_transition_operation=False
    )

    screen_identifiers = package_manager.discover_packages(
        package_type=PackageEndpointType.screen,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=PackageEndpointType.screen,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in screen_identifiers
        ],
        operation=screen_operation,
        instantiate_objects=True,
    )


def test_data_package_interfaces(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the data_package_interfaces"""

    package_manager = base_repo_review_manager.get_package_manager()
    data_operation = base_repo_review_manager.get_data_operation(
        notify_state_transition_operation=False
    )

    data_identifiers = package_manager.discover_packages(
        package_type=PackageEndpointType.data,
        installed_only=True,
    )

    package_manager.load_packages(
        package_type=PackageEndpointType.data,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in data_identifiers
            if p
            not in [
                "colrev.obsidian",
                "colrev.colrev_curation",
            ]
        ]
        + [
            {"endpoint": "colrev.obsidian", "version": "0.1.0", "config": {}},
            {
                "endpoint": "colrev.colrev_curation",
                "curation_url": "",
                "curated_masterdata": True,
                "masterdata_restrictions": {},
                "curated_fields": [],
            },
        ],
        operation=data_operation,
        instantiate_objects=True,
    )


def test_update_package_list(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test update_package_list()"""
    package_manager = base_repo_review_manager.get_package_manager()
    colrev_spec = importlib.util.find_spec("colrev")

    os.chdir(Path(colrev_spec.origin).parents[1])  # type: ignore
    package_manager.update_package_list()


def test_load_settings_not_supported() -> None:
    """Test load_settings() with unsupported settings"""
    with pytest.raises(colrev_exceptions.ParameterError):
        colrev.package_manager.package_settings.DefaultSettings.load_settings(
            data={"xyz": 123}
        )


def test_add_package_to_settings(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:

    dedupe_operation = base_repo_review_manager.get_dedupe_operation()
    package_manager = base_repo_review_manager.get_package_manager()

    with pytest.raises(colrev_exceptions.MissingDependencyError):
        package_manager.add_package_to_settings(
            operation=dedupe_operation,
            package_identifier="colrev.curation_dedupe",
            params="",
        )

    package_manager.add_package_to_settings(
        operation=dedupe_operation,
        package_identifier="colrev.curation_missing_dedupe",
        params="",
    )

    assert (
        "colrev.curation_missing_dedupe"
        == base_repo_review_manager.settings.dedupe.dedupe_package_endpoints[-1][
            "endpoint"
        ]
    )
