#! /usr/bin/env python
import hashlib
import importlib
import re
import sys
import typing
from datetime import datetime
from pathlib import Path

import imagehash
import pandas as pd
import pandasql as ps
import requests
import zope.interface
from crossref.restful import Journals
from pandasql.sqldf import PandaSQLException
from pdf2image import convert_from_path
from zope.interface.verify import verifyObject

from colrev_core.prep import Preparation
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import Record
from colrev_core.review_manager import MissingDependencyError


class SearchEndpoint(zope.interface.Interface):

    source_identifier = zope.interface.Attribute("""Source identifier""")
    mode = zope.interface.Attribute("""Mode""")

    def run_search(SEARCH, params: dict, feed_file: Path) -> None:
        pass

    def validate_params(query: str) -> None:
        pass


@zope.interface.implementer(SearchEndpoint)
class CrossrefSearchEndpoint:

    source_identifier = "https://api.crossref.org/works/{{doi}}"
    mode = "all"

    @classmethod
    def run_search(cls, SEARCH, params: dict, feed_file: Path) -> None:
        from colrev_core.prep import PrepRecord

        if "journal_issn" not in params["scope"]:
            print("Error: journal_issn not in params")
            return

        PREPARATION = Preparation(
            REVIEW_MANAGER=SEARCH.REVIEW_MANAGER, notify_state_transition_process=False
        )
        # works = Works()
        # https://api.crossref.org/swagger-ui/index.html#/Works/get_works
        # use FACETS!
        # w1 = works.query(bibliographic='microsourcing')
        # w1 = works.query(
        #     container_title="Journal of the Association for Information Systems"
        # )
        if "selection_clause" in params:
            query = f"SELECT * FROM rec_df WHERE {params['selection_clause']}"
            SEARCH.REVIEW_MANAGER.logger.info(query)

        for journal_issn in params["scope"]["journal_issn"].split("|"):

            journals = Journals()
            # t = journals.journal('1526-5536')
            # input(feed_item['search_parameters'].split('=')[1])
            w1 = journals.works(journal_issn).query()
            # for it in t:
            #     pp.pprint(it)
            #     input('stop')

            available_ids = []
            max_id = 1
            if not feed_file.is_file():
                records = {}
            else:
                with open(feed_file, encoding="utf8") as bibtex_file:
                    records = SEARCH.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                        load_str=bibtex_file.read()
                    )

                available_ids = [x["doi"] for x in records.values() if "doi" in x]
                max_id = (
                    max(
                        [int(x["ID"]) for x in records.values() if x["ID"].isdigit()]
                        + [1]
                    )
                    + 1
                )

            try:
                for item in w1:
                    if "DOI" in item:
                        if item["DOI"].upper() not in available_ids:
                            record = PREPARATION.crossref_json_to_record(item=item)

                            # TODO : collect list of records
                            # for more efficient selection
                            # select once (parse result to list of dicts?)
                            if "selection_clause" in params:
                                res = []
                                try:
                                    rec_df = pd.DataFrame.from_records([record])
                                    # print(rec_df)
                                    res = ps.sqldf(query, locals())
                                except PandaSQLException:
                                    # print(e)
                                    pass

                                if len(res) == 0:
                                    continue

                            # Note : do not download "empty" records
                            if "" == record.get("author", "") and "" == record.get(
                                "title", ""
                            ):
                                continue

                            SEARCH.REVIEW_MANAGER.logger.info(
                                "Retrieved " + record["doi"]
                            )
                            record["ID"] = str(max_id).rjust(6, "0")
                            if "ENTRYTYPE" not in record:
                                record["ENTRYTYPE"] = "misc"
                            record["source_url"] = (
                                "https://api.crossref.org/works/" + item["DOI"]
                            )
                            record = PREPARATION.get_link_from_doi(
                                PrepRecord(data=record)
                            ).get_data()
                            available_ids.append(record["doi"])
                            records[record["ID"]] = record
                            max_id += 1
            except requests.exceptions.JSONDecodeError as e:
                print(e)
                pass

            # Note : we may have to set temporary IDs to ensure the sort order
            # records = sorted(
            #     records,
            #     key=lambda e: (
            #         e.get("year", ""),
            #         e.get("volume", ""),
            #         e.get("number", ""),
            #         e.get("author", ""),
            #         e.get("title", ""),
            #     ),
            # )

            SEARCH.save_feed_file(records, feed_file)
        return

    @classmethod
    def validate_params(cls, query: str) -> None:
        if " SCOPE " not in query:
            raise InvalidQueryException("CROSSREF queries require a SCOPE section")

        scope = query[query.find(" SCOPE ") :]
        if "journal_issn" not in scope:
            raise InvalidQueryException(
                "CROSSREF queries require a journal_issn field in the SCOPE section"
            )
        pass


@zope.interface.implementer(SearchEndpoint)
class DBLPSearchEndpoint:

    source_identifier = "{{dblp_key}}"
    mode = "all"

    @classmethod
    def run_search(cls, SEARCH, params: dict, feed_file: Path) -> None:
        from colrev_core.prep import Preparation

        # https://dblp.org/search/publ/api?q=ADD_TITLE&format=json

        if "venue_key" not in params["scope"]:
            print("Error: venue_key not in params")
            return
        if "journal_abbreviated" not in params["scope"]:
            print("Error: journal_abbreviated not in params")
            return
        SEARCH.REVIEW_MANAGER.logger.info(f"Retrieve DBLP: {params}")

        available_ids = []
        max_id = 1
        if not feed_file.is_file():
            records = []
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:
                feed_rd = SEARCH.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                    load_str=bibtex_file.read()
                )
                records = feed_rd.values()

            available_ids = [x["dblp_key"] for x in records if "dblp_key" in x]
            max_id = max([int(x["ID"]) for x in records if x["ID"].isdigit()] + [1]) + 1

        try:
            api_url = "https://dblp.org/search/publ/api?q="

            # Note : journal_abbreviated is the abbreviated venue_key
            # TODO : tbd how the abbreviated venue_key can be retrieved
            # https://dblp.org/rec/journals/jais/KordzadehW17.html?view=bibtex

            start = 1980
            if len(records) > 100 and not SEARCH.REVIEW_MANAGER.force_mode:
                start = datetime.now().year - 2
            for year in range(start, datetime.now().year):
                SEARCH.REVIEW_MANAGER.logger.info(f"Retrieving year {year}")
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
                    SEARCH.REVIEW_MANAGER.logger.debug(url)

                    retrieved = False
                    PREPARATION = Preparation(
                        REVIEW_MANAGER=SEARCH.REVIEW_MANAGER,
                        notify_state_transition_process=False,
                    )
                    for RETRIEVED_RECORD in PREPARATION.retrieve_dblp_records(url=url):
                        if "colrev_data_provenance" in RETRIEVED_RECORD.data:
                            del RETRIEVED_RECORD.data["colrev_data_provenance"]
                        if "colrev_masterdata_provenance" in RETRIEVED_RECORD.data:
                            del RETRIEVED_RECORD.data["colrev_masterdata_provenance"]

                        retrieved = True

                        if (
                            f"{params['scope']['venue_key']}/"
                            not in RETRIEVED_RECORD.data["dblp_key"]
                        ):
                            continue

                        if RETRIEVED_RECORD.data["dblp_key"] not in available_ids:
                            RETRIEVED_RECORD.data["ID"] = str(max_id).rjust(6, "0")
                            if RETRIEVED_RECORD.data.get("ENTRYTYPE", "") not in [
                                "article",
                                "inproceedings",
                            ]:
                                continue
                                # retrieved_record["ENTRYTYPE"] = "misc"
                            if "pages" in RETRIEVED_RECORD.data:
                                del RETRIEVED_RECORD.data["pages"]
                            available_ids.append(RETRIEVED_RECORD.data["dblp_key"])

                            # RETRIEVED_RECORD.data["source_url"] = (
                            #     RETRIEVED_RECORD.data["dblp_key"] + "?view=bibtex"
                            # )

                            records = [
                                {
                                    k: v.replace("\n", "").replace("\r", "")
                                    for k, v in r.items()
                                }
                                for r in records
                            ]
                            records.append(RETRIEVED_RECORD.data)
                            max_id += 1

                    if not retrieved:
                        break

                    # Note : we may have to set temporary IDs to ensure the sort order
                    # records = sorted(
                    #     records,
                    #     key=lambda e: (
                    #         e.get("year", ""),
                    #         e.get("volume", ""),
                    #         e.get("number", ""),
                    #         e.get("author", ""),
                    #         e.get("title", ""),
                    #     ),
                    # )

                    if len(records) == 0:
                        continue

                    records_dict = {r["ID"]: r for r in records}
                SEARCH.save_feed_file(records_dict, feed_file)

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

    @classmethod
    def validate_params(cls, query: str) -> None:
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
        pass


@zope.interface.implementer(SearchEndpoint)
class BackwardSearchEndpoint:

    source_identifier = "{{cited_by_file}} (references)"
    mode = "individual"

    def run_search(self, *, SEARCH, params: dict, feed_file: Path) -> None:
        from colrev_core.record import RecordState
        from colrev_core.environment import GrobidService

        if params["scope"]["colrev_status"] != "rev_included|rev_synthesized":
            print("scopes other than rev_included|rev_synthesized not yet implemented")
            return

        if not SEARCH.REVIEW_MANAGER.paths["MAIN_REFERENCES"].is_file():
            print("No records imported. Cannot run backward search yet.")
            return

        GROBID_SERVICE = GrobidService()
        GROBID_SERVICE.start()

        records = SEARCH.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        if feed_file.is_file():
            with open(feed_file, encoding="utf8") as bibtex_file:
                if bibtex_file.read() == "":
                    feed_file_records = []
                else:
                    feed_rd = SEARCH.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                        load_str=bibtex_file.read()
                    )
                    feed_file_records = list(feed_rd.values())
        else:
            feed_file_records = []

        for record in records.values():

            # rev_included/rev_synthesized
            if record["colrev_status"] not in [
                RecordState.rev_included,
                RecordState.rev_synthesized,
            ]:
                continue
            SEARCH.REVIEW_MANAGER.logger.info(
                f'Running backward search for {record["ID"]} ({record["file"]})'
            )

            pdf_path = SEARCH.REVIEW_MANAGER.path / Path(record["file"])
            if not Path(pdf_path).is_file():
                SEARCH.REVIEW_MANAGER.logger.error(f'File not found for {record["ID"]}')
                continue

            options = {"consolidateHeader": "0", "consolidateCitations": "0"}
            r = requests.post(
                GROBID_SERVICE.GROBID_URL + "/api/processReferences",
                files=dict(input=open(pdf_path, "rb"), encoding="utf8"),
                data=options,
                headers={"Accept": "application/x-bibtex"},
            )

            new_records_dict = SEARCH.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                load_str=r.text
            )
            new_records = list(new_records_dict.values())
            for new_record in new_records:
                # IDs have to be distinct
                new_record["ID"] = record["ID"] + "_backward_search_" + new_record["ID"]
                new_record["cited_by"] = record["ID"]
                new_record["cited_by_file"] = record["file"]
                if new_record["ID"] not in [r["ID"] for r in feed_file_records]:
                    feed_file_records.append(new_record)

        feed_file_records_dict = {r["ID"]: r for r in feed_file_records}
        SEARCH.save_feed_file(feed_file_records_dict, feed_file)

        if SEARCH.REVIEW_MANAGER.REVIEW_DATASET.has_changes():
            SEARCH.REVIEW_MANAGER.create_commit(msg="Backward search")
        else:
            print("No new records added.")
        return

    def validate_params(cls, query: str) -> None:
        print("not yet imlemented")
        pass


@zope.interface.implementer(SearchEndpoint)
class ColrevProjectSearchEndpoint:

    # TODO : add a colrev_projet_origin field and use it as the identifier?
    source_identifier = "project"
    mode = "individual"

    def run_search(self, *, SEARCH, params: dict, feed_file: Path) -> None:
        from colrev_core.review_manager import ReviewManager
        from colrev_core.load import Loader
        from tqdm import tqdm

        if not feed_file.is_file():
            records = []
            imported_ids = []
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:
                feed_rd = SEARCH.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                    load_str=bibtex_file.read()
                )
                records = feed_rd.values()

            imported_ids = [x["ID"] for x in records]

        PROJECT_REVIEW_MANAGER = ReviewManager(path_str=params["scope"]["url"])
        Loader(
            REVIEW_MANAGER=PROJECT_REVIEW_MANAGER,
            notify_state_transition_process=False,
        )
        SEARCH.REVIEW_MANAGER.logger.info(
            f'Loading records from {params["scope"]["url"]}'
        )
        records_to_import = PROJECT_REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        records_to_import = {
            ID: rec for ID, rec in records_to_import.items() if ID not in imported_ids
        }
        records_to_import_list = [
            {k: str(v) for k, v in r.items()} for r in records_to_import.values()
        ]

        SEARCH.REVIEW_MANAGER.logger.info("Importing selected records")
        for record_to_import in tqdm(records_to_import_list):
            if "selection_clause" in params:
                res = []
                try:
                    rec_df = pd.DataFrame.from_records([record_to_import])
                    query = f"SELECT * FROM rec_df WHERE {params['selection_clause']}"
                    res = ps.sqldf(query, locals())
                except PandaSQLException:
                    pass

                if len(res) == 0:
                    continue
            SEARCH.REVIEW_MANAGER.REVIEW_DATASET.import_file(record_to_import)

            records = records + [record_to_import]

        keys_to_drop = [
            "colrev_status",
            "colrev_origin",
            "exclusion_criteria",
        ]

        records = [
            {key: item[key] for key in item.keys() if key not in keys_to_drop}
            for item in records
        ]
        if len(records) > 0:
            records_dict = {r["ID"]: r for r in records}

            SEARCH.save_feed_file(records_dict, feed_file)

        else:
            print("No records retrieved.")
        return

    def validate_params(cls, query: str) -> None:
        if " SCOPE " not in query:
            raise InvalidQueryException("PROJECT queries require a SCOPE section")

        scope = query[query.find(" SCOPE ") :]
        if "url" not in scope:
            raise InvalidQueryException(
                "PROJECT queries require a url field in the SCOPE section"
            )
        return


@zope.interface.implementer(SearchEndpoint)
class IndexSearchEndpoint:

    source_identifier = "index"
    mode = "individual"

    def run_search(self, *, SEARCH, params: dict, feed_file: Path) -> None:
        assert "selection_clause" in params

        if not feed_file.is_file():
            records = []
            imported_ids = []
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:

                feed_rd = SEARCH.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                    load_str=bibtex_file.read()
                )
                records = feed_rd.values()

            imported_ids = [x["ID"] for x in records]

        from colrev_core.environment import LocalIndex

        LOCAL_INDEX = LocalIndex()

        def retrieve_from_index(params) -> typing.List[typing.Dict]:
            # Note: we retrieve colrev_ids and full records afterwards
            # because the os.sql.query throws errors when selecting
            # complex fields like lists of alsoKnownAs fields
            query = (
                f"SELECT colrev_id FROM {LOCAL_INDEX.RECORD_INDEX} "
                f"WHERE {params['selection_clause']}"
            )
            # TODO : update to opensearch standard
            # https://github.com/opensearch-project/opensearch-py/issues/98
            # see extract_references.py (methods repo)
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
                record_to_import = LOCAL_INDEX.prep_record_for_return(
                    record=record_to_import, include_file=False
                )

                records_to_import.append(record_to_import)

            return records_to_import

        records_to_import = retrieve_from_index(params)

        records_to_import = [r for r in records_to_import if r]
        records_to_import = [
            x for x in records_to_import if x["ID"] not in imported_ids
        ]
        records = records + records_to_import

        keys_to_drop = [
            "colrev_status",
            "colrev_origin",
            "exclusion_criteria",
        ]
        records = [
            {key: item[key] for key in item.keys() if key not in keys_to_drop}
            for item in records
        ]

        if len(records) > 0:
            records_dict = {r["ID"]: r for r in records}
            SEARCH.save_feed_file(records_dict, feed_file)

        else:
            print("No records found")
        return

    def validate_params(cls, query: str) -> None:
        print("not yet imlemented")
        pass


@zope.interface.implementer(SearchEndpoint)
class PDFSearchEndpoint:

    source_identifier = "{{file}}"
    mode = "all"

    def run_search(self, SEARCH, params: dict, feed_file: Path) -> None:
        from collections import Counter
        from p_tqdm import p_map
        from colrev_core.environment import GrobidService

        from colrev_core.environment import TEIParser
        from colrev_core.environment import TEI_Exception
        from pdfminer.pdfdocument import PDFDocument
        from pdfminer.pdfinterp import resolve1
        from pdfminer.pdfparser import PDFParser
        from colrev_core.pdf_prep import PDF_Preparation

        from colrev_core.record import RecordState

        skip_duplicates = True

        self.PDF_PREPARATION = PDF_Preparation(
            REVIEW_MANAGER=SEARCH.REVIEW_MANAGER, notify_state_transition_process=False
        )

        def update_if_pdf_renamed(
            x: dict, records: typing.Dict, search_source: Path
        ) -> bool:
            UPDATED = True
            NOT_UPDATED = False

            c_rec_l = [
                r
                for r in records.values()
                if f"{search_source}/{x['ID']}" in r["colrev_origin"].split(";")
            ]
            if len(c_rec_l) == 1:
                c_rec = c_rec_l.pop()
                if "colrev_pdf_id" in c_rec:
                    cpid = c_rec["colrev_pdf_id"]
                    pdf_fp = SEARCH.REVIEW_MANAGER.path / Path(x["file"])
                    pdf_path = pdf_fp.parents[0]
                    potential_pdfs = pdf_path.glob("*.pdf")
                    # print(f'search cpid {cpid}')
                    for potential_pdf in potential_pdfs:
                        cpid_potential_pdf = get_colrev_pdf_id(path=potential_pdf)

                        # print(f'cpid_potential_pdf {cpid_potential_pdf}')
                        if cpid == cpid_potential_pdf:
                            x["file"] = str(
                                potential_pdf.relative_to(SEARCH.REVIEW_MANAGER.path)
                            )
                            c_rec["file"] = str(
                                potential_pdf.relative_to(SEARCH.REVIEW_MANAGER.path)
                            )
                            return UPDATED
            return NOT_UPDATED

        def remove_records_if_pdf_no_longer_exists() -> None:

            SEARCH.REVIEW_MANAGER.logger.debug("Checking for PDFs that no longer exist")

            if not feed_file.is_file():
                return

            with open(feed_file, encoding="utf8") as target_db:

                search_rd = SEARCH.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                    load_str=target_db.read()
                )

            records = {}
            if SEARCH.REVIEW_MANAGER.paths["MAIN_REFERENCES"].is_file():
                records = SEARCH.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

            to_remove: typing.List[str] = []
            for x in search_rd.values():
                x_pdf_path = SEARCH.REVIEW_MANAGER.path / Path(x["file"])
                if not x_pdf_path.is_file():
                    if records:
                        updated = update_if_pdf_renamed(x, records, feed_file)
                        if updated:
                            continue
                    to_remove = to_remove + [
                        f"{feed_file.name}/{id}" for id in search_rd.keys()
                    ]

            search_rd = {x["ID"]: x for x in search_rd.values() if x_pdf_path.is_file()}
            if len(search_rd.values()) != 0:
                SEARCH.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict_to_file(
                    records=search_rd, save_path=feed_file
                )

            if SEARCH.REVIEW_MANAGER.paths["MAIN_REFERENCES"].is_file():
                # Note : origins may contain multiple links
                # but that should not be a major issue in indexing repositories

                to_remove = []
                source_ids = list(search_rd.keys())
                for record in records.values():
                    if str(feed_file.name) in record["colrev_origin"]:
                        if (
                            record["colrev_origin"].split(";")[0].split("/")[1]
                            not in source_ids
                        ):
                            print("REMOVE " + record["colrev_origin"])
                            to_remove.append(record["colrev_origin"])

                for r in to_remove:
                    SEARCH.REVIEW_MANAGER.logger.debug(
                        f"remove from index (PDF path no longer exists): {r}"
                    )
                    SEARCH.REVIEW_MANAGER.report_logger.info(
                        f"remove from index (PDF path no longer exists): {r}"
                    )

                records = {
                    k: v
                    for k, v in records.items()
                    if v["colrev_origin"] not in to_remove
                }
                SEARCH.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
                SEARCH.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

            return

        def get_pdf_links(*, bib_file: Path) -> list:
            pdf_list = []
            if bib_file.is_file():
                with open(bib_file, encoding="utf8") as f:
                    line = f.readline()
                    while line:
                        if "file" == line.lstrip()[:4]:
                            file = line[line.find("{") + 1 : line.rfind("}")]
                            pdf_list.append(Path(file))
                        line = f.readline()
            return pdf_list

        def get_colrev_pdf_id(*, path: Path) -> str:
            cpid1 = "cpid1:" + str(
                imagehash.average_hash(
                    convert_from_path(path, first_page=1, last_page=1)[0],
                    hash_size=32,
                )
            )
            return cpid1

        def get_pdf_cpid_path(path) -> typing.List[str]:
            cpid = get_colrev_pdf_id(path=path)
            return [str(path), str(cpid)]

        if not feed_file.is_file():
            records = []
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:
                feed_rd = SEARCH.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                    load_str=bibtex_file.read()
                )
                records = list(feed_rd.values())

        path = Path(params["scope"]["path"])

        remove_records_if_pdf_no_longer_exists()

        indexed_pdf_paths = get_pdf_links(bib_file=feed_file)
        #  + get_pdf_links(REVIEW_MANAGER.paths["MAIN_REFERENCES"])

        indexed_pdf_path_str = "\n  ".join([str(x) for x in indexed_pdf_paths])
        SEARCH.REVIEW_MANAGER.logger.debug(f"indexed_pdf_paths: {indexed_pdf_path_str}")

        overall_pdfs = path.glob("**/*.pdf")

        # Note: sets are more efficient:
        pdfs_to_index = list(set(overall_pdfs).difference(set(indexed_pdf_paths)))

        if skip_duplicates:
            pdfs_path_cpid = p_map(get_pdf_cpid_path, pdfs_to_index)
            pdfs_cpid = [x[1] for x in pdfs_path_cpid]
            duplicate_cpids = [
                item for item, count in Counter(pdfs_cpid).items() if count > 1
            ]
            duplicate_pdfs = [
                str(path) for path, cpid in pdfs_path_cpid if cpid in duplicate_cpids
            ]
            pdfs_to_index = [p for p in pdfs_to_index if str(p) not in duplicate_pdfs]

        broken_filepaths = [str(x) for x in pdfs_to_index if ";" in str(x)]
        if len(broken_filepaths) > 0:
            broken_filepath_str = "\n ".join(broken_filepaths)
            SEARCH.REVIEW_MANAGER.logger.error(
                f'skipping PDFs with ";" in filepath: \n{broken_filepath_str}'
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
            SEARCH.REVIEW_MANAGER.logger.info(
                f"Skipping PDFs with _ocr.pdf/_wo_cp.pdf: {fp_to_skip_str}"
            )
            pdfs_to_index = [
                x for x in pdfs_to_index if str(x) not in filepaths_to_skip
            ]

        # pdfs_to_index = list(set(overall_pdfs) - set(indexed_pdf_paths))
        # pdfs_to_index = ['/home/path/file.pdf']
        pdfs_to_index_str = "\n  ".join([str(x) for x in pdfs_to_index])
        SEARCH.REVIEW_MANAGER.logger.debug(f"pdfs_to_index: {pdfs_to_index_str}")

        if len(pdfs_to_index) > 0:
            GROBID_SERVICE = GrobidService()
            GROBID_SERVICE.start()
        else:
            SEARCH.REVIEW_MANAGER.logger.info("No additional PDFs to index")
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

                # Note : no file access here (just parsing the patterns)
                # no absolute paths needed
                partial_path = Path(record["file"]).parents[0].stem
                if "year" == sub_dir_pattern:
                    r_sub_dir_pattern = re.compile("([1-3][0-9]{3})")
                    # Note: for year-patterns, we allow subfolders
                    # (eg., conference tracks)
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
        def get_record_from_pdf_grobid(*, record) -> dict:
            from colrev_core.environment import EnvironmentManager

            if RecordState.md_prepared == record.get("colrev_status", "NA"):
                return record

            pdf_path = SEARCH.REVIEW_MANAGER.path / Path(record["file"])

            # Note: activate the following when new grobid version is released (> 0.7)
            # Note: we have more control and transparency over the consolidation
            # if we do it in the colrev_core process
            # header_data = {"consolidateHeader": "0"}

            # # https://github.com/kermitt2/grobid/issues/837
            # r = requests.post(
            #     GROBID_SERVICE.GROBID_URL() + "/api/processHeaderDocument",
            #     headers={"Accept": "application/x-bibtex"},
            #     params=header_data,
            #     files=dict(input=open(pdf_path, "rb"), encoding="utf8"),
            # )

            # if 200 == r.status_code:
            #     rec_d = REVIEW_MANAGER.REVIEW_DATASET.
            #               load_records_dict(load_str=r.text)
            #     record = rec_d.values()[0]
            #     return record
            # if 500 == r.status_code:
            #     REVIEW_MANAGER.logger.error(f"Not a readable
            #           pdf file: {pdf_path.name}")
            #     print(f"Grobid: {r.text}")
            #     return {}

            # print(f"Status: {r.status_code}")
            # print(f"Response: {r.text}")
            # return {}

            TEI_INSTANCE = TEIParser(
                pdf_path=pdf_path,
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
            record["grobid-version"] = EnvironmentManager.docker_images[
                "lfoppiano/grobid"
            ]
            return record

        def index_pdf(*, pdf_path: Path) -> dict:

            SEARCH.REVIEW_MANAGER.report_logger.info(pdf_path)
            SEARCH.REVIEW_MANAGER.logger.info(pdf_path)

            record: typing.Dict[str, typing.Any] = {
                "file": str(pdf_path),
                "ENTRYTYPE": "misc",
            }
            try:
                record = get_record_from_pdf_grobid(record=record)

                file = open(pdf_path, "rb")
                parser = PDFParser(file)
                document = PDFDocument(parser)
                pages_in_file = resolve1(document.catalog["Pages"])["Count"]
                if pages_in_file < 6:
                    RECORD = Record(data=record)
                    RECORD.get_text_from_pdf(project_path=SEARCH.REVIEW_MANAGER.path)
                    record = RECORD.get_data()
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

                # add details based on path
                record = update_fields_based_on_pdf_dirs(record)

            except TEI_Exception:
                pass

            return record

        def get_last_ID(*, bib_file: Path) -> int:
            IDs = []
            if bib_file.is_file():
                with open(bib_file, encoding="utf8") as f:
                    line = f.readline()
                    while line:
                        if "@" in line[:3]:
                            current_ID = line[line.find("{") + 1 : line.rfind(",")]
                            IDs.append(current_ID)
                        line = f.readline()
            max_id = max([int(cid) for cid in IDs if cid.isdigit()] + [1]) + 1
            return max_id

        batch_size = 10
        pdf_batches = [
            pdfs_to_index[i * batch_size : (i + 1) * batch_size]
            for i in range((len(pdfs_to_index) + batch_size - 1) // batch_size)
        ]

        ID = int(get_last_ID(bib_file=feed_file))
        for pdf_batch in pdf_batches:

            print("\n")
            lenrec = len(indexed_pdf_paths)
            if len(list(overall_pdfs)) > 0:
                SEARCH.REVIEW_MANAGER.logger.info(
                    f"Number of indexed records: {lenrec} of {len(list(overall_pdfs))} "
                    f"({round(lenrec/len(list(overall_pdfs))*100, 2)}%)"
                )

            new_records = []

            for pdf_path in pdf_batch:
                new_records.append(index_pdf(pdf_path=pdf_path))
            # new_record_db.entries = p_map(self.index_pdf, pdf_batch)
            # p = Pool(ncpus=4)
            # new_records = p.map(index_pdf, pdf_batch)
            # alternatively:
            # new_records = p_map(index_pdf, pdf_batch)

            if 0 != len(new_records):
                for new_r in new_records:
                    indexed_pdf_paths.append(new_r["file"])
                    ID += 1
                    new_r["ID"] = f"{ID}".rjust(10, "0")

                    if "colrev_status" in new_r:
                        if Record(data=new_r).masterdata_is_curated():
                            del new_r["colrev_status"]
                        else:
                            new_r["colrev_status"] = str(new_r["colrev_status"])

            records = records + new_records

        if len(records) > 0:
            records_dict = {r["ID"]: r for r in records}
            SEARCH.save_feed_file(records_dict, feed_file)

        else:
            print("No records found")
        return

    def validate_params(cls, query: str) -> None:
        if " SCOPE " not in query:
            raise InvalidQueryException("PDFS_DIR queries require a SCOPE section")

        scope = query[query.find(" SCOPE ") :]
        if "path" not in scope:
            raise InvalidQueryException(
                "PDFS_DIR queries require a path field in the SCOPE section"
            )

        # Note: WITH .. is optional.
        return


class Search(Process):
    def __init__(
        self,
        *,
        REVIEW_MANAGER,
        notify_state_transition_process=True,
    ):

        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            type=ProcessType.check,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.sources = REVIEW_MANAGER.REVIEW_DATASET.load_sources()

        self.load_search_scripts(
            sources=[s.source_name for s in REVIEW_MANAGER.settings.search.sources]
        )

    def load_search_scripts(self, *, sources: list) -> None:

        self.search_scripts: typing.Dict[str, typing.Dict[str, typing.Any]] = {}
        self.built_in_search_scripts: typing.Dict[str, typing.Dict[str, typing.Any]] = {
            "CROSSREF": {
                "endpoint": CrossrefSearchEndpoint,
            },
            "DBLP": {
                "endpoint": DBLPSearchEndpoint,
            },
            "BACKWARD_SEARCH": {
                "endpoint": BackwardSearchEndpoint,
            },
            "COLREV_PROJECT": {
                "endpoint": ColrevProjectSearchEndpoint,
            },
            "INDEX": {
                "endpoint": IndexSearchEndpoint,
            },
            "PDFS": {
                "endpoint": PDFSearchEndpoint,
            },
        }

        list_built_in_scripts = [
            s for s in sources if s in self.built_in_search_scripts
        ]

        for plugin_script in list_built_in_scripts:
            built_in_search_script = self.built_in_search_scripts[plugin_script][
                "endpoint"
            ]
            self.search_scripts[plugin_script] = {"endpoint": built_in_search_script()}

        list_custom_scripts = [
            s
            for s in sources
            if s not in self.search_scripts and Path(s + ".py").is_file()
        ]
        sys.path.append(".")  # to import custom scripts from the project dir
        for plugin_script in list_custom_scripts:
            custom_search_script = importlib.import_module(
                plugin_script, "."
            ).CustomSearch
            self.search_scripts[plugin_script] = {"endpoint": custom_search_script()}

        # TODO : test the module search_scripts
        list_module_scripts = [
            s
            for s in sources
            if s not in self.search_scripts and not Path(s + ".py").is_file()
        ]
        for plugin_script in list_module_scripts:
            try:
                custom_search_script = importlib.import_module(
                    plugin_script
                ).CustomSearch
                self.search_scripts[plugin_script] = {
                    "endpoint": custom_search_script()
                }
            except ModuleNotFoundError:
                pass
                raise MissingDependencyError(
                    "Dependency search_script " + f"{plugin_script} not found. "
                    "Please install it\n  pip install "
                    f"{plugin_script}"
                )

        for script in self.search_scripts.values():
            verifyObject(SearchEndpoint, script["endpoint"])
        return

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

        self.load_search_scripts(sources=sources)

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

            # NOTE: for now, the parameters are limited to whole journals.
            source_details = {
                "filename": filename,
                "source_name": source,
                "search_type": search_type,
                "source_identifier": source_identifier,
                "search_parameters": selection,
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
