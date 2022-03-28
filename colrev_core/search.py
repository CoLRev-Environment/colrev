#! /usr/bin/env python
import hashlib
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
                "script": self.search_dblp,
                "validate_params": self.validate_dblp_params,
                "mode": "all",
            },
            {
                "search_endpoint": "crossref",
                "source_url": "https://crossref.org/",
                "script": self.search_crossref,
                "validate_params": self.validate_crossref_params,
                "mode": "all",
            },
            {
                "search_endpoint": "backward_search",
                "source_url": "",
                "script": self.search_backward,
                "validate_params": self.validate_backwardsearch_params,
                "mode": "individual",
            },
            {
                "search_endpoint": "project",
                "source_url": "",
                "script": self.search_project,
                "validate_params": self.validate_project_params,
                "mode": "individual",
            },
            {
                "search_endpoint": "index",
                "source_url": "",
                "script": self.search_index,
                "validate_params": self.validate_index_params,
                "mode": "individual",
            },
            {
                "search_endpoint": "pdfs_directory",
                "source_url": "",
                "script": self.search_pdfs_dir,
                "validate_params": self.validate_pdfs_dir_params,
                "mode": "individual",
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

    def search_crossref(self, params, feed_file):

        if "journal_issn" not in params["scope"]:
            print("Error: journal_issn not in params")
            return

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
        w1 = journals.works(params["scope"]["journal_issn"]).query()
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
            max_id = max([int(x["ID"]) for x in records if x["ID"].isdigit()] + [1]) + 1

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
                        except PandaSQLException:
                            # print(e)
                            pass

                        if len(res) == 0:
                            continue

                    # Note : do not download "empty" records
                    if "" == record.get("author", "") and "" == record.get("title", ""):
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

    def search_dblp(self, params, feed_file):

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
            max_id = max([int(x["ID"]) for x in records if x["ID"].isdigit()] + [1]) + 1

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

    def search_backward(self, params: dict, feed_file: Path) -> None:
        from colrev_core.process import RecordState
        from colrev_core import grobid_client

        if not self.REVIEW_MANAGER.paths["MAIN_REFERENCES"].is_file():
            print("No records imported. Cannot run backward search yet.")
            return

        grobid_client.start_grobid(self.REVIEW_MANAGER)
        print(params)
        print(feed_file)
        print(
            "TODO: one or multiple source entries? "
            "(general search query vs individual source descriptions...) \n "
            "Or maybe use a pattern to link? e.g., files=backward_search*.bib "
            "(this would allow us to avoid redundant queries...)"
        )

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()

        # default: rev_included/rev_synthesized and no selection clauses
        for record in records:
            if record["status"] not in [
                RecordState.rev_included,
                RecordState.rev_synthesized,
            ]:
                continue
            print(record["ID"])

            if not Path(record["file"]).is_file():
                print(f'File not found for {record["ID"]}')
                continue

            options = {"consolidateHeader": "0", "consolidateCitations": "0"}
            r = requests.post(
                grobid_client.get_grobid_url() + "/api/processReferences",
                files=dict(input=open(record["file"], "rb")),
                data=options,
                headers={"Accept": "application/x-bibtex"},
            )

            bib_filename = self.REVIEW_MANAGER.paths["SEARCHDIR_RELATIVE"] / Path(
                f"backward_search_{record['ID']}.bib"
            )
            bib_content = r.text.encode("utf-8")
            with open(bib_filename, "wb") as f:
                f.write(bib_content)

            self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(str(bib_filename))

        self.REVIEW_MANAGER.create_commit("Backward search")

        return

    def search_project(self, params: dict, feed_file: Path) -> None:
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
                except PandaSQLException:
                    # print(e)
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
            "manual_duplicate",
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

    def search_index(self, params: dict, feed_file: Path) -> None:

        assert "selection_clause" in params

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

        from colrev_core.environment import LocalIndex

        LOCAL_INDEX = LocalIndex(self.REVIEW_MANAGER)

        def retrieve_from_index(params) -> typing.List[typing.Dict]:
            # Note: we retrieve colrev_IDs and full records afterwards
            # because the os.sql.query throws errors when selecting
            # complex fields like lists of alsoKnownAs fields
            query = (
                f"SELECT colrev_ID FROM {LOCAL_INDEX.RECORD_INDEX} "
                f"WHERE {params['selection_clause']}"
            )
            resp = LOCAL_INDEX.os.sql.query(body={"query": query})
            IDs_to_retrieve = [item for sublist in resp["rows"] for item in sublist]

            records_to_import = []
            for ID_to_retrieve in IDs_to_retrieve:

                hash = hashlib.sha256(ID_to_retrieve.encode("utf-8")).hexdigest()
                res = LOCAL_INDEX.os.get(index=LOCAL_INDEX.RECORD_INDEX, id=hash)
                record_to_import = res["_source"]
                record_to_import = {k: str(v) for k, v in record_to_import.items()}
                record_to_import = {
                    k: v for k, v in record_to_import.items() if "None" != v
                }
                record_to_import = LOCAL_INDEX.prep_record_for_return(record_to_import)
                records_to_import.append(record_to_import)

            return records_to_import

        records_to_import = retrieve_from_index(params)

        records_to_import = [r for r in records_to_import if r]
        records_to_import = [
            x for x in records_to_import if x["ID"] not in imported_ids
        ]
        records = records + records_to_import

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

        if len(records) > 0:
            feed_file.parents[0].mkdir(parents=True, exist_ok=True)
            feed_db.entries = records
            with open(feed_file, "w") as fi:
                fi.write(bibtexparser.dumps(feed_db, self.__get_bibtex_writer()))
        else:
            print("No records found")

        return

    def search_pdfs_dir(self, params: dict, feed_file: Path) -> None:
        from collections import Counter
        from p_tqdm import p_map
        import imagehash
        from pdf2image import convert_from_path
        from colrev_core import grobid_client

        from colrev_core.tei import TEI
        from colrev_core.tei import TEI_Exception
        from pdfminer.pdfdocument import PDFDocument
        from pdfminer.pdfinterp import resolve1
        from pdfminer.pdfparser import PDFParser
        from colrev_core.pdf_prep import PDF_Preparation

        from colrev_core.process import RecordState

        skip_duplicates = True

        self.PDF_PREPARATION = PDF_Preparation(
            self.REVIEW_MANAGER, notify_state_transition_process=False
        )

        def update_if_pdf_renamed(
            x: dict, records: typing.List[typing.Dict], search_source: Path
        ) -> bool:
            UPDATED = True
            NOT_UPDATED = False

            c_rec_l = [
                r
                for r in records
                if f"{search_source}/{x['ID']}" in r["origin"].split(";")
            ]
            if len(c_rec_l) == 1:
                c_rec = c_rec_l.pop()
                if "pdf_hash" in c_rec:
                    pdf_hash = c_rec["pdf_hash"]
                    pdf_path = Path(x["file"]).parents[0]
                    potential_pdfs = pdf_path.glob("*.pdf")
                    # print(f'search pdf_hash {pdf_hash}')
                    for potential_pdf in potential_pdfs:
                        hash_potential_pdf = str(
                            imagehash.average_hash(
                                convert_from_path(
                                    potential_pdf, first_page=0, last_page=1
                                )[0],
                                hash_size=32,
                            )
                        )
                        # print(f'hash_potential_pdf {hash_potential_pdf}')
                        if pdf_hash == hash_potential_pdf:
                            x["file"] = str(potential_pdf)
                            c_rec["file"] = str(potential_pdf)
                            return UPDATED
            return NOT_UPDATED

        def remove_records_if_pdf_no_longer_exists() -> None:

            self.REVIEW_MANAGER.logger.debug("Checking for PDFs that no longer exist")

            if not feed_file.is_file():
                return
            writer = self.REVIEW_MANAGER.REVIEW_DATASET.get_bibtex_writer()

            with open(feed_file) as target_db:
                search_db = BibTexParser(
                    customization=convert_to_unicode,
                    ignore_nonstandard_types=False,
                    common_strings=True,
                ).parse_file(target_db, partial=True)

            records = []
            if self.REVIEW_MANAGER.paths["MAIN_REFERENCES"].is_file():
                records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()

            to_remove: typing.List[str] = []
            for x in search_db.entries:
                if not Path(x["file"]).is_file():
                    if records:
                        updated = update_if_pdf_renamed(x, records, feed_file)
                        if updated:
                            continue
                    to_remove = to_remove + [
                        f"{feed_file.name}/{x['ID']}" for x in search_db.entries
                    ]

            search_db.entries = [
                x for x in search_db.entries if Path(x["file"]).is_file()
            ]
            if len(search_db.entries) != 0:
                bibtex_str = bibtexparser.dumps(search_db, writer)
                with open(feed_file, "w") as f:
                    f.write(bibtex_str)

            self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
                str(feed_file.parent / feed_file.name)
            )

            if self.REVIEW_MANAGER.paths["MAIN_REFERENCES"].is_file():
                # Note : origins may contain multiple links
                # but that should not be a major issue in indexing repositories

                to_remove = []
                source_ids = [x["ID"] for x in search_db.entries]
                for record in records:
                    if str(feed_file.name) in record["origin"]:
                        if (
                            record["origin"].split(";")[0].split("/")[1]
                            not in source_ids
                        ):
                            print("REMOVE " + record["origin"])
                            to_remove.append(record["origin"])

                for r in to_remove:
                    self.REVIEW_MANAGER.logger.debug(
                        f"remove from index (PDF path no longer exists): {r}"
                    )
                    self.REVIEW_MANAGER.report_logger.info(
                        f"remove from index (PDF path no longer exists): {r}"
                    )

                records = [x for x in records if x["origin"] not in to_remove]
                self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)
                self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

            return

        def get_pdf_links(bib_file: Path) -> list:
            pdf_list = []
            if bib_file.is_file():
                with open(bib_file) as f:
                    line = f.readline()
                    while line:
                        if "file" == line.lstrip()[:4]:
                            file = line[line.find("{") + 1 : line.rfind("}")]
                            pdf_list.append(Path(file))
                        line = f.readline()
            return pdf_list

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

        path = Path(params["scope"]["path"])

        remove_records_if_pdf_no_longer_exists()

        indexed_pdf_paths = get_pdf_links(feed_file)
        #  + get_pdf_links(self.REVIEW_MANAGER.paths["MAIN_REFERENCES"])

        indexed_pdf_path_str = "\n  ".join([str(x) for x in indexed_pdf_paths])
        self.REVIEW_MANAGER.logger.debug(f"indexed_pdf_paths: {indexed_pdf_path_str}")

        overall_pdfs = path.glob("**/*.pdf")

        # Note: sets are more efficient:
        pdfs_to_index = list(set(overall_pdfs).difference(set(indexed_pdf_paths)))

        def get_pdf_hash(path) -> typing.List[str]:
            current_hash = imagehash.average_hash(
                convert_from_path(str(path), first_page=0, last_page=1)[0],
                hash_size=32,
            )
            return [str(path), str(current_hash)]

        if skip_duplicates:
            pdfs_hashed = p_map(get_pdf_hash, pdfs_to_index)
            pdf_hashes = [x[1] for x in pdfs_hashed]
            duplicate_hashes = [
                item for item, count in Counter(pdf_hashes).items() if count > 1
            ]
            duplicate_pdfs = [
                str(path) for path, hash in pdfs_hashed if hash in duplicate_hashes
            ]
            pdfs_to_index = [p for p in pdfs_to_index if str(p) not in duplicate_pdfs]

        broken_filepaths = [str(x) for x in pdfs_to_index if ";" in str(x)]
        if len(broken_filepaths) > 0:
            broken_filepath_str = "\n ".join(broken_filepaths)
            self.REVIEW_MANAGER.logger.error(
                f'skipping PDFs with ";" in filepath: {broken_filepath_str}'
            )
            pdfs_to_index = [x for x in pdfs_to_index if str(x) not in broken_filepaths]

        filepaths_to_skip = [
            str(x)
            for x in pdfs_to_index
            if "_ocr.pdf" == str(x)[-8:]
            or "_wo_cp.pdf" == str(x)[-10:]
            or "_wo_lp.pdf" == str(x)[-10:]
            or "_backup.pdf" == str(x)[-11:]
        ]
        if len(filepaths_to_skip) > 0:
            fp_to_skip_str = "\n ".join(filepaths_to_skip)
            self.REVIEW_MANAGER.logger.info(
                f"Skipping PDFs with _ocr.pdf/_wo_cp.pdf: {fp_to_skip_str}"
            )
            pdfs_to_index = [
                x for x in pdfs_to_index if str(x) not in filepaths_to_skip
            ]

        # pdfs_to_index = list(set(overall_pdfs) - set(indexed_pdf_paths))
        # pdfs_to_index = ['/home/path/file.pdf']
        pdfs_to_index_str = "\n  ".join([str(x) for x in pdfs_to_index])
        self.REVIEW_MANAGER.logger.debug(f"pdfs_to_index: {pdfs_to_index_str}")

        if len(pdfs_to_index) > 0:
            grobid_client.start_grobid(self.REVIEW_MANAGER)
        else:
            self.REVIEW_MANAGER.logger.info("No additional PDFs to index")
            return

        def update_fields_based_on_pdf_dirs(record: dict) -> dict:

            if "params" not in params:
                return record

            if "journal" in params["params"]:
                record["journal"] = params["params"]["journal"]
                record["ENTRYTYPE"] = "article"

            if "conference" in params["params"]:
                record["booktitle"] = params["params"]["conference"]
                record["ENTRYTYPE"] = "inproceedings"

            if "sub_dir_pattern" in params["params"]:
                sub_dir_pattern = params["params"]["sub_dir_pattern"]
                assert sub_dir_pattern in ["NA", "volume_number", "year", "volume"]

                partial_path = Path(record["file"]).parents[0].stem
                if "year" == sub_dir_pattern:
                    r_sub_dir_pattern = re.compile("([1-3][0-9]{3})")
                    partial_path = Path(record["file"]).parents[0].stem
                    # Note: for year-patterns, we allow subfolders
                    # (eg., conference tracks)
                    partial_path = str(Path(record["file"]).parents[0]).replace(
                        params["scope"]["path"], ""
                    )
                    match = r_sub_dir_pattern.search(str(partial_path))
                    if match is not None:
                        year = match.group(1)
                        record["year"] = year

                if "volume_number" == sub_dir_pattern:
                    r_sub_dir_pattern = re.compile("([0-9]{1,3})_([0-9]{1,2})")
                    match = r_sub_dir_pattern.search(str(partial_path))
                    if match is not None:
                        volume = match.group(1)
                        number = match.group(2)
                        record["volume"] = volume
                        record["number"] = number
                    else:
                        # sometimes, journals switch...
                        r_sub_dir_pattern = re.compile("([0-9]{1,3})")
                        match = r_sub_dir_pattern.search(str(partial_path))
                        if match is not None:
                            volume = match.group(1)
                            record["volume"] = volume

                if "volume" == sub_dir_pattern:
                    r_sub_dir_pattern = re.compile("([0-9]{1,4})")
                    match = r_sub_dir_pattern.search(str(partial_path))
                    if match is not None:
                        volume = match.group(1)
                        record["volume"] = volume

            return record

        # curl -v --form input=@./profit.pdf localhost:8070/api/processHeaderDocument
        # curl -v --form input=@./thefile.pdf -H "Accept: application/x-bibtex"
        # -d "consolidateHeader=0" localhost:8070/api/processHeaderDocument
        def get_record_from_pdf_grobid(record) -> dict:
            if RecordState.md_prepared == record.get("status", "NA"):
                return record
            grobid_client.check_grobid_availability()

            pdf_path = Path(record["file"])

            # Note: activate the following when new grobid version is released (> 0.7)
            # Note: we have more control and transparency over the consolidation
            # if we do it in the colrev_core process
            # header_data = {"consolidateHeader": "0"}

            # # https://github.com/kermitt2/grobid/issues/837
            # r = requests.post(
            #     grobid_client.get_grobid_url() + "/api/processHeaderDocument",
            #     headers={"Accept": "application/x-bibtex"},
            #     params=header_data,
            #     files=dict(input=open(pdf_path, "rb")),
            # )

            # if 200 == r.status_code:
            #     parser = BibTexParser(customization=convert_to_unicode)
            #     db = bibtexparser.loads(r.text, parser=parser)
            #     record = db.entries[0]
            #     return record
            # if 500 == r.status_code:
            #     self.REVIEW_MANAGER.logger.error(f"Not a readable
            #           pdf file: {pdf_path.name}")
            #     print(f"Grobid: {r.text}")
            #     return {}

            # print(f"Status: {r.status_code}")
            # print(f"Response: {r.text}")
            # return {}

            TEI_INSTANCE = TEI(
                self.REVIEW_MANAGER,
                pdf_path=pdf_path,
                notify_state_transition_process=False,
            )

            extracted_record = TEI_INSTANCE.get_metadata()

            for key, val in extracted_record.items():
                if val:
                    record[key] = str(val)

            fp = open(pdf_path, "rb")
            parser = PDFParser(fp)
            doc = PDFDocument(parser)

            if record.get("title", "NA") in ["NA", ""]:
                if "Title" in doc.info[0]:
                    try:
                        record["title"] = doc.info[0]["Title"].decode("utf-8")
                    except UnicodeDecodeError:
                        pass
            if record.get("author", "NA") in ["NA", ""]:
                if "Author" in doc.info[0]:
                    try:
                        pdf_md_author = doc.info[0]["Author"].decode("utf-8")
                        if (
                            "Mirko Janc" not in pdf_md_author
                            and "wendy" != pdf_md_author
                            and "yolanda" != pdf_md_author
                        ):
                            record["author"] = pdf_md_author
                    except UnicodeDecodeError:
                        pass

            if "abstract" in record:
                del record["abstract"]
            if "keywords" in record:
                del record["keywords"]

            # to allow users to update/reindex with newer version:
            record["grobid-version"] = self.REVIEW_MANAGER.docker_images[
                "lfoppiano/grobid"
            ]
            return record

        def index_pdf(pdf_path: Path) -> dict:

            self.REVIEW_MANAGER.report_logger.info(pdf_path)
            self.REVIEW_MANAGER.logger.info(pdf_path)

            record: typing.Dict[str, typing.Any] = {
                "file": str(pdf_path),
                "ENTRYTYPE": "misc",
            }
            try:
                record = get_record_from_pdf_grobid(record)

                file = open(pdf_path, "rb")
                parser = PDFParser(file)
                document = PDFDocument(parser)
                pages_in_file = resolve1(document.catalog["Pages"])["Count"]
                if pages_in_file < 6:
                    record = self.PDF_PREPARATION.get_text_from_pdf(record, PAD=40)
                    if "text_from_pdf" in record:
                        text: str = record["text_from_pdf"]
                        if "bookreview" in text.replace(" ", "").lower():
                            record["ENTRYTYPE"] = "misc"
                            record["note"] = "Book review"
                        if "erratum" in text.replace(" ", "").lower():
                            record["ENTRYTYPE"] = "misc"
                            record["note"] = "Erratum"
                        if "correction" in text.replace(" ", "").lower():
                            record["ENTRYTYPE"] = "misc"
                            record["note"] = "Correction"
                        if "contents" in text.replace(" ", "").lower():
                            record["ENTRYTYPE"] = "misc"
                            record["note"] = "Contents"
                        if "withdrawal" in text.replace(" ", "").lower():
                            record["ENTRYTYPE"] = "misc"
                            record["note"] = "Withdrawal"
                        del record["text_from_pdf"]
                    # else:
                    #     print(f'text extraction error in {record["ID"]}')
                    if "pages_in_file" in record:
                        del record["pages_in_file"]

                record = {k: v for k, v in record.items() if v is not None}
                record = {k: v for k, v in record.items() if v != "NA"}

                record["file"] = str(pdf_path)

                # add details based on path
                record = update_fields_based_on_pdf_dirs(record)

            except TEI_Exception:
                pass

            return record

        def get_last_ID(bib_file: Path) -> str:
            current_ID = "1"
            if bib_file.is_file():
                with open(bib_file) as f:
                    line = f.readline()
                    while line:
                        if "@" in line[:3]:
                            current_ID = line[line.find("{") + 1 : line.rfind(",")]
                        line = f.readline()
            return current_ID

        batch_size = 10
        pdf_batches = [
            pdfs_to_index[i * batch_size : (i + 1) * batch_size]
            for i in range((len(pdfs_to_index) + batch_size - 1) // batch_size)
        ]

        for pdf_batch in pdf_batches:

            print("\n")
            lenrec = len(indexed_pdf_paths)
            if len(list(overall_pdfs)) > 0:
                self.REVIEW_MANAGER.logger.info(
                    f"Number of indexed records: {lenrec} of {len(list(overall_pdfs))} "
                    f"({round(lenrec/len(list(overall_pdfs))*100, 2)}%)"
                )

            new_records = []

            for pdf_path in pdf_batch:
                new_records.append(index_pdf(pdf_path))
            # if self.REVIEW_MANAGER.config["DEBUG_MODE"]:
            # else:
            #     # new_record_db.entries = p_map(self.index_pdf, pdf_batch)
            #     # p = Pool(ncpus=4)
            #     # new_records = p.map(index_pdf, pdf_batch)
            #     new_records = p_map(index_pdf, pdf_batch)

            if 0 != len(new_records):
                ID = int(get_last_ID(feed_file))
                for new_r in new_records:
                    indexed_pdf_paths.append(new_r["file"])
                    ID += 1
                    new_r["ID"] = f"{ID}".rjust(10, "0")

                    if "status" in new_r:
                        if "CURATED" != new_r.get("metadata_source", "NA"):
                            del new_r["status"]
                        else:
                            new_r["status"] = str(new_r["status"])

            records = records + new_records

        if len(records) > 0:
            feed_file.parents[0].mkdir(parents=True, exist_ok=True)
            feed_db.entries = records
            with open(feed_file, "w") as fi:
                fi.write(bibtexparser.dumps(feed_db, self.__get_bibtex_writer()))
        else:
            print("No records found")

        return

    def parse_sources(self, query: str) -> list:
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

    def parse_parameters(self, search_params: dict) -> dict:

        query = search_params["params"]
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
                    if "dblp" == search_params["endpoint"]:
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

    def validate_dblp_params(self, query: str) -> None:

        if " SCOPE " not in query:
            raise InvalidQueryException("DBLP queries require a SCOPE section")

        scope = query[query.find(" SCOPE ") :]
        if "venue_key" not in scope:
            raise InvalidQueryException(
                "DBLP queries require a venue_key in the SCOPE section"
            )
        if "journal_abbreviated" not in scope:
            raise InvalidQueryException(
                "DBLP queries require a journal_abbreviated field in the SCOPE section"
            )

        return

    def validate_crossref_params(self, query: str) -> None:
        if " SCOPE " not in query:
            raise InvalidQueryException("CROSSREF queries require a SCOPE section")

        scope = query[query.find(" SCOPE ") :]
        if "journal_issn" not in scope:
            raise InvalidQueryException(
                "CROSSREF queries require a journal_issn field in the SCOPE section"
            )

        return

    def validate_backwardsearch_params(self, query: str) -> None:
        return

    def validate_project_params(self, query: str) -> None:
        if " SCOPE " not in query:
            raise InvalidQueryException("PROJECT queries require a SCOPE section")

        scope = query[query.find(" SCOPE ") :]
        if "url" not in scope:
            raise InvalidQueryException(
                "PROJECT queries require a url field in the SCOPE section"
            )

        return

    def validate_index_params(self, query: str) -> None:
        return

    def validate_pdfs_dir_params(self, query: str) -> None:
        if " SCOPE " not in query:
            raise InvalidQueryException("PDFS_DIR queries require a SCOPE section")

        scope = query[query.find(" SCOPE ") :]
        if "path" not in scope:
            raise InvalidQueryException(
                "PDFS_DIR queries require a path field in the SCOPE section"
            )

        # Note: WITH .. is optional.

        return

    def validate_query(self, query: str) -> None:

        if " FROM " not in query:
            raise InvalidQueryException('Query missing "FROM" clause')

        sources = self.parse_sources(query)

        available_source_types = [x["search_endpoint"] for x in self.search_scripts]
        if not all(source in available_source_types for source in sources):
            violation = [
                source for source in sources if source not in available_source_types
            ]
            raise InvalidQueryException(
                f"source {violation} not in available sources "
                f"({available_source_types})"
            )

        if len(sources) > 1:
            individual_sources = [
                s["search_endpoint"]
                for s in self.search_scripts
                if "individual" == s["mode"]
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
            script = [s for s in self.search_scripts if s["search_endpoint"] == source][
                0
            ]
            script["validate_params"](query)

        # TODO : parse params (which may also raise errors)

        return

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
        query = f"SELECT * {query}"

        self.validate_query(query)

        # TODO : check whether url exists (dblp, project, ...)
        sources = self.parse_sources(query)
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

            duplicate_source = [
                x
                for x in source_details
                if source == x["search_parameters"][0]["endpoint"]
                and selection == x["search_parameters"][0]["params"]
            ]
            if len(duplicate_source) > 0:
                print(
                    "Source already exists: "
                    f"RETRIEVE * FROM {source} {selection}\nSkipping.\n"
                )
                continue

            # TODO : check whether it already exists
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

        self.update(selection_str="all")

        return

    def update(self, selection_str: str) -> None:

        # TODO: when the search_file has been filled only query the last years
        # in the next calls?"

        sources = self.REVIEW_MANAGER.REVIEW_DATASET.load_sources()
        search_dir = Path.cwd() / Path("search")
        feed_paths = [x for x in sources if "FEED" == x["search_type"]]
        for feed_item in feed_paths:

            feed_file = search_dir / Path(feed_item["filename"])
            search_param = feed_item["search_parameters"][0]
            if search_param["endpoint"] not in [
                x["search_endpoint"] for x in self.search_scripts
            ]:
                print(
                    f'Endpoint not supported: {feed_item["search_endpoint"]} (skipping)'
                )
                continue

            if selection_str is not None:
                if "all" != selection_str:
                    if search_param["endpoint"] not in selection_str:
                        continue

            script = [
                s
                for s in self.search_scripts
                if s["search_endpoint"] == search_param["endpoint"]
            ][0]
            params = self.parse_parameters(search_param)

            print(f"Retrieve from {search_param['endpoint']}: {params}")

            script["script"](params, feed_file)

            if feed_file.is_file():
                self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(str(feed_file))
                self.REVIEW_MANAGER.create_commit("Run search")

        return

    def view_sources(self) -> None:
        sources = self.REVIEW_MANAGER.REVIEW_DATASET.load_sources()
        for source in sources:
            self.REVIEW_MANAGER.pp.pprint(source)

        print("\n\n\nOptions:")
        options = ", ".join([s["search_endpoint"] for s in self.search_scripts])
        print(f"- endpoints (FEED): {options}")
        return


class InvalidQueryException(Exception):
    def __init__(self, msg: str):
        self.message = msg
        super().__init__(self.message)


if __name__ == "__main__":
    pass
