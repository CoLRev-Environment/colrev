#! /usr/bin/env python
"""Discovering and using packages."""
from __future__ import annotations

import json
import os
import tempfile
import typing
from pathlib import Path

import requests
import toml
from m2r import parse_from_file

import colrev.package_manager.colrev_internal_packages
from colrev.constants import EndpointType
from colrev.constants import Filepaths
from colrev.constants import SearchType


INTERNAL_PACKAGES = (
    colrev.package_manager.colrev_internal_packages.get_internal_packages_dict()
)


# pylint: disable=too-many-instance-attributes
class PackageDoc:
    """PackageDoc"""

    package_id: str
    version: str
    license: str
    authors: list
    documentation: str
    repository: str = ""

    # For monorepo packages
    package_dir: Path

    package_metadata: dict

    description: str
    dev_status: str
    endpoints: list
    search_types: list

    docs_package_readme_path: Path
    docs_rst_path: Path

    def __init__(self, package_id: str) -> None:
        self.package_id = package_id

        methods = [
            self._initialize_from_colrev_monorepo,
            self._initialize_from_pypi,
        ]

        for method in methods:
            if method(package_id):
                break
        else:
            raise NotImplementedError(
                f"Package {package_id} not found on PyPI/in CoLRev monorepo"
            )

        main_section = self.package_metadata["tool"]["poetry"]
        self.license = main_section["license"]
        self.version = main_section["version"]
        self.authors = main_section["authors"]
        self.documentation = main_section.get("documentation", None)
        self.repository = main_section.get("repository", None)
        self.endpoints = list(
            main_section.get("plugins", {}).get("colrev", {"na": "na"}).keys()
        )

        colrev_section = self.package_metadata.get("tool", {}).get("colrev", {})
        self.description = colrev_section.get("colrev_doc_description", "NA")
        self.search_types = colrev_section.get("search_types", [])

        colrev_doc_link = colrev_section.get("colrev_doc_link")
        self._set_docs_package_readme_path(colrev_doc_link)

        self.docs_rst_path = Path(f"{self.package_id}.rst")

    def _initialize_from_colrev_monorepo(self, package_id: str) -> bool:

        if package_id in INTERNAL_PACKAGES:
            self.package_dir = Path(INTERNAL_PACKAGES[package_id])
            with open(
                self.package_dir / Path("pyproject.toml"), encoding="utf-8"
            ) as file:
                self.package_metadata = toml.load(file)

            assert str(self.package_dir).endswith(
                package_id.replace("colrev.", "")
            ), package_id

            return True
        return False

    def _initialize_from_pypi(self, package_id: str) -> bool:

        response = requests.get(f"https://pypi.org/pypi/{package_id}/json", timeout=30)
        if response.status_code != 200:
            return False

        repo_url = response.json()["info"].get("project_urls", {}).get("Repository")
        gh_response = requests.get(f"{repo_url}/blob/main/pyproject.toml", timeout=30)
        if response.status_code != 200:
            return False

        self.package_metadata = toml.loads(gh_response.text)

        return True

    def has_endpoint(self, endpoint_type: EndpointType) -> bool:
        """Check if the package has a specific endpoint type"""

        return endpoint_type.value in self.endpoints

    def _get_authors_for_docs(self) -> str:
        """Get the authors for the documentation  (without emails in <>)"""

        authors = []
        for author in self.authors:
            authors.append(author.split("<")[0].strip())

        return ", ".join(authors)

    def _get_docs_short_description(self) -> str:
        return (
            self.description
            + " (:doc:`instructions </manual/packages/"
            + f"{self.package_id}>`)"
        )

    def _set_docs_package_readme_path(self, colrev_doc_link: str) -> None:

        if self.package_dir:
            self.docs_package_readme_path = self.package_dir / colrev_doc_link
        else:
            response = requests.get(self.repository + "/" + colrev_doc_link, timeout=30)
            if response.status_code != 200:
                raise ValueError("Failed to download package readme from repository")
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(response.content)
                self.docs_package_readme_path = Path(temp_file.name)

        readme_content = self.docs_package_readme_path.read_text(encoding="utf-8")
        if not readme_content.startswith("## Summary"):
            raise ValueError(
                f"Package {self.package_id} readme does not start with '## Summary'"
            )

    # pylint: disable=line-too-long
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-statements
    # flake8: noqa: E501
    def _get_header_info(self) -> str:

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
        header_info += "   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html\n"
        header_info += ".. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen\n"
        header_info += "   :height: 14pt\n"
        header_info += "   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html\n"
        header_info += ".. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen\n"
        header_info += "   :height: 14pt\n"
        header_info += "   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html\n"
        header_info += ".. |VERSION| image:: /_static/svg/iconmonstr-product-10.svg\n"
        header_info += "   :width: 15\n"
        header_info += "   :alt: Version\n"
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

        header_info += f"{self.package_id}\n"
        header_info += "=" * len(self.package_id) + "\n\n"
        header_info += f"|VERSION| Version: {self.version}\n\n"
        header_info += f"|MAINTAINER| Maintainer: {self._get_authors_for_docs()}\n\n"
        header_info += f"|LICENSE| License: {self.license}  \n\n"
        if self.repository != "":
            repo_name = self.repository.replace("https://github.com/", "")
            if "CoLRev-Environment/colrev" in repo_name:
                repo_name = "CoLRev-Environment/colrev"
            header_info += (
                f"|GIT_REPO| Repository: `{repo_name} <{self.repository}>`_ \n\n"
            )

        if self.documentation:
            header_info += (
                f"|DOCUMENTATION| `External documentation <{self.documentation}>`_\n\n"
            )

        header_info += ".. list-table::\n"
        header_info += "   :header-rows: 1\n"
        header_info += "   :widths: 20 30 80\n\n"
        header_info += "   * - Endpoint\n"
        header_info += "     - Status\n"
        header_info += "     - Add\n"

        for endpoint_type in EndpointType:
            if self.has_endpoint(endpoint_type):
                header_info += f"   * - {endpoint_type.value}\n"
                header_info += f"     - |{self.dev_status.upper()}|\n"
                if endpoint_type == EndpointType.review_type:
                    header_info += f"     - .. code-block:: \n\n\n         colrev init --type {self.package_id}\n\n"
                elif endpoint_type == EndpointType.search_source:
                    header_info += f"     - .. code-block:: \n\n\n         colrev search --add {self.package_id}\n\n"
                elif endpoint_type == EndpointType.prep:
                    header_info += f"     - .. code-block:: \n\n\n         colrev prep --add {self.package_id}\n\n"
                elif endpoint_type == EndpointType.prep_man:
                    header_info += f"     - .. code-block:: \n\n\n         colrev prep-man --add {self.package_id}\n\n"
                elif endpoint_type == EndpointType.dedupe:
                    header_info += f"     - .. code-block:: \n\n\n         colrev dedupe --add {self.package_id}\n\n"
                elif endpoint_type == EndpointType.prescreen:
                    header_info += f"     - .. code-block:: \n\n\n         colrev prescreen --add {self.package_id}\n\n"
                elif endpoint_type == EndpointType.pdf_get:
                    header_info += f"     - .. code-block:: \n\n\n         colrev pdf-get --add {self.package_id}\n\n"
                elif endpoint_type == EndpointType.pdf_get_man:
                    header_info += f"     - .. code-block:: \n\n\n         colrev pdf-get-man --add {self.package_id}\n\n"
                elif endpoint_type == EndpointType.pdf_prep:
                    header_info += f"     - .. code-block:: \n\n\n         colrev pdf-prep --add {self.package_id}\n\n"
                elif endpoint_type == EndpointType.pdf_prep_man:
                    header_info += f"     - .. code-block:: \n\n\n         colrev pdf-prep-man --add {self.package_id}\n\n"
                elif endpoint_type == EndpointType.screen:
                    header_info += f"     - .. code-block:: \n\n\n         colrev screen --add {self.package_id}\n\n"
                elif endpoint_type == EndpointType.data:
                    header_info += f"     - .. code-block:: \n\n\n         colrev data --add {self.package_id}\n\n"

        return header_info

    def import_package_docs(self) -> None:
        """Import the package documentation"""

        with open(
            Filepaths.COLREV_PATH
            / Path(f"docs/source/manual/packages/{self.docs_rst_path}"),
            "w",
            encoding="utf-8",
        ) as file:
            file.write(self._get_header_info())
            output = parse_from_file(self.docs_package_readme_path)
            output = output.replace(
                ".. list-table::", ".. list-table::\n   :align: left"
            )
            file.write(output)

    def get_endpoint_item(self, endpoint_type: EndpointType) -> dict:
        """Get the endpoint item for the package

        Format:
        {
            "package_endpoint_identifier": package_id,
            "status": status,
            "short_description": docs_short_description,
            "search_types": search_types,
        }
        """

        status = (
            self.dev_status.replace("stable", "|STABLE|")
            .replace("maturing", "|MATURING|")
            .replace("experimental", "|EXPERIMENTAL|")
        )
        endpoint_item = {
            "package_endpoint_identifier": self.package_id,
            "status": status,
            "short_description": self._get_docs_short_description(),
        }

        if endpoint_type == EndpointType.search_source:
            endpoint_item["search_types"] = self.search_types  # type: ignore

        return endpoint_item

    def get_docs_item(self) -> dict:
        """Get the documentation item for the package

        Format:
        {
            "identifier": package_id,
            "short_description": short_description,
            "path": docs_rst_path,
        }

        """
        item = {
            "identifier": self.package_id,
            "short_description": self._get_docs_short_description(),
            "path": self.docs_rst_path,
        }
        return item

    def __repr__(self) -> str:
        package_str = f"Package name: {self.package_id}\n"
        package_str += f"Package license: {self.license}\n"
        package_str += f"Package endpoints: {self.endpoints}\n"
        package_str += f"Package search types: {self.search_types}\n"
        package_str += f"Package authors: {self.authors}\n"
        package_str += f"Package documentation: {self.docs_package_readme_path}\n"
        package_str += f"Package description: {self.description}\n"

        return package_str


# pylint: disable=too-few-public-methods
class DocRegistryManager:
    """DocRegistryManager"""

    # Overview page of packages: rst
    docs_packages_index_path = Filepaths.COLREV_PATH / Path(
        "docs/source/manual/packages.rst"
    )
    # Overview page of packages: json
    docs_packages_overview_json_file = Filepaths.COLREV_PATH / Path(
        "docs/source/manual/packages_overview.json"
    )

    # Overviews of endpoints
    docs_package_endpoints_json_file = Filepaths.COLREV_PATH / Path(
        "docs/source/manual/package_endpoints.json"
    )

    # Overviews of search source types
    docs_search_source_types_json_file = Filepaths.COLREV_PATH / Path(
        "docs/source/manual/search_source_types.json"
    )

    package_endpoints_json: typing.Dict[str, list] = {x.value: [] for x in EndpointType}
    docs_for_index: typing.Dict[str, list] = {x.value: [] for x in EndpointType}

    def __init__(self) -> None:
        self._load_packages()

    def _load_packages(self) -> None:

        with open(Filepaths.PACKAGES_JSON, encoding="utf-8") as file:
            packages_data = json.load(file)

        self.packages = []
        for package_id, package_data in packages_data.items():
            try:
                package_doc = PackageDoc(package_id)
                package_doc.dev_status = package_data["dev_status"]
                self.packages.append(package_doc)
            except (
                toml.decoder.TomlDecodeError,
                NotImplementedError,
                ValueError,
            ) as exc:
                print(exc)
                print(f"Error loading package {package_id}")

        # Add package endpoints
        os.chdir(Filepaths.COLREV_PATH)
        for package in self.packages:
            for endpoint_type in EndpointType:
                if not package.has_endpoint(endpoint_type):
                    continue

                print(f"-  {package.package_id} / {endpoint_type.value}")

                package.import_package_docs()

                self.package_endpoints_json[endpoint_type.value].append(
                    package.get_endpoint_item(endpoint_type)
                )
                self.docs_for_index[endpoint_type.value].append(package.get_docs_item())

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
        with open(
            self.docs_search_source_types_json_file, "w", encoding="utf-8"
        ) as file:
            file.write(json_object)
            file.write("\n")  # to avoid pre-commit/eof-fix changes

    def _update_package_endpoints_json(self) -> None:
        for key in self.package_endpoints_json.keys():
            self.package_endpoints_json[key] = sorted(
                self.package_endpoints_json[key],
                key=lambda d: d["package_endpoint_identifier"],
            )

        self.docs_package_endpoints_json_file.unlink(missing_ok=True)
        json_object = json.dumps(self.package_endpoints_json, indent=4)
        with open(self.docs_package_endpoints_json_file, "w", encoding="utf-8") as file:
            file.write(json_object)
            file.write("\n")  # to avoid pre-commit/eof-fix changes

        with open(Filepaths.PACKAGES_ENDPOINTS_JSON, "w", encoding="utf-8") as file:
            file.write(json_object)
            file.write("\n")  # to avoid pre-commit/eof-fix changes

    def _update_packages_overview(self) -> None:
        packages_overview = []
        # for key, packages in self.package_endpoints_json.items():

        for endpoint_type in [x.value for x in EndpointType]:
            packages = self.package_endpoints_json[endpoint_type]
            for package in packages:
                package["endpoint_type"] = endpoint_type
                packages_overview.append(package)

        self.docs_packages_overview_json_file.unlink(missing_ok=True)
        json_object = json.dumps(packages_overview, indent=4)
        with open(self.docs_packages_overview_json_file, "w", encoding="utf-8") as file:
            file.write(json_object)
            file.write("\n")  # to avoid pre-commit/eof-fix changes

    def _write_docs_for_index(self) -> None:
        """Writes data from self.docs_for_index to the packages.rst file."""

        docs_packages_index_path_content = self.docs_packages_index_path.read_text(
            encoding="utf-8"
        )
        new_doc = []
        # append header
        for line in docs_packages_index_path_content.split("\n"):
            new_doc.append(line)
            if ":caption:" in line:
                new_doc.append("")
                break

        # append new links
        for endpoint_type in [x.value for x in EndpointType]:
            new_doc.append("")
            new_doc.append("")

            doc_items = self.docs_for_index[endpoint_type]
            for doc_item in sorted(doc_items, key=lambda d: d["identifier"]):
                if doc_item == "NotImplemented":
                    print(doc_item["path"])
                    continue
                new_doc.append(f"   packages/{doc_item['path']}")

        with open(self.docs_packages_index_path, "w", encoding="utf-8") as file:
            for line in new_doc:
                file.write(line + "\n")

    def update(self) -> None:
        """Update the package endpoints and the package status."""

        self._update_package_endpoints_json()
        self._extract_search_source_types()
        self._update_packages_overview()
        self._write_docs_for_index()
