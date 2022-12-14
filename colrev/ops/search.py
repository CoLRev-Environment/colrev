#! /usr/bin/env python
"""CoLRev search operation: Search for relevant records."""
from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path
from random import randint

import requests
from pybtex.database.input import bibtex

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

    def __get_unique_filename(
        self, file_path_string: str, suffix: str = ".bib"
    ) -> Path:
        file_path_string = file_path_string.replace("+", "_").replace(" ", "_")

        filename = Path(f"data/search/{file_path_string}{suffix}")
        existing_filenames = [x.filename for x in self.sources]
        if filename not in existing_filenames:
            return filename

        i = 1
        while filename in existing_filenames:
            filename = Path(f"data/search/{file_path_string}_{i}{suffix}")
            i += 1

        return filename

    def add_source(self, *, query: str) -> None:
        """Add a new source"""

        # pylint: disable=too-many-statements

        saved_args = {"add": f'"{query}"'}
        if "pdfs" == query:

            filename = self.__get_unique_filename(file_path_string="pdfs")
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

            filename = self.__get_unique_filename(
                file_path_string=f"dblp_{query.replace('https://dblp.org/search/publ/api?q=', '')}"
            )
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

            filename = self.__get_unique_filename(file_path_string=f"crossref_{query}")
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
        elif Path(query).is_file():
            # pylint: disable=import-outside-toplevel
            import shutil

            dst = self.review_manager.search_dir / Path(query).name
            shutil.copyfile(query, dst)
            filename = self.__get_unique_filename(file_path_string=Path(query).name)
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
                filename = self.__get_unique_filename(
                    file_path_string=query_dict["filename"]
                )
            else:
                filename = self.__get_unique_filename(
                    file_path_string=f"{query_dict['endpoint'].replace('colrev_built_in.', '')}"
                )
                i = 0
                while filename in [x.filename for x in self.sources]:
                    i += 1
                    filename = Path(
                        str(filename)[: str(filename).find("_query") + 6] + f"_{i}.bib"
                    )
            feed_file_path = self.review_manager.path / filename
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

    def __have_changed(self, *, record_a_orig: dict, record_b_orig: dict) -> bool:

        # To ignore changes introduced by saving/loading the feed-records,
        # we parse and load them in the following.
        record_a = deepcopy(record_a_orig)
        record_b = deepcopy(record_b_orig)

        bibtex_str = self.review_manager.dataset.parse_bibtex_str(
            recs_dict_in={record_a["ID"]: record_a}
        )
        parser = bibtex.Parser()
        bib_data = parser.parse_string(bibtex_str)
        record_a = list(
            self.review_manager.dataset.parse_records_dict(
                records_dict=bib_data.entries
            ).values()
        )[0]

        bibtex_str = self.review_manager.dataset.parse_bibtex_str(
            recs_dict_in={record_b["ID"]: record_b}
        )
        parser = bibtex.Parser()
        bib_data = parser.parse_string(bibtex_str)
        record_b = list(
            self.review_manager.dataset.parse_records_dict(
                records_dict=bib_data.entries
            ).values()
        )[0]

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

        origin = f"{source.get_origin_prefix()}/{record_dict['ID']}"
        for main_record_dict in records.values():

            if origin not in main_record_dict["colrev_origin"]:
                continue

            # TBD: in curated masterdata repositories?

            record = colrev.record.Record(data=record_dict)
            if record.check_potential_retracts():
                self.review_manager.logger.info(
                    f"{colors.GREEN}Found paper retract: "
                    f"{main_record_dict['ID']}{colors.END}"
                )
                main_record = colrev.record.Record(data=main_record_dict)
                main_record.prescreen_exclude(reason="retracted", print_warning=True)
                main_record.remove_field(key="warning")
                changed = True

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

            if (
                "CURATED" in main_record_dict.get("colrev_masterdata_provenance", {})
                and "md_curated.bib" != source.get_origin_prefix()
            ):
                continue

            similarity_score = colrev.record.Record.get_record_similarity(
                record_a=colrev.record.Record(data=record_dict),
                record_b=colrev.record.Record(data=prev_record_dict_version),
            )
            dict_diff = colrev.record.Record(data=record_dict).get_diff(
                other_record=colrev.record.Record(data=prev_record_dict_version)
            )

            for key, value in record_dict.items():

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
            if self.__have_changed(
                record_a_orig=main_record_dict, record_b_orig=prev_record_dict_version
            ):
                changed = True

            if self.__have_changed(
                record_a_orig=record_dict, record_b_orig=prev_record_dict_version
            ):
                # Note : not (yet) in the main records but changed
                changed = True
            if changed:
                if similarity_score > 0.98:
                    self.review_manager.logger.info(f" check/update {origin}")
                else:
                    self.review_manager.logger.info(
                        f" {colors.RED} check/update {origin} leads to substantial changes "
                        f"({similarity_score}) in {main_record_dict['ID']}:{colors.END}"
                    )
                    self.review_manager.p_printer.pprint(
                        [x for x in dict_diff if "change" == x[0]]
                    )

            break

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

            try:
                endpoint.run_search(  # type: ignore
                    search_operation=self, update_only=update_only
                )
            except requests.exceptions.ConnectionError as exc:
                raise colrev_exceptions.ServiceNotAvailableException(
                    source.endpoint
                ) from exc

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


# Keep in mind the need for lock-mechanisms, e.g., in concurrent prep operations
class GeneralOriginFeed:
    """A general-purpose Origin feed"""

    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        search_source: colrev.settings.SearchSource,
        source_identifier: str,
        update_only: bool,
    ):

        self.source = search_source
        self.feed_file = search_source.filename

        # Note: the source_identifier identifies records in the search feed.
        # This could be a doi or link or database-specific ID (like WOS accession numbers)
        # The source_identifier can be stored in the main records.bib (it does not have to)
        # The record source_identifier (feed-specific) is used in search
        # or other operations (like prep)
        # In search operations, records are added/updated based on available_ids
        # (which maps source_identifiers to IDs used to generate the colrev_origin)
        # In other operations, records are linked through colrev_origins,
        # i.e., there is no need to store the source_identifier in the main records (redundantly)
        self.source_identifier = source_identifier

        self.update_only = update_only
        self.review_manager = review_manager
        self.origin_prefix = self.source.get_origin_prefix()

        self.__available_ids = {}
        self.__max_id = 1
        if not self.feed_file.is_file():
            self.feed_records = {}
        else:
            with open(self.feed_file, encoding="utf8") as bibtex_file:
                self.feed_records = self.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )

            self.__available_ids = {
                x[self.source_identifier]: x["ID"]
                for x in self.feed_records.values()
                if self.source_identifier in x
            }
            self.__max_id = (
                max(
                    [
                        int(x["ID"])
                        for x in self.feed_records.values()
                        if x["ID"].isdigit()
                    ]
                    + [1]
                )
                + 1
            )

    def save_feed_file(self) -> None:
        """Save the feed file"""

        search_operation = self.review_manager.get_search_operation()
        if len(self.feed_records) > 0:

            self.feed_file.parents[0].mkdir(parents=True, exist_ok=True)
            self.review_manager.dataset.save_records_dict_to_file(
                records=self.feed_records, save_path=self.feed_file
            )

            while True:
                search_operation.review_manager.load_settings()
                if self.source.filename.name not in [
                    s.filename.name
                    for s in search_operation.review_manager.settings.sources
                ]:
                    search_operation.review_manager.settings.sources.append(self.source)
                    search_operation.review_manager.save_settings()

                try:
                    search_operation.review_manager.dataset.add_changes(
                        path=self.feed_file
                    )
                    break
                except (FileExistsError, OSError):
                    search_operation.review_manager.logger.debug("Wait for git")
                    time.sleep(randint(1, 15))

    def set_id(self, *, record_dict: dict) -> dict:
        """Set incremental record ID
        If self.source_identifier is in record_dict, it is updated, otherwise added as a new record.
        """

        if record_dict[self.source_identifier] in self.__available_ids:
            record_dict["ID"] = self.__available_ids[
                record_dict[self.source_identifier]
            ]
        else:
            record_dict["ID"] = str(self.__max_id).rjust(6, "0")

        return record_dict

    def add_record(self, *, record: colrev.record.Record) -> bool:
        """Add a record to the feed and set its colrev_origin"""

        # Feed:
        feed_record_dict = record.data.copy()
        added_new = True
        if feed_record_dict[self.source_identifier] in self.__available_ids:
            added_new = False
        else:
            self.__max_id += 1

        if "colrev_data_provenance" in feed_record_dict:
            del feed_record_dict["colrev_data_provenance"]
        if "colrev_masterdata_provenance" in feed_record_dict:
            del feed_record_dict["colrev_masterdata_provenance"]
        if "colrev_status" in feed_record_dict:
            del feed_record_dict["colrev_status"]

        if self.update_only and added_new:
            added_new = False
        else:
            self.__available_ids[
                feed_record_dict[self.source_identifier]
            ] = feed_record_dict["ID"]
            self.feed_records[feed_record_dict["ID"]] = feed_record_dict

        # Original record
        colrev_origin = f"{self.origin_prefix}/{record.data['ID']}"
        record.data["colrev_origin"] = [colrev_origin]
        record.add_provenance_all(source=colrev_origin)

        return added_new


if __name__ == "__main__":
    pass
