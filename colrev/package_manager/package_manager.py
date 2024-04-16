#! /usr/bin/env python
"""Discovering and using packages."""
from __future__ import annotations

import importlib.util
import json
import sys
import typing
from copy import deepcopy
from pathlib import Path

from zope.interface.verify import verifyObject

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.package_manager.doc_registry_manager
import colrev.package_manager.interfaces
import colrev.process.operation
import colrev.record.record
import colrev.settings
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import OperationsType
from colrev.constants import PackageEndpointType

# Inspiration for package descriptions:
# https://github.com/rstudio/reticulate/blob/
# 9ebca7ecc028549dadb3d51d2184f9850f6f9f9d/DESCRIPTION

PACKAGE_TYPE_OVERVIEW = {
    PackageEndpointType.review_type: {
        "import_name": colrev.package_manager.interfaces.ReviewTypePackageEndpointInterface,
        "custom_class": "CustomReviewType",
        "operation_name": "operation",
    },
    PackageEndpointType.search_source: {
        "import_name": colrev.package_manager.interfaces.SearchSourcePackageEndpointInterface,
        "custom_class": "CustomSearchSource",
        "operation_name": "source_operation",
    },
    PackageEndpointType.prep: {
        "import_name": colrev.package_manager.interfaces.PrepPackageEndpointInterface,
        "custom_class": "CustomPrep",
        "operation_name": "prep_operation",
    },
    PackageEndpointType.prep_man: {
        "import_name": colrev.package_manager.interfaces.PrepManPackageEndpointInterface,
        "custom_class": "CustomPrepMan",
        "operation_name": "prep_man_operation",
    },
    PackageEndpointType.dedupe: {
        "import_name": colrev.package_manager.interfaces.DedupePackageEndpointInterface,
        "custom_class": "CustomDedupe",
        "operation_name": "dedupe_operation",
    },
    PackageEndpointType.prescreen: {
        "import_name": colrev.package_manager.interfaces.PrescreenPackageEndpointInterface,
        "custom_class": "CustomPrescreen",
        "operation_name": "prescreen_operation",
    },
    PackageEndpointType.pdf_get: {
        "import_name": colrev.package_manager.interfaces.PDFGetPackageEndpointInterface,
        "custom_class": "CustomPDFGet",
        "operation_name": "pdf_get_operation",
    },
    PackageEndpointType.pdf_get_man: {
        "import_name": colrev.package_manager.interfaces.PDFGetManPackageEndpointInterface,
        "custom_class": "CustomPDFGetMan",
        "operation_name": "pdf_get_man_operation",
    },
    PackageEndpointType.pdf_prep: {
        "import_name": colrev.package_manager.interfaces.PDFPrepPackageEndpointInterface,
        "custom_class": "CustomPDFPrep",
        "operation_name": "pdf_prep_operation",
    },
    PackageEndpointType.pdf_prep_man: {
        "import_name": colrev.package_manager.interfaces.PDFPrepManPackageEndpointInterface,
        "custom_class": "CustomPDFPrepMan",
        "operation_name": "pdf_prep_man_operation",
    },
    PackageEndpointType.screen: {
        "import_name": colrev.package_manager.interfaces.ScreenPackageEndpointInterface,
        "custom_class": "CustomScreen",
        "operation_name": "screen_operation",
    },
    PackageEndpointType.data: {
        "import_name": colrev.package_manager.interfaces.DataPackageEndpointInterface,
        "custom_class": "CustomData",
        "operation_name": "data_operation",
    },
}

# pylint: disable=too-few-public-methods


class Package:
    """A Python package for CoLRev"""

    def __init__(self, *, module: str) -> None:
        self.module = module
        print(f"Loading package endpoints from {module}")
        module_spec = importlib.util.find_spec(module)
        endpoints_path = Path(module_spec.origin).parent / Path(  # type:ignore
            ".colrev_endpoints.json"
        )
        if not endpoints_path.is_file():  # pragma: no cover
            print(f"File does not exist: {endpoints_path}")
            raise AttributeError

        with open(endpoints_path, encoding="utf-8") as file:
            self.package_endpoints = json.load(file)


class PackageManager:
    """The PackageManager provides functionality for package lookup and discovery"""

    package: typing.Dict[str, typing.Dict[str, typing.Dict]]

    def __init__(self) -> None:
        self.type_identifier_endpoint_dict = self._load_type_identifier_endpoint_dict()
        # {PackageEndpointType.review_type:
        #   {'colrev.blank': {'endpoint': 'colrev.packages.review_types.blank.BlankReview'},
        #     ...
        # }
        self._flag_installed_packages()

    def _load_type_identifier_endpoint_dict(self) -> dict:
        filedata = colrev.env.utils.get_package_file_content(
            module="colrev.packages", filename=Path("package_endpoints.json")
        )
        if not filedata:  # pragma: no cover
            raise colrev_exceptions.CoLRevException(
                "Package index not available (packages/package_endpoints.json)"
            )

        package_dict = json.loads(filedata.decode("utf-8"))

        packages: typing.Dict[PackageEndpointType, dict] = {}
        for key, package_list in package_dict.items():
            packages[PackageEndpointType[key]] = {}
            for package_item in package_list:
                assert " " not in package_item["package_endpoint_identifier"]
                assert " " not in package_item["endpoint"]
                assert package_item["package_endpoint_identifier"].islower()
                packages[PackageEndpointType[key]][
                    package_item["package_endpoint_identifier"]
                ] = {"endpoint": package_item["endpoint"]}

        return packages

    def _flag_installed_packages(self) -> None:
        for package_type, package_list in self.type_identifier_endpoint_dict.items():
            for package_identifier, package in package_list.items():
                try:
                    self.load_package_endpoint(
                        package_type=package_type, package_identifier=package_identifier
                    )
                    package["installed"] = True
                except (AttributeError, ModuleNotFoundError) as exc:
                    if hasattr(exc, "name"):
                        if package_identifier.split(".")[0] != exc.name:  # type: ignore
                            print(f"Error loading package {package_identifier}: {exc}")

                    package["installed"] = False

    def load_package_endpoint(  # type: ignore
        self, *, package_type: PackageEndpointType, package_identifier: str
    ):
        """Load a package endpoint"""

        package_identifier = package_identifier.lower()
        if package_identifier not in self.type_identifier_endpoint_dict[package_type]:
            raise colrev_exceptions.MissingDependencyError(
                f"{package_identifier} ({package_type}) not available"
            )

        package_str = self.type_identifier_endpoint_dict[package_type][
            package_identifier
        ]["endpoint"]
        package_module = package_str.rsplit(".", 1)[0]
        package_class = package_str.rsplit(".", 1)[-1]
        imported_package = importlib.import_module(package_module)
        package_class = getattr(imported_package, package_class)
        return package_class

    def _build_packages_dict(
        self,
        *,
        selected_packages: list,
        package_type: PackageEndpointType,
        ignore_not_available: bool,
    ) -> typing.Dict:
        # avoid changes in the config
        selected_packages = deepcopy(selected_packages)

        custom_classes = PACKAGE_TYPE_OVERVIEW[package_type]

        packages_dict: typing.Dict = {}
        for selected_package in selected_packages:
            package_identifier = selected_package["endpoint"].lower()
            packages_dict[package_identifier] = {}

            packages_dict[package_identifier]["settings"] = selected_package

            # 1. Load built-in packages
            if not Path(package_identifier + ".py").is_file():
                if (
                    package_identifier
                    not in self.type_identifier_endpoint_dict[package_type]
                ):
                    raise colrev_exceptions.MissingDependencyError(
                        "Built-in dependency "
                        + f"{package_identifier} ({package_type}) not in package_endpoints.json. "
                    )
                if not self.type_identifier_endpoint_dict[package_type][
                    package_identifier
                ][
                    "installed"
                ]:  # pragma: no cover
                    raise colrev_exceptions.MissingDependencyError(
                        f"Dependency {package_identifier} ({package_type}) not found. "
                        f"Please install it\n  pip install {package_identifier.split('.')[0]}"
                    )
                packages_dict[package_identifier]["endpoint"] = (
                    self.load_package_endpoint(
                        package_type=package_type, package_identifier=package_identifier
                    )
                )

            # 2. Load custom packages in the directory
            elif Path(package_identifier + ".py").is_file():
                try:
                    # to import custom packages from the project dir
                    sys.path.append(".")
                    packages_dict[package_identifier]["settings"] = selected_package
                    packages_dict[package_identifier]["endpoint"] = (
                        importlib.import_module(package_identifier, ".")
                    )
                    try:
                        packages_dict[package_identifier]["endpoint"] = getattr(  # type: ignore
                            packages_dict[package_identifier]["endpoint"],
                            custom_classes["custom_class"],
                        )
                    except AttributeError as exc:
                        # Note : these may also be (package name) conflicts
                        if not ignore_not_available:
                            raise colrev_exceptions.MissingDependencyError(
                                f"Dependency {package_identifier} not available"
                            ) from exc
                        print(f"Skipping broken package ({package_identifier})")
                        packages_dict.pop(package_identifier, None)

                except ModuleNotFoundError as exc:  # pragma: no cover
                    if ignore_not_available:
                        print(f"Could not load {selected_package}")
                        del packages_dict[package_identifier]
                        continue
                    raise colrev_exceptions.MissingDependencyError(
                        "Dependency "
                        + f"{package_identifier} ({package_type}) not found. "
                        "Please install it\n  pip install "
                        f"{package_identifier.split('.')[0]}"
                    ) from exc

        return packages_dict

    # pylint: disable=too-many-arguments
    def load_packages(
        self,
        *,
        package_type: PackageEndpointType,
        selected_packages: list,
        operation: colrev.process.operation.Operation,
        ignore_not_available: bool = False,
        instantiate_objects: bool = True,
        only_ci_supported: bool = False,
    ) -> typing.Dict[str, typing.Dict[str, typing.Any]]:
        """Load the packages for a particular package_type"""
        # selected_packages = [{'endpoint': 'colrev.literature_review'}]

        packages_dict = self._build_packages_dict(
            selected_packages=selected_packages,
            package_type=package_type,
            ignore_not_available=ignore_not_available,
        )

        package_details = PACKAGE_TYPE_OVERVIEW[package_type]
        endpoint_class = package_details["import_name"]  # type: ignore
        to_remove = []
        for package_identifier, package_class in packages_dict.items():
            params = {
                package_details["operation_name"]: operation,
                "settings": package_class["settings"],
            }
            if package_type == "search_source":
                del params["check_operation"]

            if "endpoint" not in package_class:
                raise colrev_exceptions.MissingDependencyError(
                    f"{package_identifier} is not available"
                )

            if instantiate_objects:
                try:
                    packages_dict[package_identifier] = package_class["endpoint"](
                        **params
                    )
                    if only_ci_supported:
                        if not packages_dict[package_identifier].ci_supported:
                            to_remove.append(package_identifier)
                            continue
                    verifyObject(endpoint_class, packages_dict[package_identifier])
                except colrev_exceptions.ServiceNotAvailableException as sna_exc:
                    if sna_exc.dep == "docker":
                        print(
                            f"{Colors.ORANGE}Docker not available. Deactivate "
                            f"{package_identifier}{Colors.END}"
                        )
                        to_remove.append(package_identifier)
                    else:
                        raise sna_exc
            else:
                packages_dict[package_identifier] = package_class["endpoint"]

        packages_dict = {k: v for k, v in packages_dict.items() if k not in to_remove}

        # {'colrev.literature_review': LiteratureReview(ci_supported=True)}
        return packages_dict

    def _load_python_packages(self) -> list:
        filedata = colrev.env.utils.get_package_file_content(
            module="colrev.packages", filename=Path("packages.json")
        )
        if not filedata:  # pragma: no cover
            raise colrev_exceptions.CoLRevException(
                "Package index not available (colrev/packages/packages.json)"
            )
        package_list = json.loads(filedata.decode("utf-8"))
        packages = []
        for package in package_list:
            try:
                packages.append(Package(module=package["module"]))
            except json.decoder.JSONDecodeError as exc:  # pragma: no cover
                print(f"Invalid json {exc}")
                continue
            except AttributeError:
                continue

        return packages

    def update_package_list(self) -> None:
        """Generates the packages/package_endpoints.json
        based on the packages in packages/packages.json
        and the endpoints.json files in the top directory of each package."""

        doc_reg_manager = (
            colrev.package_manager.doc_registry_manager.DocRegistryManager(
                package_manager=self, packages=self._load_python_packages()
            )
        )
        doc_reg_manager.update()

    def discover_packages(
        self, *, package_type: PackageEndpointType, installed_only: bool = False
    ) -> typing.Dict:
        """Discover packages (for cli usage)

        returns: Dictionary with package_identifier as key"""

        discovered_packages = self.type_identifier_endpoint_dict[package_type]
        for package_identifier, package in discovered_packages.items():
            if installed_only and not package["installed"]:
                continue
            package_class = self.load_package_endpoint(
                package_type=package_type, package_identifier=package_identifier
            )
            discovered_packages[package_identifier] = package
            discovered_packages[package_identifier][
                "description"
            ] = package_class.__doc__
            discovered_packages[package_identifier]["installed"] = package["installed"]

        return discovered_packages

    # pylint: disable=too-many-locals
    def add_package_to_settings(
        self,
        *,
        operation: colrev.process.operation.Operation,
        package_identifier: str,
        params: str,
        prompt_on_same_source: bool = True,
    ) -> dict:
        """Add a package_endpoint (for cli usage)"""

        settings = operation.review_manager.settings
        package_type_dict = {
            OperationsType.search: {
                "package_type": PackageEndpointType.search_source,
                "endpoint_location": settings.sources,
            },
            OperationsType.prep: {
                "package_type": PackageEndpointType.prep,
                "endpoint_location": settings.prep.prep_rounds[
                    0
                ].prep_package_endpoints,
            },
            OperationsType.prep_man: {
                "package_type": PackageEndpointType.prep_man,
                "endpoint_location": settings.prep.prep_man_package_endpoints,
            },
            OperationsType.dedupe: {
                "package_type": PackageEndpointType.dedupe,
                "endpoint_location": settings.dedupe.dedupe_package_endpoints,
            },
            OperationsType.prescreen: {
                "package_type": PackageEndpointType.prescreen,
                "endpoint_location": settings.prescreen.prescreen_package_endpoints,
            },
            OperationsType.pdf_get: {
                "package_type": PackageEndpointType.pdf_get,
                "endpoint_location": settings.pdf_get.pdf_get_package_endpoints,
            },
            OperationsType.pdf_get_man: {
                "package_type": PackageEndpointType.pdf_get_man,
                "endpoint_location": settings.pdf_get.pdf_get_man_package_endpoints,
            },
            OperationsType.pdf_prep: {
                "package_type": PackageEndpointType.pdf_prep,
                "endpoint_location": settings.pdf_prep.pdf_prep_package_endpoints,
            },
            OperationsType.pdf_prep_man: {
                "package_type": PackageEndpointType.pdf_prep_man,
                "endpoint_location": settings.pdf_prep.pdf_prep_man_package_endpoints,
            },
            OperationsType.screen: {
                "package_type": PackageEndpointType.screen,
                "endpoint_location": settings.screen.screen_package_endpoints,
            },
            OperationsType.data: {
                "package_type": PackageEndpointType.data,
                "endpoint_location": settings.data.data_package_endpoints,
            },
        }

        package_type = package_type_dict[operation.type]["package_type"]
        endpoints = package_type_dict[operation.type]["endpoint_location"]

        registered_endpoints = [
            e["endpoint"] if isinstance(e, dict) else e.endpoint for e in endpoints  # type: ignore
        ]
        if package_identifier in registered_endpoints and prompt_on_same_source:
            operation.review_manager.logger.warning(
                f"Package {package_identifier} already in {endpoints}"
            )
            if "y" != input("Continue [y/n]?"):
                return {}

        operation.review_manager.logger.info(
            f"{Colors.GREEN}Add {operation.type} "
            f"package:{Colors.END} {package_identifier}"
        )

        endpoint_dict = self.load_packages(
            package_type=package_type,  # type: ignore
            selected_packages=[{"endpoint": package_identifier}],
            operation=operation,
            instantiate_objects=False,
        )

        e_class = endpoint_dict[package_identifier]
        if hasattr(endpoint_dict[package_identifier], "add_endpoint"):
            if params:
                if params.startswith("http"):
                    params_dict = {Fields.URL: params}
                else:
                    params_dict = {}
                    for item in params.split(";"):
                        key, value = item.split("=")
                        params_dict[key] = value
            else:
                params_dict = {}
            add_source = e_class.add_endpoint(  # type: ignore
                operation=operation, params=params_dict
            )
            operation.review_manager.settings.sources.append(add_source)
            operation.review_manager.save_settings()
            operation.review_manager.dataset.add_changes(
                add_source.filename, ignore_missing=True
            )
            add_package = add_source.to_dict()

        else:
            add_package = {"endpoint": package_identifier}
            endpoints.append(add_package)  # type: ignore

        operation.review_manager.save_settings()
        operation.review_manager.dataset.create_commit(
            msg=f"Add {operation.type} {package_identifier}",
        )
        return add_package
