#! /usr/bin/env python
import re
import typing
from pathlib import Path

from colrev_core.environment import AdapterManager
from colrev_core.exceptions import InvalidQueryException
from colrev_core.exceptions import NoSearchFeedRegistered
from colrev_core.process import Process
from colrev_core.process import ProcessType


class Search(Process):

    from colrev_core.built_in import search as built_in_search

    built_in_scripts: typing.Dict[str, typing.Dict[str, typing.Any]] = {
        "search_crossref": {
            "endpoint": built_in_search.CrossrefSearchEndpoint,
        },
        "search_dblp": {
            "endpoint": built_in_search.DBLPSearchEndpoint,
        },
        "backward_search": {
            "endpoint": built_in_search.BackwardSearchEndpoint,
        },
        "search_colrev_project": {
            "endpoint": built_in_search.ColrevProjectSearchEndpoint,
        },
        "search_local_index": {
            "endpoint": built_in_search.IndexSearchEndpoint,
        },
        "search_pdfs_dir": {
            "endpoint": built_in_search.PDFSearchEndpoint,
        },
    }

    def __init__(
        self,
        *,
        REVIEW_MANAGER,
        notify_state_transition_process=True,
    ):

        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            type=ProcessType.search,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.SOURCES = REVIEW_MANAGER.settings.sources

        self.search_scripts: typing.Dict[str, typing.Any] = AdapterManager.load_scripts(
            PROCESS=self,
            scripts=[s.search_script for s in self.SOURCES],
        )

    def save_feed_file(self, records: dict, feed_file: Path) -> None:
        from colrev_core.review_dataset import ReviewDataset

        feed_file.parents[0].mkdir(parents=True, exist_ok=True)
        records = {
            str(r["ID"])
            .lower()
            .replace(" ", ""): {
                k.lower()
                .replace(" ", "_")
                .replace("id", "ID")
                .replace("entrytype", "ENTRYTYPE"): v
                for k, v in r.items()
            }
            for r in records.values()
        }
        ReviewDataset.save_records_dict_to_file(records=records, save_path=feed_file)

        return

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

    def validate_query(self, *, query: str) -> None:

        if " FROM " not in query:
            raise InvalidQueryException('Query missing "FROM" clause')

        sources = self.parse_sources(query=query)

        scripts = []
        for source_name in sources:
            feed_config = self.get_feed_config(source_name=source_name)
            scripts.append(feed_config["search_script"])

        required_search_scripts = [
            s.search_script for s in self.REVIEW_MANAGER.settings.sources
        ]
        self.search_scripts = AdapterManager.load_scripts(
            PROCESS=self,
            scripts=scripts + required_search_scripts,
        )

        if len(sources) > 1:
            individual_sources = [
                k
                for k, v in self.search_scripts.items()
                if "individual" == v["endpoint"].mode
            ]
            if any(source in individual_sources for source in sources):
                violations = [
                    source for source in sources if source in individual_sources
                ]
                raise InvalidQueryException(
                    "Multiple query sources include a source that can only be"
                    f" used individually: {violations}"
                )

        for source_name in sources:
            feed_config = self.get_feed_config(source_name=source_name)
            for source in sources:
                # TODO : parse params (which may also raise errors)
                SCRIPT = self.search_scripts[feed_config["search_script"]["endpoint"]]
                SCRIPT.validate_params(query=query)  # type: ignore

        return

    def get_feed_config(self, *, source_name) -> dict:

        conversion_script = {"endpoint": "bibtex"}

        search_script = {"endpoint": "TODO"}
        if source_name == "DBLP":
            search_script = {"endpoint": "search_dblp"}
        elif source_name == "CROSSREF":
            search_script = {"endpoint": "search_crossref"}
        elif source_name == "BACKWARD_SEARCH":
            search_script = {"endpoint": "backward_search"}
        elif source_name == "COLREV_PROJECT":
            search_script = {"endpoint": "search_colrev_project"}
        elif source_name == "INDEX":
            search_script = {"endpoint": "search_local_index"}
        elif source_name == "PDFS":
            search_script = {"endpoint": "search_pdfs_dir"}

        source_identifier = "TODO"
        if search_script["endpoint"] in self.built_in_scripts:
            source_identifier = self.built_in_scripts[search_script["endpoint"]][
                "endpoint"
            ].source_identifier

        return {
            "source_identifier": source_identifier,
            "search_script": search_script,
            "conversion_script": conversion_script,
            "source_prep_scripts": [],
        }

    def add_source(self, *, query: str) -> None:

        from colrev_core.settings import SearchSource, SearchType

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

        self.validate_query(query=query)

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
                    x
                    for x in self.SOURCES
                    if source_name == x["search_parameters"][0]["endpoint"]
                    and selection == x["search_parameters"][0]["params"]
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
                while filename in [x.filename for x in self.SOURCES]:
                    i += 1
                    filename = filename[: filename.find("_query") + 6] + f"_{i}.bib"

            feed_file_path = self.REVIEW_MANAGER.path / Path(filename)
            assert not feed_file_path.is_file()

            # The following must be in line with settings.py/SearchSource
            search_type = "DB"
            source_identifier = "TODO"

            # TODO : add "USING script_x" when we add a search_script!

            if search_type == "DB":
                feed_config = self.get_feed_config(source_name=source_name)
                source_identifier = feed_config["source_identifier"]
                search_script = feed_config["search_script"]
                conversion_script = feed_config["conversion_script"]
                source_prep_scripts = feed_config["source_prep_scripts"]
            else:
                search_script = {}
                conversion_script = {"endpoint": "bibtex"}
                source_prep_scripts = []

            # NOTE: for now, the parameters are limited to whole journals.
            add_source = SearchSource(
                filename=Path(
                    f"search/{filename}",
                ),
                search_type=SearchType(search_type),
                source_name=source_name,
                source_identifier=source_identifier,
                search_parameters=selection,
                search_script=search_script,
                conversion_script=conversion_script,
                source_prep_scripts=source_prep_scripts,
                comment="",
            )
            self.REVIEW_MANAGER.pp.pprint(add_source)
            self.REVIEW_MANAGER.settings.sources.append(add_source)
            self.REVIEW_MANAGER.save_settings()

            self.REVIEW_MANAGER.create_commit(
                msg=f"Add search source {filename}",
                script_call="colrev search",
                saved_args=saved_args,
            )

        self.main(selection_str="all")

        return

    def main(self, *, selection_str: str) -> None:

        # Reload the settings because the search sources may have been updated
        self.REVIEW_MANAGER.settings = self.REVIEW_MANAGER.load_settings()

        # TODO : when the search_file has been filled only query the last years

        def load_automated_search_sources() -> list:

            AUTOMATED_SOURCES = [
                x for x in self.SOURCES if "endpoint" in x.search_script
            ]

            AUTOMATED_SOURCES_SELECTED = AUTOMATED_SOURCES
            if selection_str is not None:
                if "all" != selection_str:
                    AUTOMATED_SOURCES_SELECTED = [
                        f
                        for f in AUTOMATED_SOURCES
                        if str(f.filename) in selection_str.split(",")
                    ]
                if len(AUTOMATED_SOURCES_SELECTED) == 0:
                    available_options = ", ".join(
                        [str(f.filename) for f in AUTOMATED_SOURCES]
                    )
                    print(f"Error: {selection_str} not in {available_options}")
                    raise NoSearchFeedRegistered()

            for SOURCE in AUTOMATED_SOURCES_SELECTED:
                SOURCE.feed_file = self.REVIEW_MANAGER.path / Path(SOURCE.filename)

            return AUTOMATED_SOURCES_SELECTED

        for SOURCE in load_automated_search_sources():

            params = self.parse_parameters(search_params=SOURCE.search_parameters)

            print()
            self.REVIEW_MANAGER.logger.info(
                f"Retrieve from {SOURCE.source_name}: {params}"
            )

            SEARCH_SCRIPT = self.search_scripts[SOURCE.search_script["endpoint"]]
            SEARCH_SCRIPT.run_search(
                SEARCH=self,
                params=params,
                feed_file=SOURCE.feed_file,
            )

            if SOURCE.feed_file.is_file():
                self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
                    path=str(SOURCE.feed_file)
                )
                self.REVIEW_MANAGER.create_commit(
                    msg="Run search", script_call="colrev search"
                )

        return

    def setup_custom_script(self) -> None:
        import pkgutil
        from colrev_core.settings import SearchSource, SearchType

        filedata = pkgutil.get_data(__name__, "template/custom_search_script.py")
        if filedata:
            with open("custom_search_script.py", "w") as file:
                file.write(filedata.decode("utf-8"))

        self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(path="custom_search_script.py")

        NEW_SOURCE = SearchSource(
            filename=Path("custom_search.bib"),
            search_type=SearchType.DB,
            source_name="custom_search_script",
            source_identifier="TODO",
            search_parameters="TODO",
            search_script={"endpoint": "TODO"},
            conversion_script={"endpoint": "TODO"},
            source_prep_scripts=[{"endpoint": "TODO"}],
            comment="",
        )

        self.REVIEW_MANAGER.settings.sources.append(NEW_SOURCE)
        self.REVIEW_MANAGER.save_settings()

        return

    def view_sources(self) -> None:

        for SOURCE in self.SOURCES:
            self.REVIEW_MANAGER.pp.pprint(SOURCE)

        print("\nOptions:")
        options = ", ".join(list(self.search_scripts.keys()))
        print(f"- endpoints: {options}")
        return


if __name__ == "__main__":
    pass
