#! /usr/bin/env python
"""Discovering and using packages."""
from __future__ import annotations

import colrev.env.utils
import colrev.package_manager.doc_registry_manager
import colrev.package_manager.interfaces
import colrev.process.operation
import colrev.record.record
import colrev.settings
from colrev.constants import Colors
from colrev.constants import EndpointType
from colrev.constants import OperationsType


def _get_endpoint_with_type(operation: colrev.process.operation.Operation) -> tuple:
    settings = operation.review_manager.settings
    package_type_dict = {
        OperationsType.search: {
            "package_type": EndpointType.search_source,
            "endpoint_location": settings.sources,
        },
        OperationsType.prep: {
            "package_type": EndpointType.prep,
            "endpoint_location": settings.prep.prep_rounds[0].prep_package_endpoints,
        },
        OperationsType.prep_man: {
            "package_type": EndpointType.prep_man,
            "endpoint_location": settings.prep.prep_man_package_endpoints,
        },
        OperationsType.dedupe: {
            "package_type": EndpointType.dedupe,
            "endpoint_location": settings.dedupe.dedupe_package_endpoints,
        },
        OperationsType.prescreen: {
            "package_type": EndpointType.prescreen,
            "endpoint_location": settings.prescreen.prescreen_package_endpoints,
        },
        OperationsType.pdf_get: {
            "package_type": EndpointType.pdf_get,
            "endpoint_location": settings.pdf_get.pdf_get_package_endpoints,
        },
        OperationsType.pdf_get_man: {
            "package_type": EndpointType.pdf_get_man,
            "endpoint_location": settings.pdf_get.pdf_get_man_package_endpoints,
        },
        OperationsType.pdf_prep: {
            "package_type": EndpointType.pdf_prep,
            "endpoint_location": settings.pdf_prep.pdf_prep_package_endpoints,
        },
        OperationsType.pdf_prep_man: {
            "package_type": EndpointType.pdf_prep_man,
            "endpoint_location": settings.pdf_prep.pdf_prep_man_package_endpoints,
        },
        OperationsType.screen: {
            "package_type": EndpointType.screen,
            "endpoint_location": settings.screen.screen_package_endpoints,
        },
        OperationsType.data: {
            "package_type": EndpointType.data,
            "endpoint_location": settings.data.data_package_endpoints,
        },
    }
    endpoints_in_settings = package_type_dict[operation.type]["endpoint_location"]
    package_type = package_type_dict[operation.type]["package_type"]
    return endpoints_in_settings, package_type


def add_package_to_settings(
    package_manager: colrev.package_manager.package_manager.PackageManager,
    *,
    operation: colrev.process.operation.Operation,
    package_identifier: str,
    params: str,
) -> None:
    """Add a package_endpoint (for cli usage)"""

    operation.review_manager.logger.info(
        f"{Colors.GREEN}Add {operation.type} "
        f"package:{Colors.END} {package_identifier}"
    )

    endpoints_in_settings, package_type = _get_endpoint_with_type(operation)
    e_class = package_manager.get_package_endpoint_class(
        package_type=package_type,
        package_identifier=package_identifier,
    )

    if hasattr(e_class, "add_endpoint"):
        e_class.add_endpoint(operation=operation, params=params)  # type: ignore

    else:
        add_package = {"endpoint": package_identifier}
        endpoints_in_settings.append(add_package)  # type: ignore
        operation.review_manager.save_settings()
        operation.review_manager.dataset.create_commit(
            msg=f"Add {operation.type} {package_identifier}",
        )
