#!/usr/bin/env python
import os
from pathlib import Path

import pytest

import colrev.env.utils
import colrev.review_manager
import colrev.settings


@pytest.fixture
def settings() -> colrev.settings.Settings:
    return colrev.settings.load_settings(
        settings_path=Path(colrev.__file__).parents[0]
        / Path("template/init/settings.json")
    )


@pytest.fixture
def review_manager(mocker, tmp_path: Path) -> colrev.review_manager.ReviewManager:  # type: ignore
    os.chdir(tmp_path)
    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    review_manager = colrev.review_manager.ReviewManager(
        path_str=str(tmp_path), force_mode=True
    )
    review_manager.settings = colrev.settings.load_settings(
        settings_path=Path(colrev.__file__).parents[0]
        / Path("template/init/settings.json")
    )
    return review_manager


def test_review_type_interfaces(
    review_manager: colrev.review_manager.ReviewManager,
) -> None:
    package_manager = review_manager.get_package_manager()
    load_operation = review_manager.get_load_operation()

    review_type_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.review_type,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.review_type,
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
    review_manager: colrev.review_manager.ReviewManager,
) -> None:
    package_manager = review_manager.get_package_manager()
    load_operation = review_manager.get_load_operation(
        notify_state_transition_operation=False
    )

    search_source_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.search_source,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.search_source,
        selected_packages=[
            {
                "endpoint": p,
                "filename": Path("test.bib"),
                "search_type": colrev.settings.SearchType.DB,
                "search_parameters": {"scope": {"path": "test"}},
                "load_conversion_package_endpoint": {
                    "endpoint": "colrev_built_in.bibtex"
                },
                "comment": "",
                "interface_test": True,
            }
            for p in search_source_identifiers
        ],
        operation=load_operation,
        instantiate_objects=True,
    )


def test_load_conversion_package_interfaces(
    review_manager: colrev.review_manager.ReviewManager,
) -> None:
    package_manager = review_manager.get_package_manager()
    load_operation = review_manager.get_load_operation(
        notify_state_transition_operation=False
    )

    load_conversion_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.load_conversion,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.load_conversion,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in load_conversion_identifiers
        ],
        operation=load_operation,
        instantiate_objects=True,
    )


def test_prep_package_interfaces(
    review_manager: colrev.review_manager.ReviewManager,
) -> None:
    package_manager = review_manager.get_package_manager()
    prep_operation = review_manager.get_prep_operation(
        notify_state_transition_operation=False
    )

    prep_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.prep,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.prep,
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
    review_manager: colrev.review_manager.ReviewManager,
) -> None:
    package_manager = review_manager.get_package_manager()
    prep_man_operation = review_manager.get_prep_man_operation(
        notify_state_transition_operation=False
    )

    prep_man_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.prep_man,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.prep_man,
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
    review_manager: colrev.review_manager.ReviewManager,
) -> None:
    package_manager = review_manager.get_package_manager()
    dedupe_operation = review_manager.get_dedupe_operation(
        notify_state_transition_operation=False
    )

    dedupe_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.dedupe,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.dedupe,
        selected_packages=[
            {"endpoint": p}
            for p in dedupe_identifiers
            if p not in ["colrev_built_in.curation_full_outlet_dedupe"]
        ]
        + [
            {
                "endpoint": "colrev_built_in.curation_full_outlet_dedupe",
                "selected_source": "test",
            },
        ],
        operation=dedupe_operation,
        instantiate_objects=True,
    )


def test_prescreen_package_interfaces(
    review_manager: colrev.review_manager.ReviewManager,
) -> None:
    package_manager = review_manager.get_package_manager()
    prescreen_operation = review_manager.get_prescreen_operation(
        notify_state_transition_operation=False
    )

    prescreen_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.prescreen,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.prescreen,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in prescreen_identifiers
            # Note : asreview dependency fails on gh actions
            if p not in ["colrev_built_in.asreview_prescreen"]
        ],
        operation=prescreen_operation,
        instantiate_objects=True,
    )


def test_pdf_get_package_interfaces(
    review_manager: colrev.review_manager.ReviewManager,
) -> None:
    package_manager = review_manager.get_package_manager()
    pdf_get_operation = review_manager.get_pdf_get_operation(
        notify_state_transition_operation=False
    )

    pdf_get_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.pdf_get,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.pdf_get,
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
    review_manager: colrev.review_manager.ReviewManager,
) -> None:
    package_manager = review_manager.get_package_manager()
    pdf_get_man_operation = review_manager.get_pdf_get_man_operation(
        notify_state_transition_operation=False
    )

    pdf_get_man_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.pdf_get_man,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.pdf_get_man,
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
    review_manager: colrev.review_manager.ReviewManager,
) -> None:
    package_manager = review_manager.get_package_manager()
    pdf_prep_operation = review_manager.get_pdf_prep_operation(
        notify_state_transition_operation=False
    )

    pdf_prep_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.pdf_prep,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.pdf_prep,
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
    review_manager: colrev.review_manager.ReviewManager,
) -> None:
    package_manager = review_manager.get_package_manager()
    pdf_prep_man_operation = review_manager.get_pdf_prep_man_operation(
        notify_state_transition_operation=False
    )

    pdf_prep_man_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.pdf_prep_man,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.pdf_prep_man,
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
    review_manager: colrev.review_manager.ReviewManager,
) -> None:
    package_manager = review_manager.get_package_manager()
    screen_operation = review_manager.get_screen_operation(
        notify_state_transition_operation=False
    )

    screen_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.screen,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.screen,
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
    review_manager: colrev.review_manager.ReviewManager,
) -> None:
    package_manager = review_manager.get_package_manager()
    data_operation = review_manager.get_data_operation(
        notify_state_transition_operation=False
    )

    data_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.data,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.data,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in data_identifiers
            if p
            not in [
                "colrev_built_in.obsidian",
                "colrev_built_in.colrev_curation",
            ]
        ]
        + [
            {"endpoint": "colrev_built_in.obsidian", "version": "0.1.0", "config": {}},
            {
                "endpoint": "colrev_built_in.colrev_curation",
                "curation_url": "",
                "curated_masterdata": True,
                "masterdata_restrictions": {},
                "curated_fields": [],
            },
        ],
        operation=data_operation,
        instantiate_objects=True,
    )
