#! /usr/bin/env python
"""CoLRev search operation: Search for relevant records."""
from __future__ import annotations

import json
from pathlib import Path

import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.settings


class Search(colrev.operation.Operation):
    """Search for new records"""

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
    ) -> None:

        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.search,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.sources = review_manager.settings.sources

    def save_feed_file(self, *, records: dict, feed_file: Path) -> None:
        """Save the feed file"""

        feed_file.parents[0].mkdir(parents=True, exist_ok=True)
        records = {str(r["ID"]).replace(" ", ""): r for r in records.values()}
        self.review_manager.dataset.save_records_dict_to_file(
            records=records, save_path=feed_file
        )

    def __get_feed_config(self, *, query_dict: dict) -> dict:

        load_conversion_package_endpoint = {"endpoint": "bibtex"}

        package_manager = self.review_manager.get_package_manager()

        available_search_package_endpoints = package_manager.discover_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source
        )

        source_identifier = "TODO"
        if query_dict["endpoint"] in available_search_package_endpoints:
            search_script_packages = package_manager.load_packages(
                package_type=colrev.env.package_manager.PackageEndpointType.search_source,
                selected_packages=[query_dict],
                operation=self,
            )
            source_identifier = search_script_packages[  # type: ignore
                query_dict["endpoint"]
            ].source_identifier

        return {
            "source_identifier": source_identifier,
            "load_conversion_package_endpoint": load_conversion_package_endpoint,
        }

    def add_source(self, *, query: str) -> None:
        """Add a new source"""

        saved_args = {"add": f'"{query}"'}
        query_dict = json.loads(query)

        assert "endpoint" in query_dict

        if "filename" in query_dict:
            filename = query_dict["filename"]
        else:
            filename = f"{query_dict['endpoint']}.bib"
            i = 0
            while filename in [x.filename for x in self.sources]:
                i += 1
                filename = filename[: filename.find("_query") + 6] + f"_{i}.bib"
        feed_file_path = self.review_manager.path / Path(filename)
        assert not feed_file_path.is_file()
        query_dict["filename"] = feed_file_path

        # gh_issue https://github.com/geritwagner/colrev/issues/68
        # get search_type/source_identifier from the SearchSource
        # query validation based on ops.built_in.search_source settings
        # prevent duplicate sources (same endpoint and search_parameters)
        if "search_type" not in query_dict:
            query_dict["search_type"] = colrev.settings.SearchType.DB
        else:
            query_dict["search_type"] = colrev.settings.SearchType[
                query_dict["search_type"]
            ]
        if "source_identifier" not in query_dict:
            query_dict["source_identifier"] = "TODO"

        if "load_conversion_package_endpoint" not in query_dict:
            query_dict["load_conversion_package_endpoint"] = {"endpoint": "bibtex"}
        if query_dict["search_type"] == colrev.settings.SearchType.DB:
            feed_config = self.__get_feed_config(query_dict=query_dict)
            query_dict["source_identifier"] = feed_config["source_identifier"]
            query_dict["load_conversion_package_endpoint"] = feed_config[
                "load_conversion_package_endpoint"
            ]

        # NOTE: for now, the parameters are limited to whole journals.
        add_source = colrev.settings.SearchSource(
            endpoint=query_dict["endpoint"],
            filename=Path(
                f"data/search/{filename}",
            ),
            search_type=colrev.settings.SearchType(query_dict["search_type"]),
            source_identifier=query_dict["source_identifier"],
            search_parameters=query_dict.get("search_parameters", {}),
            load_conversion_package_endpoint=query_dict[
                "load_conversion_package_endpoint"
            ],
            comment="",
        )
        self.review_manager.p_printer.pprint(add_source)
        self.review_manager.settings.sources.append(add_source)
        self.review_manager.save_settings()

        self.review_manager.create_commit(
            msg=f"Add search source {filename}",
            script_call="colrev search",
            saved_args=saved_args,
        )

        self.main(selection_str="all")

    def __remove_forthcoming(self, *, source: colrev.settings.SearchSource) -> None:
        self.review_manager.logger.info("Remove forthcoming")

        with open(source.get_corresponding_bib_file(), encoding="utf8") as bibtex_file:
            records = self.review_manager.dataset.load_records_dict(
                load_str=bibtex_file.read()
            )

            record_list = list(records.values())
            record_list = [r for r in record_list if "forthcoming" != r.get("year", "")]
            records = {r["ID"]: r for r in record_list}

            self.review_manager.dataset.save_records_dict_to_file(
                records=records, save_path=source.get_corresponding_bib_file()
            )

    def __get_search_sources(
        self, *, selection_str: str = None
    ) -> list[colrev.settings.SearchSource]:

        sources_selected = self.sources
        if selection_str:
            if "all" != selection_str:
                sources_selected = [
                    f
                    for f in self.sources
                    if str(f.filename) in selection_str.split(",")
                ]
            if len(sources_selected) == 0:
                available_options = [str(f.filename) for f in self.sources]
                raise colrev_exceptions.ParameterError(
                    parameter="selection_str",
                    value=selection_str,
                    options=available_options,
                )

        for source in sources_selected:
            source.filename = self.review_manager.path / Path(source.filename)
        return sources_selected

    def main(self, *, selection_str: str = None) -> None:
        """Search for records (main entrypoint)"""

        # Reload the settings because the search sources may have been updated
        self.review_manager.settings = self.review_manager.load_settings()

        package_manager = self.review_manager.get_package_manager()

        for source in self.__get_search_sources(selection_str=selection_str):

            print()
            self.review_manager.logger.info(
                f"Retrieve from {source.endpoint} ({source.filename.name})"
            )

            endpoint_dict = package_manager.load_packages(
                package_type=colrev.env.package_manager.PackageEndpointType.search_source,
                selected_packages=[source.get_dict()],
                operation=self,
            )

            endpoint = endpoint_dict[source.endpoint.lower()]
            endpoint.run_search(  # type: ignore
                search_operation=self,
            )

            if source.filename.is_file():
                if not self.review_manager.settings.search.retrieve_forthcoming:
                    self.__remove_forthcoming(source=source)

                self.review_manager.dataset.add_changes(path=source.filename)
                self.review_manager.create_commit(
                    msg="Run search", script_call="colrev search"
                )

    def setup_custom_script(self) -> None:
        """Setup a custom search script"""

        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/custom_search_source_script.py")
        )

        if filedata:
            with open("custom_search_source_script.py", "w", encoding="utf-8") as file:
                file.write(filedata.decode("utf-8"))

        self.review_manager.dataset.add_changes(
            path=Path("custom_search_source_script.py")
        )

        new_source = colrev.settings.SearchSource(
            endpoint="custom_search_source_script",
            filename=Path("data/search/custom_search.bib"),
            search_type=colrev.settings.SearchType.DB,
            source_identifier="TODO",
            search_parameters={},
            load_conversion_package_endpoint={"endpoint": "colrev_built_in.bibtex"},
            comment="",
        )

        self.review_manager.settings.sources.append(new_source)
        self.review_manager.save_settings()

    def view_sources(self) -> None:
        """View the sources info"""

        for source in self.sources:
            self.review_manager.p_printer.pprint(source)


if __name__ == "__main__":
    pass
