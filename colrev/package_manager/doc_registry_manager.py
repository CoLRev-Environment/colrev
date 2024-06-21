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
import colrev.package_manager.package
import colrev.process.operation
import colrev.record.record
import colrev.settings
from colrev.constants import EndpointType
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
        packages: typing.List[colrev.package_manager.package.Package],
    ) -> None:
        self.package_manager = package_manager
        self.packages = packages

        self.package_endpoints_json: typing.Dict[str, list] = {
            x.name: [] for x in colrev.package_manager.interfaces.ENDPOINT_OVERVIEW
        }
        self.docs_for_index: typing.Dict[str, list] = {}

        self._colrev_path = self._get_colrev_path()

        os.chdir(self._colrev_path)
        for package in self.packages:
            self._add_package_endpoints(package)

    def _get_colrev_path(self) -> Path:
        colrev_spec = importlib.util.find_spec("colrev")
        if colrev_spec is None:  # pragma: no cover
            raise colrev_exceptions.MissingDependencyError(dep="colrev")
        if colrev_spec.origin is None:  # pragma: no cover
            raise colrev_exceptions.MissingDependencyError(dep="colrev")
        return Path(colrev_spec.origin).parents[1]

    def _add_package_endpoints(
        self, package: colrev.package_manager.package.Package
    ) -> None:
        # package_endpoints_json: should be updated based on the package classes etc.

        for endpoint_type in EndpointType:
            if not package.has_endpoint(endpoint_type):
                continue

            print(f"-  {package.name} / {endpoint_type.value}")

            endpoint_class = package.get_endpoint_class(endpoint_type)
            status = (
                package.status.replace("stable", "|STABLE|")
                .replace("maturing", "|MATURING|")
                .replace("experimental", "|EXPERIMENTAL|")
            )
            short_description = endpoint_class.__doc__
            if "\n" in endpoint_class.__doc__:
                short_description = endpoint_class.__doc__.split("\n")[0]
            short_description = (
                short_description
                + " (:doc:`instructions </manual/packages/"
                + f"{package.name}>`)"
            )

            endpoint_item = {
                "package_endpoint_identifier": package.name,
                "status": status,
                "short_description": short_description,
                "ci_supported": endpoint_class.ci_supported,
            }

            if endpoint_type == EndpointType.search_source:
                endpoint_item["search_types"] = [
                    x.value for x in endpoint_class.search_types
                ]

            self.package_endpoints_json[endpoint_type.value] += [endpoint_item]

            package_index_path = self._import_package_docs(package)
            item = {
                "path": package_index_path,
                "short_description": endpoint_item["short_description"],
                "identifier": package.name,
            }
            try:
                self.docs_for_index[endpoint_type.value].append(item)
            except KeyError:
                self.docs_for_index[endpoint_type.value] = [item]

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

    # pylint: disable=line-too-long
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-statements
    # flake8: noqa: E501
    def _get_header_info(self, package: colrev.package_manager.package.Package) -> str:

        # To format the table (adjust row height), the following is suggested:
        # from bs4 import BeautifulSoup

        # # Parse the generated HTML
        # with open('output.html', 'r') as f:
        #     soup = BeautifulSoup(f, 'html.parser')

        # # Find the table and add the ID
        # table = soup.find('table')
        # table['id'] = 'endpoint_overview_container'

        # # Write the modified HTML back to the file
        # with open('output.html', 'w') as f:
        #     f.write(str(soup))
        header_info = ""
        header_info += ".. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue\n"
        header_info += "   :height: 14pt\n"
        header_info += "   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html\n"
        header_info += ".. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen\n"
        header_info += "   :height: 14pt\n"
        header_info += "   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html\n"
        header_info += ".. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen\n"
        header_info += "   :height: 14pt\n"
        header_info += "   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html\n"
        header_info += ".. |GIT_REPO| image:: /_static/svg/iconmonstr-code-fork-1.svg\n"
        header_info += "   :width: 15\n"
        header_info += "   :alt: Git repository\n"
        header_info += ".. |LICENSE| image:: /_static/svg/iconmonstr-copyright-2.svg\n"
        header_info += "   :width: 15\n"
        header_info += "   :alt: Licencse\n"
        header_info += ".. |MAINTAINER| image:: /_static/svg/iconmonstr-user-29.svg\n"
        header_info += "   :width: 20\n"
        header_info += "   :alt: Maintainer\n"
        header_info += (
            ".. |DOCUMENTATION| image:: /_static/svg/iconmonstr-book-17.svg\n"
        )
        header_info += "   :width: 15\n"
        header_info += "   :alt: Documentation\n"

        header_info += f"{package.name}\n"
        header_info += "=" * len(package.name) + "\n\n"
        header_info += "Package\n"
        header_info += "-" * 20 + "\n\n"
        header_info += f"|MAINTAINER| Maintainer: {', '.join(x['name'] for x in package.authors)}\n\n"
        header_info += f"|LICENSE| License: {package.license}\n\n"
        if package.repository != "":
            repo_name = package.repository.replace("https://github.com/", "")
            if "CoLRev-Environment/colrev" in repo_name:
                repo_name = "CoLRev-Environment/colrev"
            header_info += (
                f"|GIT_REPO| Repository: `{repo_name} <{package.repository}>`_ \n\n"
            )

        if package.documentation != "":
            header_info += (
                f"|DOCUMENTATION| `Documentation <{package.documentation}>`_ \n\n"
            )

        header_info += ".. list-table::\n"
        header_info += "   :header-rows: 1\n"
        header_info += "   :widths: 20 30 80\n\n"
        header_info += "   * - Endpoint\n"
        header_info += "     - Status\n"
        header_info += "     - Add\n"

        for endpoint_type in EndpointType:
            if package.has_endpoint(endpoint_type):
                header_info += f"   * - {endpoint_type.value}\n"
                header_info += f"     - |{package.status.upper()}|\n"
                if endpoint_type == EndpointType.review_type:
                    header_info += f"     - .. code-block:: \n\n\n         colrev init --type {package.name}\n\n"
                elif endpoint_type == EndpointType.search_source:
                    header_info += f"     - .. code-block:: \n\n\n         colrev search --add {package.name}\n\n"
                elif endpoint_type == EndpointType.prep:
                    header_info += f"     - .. code-block:: \n\n\n         colrev prep --add {package.name}\n\n"
                elif endpoint_type == EndpointType.prep_man:
                    header_info += f"     - .. code-block:: \n\n\n         colrev prep-man --add {package.name}\n\n"
                elif endpoint_type == EndpointType.dedupe:
                    header_info += f"     - .. code-block:: \n\n\n         colrev dedupe --add {package.name}\n\n"
                elif endpoint_type == EndpointType.prescreen:
                    header_info += f"     - .. code-block:: \n\n\n         colrev prescreen --add {package.name}\n\n"
                elif endpoint_type == EndpointType.pdf_get:
                    header_info += f"     - .. code-block:: \n\n\n         colrev pdf-get --add {package.name}\n\n"
                elif endpoint_type == EndpointType.pdf_get_man:
                    header_info += f"     - .. code-block:: \n\n\n         colrev pdf-get-man --add {package.name}\n\n"
                elif endpoint_type == EndpointType.pdf_prep:
                    header_info += f"     - .. code-block:: \n\n\n         colrev pdf-prep --add {package.name}\n\n"
                elif endpoint_type == EndpointType.pdf_prep_man:
                    header_info += f"     - .. code-block:: \n\n\n         colrev pdf-prep-man --add {package.name}\n\n"
                elif endpoint_type == EndpointType.screen:
                    header_info += f"     - .. code-block:: \n\n\n         colrev screen --add {package.name}\n\n"
                elif endpoint_type == EndpointType.data:
                    header_info += f"     - .. code-block:: \n\n\n         colrev data --add {package.name}\n\n"

        return header_info

    def _import_package_docs(
        self, package: colrev.package_manager.package.Package
    ) -> str:

        docs_link = package.package_dir / package.colrev_doc_link

        packages_index_path = Path(__file__).parent.parent.parent / Path(
            "docs/source/manual/packages"
        )

        output = parse_from_file(docs_link)
        output = output.replace(".. list-table::", ".. list-table::\n   :align: left")

        header_info = self._get_header_info(package)

        file_path = Path(f"{package.name}.rst")
        target = packages_index_path / file_path
        with open(target, "w", encoding="utf-8") as file:
            # NOTE: at this point, we may add metadata
            # (such as package status, authors, url etc.)
            file.write(header_info)
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
            "docs/source/search_source_types.json"
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
        package_endpoints_json_file = self._colrev_path / Path(
            "docs/source/package_endpoints.json"
        )
        package_endpoints_json_file.unlink(missing_ok=True)
        json_object = json.dumps(self.package_endpoints_json, indent=4)
        with open(package_endpoints_json_file, "w", encoding="utf-8") as file:
            file.write(json_object)
            file.write("\n")  # to avoid pre-commit/eof-fix changes

    def _update_packages_overview(self) -> None:
        packages_overview = []
        # for key, packages in self.package_endpoints_json.items():

        for endpoint_type in [
            "review_type",
            "search_source",
            "prep",
            "dedupe",
            "prescreen",
            "pdf_get",
            "pdf_prep",
            "screen",
            "data",
        ]:
            packages = self.package_endpoints_json[endpoint_type]
            for package in packages:
                package["endpoint_type"] = endpoint_type
                packages_overview.append(package)

        packages_overview_json_file = self._colrev_path / Path(
            "docs/source/packages_overview.json"
        )
        packages_overview_json_file.unlink(missing_ok=True)
        json_object = json.dumps(packages_overview, indent=4)
        with open(packages_overview_json_file, "w", encoding="utf-8") as file:
            file.write(json_object)
            file.write("\n")  # to avoid pre-commit/eof-fix changes

    def update(self) -> None:
        """Update the package endpoints and the package status."""

        self._extract_search_source_types()
        self._update_package_endpoints_json()
        self._update_packages_overview()
        self._write_docs_for_index()
