#! /usr/bin/env python
import re
import typing
from pathlib import Path

from colrev_core.environment import AdapterManager
from colrev_core.process import Process
from colrev_core.process import ProcessType


class Search(Process):

    from colrev_core.built_in import search as built_in_search

    built_in_scripts: typing.Dict[str, typing.Dict[str, typing.Any]] = {
        "CROSSREF": {
            "endpoint": built_in_search.CrossrefSearchEndpoint,
        },
        "DBLP": {
            "endpoint": built_in_search.DBLPSearchEndpoint,
        },
        "BACKWARD_SEARCH": {
            "endpoint": built_in_search.BackwardSearchEndpoint,
        },
        "COLREV_PROJECT": {
            "endpoint": built_in_search.ColrevProjectSearchEndpoint,
        },
        "INDEX": {
            "endpoint": built_in_search.IndexSearchEndpoint,
        },
        "PDFS": {
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

        self.sources = REVIEW_MANAGER.REVIEW_DATASET.load_sources()

        required_search_scripts = [
            s.source_name for s in REVIEW_MANAGER.settings.search.sources
        ]

        self.search_scripts: typing.Dict[
            str, typing.Dict[str, typing.Any]
        ] = AdapterManager.load_scripts(
            PROCESS=self,
            scripts=required_search_scripts,
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

        self.search_scripts = AdapterManager.load_scripts(
            PROCESS=self,
            scripts=sources,
        )

        if not all(source in self.search_scripts for source in sources):
            violation = [
                source for source in sources if source not in self.search_scripts
            ]
            raise InvalidQueryException(
                f"source {violation} not in available sources "
                f"({self.search_scripts.keys()})"
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

        for source in sources:
            SCRIPT = self.search_scripts[source]["endpoint"]
            SCRIPT.validate_params(query=query)

        # TODO : parse params (which may also raise errors)

        return

    def add_source(self, *, query: str) -> None:

        # TODO : parse query (input format changed to sql-like string)
        # TODO : the search query/syntax translation has to be checked carefully
        # (risk of false-negative search results caused by errors/missing functionality)
        # https://lucene.apache.org/core/2_9_4/queryparsersyntax.html
        # https://github.com/netgen/query-translator/tree/master/lib/Languages/Galach
        # https://github.com/netgen/query-translator
        # https://medlinetranspose.github.io/documentation.html
        # https://sr-accelerator.com/#/help/polyglot

        # Zotero connector:
        # https://github.com/urschrei/pyzotero

        # Start with basic query
        # RETRIEVE * FROM crossref,dblp WHERE digital AND platform
        # Note: corresponds to "digital[all] AND platform[all]"

        saved_args = {"add": f'"{query}"'}

        as_filename = ""
        if " AS " in query:
            as_filename = query[query.find(" AS ") + 4 :]
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

        source_details = self.REVIEW_MANAGER.REVIEW_DATASET.load_sources()

        for source in sources:
            duplicate_source = []
            try:
                duplicate_source = [
                    x
                    for x in source_details
                    if source == x["search_parameters"][0]["endpoint"]
                    and selection == x["search_parameters"][0]["params"]
                ]
            except TypeError:
                pass

            if len(duplicate_source) > 0:
                print(
                    "Source already exists: "
                    f"RETRIEVE * FROM {source} {selection}\nSkipping.\n"
                )
                continue

            if as_filename != "":
                filename = as_filename
            else:
                filename = f"{source}.bib"
                i = 0
                while filename in [x.filename for x in source_details]:
                    i += 1
                    filename = filename[: filename.find("_query") + 6] + f"_{i}.bib"

            feed_file_path = Path.cwd() / Path("search") / Path(filename)
            assert not feed_file_path.is_file()

            # The following must be in line with settings.py/SearchSource
            search_type = "FEED"
            source_identifier = "TODO"
            if source in self.search_scripts:
                source_identifier = self.search_scripts[source][
                    "endpoint"
                ].source_identifier

            # TODO : add "USING script_x" when we add a search_script!
            script = {"endpoint": "bib_pybtex"}
            if search_type == "FEED" and source == "DBLP":
                script = {"endpoint": "bib_pybtex"}
            if search_type == "FEED" and source == "CROSSREF":
                script = {"endpoint": "bib_pybtex"}
            if search_type == "FEED" and source == "BACKWARD_SEARCH":
                script = {"endpoint": "bib_pybtex"}
            if search_type == "FEED" and source == "COLREV_PROJECT":
                script = {"endpoint": "bib_pybtex"}
            if search_type == "FEED" and source == "INDEX":
                script = {"endpoint": "bib_pybtex"}
            if search_type == "FEED" and source == "PDFS":
                script = {"endpoint": "bib_pybtex"}

            # NOTE: for now, the parameters are limited to whole journals.
            source_details = {
                "filename": filename,
                "source_name": source,
                "search_type": search_type,
                "source_identifier": source_identifier,
                "search_parameters": selection,
                "script": script,
                "comment": "",
            }
            self.REVIEW_MANAGER.pp.pprint(source_details)

            self.REVIEW_MANAGER.sources.append(source_details)
            self.REVIEW_MANAGER.save_settings()

            self.REVIEW_MANAGER.create_commit(
                msg=f"Add search source {filename}", saved_args=saved_args
            )

        self.update(selection_str="all")

        return

    def update(self, *, selection_str: str) -> None:
        from colrev_core.settings import SearchType

        # Reload the settings because the search sources may have been updated
        self.REVIEW_MANAGER.settings = self.REVIEW_MANAGER.load_settings()

        # TODO : when the search_file has been filled only query the last years
        sources = self.REVIEW_MANAGER.REVIEW_DATASET.load_sources()

        feed_sources = [x for x in sources if SearchType.FEED == x.search_type]

        if selection_str is not None:
            feed_sources_selected = feed_sources
            if "all" != selection_str:
                feed_sources_selected = [
                    f
                    for f in feed_sources
                    if str(f.filename) in selection_str.split(",")
                ]
            if len(feed_sources_selected) != 0:
                feed_sources = feed_sources_selected
            else:
                available_options = ", ".join([str(f.filename) for f in feed_sources])
                print(f"Error: {selection_str} not in {available_options}")
                return

        for feed_item in feed_sources:
            feed_file = Path.cwd() / Path("search") / Path(feed_item.filename)

            if feed_item.source_name not in self.search_scripts:
                print(
                    "Endpoint not supported:"
                    f" {feed_item.source_identifier} (skipping)"
                )
                continue

            script = self.search_scripts[feed_item.source_name]

            params = self.parse_parameters(search_params=feed_item.search_parameters)
            print()
            self.REVIEW_MANAGER.logger.info(
                f"Retrieve from {feed_item.source_name}: {params}"
            )

            SEARCH_SCRIPT = script["endpoint"]
            SEARCH_SCRIPT.run_search(SEARCH=self, params=params, feed_file=feed_file)

            if feed_file.is_file():
                self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(path=str(feed_file))
                self.REVIEW_MANAGER.create_commit(msg="Run search")

        if len(feed_sources) == 0:
            raise NoSearchFeedRegistered()

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
            search_type=SearchType.FEED,
            source_name="custom_search_script",
            source_identifier="TODO",
            script={"endpoint": "TODO"},
            search_parameters="TODO",
            comment="",
        )

        self.REVIEW_MANAGER.settings.search.sources.append(NEW_SOURCE)
        self.REVIEW_MANAGER.save_settings()

        return

    def view_sources(self) -> None:
        sources = self.REVIEW_MANAGER.REVIEW_DATASET.load_sources()
        for source in sources:
            self.REVIEW_MANAGER.pp.pprint(source)

        print("\nOptions:")
        options = ", ".join(list(self.search_scripts.keys()))
        print(f"- endpoints (FEED): {options}")
        return


class InvalidQueryException(Exception):
    def __init__(self, msg: str):
        self.message = msg
        super().__init__(self.message)


class NoSearchFeedRegistered(Exception):
    """No search feed endpoints registered in settings.json"""

    def __init__(self):
        super().__init__("No search feed endpoints registered in settings.json")


if __name__ == "__main__":
    pass
