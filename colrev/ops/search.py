#! /usr/bin/env python
"""CoLRev search operation: Search for relevant records."""
from __future__ import annotations

import json
import typing
from dataclasses import asdict
from pathlib import Path

import colrev.exceptions as colrev_exceptions
import colrev.process
import colrev.settings


class Search(colrev.process.Process):
    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation=True,
    ) -> None:

        super().__init__(
            review_manager=review_manager,
            process_type=colrev.process.ProcessType.search,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.sources = review_manager.settings.sources

        package_manager = self.review_manager.get_package_manager()
        self.search_scripts: dict[str, typing.Any] = package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageType.search_source,
            selected_packages=[asdict(s) for s in self.sources],
            process=self,
        )

    def save_feed_file(self, *, records: dict, feed_file: Path) -> None:
        feed_file.parents[0].mkdir(parents=True, exist_ok=True)
        records = {
            str(r["ID"]).replace(" ", ""): {
                k.lower()
                .replace(" ", "_")
                .replace("id", "ID")
                .replace("entrytype", "ENTRYTYPE"): v
                for k, v in r.items()
            }
            for r in records.values()
        }
        self.review_manager.dataset.save_records_dict_to_file(
            records=records, save_path=feed_file
        )

    def __get_feed_config(self, *, query_dict: dict) -> dict:

        load_conversion_script = {"endpoint": "bibtex"}

        package_manager = self.review_manager.get_package_manager()

        available_search_scripts = package_manager.discover_packages(
            package_type=colrev.env.package_manager.PackageType.search_source
        )

        source_identifier = "TODO"
        if query_dict["source_name"] in available_search_scripts:
            search_script_packages = package_manager.load_packages(
                package_type=colrev.env.package_manager.PackageType.search_source,
                selected_packages=[query_dict],
                process=self,
            )
            source_identifier = search_script_packages[  # type: ignore
                query_dict["source_name"]
            ].source_identifier

        return {
            "source_identifier": source_identifier,
            "load_conversion_script": load_conversion_script,
        }

    def add_source(self, *, query: str) -> None:

        saved_args = {"add": f'"{query}"'}

        query_dict = json.loads(query)

        assert "source_name" in query_dict

        if "filename" in query_dict:
            filename = query_dict["filename"]
        else:
            filename = f"{query_dict['source_name']}.bib"
            i = 0
            while filename in [x.filename for x in self.sources]:
                i += 1
                filename = filename[: filename.find("_query") + 6] + f"_{i}.bib"
        feed_file_path = self.review_manager.path / Path(filename)
        assert not feed_file_path.is_file()
        query_dict["filename"] = feed_file_path

        # TODO : get search_type/source_identifier from the SearchSource
        # TODO : query validation based on ops.built_in.search_source settings
        # TODO : prevent duplicate sources (same source_name and search_parameters)
        if "search_type" not in query_dict:
            query_dict["search_type"] = colrev.settings.SearchType.DB
        else:
            query_dict["search_type"] = colrev.settings.SearchType[
                query_dict["search_type"]
            ]
        if "source_identifier" not in query_dict:
            query_dict["source_identifier"] = "TODO"

        if "load_conversion_script" not in query_dict:
            query_dict["load_conversion_script"] = {"endpoint": "bibtex"}
        if query_dict["search_type"] == colrev.settings.SearchType.DB:
            feed_config = self.__get_feed_config(query_dict=query_dict)
            query_dict["source_identifier"] = feed_config["source_identifier"]
            query_dict["load_conversion_script"] = feed_config["load_conversion_script"]

        # NOTE: for now, the parameters are limited to whole journals.
        add_source = colrev.settings.SearchSource(
            filename=Path(
                f"data/search/{filename}",
            ),
            search_type=colrev.settings.SearchType(query_dict["search_type"]),
            source_name=query_dict["source_name"],
            source_identifier=query_dict["source_identifier"],
            search_parameters=query_dict.get("search_parameters", {}),
            load_conversion_script=query_dict["load_conversion_script"],
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

    def main(self, *, selection_str: str = None) -> None:

        # Reload the settings because the search sources may have been updated
        self.review_manager.settings = self.review_manager.load_settings()

        # TODO : when the search_file has been filled only query the last years

        def get_serach_sources() -> list[colrev.settings.SearchSource]:

            sources_selected = self.sources
            if selection_str is not None:
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

        for source in get_serach_sources():

            print()
            self.review_manager.logger.info(
                f"Retrieve from {source.source_name} ({source.filename.name})"
            )

            search_script = self.search_scripts[source.source_name.lower()]
            search_script.run_search(
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

        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/custom_search_script.py")
        )

        if filedata:
            with open("custom_search_script.py", "w", encoding="utf-8") as file:
                file.write(filedata.decode("utf-8"))

        self.review_manager.dataset.add_changes(path=Path("custom_search_script.py"))

        new_source = colrev.settings.SearchSource(
            filename=Path("custom_search.bib"),
            search_type=colrev.settings.SearchType.DB,
            source_name="custom_search_script",
            source_identifier="TODO",
            search_parameters={},
            load_conversion_script={"endpoint": "TODO"},
            comment="",
        )

        self.review_manager.settings.sources.append(new_source)
        self.review_manager.save_settings()

    def view_sources(self) -> None:

        for source in self.sources:
            self.review_manager.p_printer.pprint(source)

        print("\nOptions:")
        options = ", ".join(list(self.search_scripts.keys()))
        print(f"- endpoints: {options}")


if __name__ == "__main__":
    pass
