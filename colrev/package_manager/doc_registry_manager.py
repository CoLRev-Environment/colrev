#! /usr/bin/env python
"""Discovering and using packages."""
from __future__ import annotations

import importlib.util
import json
import os
import typing
from pathlib import Path

from m2r import parse_from_file

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.package_manager.interfaces
import colrev.process.operation
import colrev.record.record
import colrev.settings
from colrev.constants import PackageEndpointType
from colrev.constants import SearchType

if typing.TYPE_CHECKING:  # pragma: no cover
    import colrev.package_manager.package_manager

# pylint: disable=too-few-public-methods


class DocRegistryManager:
    """DocRegistryManager"""

    def __init__(
        self,
        *,
        package_manager: colrev.package_manager.package_manager.PackageManager,
        packages: typing.List[colrev.package_manager.package_manager.Package],
    ) -> None:
        self.package_manager = package_manager
        self.package_endpoints_json: typing.Dict[str, list] = {
            x.name: [] for x in colrev.package_manager.interfaces.PACKAGE_TYPE_OVERVIEW
        }
        self.docs_for_index: typing.Dict[str, list] = {}
        self.package_status = self._load_package_status_json()
        self.packages = packages

        self._colrev_path = self._get_colrev_path()

    def _get_colrev_path(self) -> Path:
        colrev_spec = importlib.util.find_spec("colrev")
        if colrev_spec is None:  # pragma: no cover
            raise colrev_exceptions.MissingDependencyError(dep="colrev")
        if colrev_spec.origin is None:  # pragma: no cover
            raise colrev_exceptions.MissingDependencyError(dep="colrev")
        return Path(colrev_spec.origin).parents[1]

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

    def _iterate_package_endpoints(
        self, package: colrev.package_manager.package_manager.Package
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

    def _add_package_endpoints(
        self, package: colrev.package_manager.package_manager.Package
    ) -> None:
        # package_endpoints_json: should be updated based on the package classes etc.

        for endpoint_type, endpoint_item in self._iterate_package_endpoints(package):
            print(f"-  {endpoint_item['package_endpoint_identifier']}")
            try:
                endpoint = self.package_manager.load_package_endpoint(
                    package_type=PackageEndpointType[endpoint_type],
                    package_identifier=endpoint_item["package_endpoint_identifier"],
                )
            except colrev_exceptions.MissingDependencyError:
                print(
                    f'Missing dependency: {endpoint_item["package_endpoint_identifier"]}'
                )
                continue
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

        search_source_types_json_file = self._colrev_path / Path(
            "colrev/packages/search_source_types.json"
        )
        json_object = json.dumps(search_source_types, indent=4)
        with open(search_source_types_json_file, "w", encoding="utf-8") as file:
            file.write(json_object)
            file.write("\n")  # to avoid pre-commit/eof-fix changes

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

    def update(self) -> None:
        """Update the package endpoints and the package status."""

        os.chdir(self._colrev_path)
        for package in self.packages:
            self._add_package_endpoints(package)

        self._extract_search_source_types()
        self._update_package_endpoints_json()
        self._update_package_status()
        self._write_docs_for_index()
