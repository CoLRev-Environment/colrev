#! /usr/bin/env python
"""Discovering and using packages."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import typing
from copy import deepcopy
from pathlib import Path

from m2r import parse_from_file
from zope.interface.verify import verifyObject

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.package_manager.interfaces
import colrev.process.operation
import colrev.record.record
import colrev.settings
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import OperationsType
from colrev.constants import PackageEndpointType
from colrev.constants import SearchType

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

    def __init__(self, *, verbose: bool = False) -> None:
        self.verbose = verbose
        self.packages = self._load_package_endpoints_index()
        self._flag_installed_packages()
        colrev_spec = importlib.util.find_spec("colrev")
        if colrev_spec is None:  # pragma: no cover
            raise colrev_exceptions.MissingDependencyError(dep="colrev")
        if colrev_spec.origin is None:  # pragma: no cover
            raise colrev_exceptions.MissingDependencyError(dep="colrev")
        self._colrev_path = Path(colrev_spec.origin).parents[1]

        self._search_source_types_json_file = self._colrev_path / Path(
            "colrev/packages/search_source_types.json"
        )

        self.package_endpoints_json: typing.Dict[str, list] = {
            x.name: [] for x in PACKAGE_TYPE_OVERVIEW
        }
        self.docs_for_index: typing.Dict[str, list] = {}
        self.package_status = self._load_package_status_json()

    def _load_package_endpoints_index(self) -> dict:
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
        for package_type, package_list in self.packages.items():
            for package_identifier, package in package_list.items():
                try:
                    self.load_package_endpoint(
                        package_type=package_type, package_identifier=package_identifier
                    )
                    package["installed"] = True
                except (AttributeError, ModuleNotFoundError) as exc:
                    if hasattr(exc, "name"):
                        if package_identifier.split(".")[0] != exc.name:  # type: ignore
                            # if self.verbose:
                            #     raise exc
                            print(f"Error loading package {package_identifier}: {exc}")

                    package["installed"] = False

    def load_package_endpoint(  # type: ignore
        self, *, package_type: PackageEndpointType, package_identifier: str
    ):
        """Load a package endpoint"""

        package_identifier = package_identifier.lower()
        if package_identifier not in self.packages[package_type]:
            raise colrev_exceptions.MissingDependencyError(
                f"{package_identifier} ({package_type}) not available"
            )

        package_str = self.packages[package_type][package_identifier]["endpoint"]
        package_module = package_str.rsplit(".", 1)[0]
        package_class = package_str.rsplit(".", 1)[-1]
        imported_package = importlib.import_module(package_module)
        package_class = getattr(imported_package, package_class)
        return package_class

    def _drop_broken_packages(
        self,
        *,
        packages_dict: dict,
        package_type: PackageEndpointType,
        ignore_not_available: bool,
    ) -> None:
        package_details = PACKAGE_TYPE_OVERVIEW[package_type]
        broken_packages = []
        for k, val in packages_dict.items():
            if "custom_flag" not in val:
                continue
            try:
                packages_dict[k]["endpoint"] = getattr(  # type: ignore
                    val["endpoint"], package_details["custom_class"]
                )
                del packages_dict[k]["custom_flag"]
            except AttributeError as exc:
                # Note : these may also be (package name) conflicts
                if not ignore_not_available:
                    raise colrev_exceptions.MissingDependencyError(
                        f"Dependency {k} not available"
                    ) from exc
                broken_packages.append(k)
                print(f"Skipping broken package ({k})")
                packages_dict.pop(k, None)

    def _get_packages_dict(
        self,
        *,
        selected_packages: list,
        package_type: PackageEndpointType,
        ignore_not_available: bool,
    ) -> typing.Dict:
        # avoid changes in the config
        selected_packages = deepcopy(selected_packages)

        packages_dict: typing.Dict = {}
        for selected_package in selected_packages:
            package_identifier = selected_package["endpoint"].lower()
            packages_dict[package_identifier] = {}

            packages_dict[package_identifier]["settings"] = selected_package

            # 1. Load built-in packages
            if not Path(package_identifier + ".py").is_file():
                if package_identifier not in self.packages[package_type]:
                    raise colrev_exceptions.MissingDependencyError(
                        "Built-in dependency "
                        + f"{package_identifier} ({package_type}) not in package_endpoints.json. "
                    )
                if not self.packages[package_type][package_identifier][
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

            #     except ModuleNotFoundError as exc:
            #         if ignore_not_available:
            #             print(f"Could not load {selected_package}")
            #             del packages_dict[package_identifier]
            #             continue
            #         raise colrev_exceptions.MissingDependencyError(
            #             "Dependency "
            #             f"{package_identifier} ({package_type}) not installed. "
            #             "Please install it\n  pip install "
            #             f"{package_identifier.split('.')[0]}"
            #         ) from exc

            # 2. Load custom packages in the directory
            elif Path(package_identifier + ".py").is_file():
                try:
                    # to import custom packages from the project dir
                    sys.path.append(".")
                    packages_dict[package_identifier]["settings"] = selected_package
                    packages_dict[package_identifier]["endpoint"] = (
                        importlib.import_module(package_identifier, ".")
                    )
                    packages_dict[package_identifier]["custom_flag"] = True
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

        packages_dict = self._get_packages_dict(
            selected_packages=selected_packages,
            package_type=package_type,
            ignore_not_available=ignore_not_available,
        )
        self._drop_broken_packages(
            packages_dict=packages_dict,
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

        return packages_dict

    def _write_docs_for_index(self) -> None:
        """Writes data from self.docs_for_index to the packages.rst file."""

        packages_index_path = Path(__file__).parent.parent.parent / Path(
            "docs/source/manual/packages.rst"
        )
        packages_index_path_content = packages_index_path.read_text(encoding="utf-8")
        new_doc = []
        # append header
        for line in packages_index_path_content.split("\n"):
            new_doc.append(line)
            if ":caption:" in line:
                new_doc.append("")
                break

        # append new links
        for endpoint_type in [
            "review_type",
            "search_source",
            "prep",
            "prep_man",
            "dedupe",
            "prescreen",
            "pdf_get",
            "pdf_get_man",
            "pdf_prep",
            "pdf_prep_man",
            "screen",
            "data",
        ]:
            new_doc.append("")
            new_doc.append(endpoint_type)
            new_doc.append("-----------------------------")
            new_doc.append("")

            new_doc.append(".. toctree::")
            new_doc.append("   :maxdepth: 1")
            new_doc.append("")

            doc_items = self.docs_for_index[endpoint_type]
            for doc_item in sorted(doc_items, key=lambda d: d["identifier"]):
                if doc_item == "NotImplemented":
                    print(doc_item["path"])
                    continue
                new_doc.append(f"   packages/{doc_item['path']}")

        with open(packages_index_path, "w", encoding="utf-8") as file:
            for line in new_doc:
                file.write(line + "\n")

    def _iterate_package_endpoints(
        self, package: Package
    ) -> typing.Iterator[typing.Tuple[str, dict]]:
        for endpoint_type in self.package_endpoints_json:
            if endpoint_type not in package.package_endpoints["endpoints"]:
                continue
            for endpoint_item in package.package_endpoints["endpoints"][endpoint_type]:
                if (
                    not endpoint_item["package_endpoint_identifier"].split(".")[0]
                    == package.module
                ):
                    continue
                yield endpoint_type, endpoint_item

    def _import_package_docs(self, docs_link: str, identifier: str) -> str:

        packages_index_path = Path(__file__).parent.parent.parent / Path(
            "docs/source/manual/packages"
        )
        local_built_in_path = Path(__file__).parent.parent / Path("packages")

        if (
            "https://github.com/CoLRev-Environment/colrev/blob/main/colrev/packages/"
            in docs_link
        ):
            docs_link = docs_link.replace(
                "https://github.com/CoLRev-Environment/colrev/blob/main/colrev/packages",
                str(local_built_in_path),
            )
            output = parse_from_file(docs_link)
        else:
            # to be retreived through requests for external packages
            # output = convert('# Title\n\nSentence.')
            print(f"Cannot retrieve docs-link for {identifier}")
            return "NotImplemented"

        file_path = Path(f"{identifier}.rst")
        target = packages_index_path / file_path
        if not target.is_file():
            return ""
        with open(target, "w", encoding="utf-8") as file:
            # NOTE: at this point, we may add metadata
            # (such as package status, authors, url etc.)
            file.write(output)

        return str(file_path)

    def _add_package_endpoints(self, package: Package) -> None:
        # package_endpoints_json: should be updated based on the package classes etc.

        for endpoint_type, endpoint_item in self._iterate_package_endpoints(package):
            print(f"-  {endpoint_item['package_endpoint_identifier']}")
            self.packages[PackageEndpointType[endpoint_type]][
                endpoint_item["package_endpoint_identifier"]
            ] = {"endpoint": endpoint_item["endpoint"], "installed": True}
            try:
                endpoint = self.load_package_endpoint(
                    package_type=PackageEndpointType[endpoint_type],
                    package_identifier=endpoint_item["package_endpoint_identifier"],
                )
            except ModuleNotFoundError:
                print(
                    f'Module not found: {endpoint_item["package_endpoint_identifier"]}'
                )
                continue

            # Add development status information (if available on package_status)
            e_list = [
                x
                for x in self.package_status[endpoint_type]
                if x["package_endpoint_identifier"]
                == endpoint_item["package_endpoint_identifier"]
            ]
            if e_list:
                endpoint_item["status"] = e_list[0]["status"]
            else:
                self.package_status[endpoint_type].append(
                    {
                        "package_endpoint_identifier": endpoint_item[
                            "package_endpoint_identifier"
                        ],
                        "status": "RED",
                    }
                )
                endpoint_item["status"] = "RED"

            endpoint_item["status"] = (
                endpoint_item["status"]
                .replace("STABLE", "|STABLE|")
                .replace("MATURING", "|MATURING|")
                .replace("EXPERIMENTAL", "|EXPERIMENTAL|")
            )
            endpoint_item["status_linked"] = endpoint_item["status"]

            # Generate the contents displayed in the docs (see "datatemplate:json")
            # load short_description dynamically...
            short_description = endpoint.__doc__
            if "\n" in endpoint.__doc__:
                short_description = endpoint.__doc__.split("\n")[0]
            endpoint_item["short_description"] = short_description

            endpoint_item["ci_supported"] = endpoint.ci_supported

            code_link = (
                "https://github.com/CoLRev-Environment/colrev/blob/main/"
                + endpoint_item["endpoint"].replace(".", "/")
            )
            # In separate packages, we the main readme.md file should be used
            code_link = code_link[: code_link.rfind("/")]
            code_link += ".md"
            if hasattr(endpoint, "docs_link"):
                docs_link = endpoint.docs_link
            else:
                docs_link = code_link

            package_index_path = self._import_package_docs(
                docs_link, endpoint_item["package_endpoint_identifier"]
            )
            if package_index_path == "":
                continue

            item = {
                "path": package_index_path,
                "short_description": endpoint_item["short_description"],
                "identifier": endpoint_item["package_endpoint_identifier"],
            }
            try:
                self.docs_for_index[endpoint_type].append(item)
            except KeyError:
                self.docs_for_index[endpoint_type] = [item]

            # Note: link format for the sphinx docs
            endpoint_item["short_description"] = (
                endpoint_item["short_description"]
                + " (:doc:`instructions </manual/packages/"
                + f"{endpoint_item['package_endpoint_identifier']}>`)"
            )
            if endpoint_type == "search_source":
                endpoint_item["search_types"] = [x.value for x in endpoint.search_types]

            # Remove and add the endpoint to the package_endpoints_json
            # we do not use a dict because currently, the docs require
            # a list of endpoints (to create tables using datatemplate.json)
            self.package_endpoints_json[endpoint_type] = [
                x
                for x in self.package_endpoints_json[endpoint_type]
                if x["package_endpoint_identifier"]
                != endpoint_item["package_endpoint_identifier"]
            ]
            self.package_endpoints_json[endpoint_type] += [endpoint_item]

    def _extract_search_source_types(self) -> None:
        search_source_types: typing.Dict[str, list] = {}
        for search_source_type in SearchType:
            if search_source_type.value not in search_source_types:
                search_source_types[search_source_type.value] = []
            for search_source in self.package_endpoints_json["search_source"]:
                if search_source_type.value in search_source["search_types"]:
                    search_source_types[search_source_type.value].append(search_source)

        for key in search_source_types:
            search_source_types[key] = sorted(
                search_source_types[key],
                key=lambda d: d["package_endpoint_identifier"],
            )

        json_object = json.dumps(search_source_types, indent=4)
        with open(self._search_source_types_json_file, "w", encoding="utf-8") as file:
            file.write(json_object)
            file.write("\n")  # to avoid pre-commit/eof-fix changes

    def _load_packages(self) -> list:
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
            except AttributeError as exc:
                print(exc)
                continue

        return packages

    def _load_package_status_json(self) -> dict:
        filedata = colrev.env.utils.get_package_file_content(
            module="colrev.packages", filename=Path("package_status.json")
        )
        if not filedata:  # pragma: no cover
            raise colrev_exceptions.CoLRevException(
                "Package index not available (colrev/packages/package_status.json)"
            )
        packages = json.loads(filedata.decode("utf-8"))
        return packages

    def _update_package_endpoints_json(self) -> None:
        for key in self.package_endpoints_json.keys():
            self.package_endpoints_json[key] = sorted(
                self.package_endpoints_json[key],
                key=lambda d: d["package_endpoint_identifier"],
            )
        package_endpoints_json_file = (
            self._colrev_path / "colrev" / Path("packages/package_endpoints.json")
        )
        package_endpoints_json_file.unlink(missing_ok=True)
        json_object = json.dumps(self.package_endpoints_json, indent=4)
        with open(package_endpoints_json_file, "w", encoding="utf-8") as file:
            file.write(json_object)
            file.write("\n")  # to avoid pre-commit/eof-fix changes

    def _update_package_status(self) -> None:
        json_object = json.dumps(self.package_status, indent=4)
        package_status_json_file = (
            self._colrev_path / "colrev" / Path("packages/package_status.json")
        )
        with open(package_status_json_file, "w", encoding="utf-8") as file:
            file.write(json_object)
            file.write("\n")  # to avoid pre-commit/eof-fix changes

    def update_package_list(self) -> None:
        """Generates the packages/package_endpoints.json
        based on the packages in packages/packages.json
        and the endpoints.json files in the top directory of each package."""

        os.chdir(self._colrev_path)

        for package in self._load_packages():
            self._add_package_endpoints(package)

        self._extract_search_source_types()
        self._update_package_endpoints_json()
        self._update_package_status()
        self._write_docs_for_index()

    def discover_packages(
        self, *, package_type: PackageEndpointType, installed_only: bool = False
    ) -> typing.Dict:
        """Discover packages (for cli usage)

        returns: Dictionary with package_identifier as key"""

        discovered_packages = self.packages[package_type]
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
