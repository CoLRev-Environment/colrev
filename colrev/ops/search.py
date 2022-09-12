#! /usr/bin/env python
from __future__ import annotations

import re
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

    def parse_sources(self, *, query: str) -> list:
        if "WHERE " in query:
            sources = query[query.find("FROM ") + 5 : query.find(" WHERE")].split(",")
        elif "SCOPE " in query:
            sources = query[query.find("FROM ") + 5 : query.find(" SCOPE")].split(",")
        elif "WITH " in query:
            sources = query[query.find("FROM ") + 5 : query.find(" WITH")].split(",")
        else:
            sources = query[query.find("FROM ") + 5 :].split(",")
        sources = [s.lstrip().rstrip() for s in sources]
        return sources

    def parse_parameters(self, *, search_params: str) -> dict:

        query = search_params
        params = {}
        selection_str = query
        if "WHERE " in query:
            selection_str = query[query.find("WHERE ") + 6 :]
            if "SCOPE " in query:
                selection_str = selection_str[: selection_str.find("SCOPE ")]
            if "WITH " in query:
                selection_str = selection_str[: selection_str.find(" WITH")]

            if "[" in selection_str:
                # parse simple selection, e.g.,
                # digital[title] AND platform[all]
                selection = re.split(" AND | OR ", selection_str)
                selection_str = " ".join(
                    [
                        f"(lower(title) LIKE '%{x.lstrip().rstrip().lower()}%' OR "
                        f"lower(abstract) LIKE '%{x.lstrip().rstrip().lower()}%')"
                        if (
                            x not in ["AND", "OR"]
                            and not any(
                                t in x
                                for t in ["url=", "venue_key", "journal_abbreviated"]
                            )
                        )
                        else x
                        for x in selection
                    ]
                )

            # else: parse complex selection (no need to parse!?)
            params["selection_clause"] = selection_str

        if "SCOPE " in query:
            # selection_str = selection_str[: selection_str.find("SCOPE ")]
            scope_part_str = query[query.find("SCOPE ") + 6 :]
            if "WITH " in query:
                scope_part_str = scope_part_str[: scope_part_str.find(" WITH")]
            params["scope"] = {}  # type: ignore
            for scope_item in scope_part_str.split(" AND "):
                key, value = scope_item.split("=")
                if "url" in key:
                    if "https://dblp.org/db/" in value:
                        params["scope"]["venue_key"] = (  # type: ignore
                            value.replace("/index.html", "")
                            .replace("https://dblp.org/db/", "")
                            .replace("url=", "")
                            .replace("'", "")
                        )
                        continue
                params["scope"][key] = value.rstrip("'").lstrip("'")  # type: ignore

        if "WITH " in query:
            scope_part_str = query[query.find("WITH ") + 5 :]
            params["params"] = {}  # type: ignore
            for scope_item in scope_part_str.split(" AND "):
                key, value = scope_item.split("=")
                params["params"][key] = value.rstrip("'").lstrip("'")  # type: ignore

        return params

    def get_feed_config(self, *, source_name: str) -> dict:

        load_conversion_script = {"endpoint": "bibtex"}

        package_manager = self.review_manager.get_package_manager()

        available_search_scripts = package_manager.discover_packages(
            package_type=colrev.env.package_manager.PackageType.search_source
        )

        source_identifier = "TODO"
        if source_name in available_search_scripts:
            search_script_packages = package_manager.load_packages(
                package_type=colrev.env.package_manager.PackageType.search_source,
                selected_packages=[{"endpoint": source_name}],
                process=self,
            )
            source_identifier = search_script_packages[source_name][
                "endpoint"
            ].source_identifier

        return {
            "source_identifier": source_identifier,
            "load_conversion_script": load_conversion_script,
        }

    def add_source(self, *, query: str) -> None:

        # TODO : parse query (input format changed to sql-like string)
        # TODO : the search query/syntax translation has to be checked carefully
        # (risk of false-negative search results caused by errors/missing functionality)
        # https://lucene.apache.org/core/2_9_4/queryparsersyntax.html
        # https://github.com/netgen/query-translator/tree/master/lib/Languages/Galach
        # https://github.com/netgen/query-translator
        # https://medlinetranspose.github.io/documentation.html
        # https://sr-accelerator.com/#/help/polyglot

        # Start with basic query
        # RETRIEVE * FROM crossref,dblp WHERE digital AND platform
        # Note: corresponds to "digital[all] AND platform[all]"

        saved_args = {"add": f'"{query}"'}

        as_filename = ""
        if " AS " in query:
            as_filename = query[query.find(" AS ") + 4 :]
            as_filename = (
                as_filename.replace("'", "").replace('"', "").replace(" ", "_")
            )
            if ".bib" not in as_filename:
                as_filename = f"{as_filename}.bib"
            query = query[: query.find(" AS ")]
        query = f"SELECT * {query}"

        # TODO : query validation based on search_source settings

        # TODO : check whether url exists (dblp, project, ...)
        sources = self.parse_sources(query=query)
        if "WHERE " in query:
            selection = query[query.find("WHERE ") :]
        elif "SCOPE " in query:
            selection = query[query.find("SCOPE ") :]
        elif "WITH" in query:
            selection = query[query.find("WITH ") :]
        else:
            print("Error: missing WHERE or SCOPE clause in query")
            return

        for source_name in sources:
            duplicate_source = []
            try:
                duplicate_source = [
                    source
                    for source in self.sources
                    if source_name == source.source_name
                    and selection == source.search_parameters
                ]
            except TypeError:
                pass

            if len(duplicate_source) > 0:
                print(
                    "Source already exists: "
                    f"RETRIEVE * FROM {source_name} {selection}\nSkipping.\n"
                )
                continue

            if as_filename != "":
                filename = as_filename
            else:
                filename = f"{source_name}.bib"
                i = 0
                # TODO : filename may not yet exist (e.g., in other search feeds)
                while filename in [x.filename for x in self.sources]:
                    i += 1
                    filename = filename[: filename.find("_query") + 6] + f"_{i}.bib"

            feed_file_path = self.review_manager.path / Path(filename)
            assert not feed_file_path.is_file()

            # The following must be in line with settings.py/SearchSource
            search_type = "DB"
            source_identifier = "TODO"

            # TODO : add "USING script_x" when we add a search_script!

            if search_type == "DB":
                feed_config = self.get_feed_config(source_name=source_name)
                source_identifier = feed_config["source_identifier"]
                load_conversion_script = feed_config["load_conversion_script"]
            else:
                load_conversion_script = {"endpoint": "bibtex"}

            # NOTE: for now, the parameters are limited to whole journals.
            add_source = colrev.settings.SearchSource(
                filename=Path(
                    f"search/{filename}",
                ),
                search_type=colrev.settings.SearchType(search_type),
                source_name=source_name,
                source_identifier=source_identifier,
                search_parameters=selection,
                load_conversion_script=load_conversion_script,
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

    def remove_forthcoming(self, *, source: colrev.settings.SearchSource) -> None:
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

        def load_automated_search_sources() -> list[colrev.settings.SearchSource]:

            # automated_sources = [
            #     x for x in self.sources if "endpoint" in x.search_script
            # ]
            automated_sources = self.sources
            automated_sources_selected = automated_sources
            if selection_str is not None:
                if "all" != selection_str:
                    automated_sources_selected = [
                        f
                        for f in automated_sources
                        if str(f.filename) in selection_str.split(",")
                    ]
                if len(automated_sources_selected) == 0:
                    available_options = [str(f.filename) for f in automated_sources]
                    raise colrev_exceptions.ParameterError(
                        parameter="selection_str",
                        value=selection_str,
                        options=available_options,
                    )

            for source in automated_sources_selected:
                source.filename = self.review_manager.path / Path(source.filename)

            return automated_sources_selected

        for source in load_automated_search_sources():

            params = self.parse_parameters(search_params=source.search_parameters)

            print()
            self.review_manager.logger.info(
                f"Retrieve from {source.source_name}: {params}"
            )

            search_script = self.search_scripts[source.source_name.lower()]
            search_script.run_search(
                search_operation=self,
                params=params,
                feed_file=source.filename,
            )

            if source.filename.is_file():
                if not self.review_manager.settings.search.retrieve_forthcoming:
                    self.remove_forthcoming(source=source)

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
            search_parameters="TODO",
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
