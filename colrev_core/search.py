#! /usr/bin/env python
import json
import re
import typing
from datetime import datetime
from pathlib import Path

import bibtexparser
import pandas as pd
import pandasql as ps
import requests
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.customization import convert_to_unicode
from crossref.restful import Journals
from pandasql.sqldf import PandaSQLException

from colrev_core.prep import Preparation
from colrev_core.process import Process
from colrev_core.process import ProcessType


class Search(Process):

    EMAIL = ""
    TIMEOUT = 10

    def __init__(
        self,
        REVIEW_MANAGER,
        notify_state_transition_process=True,
    ):

        super().__init__(
            REVIEW_MANAGER,
            ProcessType.check,
            fun=self.update,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.sources = REVIEW_MANAGER.REVIEW_DATASET.load_sources()

        self.EMAIL = self.REVIEW_MANAGER.config["EMAIL"]
        self.PREPARATION = Preparation(
            REVIEW_MANAGER, notify_state_transition_process=False
        )

        self.search_scripts: typing.List[typing.Dict[str, typing.Any]] = [
            {
                "search_endpoint": "dblp",
                "source_url": "https://dblp.org/",
                "script": self.update_dblp,
            },
            {
                "search_endpoint": "crossref",
                "source_url": "https://crossref.org/",
                "script": self.update_crossref,
            },
            {
                "search_endpoint": "backward",
                "source_url": "",
                "script": self.update_backward,
            },
            {
                "search_endpoint": "project",
                "source_url": "",
                "script": self.update_project,
            },
            {
                "search_endpoint": "index",
                "source_url": "",
                "script": self.update_index,
            },
        ]

    def check_precondition(self) -> None:
        super().require_clean_repo_general()
        return

    def __get_bibtex_writer(self) -> BibTexWriter:

        writer = BibTexWriter()
        writer.contents = ["entries", "comments"]
        writer.display_order = [
            "doi",
            "dblp_key",
            "author",
            "booktitle",
            "journal",
            "title",
            "year",
            "editor",
            "number",
            "pages",
            "series",
            "volume",
            "abstract",
            "book-author",
            "book-group-author",
        ]

        # Note : use this sort order to ensure that the latest entries will be
        # appended at the end and in the same order when rerunning the feed:
        writer.order_entries_by = ("year", "volume", "number", "author", "title")
        writer.add_trailing_comma = True
        writer.align_values = True
        writer.indent = "  "
        return writer

    def update_crossref(self, params, feed_file):

        if "journal_issn" not in params:
            print("Error: journal_issn not in params")
            return
        print(f"Retrieve Crossref: {params}")

        # works = Works()
        # https://api.crossref.org/swagger-ui/index.html#/Works/get_works
        # use FACETS!
        # w1 = works.query(bibliographic='microsourcing')
        # w1 = works.query(
        #     container_title="Journal of the Association for Information Systems"
        # )

        journals = Journals()
        # t = journals.journal('1526-5536')
        # input(feed_item['search_parameters'].split('=')[1])
        w1 = journals.works(params["journal_issn"]).query()
        # for it in t:
        #     pp.pprint(it)
        #     input('stop')

        available_ids = []
        max_id = 1
        if not feed_file.is_file():
            feed_db = BibDatabase()
            records = []
        else:
            with open(feed_file) as bibtex_file:
                feed_db = BibTexParser(
                    customization=convert_to_unicode,
                    ignore_nonstandard_types=True,
                    common_strings=True,
                ).parse_file(bibtex_file, partial=True)
                records = feed_db.entries
            available_ids = [x["doi"] for x in records if "doi" in x]
            max_id = max([int(x["ID"]) for x in records] + [1]) + 1

        for item in w1:
            if "DOI" in item:
                if item["DOI"].upper() not in available_ids:
                    record = self.PREPARATION.crossref_json_to_record(item)

                    if "selection_clause" in params:
                        res = []
                        try:
                            rec_df = pd.DataFrame.from_records([record])
                            print(rec_df)
                            query = "SELECT * FROM rec_df WHERE"
                            f"{params['selection_clause']}"
                            res = ps.sqldf(query, locals())
                        except PandaSQLException as e:
                            print(e)
                            pass

                        if len(res) == 0:
                            continue

                    print(record["doi"])
                    record["ID"] = str(max_id).rjust(6, "0")
                    if "ENTRYTYPE" not in record:
                        record["ENTRYTYPE"] = "misc"
                    record["metadata_source"] = "CROSSREF"
                    record = self.PREPARATION.get_link_from_doi(record)
                    available_ids.append(record["doi"])
                    records.append(record)
                    max_id += 1
        # Note : we may have to set temporary IDs
        # (and replace them after the following sort operation) ?!
        records = sorted(
            records,
            key=lambda e: (
                e.get("year", ""),
                e.get("volume", ""),
                e.get("number", ""),
                e.get("author", ""),
                e.get("title", ""),
            ),
        )

        # TODO: append-mode (file-basis) instead of override?
        feed_file.parents[0].mkdir(parents=True, exist_ok=True)
        feed_db.entries = records
        with open(feed_file, "w") as fi:
            fi.write(bibtexparser.dumps(feed_db, self.__get_bibtex_writer()))

        return

    def get_venue_abbreviated(self, venue_key: str) -> str:
        venue_abbrev = ""

        api_url = "https://dblp.org/search/publ/api?q="
        headers = {"user-agent": f"{__name__}  (mailto:{self.EMAIL})"}
        query = (
            venue_key.replace("journals/", "journal /").replace("conf/", "Conference /")
            + "+"
            + str(2020)
        )
        url = api_url + query.replace(" ", "+") + f"&format=json&h={500}&f={0}"
        print(url)
        ret = requests.get(url, headers=headers, timeout=self.TIMEOUT)
        ret.raise_for_status()
        if ret.status_code == 500:
            return ""

        data = json.loads(ret.text)
        if "hits" not in data["result"]:
            print("no hits")
            return ""

        if "hit" not in data["result"]["hits"]:
            print("no hit")
            return ""
        hits = data["result"]["hits"]["hit"]

        for hit in hits:
            item = hit["info"]

            retrieved_record = self.PREPARATION.dblp_json_to_record(item)
            if f"{venue_key}/" in retrieved_record["dblp_key"]:
                venue_abbrev = retrieved_record.get(
                    "journal", retrieved_record.get("booktitle", "")
                )

        return venue_abbrev

    def update_dblp(self, params, feed_file):

        # https://dblp.org/search/publ/api?q=ADD_TITLE&format=json

        if "venue_key" not in params["scope"]:
            print("Error: venue_key not in params")
            return
        if "journal_abbreviated" not in params["scope"]:
            print("Error: journal_abbreviated not in params")
            return
        print(f"Retrieve DBLP: {params}")

        available_ids = []
        max_id = 1
        if not feed_file.is_file():
            feed_db = BibDatabase()
            records = []
        else:
            with open(feed_file) as bibtex_file:
                feed_db = BibTexParser(
                    customization=convert_to_unicode,
                    ignore_nonstandard_types=True,
                    common_strings=True,
                ).parse_file(bibtex_file, partial=True)
                records = feed_db.entries
            available_ids = [x["dblp_key"] for x in records if "dblp_key" in x]
            max_id = max([int(x["ID"]) for x in records] + [1]) + 1

        try:
            api_url = "https://dblp.org/search/publ/api?q="

            # Note : journal_abbreviated is the abbreviated version
            # TODO : tbd how the abbreviated version can be retrieved
            # https://dblp.org/rec/journals/jais/KordzadehW17.html?view=bibtex

            headers = {"user-agent": f"{__name__}  (mailto:{self.EMAIL})"}
            start = 1980
            if len(records) > 100:
                start = datetime.now().year - 1
            for year in range(start, datetime.now().year):
                print(year)
                query = params["scope"]["journal_abbreviated"] + "+" + str(year)
                # query = params['scope']["venue_key"] + "+" + str(year)
                f = 0
                batch_size = 250
                while True:
                    url = (
                        api_url
                        + query.replace(" ", "+")
                        + f"&format=json&h={batch_size}&f={f}"
                    )
                    f += batch_size
                    print(url)
                    ret = requests.get(url, headers=headers, timeout=self.TIMEOUT)
                    ret.raise_for_status()
                    if ret.status_code == 500:
                        return

                    data = json.loads(ret.text)
                    if "hits" not in data["result"]:
                        print("no hits")
                        break
                    if "hit" not in data["result"]["hits"]:
                        print("no hit")
                        break
                    hits = data["result"]["hits"]["hit"]

                    for hit in hits:
                        item = hit["info"]

                        retrieved_record = self.PREPARATION.dblp_json_to_record(item)

                        # TODO: include more checks
                        if (
                            f"{params['scope']['venue_key']}/"
                            not in retrieved_record["dblp_key"]
                        ):
                            continue
                        retrieved_record["dblp_key"] = (
                            "https://dblp.org/rec/" + retrieved_record["dblp_key"]
                        )

                        if retrieved_record["dblp_key"] not in available_ids:
                            retrieved_record["ID"] = str(max_id).rjust(6, "0")
                            if retrieved_record.get("ENTRYTYPE", "") not in [
                                "article",
                                "inproceedings",
                            ]:
                                continue
                                # retrieved_record["ENTRYTYPE"] = "misc"
                            if "pages" in retrieved_record:
                                del retrieved_record["pages"]
                            available_ids.append(retrieved_record["dblp_key"])
                            retrieved_record["metadata_source"] = "DBLP"
                            records = [
                                {
                                    k: v.replace("\n", "").replace("\r", "")
                                    for k, v in r.items()
                                }
                                for r in records
                            ]
                            records.append(retrieved_record)
                            max_id += 1

                    # break # TODO : remove

                    # Note : we may have to set temporary IDs
                    # (and replace them after the following sort operation) ?!
                    records = sorted(
                        records,
                        key=lambda e: (
                            e.get("year", ""),
                            e.get("volume", ""),
                            e.get("number", ""),
                            e.get("author", ""),
                            e.get("title", ""),
                        ),
                    )

                    # TODO: append-mode (file-basis) instead of override?
                    feed_file.parents[0].mkdir(parents=True, exist_ok=True)
                    if len(records) == 0:
                        continue
                    feed_db.entries = records
                    with open(feed_file, "w") as fi:
                        fi.write(
                            bibtexparser.dumps(feed_db, self.__get_bibtex_writer())
                        )

        except requests.exceptions.HTTPError:
            pass
        except UnicodeEncodeError:
            print("UnicodeEncodeError - this needs to be fixed at some time")
            pass
        except requests.exceptions.ReadTimeout:
            pass
        except requests.exceptions.ConnectionError:
            pass

        return

    def update_backward(self) -> None:

        return

    def update_project(self, params: dict, feed_file: Path) -> None:
        from colrev_core.review_manager import ReviewManager
        from colrev_core.load import Loader

        if not feed_file.is_file():
            feed_db = BibDatabase()
            records = []
            imported_ids = []
        else:
            with open(feed_file) as bibtex_file:
                feed_db = BibTexParser(
                    customization=convert_to_unicode,
                    ignore_nonstandard_types=True,
                    common_strings=True,
                ).parse_file(bibtex_file, partial=True)
                records = feed_db.entries
            imported_ids = [x["ID"] for x in records]

        PROJECT_REVIEW_MANAGER = ReviewManager(params["scope"]["url"])
        Loader(
            PROJECT_REVIEW_MANAGER,
            keep_ids=False,
            notify_state_transition_process=False,
        )
        records_to_import = PROJECT_REVIEW_MANAGER.REVIEW_DATASET.load_records()
        records_to_import = [
            x for x in records_to_import if x["ID"] not in imported_ids
        ]
        records_to_import = [
            {k: str(v) for k, v in r.items()} for r in records_to_import
        ]
        for record_to_import in records_to_import:
            if "selection_clause" in params:
                res = []
                try:
                    rec_df = pd.DataFrame.from_records([record_to_import])
                    query = f"SELECT * FROM rec_df WHERE {params['selection_clause']}"
                    res = ps.sqldf(query, locals())
                except PandaSQLException as e:
                    print(e)
                    pass

                if len(res) == 0:
                    continue
            records = records + [record_to_import]

        # records = records + records_to_import
        keys_to_drop = [
            "status",
            "origin",
            "excl_criteria",
            "manual_non_duplicate",
            "excl_criteria",
            "metadata_source",
        ]
        records = [
            {key: item[key] for key in item.keys() if key not in keys_to_drop}
            for item in records
        ]

        feed_file.parents[0].mkdir(parents=True, exist_ok=True)
        feed_db.entries = records
        with open(feed_file, "w") as fi:
            fi.write(bibtexparser.dumps(feed_db, self.__get_bibtex_writer()))

        return

    def update_index(self) -> None:

        return

    def parse_sources(self, query: str) -> list:
        if "WHERE " in query:
            sources = query[query.find("FROM ") + 5 : query.find(" WHERE")].split(",")
        elif "SCOPE " in query:
            sources = query[query.find("FROM ") + 5 : query.find(" SCOPE")].split(",")
        sources = [s.lstrip().rstrip() for s in sources]
        return sources

    def parse_parameters(self, search_params: dict) -> dict:

        query = search_params["params"]
        params = {}
        selection_str = query
        if "WHERE " in query:
            selection_str = query[query.find("WHERE ") + 6 : query.find("SCOPE ")]
            if "[" not in selection_str:
                # parse simple selection
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
            # else: parse complex selection
            params["selection_clause"] = selection_str

        if "SCOPE " in query:
            # selection_str = selection_str[: selection_str.find("SCOPE ")]
            scope_part_str = query[query.find("SCOPE ") + 6 :]
            params["scope"] = {}  # type: ignore
            for scope_item in scope_part_str.split(" AND "):
                key, value = scope_item.split("=")
                if "url" in key:
                    if "dblp" == search_params["endpoint"]:
                        params["scope"]["venue_key"] = (  # type: ignore
                            value.replace("/index.html", "")
                            .replace("https://dblp.org/db/", "")
                            .replace("url=", "")
                            .replace("'", "")
                        )
                        continue
                params["scope"][key] = value.rstrip("'").lstrip("'")  # type: ignore

        return params

    def add_source(self, query: str) -> None:

        # TODO : parse query (input format changed to sql-like string)
        # TODO: the search query/syntax translation has to be checked carefully
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
        query = query.replace("RETRIEVE ", "SELECT ")

        # TODO : check whether url exists (dblp, project, ...)
        sources = self.parse_sources(query)
        if "WHERE " in query:
            selection = query[query.find("WHERE ") :]
        elif "SCOPE " in query:
            selection = query[query.find("SCOPE ") :]
        else:
            print("Error: missing WHERE or SCOPE clause in query")
            return

        for source in sources:
            # TODO : check whether it already exists
            source_details = self.REVIEW_MANAGER.REVIEW_DATASET.load_sources()
            filename = f"{source}_query.bib"
            i = 0
            while filename in [x["filename"] for x in source_details]:
                i += 1
                filename = filename[: filename.find("_query") + 6] + f"_{i}.bib"

            # NOTE: for now, the parameters are limited to whole journals.
            source_details = {
                "filename": filename,
                "search_type": "FEED",
                "source_name": source,
                "source_url": "",
                "search_parameters": [{"endpoint": source, "params": selection}],
                "comment": "",
            }
            self.REVIEW_MANAGER.pp.pprint(source_details)

            self.REVIEW_MANAGER.REVIEW_DATASET.append_sources(source_details)
            self.REVIEW_MANAGER.create_commit(
                f"Add search source {filename}", saved_args=saved_args
            )

        self.update()

        return

    def update(self, selection_str: str = "") -> None:

        # TODO: if selection: --selected DBLP,CROSSREF,...
        # iterate over self.sources and call update_crossref(), update_dblp(), ...

        # TODO: when the search_file has been filled only query the last years
        # in the next calls?"

        sources = self.REVIEW_MANAGER.REVIEW_DATASET.load_sources()
        search_dir = Path.cwd() / Path("search")
        feed_paths = [x for x in sources if "FEED" == x["search_type"]]
        for feed_item in feed_paths:
            # self.REVIEW_MANAGER.pp.pprint(feed_item)

            feed_file = search_dir / Path(feed_item["filename"])
            search_param = feed_item["search_parameters"][0]
            if search_param["endpoint"] not in [
                x["search_endpoint"] for x in self.search_scripts
            ]:
                print(
                    f'Endpoint not supported: {feed_item["search_endpoint"]} (skipping)'
                )
                continue

            script = [
                s
                for s in self.search_scripts
                if s["search_endpoint"] == search_param["endpoint"]
            ].pop()
            params = self.parse_parameters(search_param)
            script["script"](params, feed_file)

            self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(str(feed_file))
            self.REVIEW_MANAGER.create_commit("Run search")

        return


if __name__ == "__main__":
    pass
