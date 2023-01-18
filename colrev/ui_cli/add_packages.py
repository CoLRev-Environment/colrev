#!/usr/bin/env python3
"""Scripts to add packages using the cli."""
from __future__ import annotations

import json
from pathlib import Path

import requests

import colrev.env.package_manager
import colrev.ops.built_in.data.bibliography_export
import colrev.ui_cli.cli_colors as colors


def add_search_source(
    *,
    search_operation: colrev.ops.search.search,
    query: str,
) -> None:
    """Add a search source package_endpoint"""

    # pylint: disable=too-many-branches

    if "pdfs" == query:

        filename = search_operation.get_unique_filename(file_path_string="pdfs")
        # pylint: disable=no-value-for-parameter
        add_source = colrev.settings.SearchSource(
            endpoint="colrev_built_in.pdfs_dir",
            filename=filename,
            search_type=colrev.settings.SearchType.PDFS,
            search_parameters={"scope": {"path": "data/pdfs"}},
            load_conversion_package_endpoint={"endpoint": "colrev_built_in.bibtex"},
            comment="",
        )
    elif "backwardsearch" == query.replace("_", "").replace("-", ""):
        filename = search_operation.get_unique_filename(
            file_path_string="pdf_backward_search"
        )
        # pylint: disable=no-value-for-parameter
        add_source = colrev.settings.SearchSource(
            endpoint="colrev_built_in.pdf_backward_search",
            filename=filename,
            search_type=colrev.settings.SearchType.BACKWARD_SEARCH,
            search_parameters={
                "scope": {"colrev_status": "rev_included|rev_synthesized"},
            },
            load_conversion_package_endpoint={"endpoint": "colrev_built_in.bibtex"},
            comment="",
        )
    elif (
        "https://dblp.org/search?q=" in query
        or "https://dblp.org/search/publ?q=" in query
    ):
        query = query.replace(
            "https://dblp.org/search?q=", "https://dblp.org/search/publ/api?q="
        ).replace(
            "https://dblp.org/search/publ?q=", "https://dblp.org/search/publ/api?q="
        )

        filename = search_operation.get_unique_filename(
            file_path_string=f"dblp_{query.replace('https://dblp.org/search/publ/api?q=', '')}"
        )
        add_source = colrev.settings.SearchSource(
            endpoint="colrev_built_in.dblp",
            filename=filename,
            search_type=colrev.settings.SearchType.DB,
            search_parameters={"query": query},
            load_conversion_package_endpoint={"endpoint": "colrev_built_in.bibtex"},
            comment="",
        )
    elif "https://search.crossref.org/?q=" in query:
        query = (
            query.replace("https://search.crossref.org/?q=", "")
            .replace("&from_ui=yes", "")
            .lstrip("+")
        )

        filename = search_operation.get_unique_filename(
            file_path_string=f"crossref_{query}"
        )
        add_source = colrev.settings.SearchSource(
            endpoint="colrev_built_in.crossref",
            filename=filename,
            search_type=colrev.settings.SearchType.DB,
            search_parameters={"query": query},
            load_conversion_package_endpoint={"endpoint": "colrev_built_in.bibtex"},
            comment="",
        )
    elif Path(query).is_file():
        # pylint: disable=import-outside-toplevel
        import shutil

        dst = search_operation.review_manager.search_dir / Path(query).name
        shutil.copyfile(query, dst)
        filename = search_operation.get_unique_filename(
            file_path_string=Path(query).name
        )
        add_source = colrev.settings.SearchSource(
            endpoint="colrev_built_in.unknown_source",
            filename=Path(
                f"data/search/{filename}",
            ),
            search_type=colrev.settings.SearchType.DB,
            search_parameters={},
            load_conversion_package_endpoint={"endpoint": "colrev_built_in.bibtex"},
            comment="",
        )

    else:
        query_dict = json.loads(query)

        assert "endpoint" in query_dict

        if "filename" in query_dict:
            filename = search_operation.get_unique_filename(
                file_path_string=query_dict["filename"]
            )
        else:
            filename = search_operation.get_unique_filename(
                file_path_string=f"{query_dict['endpoint'].replace('colrev_built_in.', '')}"
            )
            i = 0
            while filename in [x.filename for x in search_operation.sources]:
                i += 1
                filename = Path(
                    str(filename)[: str(filename).find("_query") + 6] + f"_{i}.bib"
                )
        feed_file_path = search_operation.review_manager.path / filename
        assert not feed_file_path.is_file()
        query_dict["filename"] = filename

        # gh_issue https://github.com/geritwagner/colrev/issues/68
        # get search_type from the SearchSource
        # query validation based on ops.built_in.search_source settings
        # prevent duplicate sources (same endpoint and search_parameters)
        if "search_type" not in query_dict:
            query_dict["search_type"] = colrev.settings.SearchType.DB
        else:
            query_dict["search_type"] = colrev.settings.SearchType[
                query_dict["search_type"]
            ]

        if "load_conversion_package_endpoint" not in query_dict:
            query_dict["load_conversion_package_endpoint"] = {
                "endpoint": "colrev_built_in.bibtex"
            }
        if query_dict["search_type"] == colrev.settings.SearchType.DB:
            feed_config = {
                "load_conversion_package_endpoint": {
                    "endpoint": "colrev_built_in.bibtex"
                },
            }
            query_dict["load_conversion_package_endpoint"] = feed_config[
                "load_conversion_package_endpoint"
            ]

        # NOTE: for now, the parameters are limited to whole journals.
        add_source = colrev.settings.SearchSource(
            endpoint=query_dict["endpoint"],
            filename=filename,
            search_type=colrev.settings.SearchType(query_dict["search_type"]),
            search_parameters=query_dict.get("search_parameters", {}),
            load_conversion_package_endpoint=query_dict[
                "load_conversion_package_endpoint"
            ],
            comment="",
        )

    search_operation.add_source(add_source=add_source, query=query)


def add_data(
    *,
    data_operation: colrev.ops.data.Data,
    add: str,
) -> None:
    """Add a data package_endpoint"""

    package_manager = data_operation.review_manager.get_package_manager()
    available_data_endpoints = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.data
    )
    data_operation.review_manager.logger.info(f"Add {add} data endpoint")
    if add in available_data_endpoints:
        package_endpoints = package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.data,
            selected_packages=[{"endpoint": add}],
            operation=data_operation,
        )
        endpoint = package_endpoints[add]

        default_endpoint_conf = endpoint.get_default_setup()  # type: ignore

        if "colrev_built_in.manuscript" == add:
            if "y" == input("Select a custom word template (y/n)?"):

                template_name = input(
                    'Please copy the word template to " \
                "the project directory and enter the filename.'
                )
                default_endpoint_conf["word_template"] = template_name
            else:
                print("Adding APA as a default")

            if "y" == input("Select a custom citation stlye (y/n)?"):
                print(
                    "Citation stlyes are available at: \n"
                    "https://github.com/citation-style-language/styles"
                )
                csl_link = input("Please select a citation style and provide the link.")
                ret = requests.get(csl_link, allow_redirects=True, timeout=30)
                with open(Path(csl_link).name, "wb") as file:
                    file.write(ret.content)
                default_endpoint_conf["csl_style"] = Path(csl_link).name
            else:
                print("Adding APA as a default")

            data_operation.review_manager.dataset.add_changes(
                path=default_endpoint_conf["csl_style"]
            )
            data_operation.review_manager.dataset.add_changes(
                path=default_endpoint_conf["word_template"]
            )

        data_operation.add_data_endpoint(data_endpoint=default_endpoint_conf)
        data_operation.review_manager.create_commit(
            msg="Add data endpoint",
            script_call="colrev data",
        )

    elif add in [
        e.value for e in colrev.ops.built_in.data.bibliography_export.BibFormats
    ]:
        package_endpoints = package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.data,
            selected_packages=[{"endpoint": "colrev_built_in.bibliography_export"}],
            operation=data_operation,
        )
        endpoint = package_endpoints["colrev_built_in.bibliography_export"]
        default_endpoint_conf = endpoint.get_default_setup()
        default_endpoint_conf["bib_format"] = add
        data_operation.add_data_endpoint(data_endpoint=default_endpoint_conf)
        data_operation.review_manager.create_commit(
            msg=f"Add {add} data endpoint",
            script_call="colrev data",
        )
    else:
        print("Data format not available")
        return

    # Note : reload updated settings
    review_manager = colrev.review_manager.ReviewManager(force_mode=True)
    data_operation = colrev.ops.data.Data(review_manager=review_manager)

    data_operation.main(
        selection_list=["colrev_built_in.bibliography_export"], silent_mode=True
    )
    data_operation.review_manager.logger.info(
        f"{colors.GREEN}Successfully added {add} data endpoint{colors.END}"
    )


if __name__ == "__main__":
    pass
