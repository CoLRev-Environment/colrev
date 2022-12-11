#! /usr/bin/env python
"""CoLRev search operation: Search for relevant records."""
from __future__ import annotations

import json
from pathlib import Path

import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.settings
import colrev.ui_cli.cli_colors as colors


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

    def add_source(self, *, query: str) -> None:
        """Add a new source"""

        # pylint: disable=too-many-statements

        saved_args = {"add": f'"{query}"'}
        if "pdfs" == query:
            filename = Path("data/search/pdfs.bib")
            # pylint: disable=no-value-for-parameter
            add_source = colrev.settings.SearchSource(
                {
                    "endpoint": "colrev_built_in.pdfs_dir",
                    "filename": filename,
                    "search_type": colrev.settings.SearchType.PDFS,
                    "search_parameters": {"scope": {"path": "data/pdfs"}},
                    "load_conversion_package_endpoint": {
                        "endpoint": "colrev_built_in.bibtex"
                    },
                    "comment": "",
                }
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

            # TODO : avoid  duplicate filenames
            filename = Path("data/search/dblp.bib")
            add_source = colrev.settings.SearchSource(
                **{  # type: ignore
                    "endpoint": "colrev_built_in.dblp",
                    "filename": filename,
                    "search_type": colrev.settings.SearchType.DB,
                    "search_parameters": {"query": query},
                    "load_conversion_package_endpoint": {
                        "endpoint": "colrev_built_in.bibtex"
                    },
                    "comment": "",
                }
            )
        elif "https://search.crossref.org/?q=" in query:
            query = (
                query.replace("https://search.crossref.org/?q=", "")
                .replace("&from_ui=yes", "")
                .lstrip("+")
            )

            # TODO : avoid  duplicate filenames

            filename = Path(f"data/search/crossref_{query.replace(' ', '_')}.bib")
            add_source = colrev.settings.SearchSource(
                **{  # type: ignore
                    "endpoint": "colrev_built_in.crossref",
                    "filename": filename,
                    "search_type": colrev.settings.SearchType.DB,
                    "search_parameters": {"query": query},
                    "load_conversion_package_endpoint": {
                        "endpoint": "colrev_built_in.bibtex"
                    },
                    "comment": "",
                }
            )
        else:
            query_dict = json.loads(query)

            assert "endpoint" in query_dict

            if "filename" in query_dict:
                filename = query_dict["filename"]
            else:
                filename = Path(
                    f"{query_dict['endpoint'].replace('colrev_built_in.', '')}.bib"
                )
                i = 0
                while filename in [x.filename for x in self.sources]:
                    i += 1
                    filename = Path(
                        str(filename)[: str(filename).find("_query") + 6] + f"_{i}.bib"
                    )
            feed_file_path = self.review_manager.path / filename
            assert not feed_file_path.is_file()
            query_dict["filename"] = feed_file_path

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
                filename=Path(
                    f"data/search/{filename}",
                ),
                search_type=colrev.settings.SearchType(query_dict["search_type"]),
                search_parameters=query_dict.get("search_parameters", {}),
                load_conversion_package_endpoint=query_dict[
                    "load_conversion_package_endpoint"
                ],
                comment="",
            )

        package_manager = self.review_manager.get_package_manager()
        endpoint_dict = package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            selected_packages=[add_source.get_dict()],
            operation=self,
        )
        endpoint = endpoint_dict[add_source.endpoint.lower()]
        endpoint.validate_source(search_operation=self, source=add_source)  # type: ignore

        self.review_manager.logger.info(f"{colors.GREEN}Add source:{colors.END}")
        # self.review_manager.p_printer.pprint(add_source)
        print(add_source)
        self.review_manager.settings.sources.append(add_source)
        self.review_manager.save_settings()

        self.review_manager.create_commit(
            msg=f"Add search source {filename}",
            script_call="colrev search",
            saved_args=saved_args,
        )
        print()

        self.main(selection_str="all", update_only=False)

    def __remove_forthcoming(self, *, source: colrev.settings.SearchSource) -> None:

        with open(source.get_corresponding_bib_file(), encoding="utf8") as bibtex_file:
            records = self.review_manager.dataset.load_records_dict(
                load_str=bibtex_file.read()
            )

            record_list = list(records.values())
            before = len(record_list)
            record_list = [r for r in record_list if "forthcoming" != r.get("year", "")]
            changed = len(record_list) - before
            if changed > 0:
                self.review_manager.logger.info(
                    f"{colors.GREEN}Removed {changed} forthcoming{colors.END}"
                )
            else:
                self.review_manager.logger.info(f"Removed {changed} forthcoming")

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

    def update_existing_record(
        self,
        *,
        records: dict,
        record_dict: dict,
        prev_record_dict_version: dict,
        source: colrev.settings.SearchSource,
    ) -> bool:
        """Convenience function to update existing records (main data/records.bib)"""

        # pylint: disable=too-many-branches

        changed = False

        def have_changed(record_a: dict, record_b: dict) -> bool:
            # Note : record_a can have more keys (that's ok)
            changed = False
            for key, value in record_b.items():
                if key in colrev.record.Record.provenance_keys + ["ID", "curation_ID"]:
                    continue
                if key not in record_a:
                    return True
                if record_a[key] != value:
                    return True
            return changed

        # TODO : notify on major changes!
        # TBD: how to handle cases where changes are too significant?

        origin = f"{source.get_origin_prefix()}/{record_dict['ID']}"
        for main_record_dict in records.values():
            if origin not in main_record_dict["colrev_origin"]:
                continue
            # TBD: in curated masterdata repositories?
            if (
                "CURATED" in main_record_dict.get("colrev_masterdata_provenance", {})
                and "md_curated.bib" != source.get_origin_prefix()
            ):
                continue

            if "retracted" in record_dict.get("prescreen_exclusion", ""):

                self.review_manager.logger.info(
                    f"{colors.GREEN}Found paper retract: "
                    f"{main_record_dict['ID']}{colors.END}"
                )
                record = colrev.record.Record(data=main_record_dict)
                record.prescreen_exclude(reason="retracted", print_warning=True)
                record.remove_field(key="warning")

            if (
                "forthcoming" == main_record_dict["year"]
                and "forthcoming" != record_dict["year"]
            ):
                self.review_manager.logger.info(
                    f"{colors.GREEN}Update published forthcoming paper: "
                    f"{record.data['ID']}{colors.END}"
                )
                # prepared_record = crossref_prep.prepare(prep_operation, record)
                main_record_dict["year"] = record_dict["year"]
                record = colrev.record.PrepRecord(data=main_record_dict)

                colrev_id = record.create_colrev_id(
                    also_known_as_record=record.get_data()
                )
                record.data["colrev_id"] = colrev_id

            for key, value in record_dict.items():
                # TODO : integrate the following into source or update_existing_record?!
                if key in ["curation_ID"]:
                    continue

                if key in colrev.record.Record.provenance_keys + ["ID"]:
                    continue

                if key not in main_record_dict:
                    if key in main_record_dict.get("colrev_masterdata_provenance", {}):
                        if (
                            main_record_dict["colrev_masterdata_provenance"][key][
                                "source"
                            ]
                            == "colrev_curation.masterdata_restrictions"
                            and main_record_dict["colrev_masterdata_provenance"][key][
                                "note"
                            ]
                            == "not_missing"
                        ):
                            continue
                    main_record = colrev.record.Record(data=main_record_dict)
                    main_record.update_field(
                        key=key,
                        value=value,
                        source=origin,
                        keep_source_if_equal=True,
                        append_edit=False,
                    )
                else:
                    if "md_curated.bib" != source.get_origin_prefix():
                        if prev_record_dict_version.get(
                            key, "NA"
                        ) != main_record_dict.get(key, "OTHER"):
                            continue
                    main_record = colrev.record.Record(data=main_record_dict)
                    main_record.update_field(
                        key=key,
                        value=value,
                        source=origin,
                        keep_source_if_equal=True,
                        append_edit=False,
                    )
            if have_changed(main_record_dict, prev_record_dict_version):
                changed = True

        if have_changed(record_dict, prev_record_dict_version):
            # Note : not (yet) in the main records but changed
            changed = True
        if changed:
            self.review_manager.logger.info(f" check/update {origin}")

        return changed

    def main(self, *, selection_str: str = None, update_only: bool) -> None:
        """Search for records (main entrypoint)"""

        # Reload the settings because the search sources may have been updated
        self.review_manager.settings = self.review_manager.load_settings()

        package_manager = self.review_manager.get_package_manager()

        self.review_manager.logger.info("Search")

        for source in self.__get_search_sources(selection_str=selection_str):

            endpoint_dict = package_manager.load_packages(
                package_type=colrev.env.package_manager.PackageEndpointType.search_source,
                selected_packages=[source.get_dict()],
                operation=self,
            )

            endpoint = endpoint_dict[source.endpoint.lower()]
            endpoint.validate_source(search_operation=self, source=source)  # type: ignore

            run_search_function = getattr(endpoint, "run_search", None)
            if not callable(run_search_function):
                # Some sources do not support automated searches (e.g., unknown sources)
                continue

            print()
            self.review_manager.logger.info(
                f"Retrieve from {source.endpoint} (results > data/search/{source.filename.name})"
            )

            endpoint.run_search(  # type: ignore
                search_operation=self, update_only=update_only
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
            file_path=Path("template/custom_scripts/custom_search_source_script.py")
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
