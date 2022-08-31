#! /usr/bin/env python
import re
import typing
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
import pandasql as ps
import requests
import zope.interface
from dacite import from_dict
from p_tqdm import p_map
from pandasql.sqldf import PandaSQLException
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import resolve1
from pdfminer.pdfparser import PDFParser
from tqdm import tqdm

import colrev.built_in.database_connectors
import colrev.exceptions as colrev_exceptions
import colrev.load
import colrev.pdf_prep
import colrev.process
import colrev.record
import colrev.review_manager


@zope.interface.implementer(colrev.process.SearchEndpoint)
class CrossrefSearchEndpoint:

    source_identifier = "https://api.crossref.org/works/{{doi}}"
    mode = "all"

    def __init__(self, *, search, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def run_search(self, search, params: dict, feed_file: Path) -> None:
        # pylint: disable=import-outside-toplevel
        from colrev.built_in.database_connectors import (
            CrossrefConnector,
            DOIConnector,
        )

        # Note: not yet implemented/supported
        if " AND " in params.get("selection_clause", ""):
            raise colrev_exceptions.InvalidQueryException(
                "AND not supported in CROSSREF query selection_clause"
            )
        # Either one or the other is possible:
        if not bool("selection_clause" in params) ^ bool(
            "journal_issn" in params.get("scope", {})
        ):
            raise colrev_exceptions.InvalidQueryException(
                "combined selection_clause and journal_issn (scope) "
                "not supported in CROSSREF query"
            )

        available_ids = []
        max_id = 1
        if not feed_file.is_file():
            records = {}
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:
                records = search.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )

            available_ids = [x["doi"] for x in records.values() if "doi" in x]
            max_id = (
                max([int(x["ID"]) for x in records.values() if x["ID"].isdigit()] + [1])
                + 1
            )
        crossref_connector = CrossrefConnector(review_manager=search.review_manager)

        def get_crossref_query_return(params):
            if "selection_clause" in params:
                crossref_query = {"bibliographic": params["selection_clause"]}
                # TODO : add the container_title:
                # crossref_query_return = works.query(
                #     container_title=
                #       "Journal of the Association for Information Systems"
                # )
                yield from crossref_connector.get_bibliographic_query_return(
                    **crossref_query
                )

            if "journal_issn" in params.get("scope", {}):

                for journal_issn in params["scope"]["journal_issn"].split("|"):
                    yield from crossref_connector.get_journal_query_return(
                        journal_issn=journal_issn
                    )

        try:
            for record in get_crossref_query_return(params):
                if record["doi"].upper() not in available_ids:

                    # Note : discard "empty" records
                    if "" == record.get("author", "") and "" == record.get("title", ""):
                        continue

                    search.review_manager.logger.info(" retrieved " + record["doi"])
                    record["ID"] = str(max_id).rjust(6, "0")

                    prep_record = colrev.record.PrepRecord(data=record)
                    DOIConnector.get_link_from_doi(
                        RECORD=prep_record, review_manager=search.review_manager
                    )
                    record = prep_record.get_data()

                    available_ids.append(record["doi"])
                    records[record["ID"]] = record
                    max_id += 1
        except requests.exceptions.JSONDecodeError as exc:
            if "504 Gateway Time-out" in str(exc):
                raise colrev_exceptions.ServiceNotAvailableException(
                    "Crossref (check https://status.crossref.org/)"
                )
            raise colrev_exceptions.ServiceNotAvailableException(
                f"Crossref (check https://status.crossref.org/) ({exc})"
            )

        search.save_feed_file(records, feed_file)

    def validate_params(self, query: str) -> None:
        if " SCOPE " not in query and " WHERE " not in query:
            raise colrev_exceptions.InvalidQueryException(
                "CROSSREF queries require a SCOPE or WHERE section"
            )

        if " SCOPE " in query:
            scope = query[query.find(" SCOPE ") :]
            if "journal_issn" not in scope:
                raise colrev_exceptions.InvalidQueryException(
                    "CROSSREF queries require a journal_issn field in the SCOPE section"
                )


@zope.interface.implementer(colrev.process.SearchEndpoint)
class DBLPSearchEndpoint:

    source_identifier = "{{dblp_key}}"
    mode = "all"

    def __init__(self, *, search, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def run_search(self, search, params: dict, feed_file: Path) -> None:

        # https://dblp.org/search/publ/api?q=ADD_TITLE&format=json

        if "venue_key" not in params["scope"]:
            print("Error: venue_key not in params")
            return
        if "journal_abbreviated" not in params["scope"]:
            print("Error: journal_abbreviated not in params")
            return
        search.review_manager.logger.info(f"Retrieve DBLP: {params}")

        available_ids = []
        max_id = 1
        if not feed_file.is_file():
            records = []
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:
                feed_rd = search.review_manager.dataset.load_records_dict(
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
            if len(records) > 100 and not search.review_manager.force_mode:
                start = datetime.now().year - 2
            records_dict = {r["ID"]: r for r in records}
            for year in range(start, datetime.now().year):
                search.review_manager.logger.info(f"Retrieving year {year}")
                query = params["scope"]["journal_abbreviated"] + "+" + str(year)
                # query = params['scope']["venue_key"] + "+" + str(year)
                nr_retrieved = 0
                batch_size = 250
                dblp_connector = colrev.built_in.database_connectors.DBLPConnector
                while True:
                    url = (
                        api_url
                        + query.replace(" ", "+")
                        + f"&format=json&h={batch_size}&f={nr_retrieved}"
                    )
                    nr_retrieved += batch_size
                    search.review_manager.logger.debug(url)

                    retrieved = False
                    for retrieved_record in dblp_connector.retrieve_dblp_records(
                        review_manager=search.review_manager, url=url
                    ):
                        if "colrev_data_provenance" in retrieved_record.data:
                            del retrieved_record.data["colrev_data_provenance"]
                        if "colrev_masterdata_provenance" in retrieved_record.data:
                            del retrieved_record.data["colrev_masterdata_provenance"]

                        retrieved = True

                        if (
                            f"{params['scope']['venue_key']}/"
                            not in retrieved_record.data["dblp_key"]
                        ):
                            continue

                        if retrieved_record.data["dblp_key"] not in available_ids:
                            retrieved_record.data["ID"] = str(max_id).rjust(6, "0")
                            if retrieved_record.data.get("ENTRYTYPE", "") not in [
                                "article",
                                "inproceedings",
                            ]:
                                continue
                                # retrieved_record["ENTRYTYPE"] = "misc"
                            if "pages" in retrieved_record.data:
                                del retrieved_record.data["pages"]
                            available_ids.append(retrieved_record.data["dblp_key"])

                            records = [
                                {
                                    k: v.replace("\n", "").replace("\r", "")
                                    for k, v in r.items()
                                }
                                for r in records
                            ]
                            records.append(retrieved_record.data)
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
                search.save_feed_file(records_dict, feed_file)

        except requests.exceptions.HTTPError:
            pass
        except UnicodeEncodeError:
            print("UnicodeEncodeError - this needs to be fixed at some time")
        except requests.exceptions.ReadTimeout:
            pass
        except requests.exceptions.ConnectionError:
            pass

    def validate_params(self, query: str) -> None:
        if " SCOPE " not in query:
            raise colrev_exceptions.InvalidQueryException(
                "DBLP queries require a SCOPE section"
            )

        scope = query[query.find(" SCOPE ") :]
        if "venue_key" not in scope:
            raise colrev_exceptions.InvalidQueryException(
                "DBLP queries require a venue_key in the SCOPE section"
            )
        if "journal_abbreviated" not in scope:
            raise colrev_exceptions.InvalidQueryException(
                "DBLP queries require a journal_abbreviated field in the SCOPE section"
            )


@zope.interface.implementer(colrev.process.SearchEndpoint)
class BackwardSearchEndpoint:

    source_identifier = "{{cited_by_file}} (references)"
    mode = "individual"

    def __init__(self, *, search, settings):

        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

        self.grobid_service = search.review_manager.get_grobid_service()
        self.grobid_service.start()

    def run_search(self, search, params: dict, feed_file: Path) -> None:

        if "colrev_status" in params["scope"]:
            if params["scope"]["colrev_status"] not in [
                "rev_included|rev_synthesized",
            ]:
                print("scope not yet implemented")
                return

        elif "file" in params["scope"]:
            if params["scope"]["file"] not in [
                "paper.pdf",
            ]:
                print("scope not yet implemented")
                return
        else:
            print("scope not yet implemented")
            return

        if not search.review_manager.paths["RECORDS_FILE"].is_file():
            print("No records imported. Cannot run backward search yet.")
            return

        records = search.review_manager.dataset.load_records_dict()

        if feed_file.is_file():
            with open(feed_file, encoding="utf8") as bibtex_file:
                if bibtex_file.read() == "":
                    feed_file_records = []
                else:
                    feed_rd = search.review_manager.dataset.load_records_dict(
                        load_str=bibtex_file.read()
                    )
                    feed_file_records = list(feed_rd.values())
        else:
            feed_file_records = []

        for record in records.values():

            # rev_included/rev_synthesized
            if "colrev_status" in params["scope"]:
                if (
                    params["scope"]["colrev_status"] == "rev_included|rev_synthesized"
                ) and record["colrev_status"] not in [
                    colrev.record.RecordState.rev_included,
                    colrev.record.RecordState.rev_synthesized,
                ]:
                    continue

            # Note: this is for peer_reviews
            if "file" in params["scope"]:
                if (
                    params["scope"]["file"] == "paper.pdf"
                ) and "pdfs/paper.pdf" != record.get("file", ""):
                    continue

            search.review_manager.logger.info(
                f'Running backward search for {record["ID"]} ({record["file"]})'
            )

            pdf_path = search.review_manager.path / Path(record["file"])
            if not Path(pdf_path).is_file():
                search.review_manager.logger.error(f'File not found for {record["ID"]}')
                continue

            # pylint: disable=consider-using-with
            options = {"consolidateHeader": "0", "consolidateCitations": "0"}
            ret = requests.post(
                self.grobid_service.GROBID_URL + "/api/processReferences",
                files=dict(input=open(pdf_path, "rb"), encoding="utf8"),
                data=options,
                headers={"Accept": "application/x-bibtex"},
            )

            new_records_dict = search.review_manager.dataset.load_records_dict(
                load_str=ret.text
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
        search.save_feed_file(feed_file_records_dict, feed_file)
        search.review_manager.dataset.add_changes(path=str(feed_file))

        if search.review_manager.dataset.has_changes():
            search.review_manager.create_commit(
                msg="Backward search", script_call="colrev search"
            )
        else:
            print("No new records added.")

    def validate_params(self, query: str) -> None:
        print("not yet imlemented")


@zope.interface.implementer(colrev.process.SearchEndpoint)
class ColrevProjectSearchEndpoint:

    # TODO : add a colrev_projet_origin field and use it as the identifier?
    source_identifier = "project"
    mode = "individual"

    def __init__(self, *, search, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def run_search(self, search, params: dict, feed_file: Path) -> None:

        if not feed_file.is_file():
            records = []
            imported_ids = []
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:
                feed_rd = search.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )
                records = feed_rd.values()

            imported_ids = [x["ID"] for x in records]

        project_review_manager = colrev.review_manager.ReviewManager(
            path_str=params["scope"]["url"]
        )
        colrev.load.Loader(
            review_manager=project_review_manager,
            notify_state_transition_process=False,
        )
        search.review_manager.logger.info(
            f'Loading records from {params["scope"]["url"]}'
        )
        records_to_import = project_review_manager.dataset.load_records_dict()
        records_to_import = {
            ID: rec for ID, rec in records_to_import.items() if ID not in imported_ids
        }
        records_to_import_list = [
            {k: str(v) for k, v in r.items()} for r in records_to_import.values()
        ]

        search.review_manager.logger.info("Importing selected records")
        for record_to_import in tqdm(records_to_import_list):
            if "selection_clause" in params:
                res = []
                try:
                    # pylint: disable=possibly-unused-variable
                    rec_df = pd.DataFrame.from_records([record_to_import])
                    query = f"SELECT * FROM rec_df WHERE {params['selection_clause']}"
                    res = ps.sqldf(query, locals())
                except PandaSQLException:
                    pass

                if len(res) == 0:
                    continue
            search.review_manager.dataset.import_file(record_to_import)

            records = records + [record_to_import]

        keys_to_drop = [
            "colrev_status",
            "colrev_origin",
            "screening_criteria",
        ]

        records = [
            {key: item[key] for key in item.keys() if key not in keys_to_drop}
            for item in records
        ]
        if len(records) > 0:
            records_dict = {r["ID"]: r for r in records}

            search.save_feed_file(records_dict, feed_file)

        else:
            print("No records retrieved.")

    def validate_params(self, query: str) -> None:
        if " SCOPE " not in query:
            raise colrev_exceptions.InvalidQueryException(
                "PROJECT queries require a SCOPE section"
            )

        scope = query[query.find(" SCOPE ") :]
        if "url" not in scope:
            raise colrev_exceptions.InvalidQueryException(
                "PROJECT queries require a url field in the SCOPE section"
            )


@zope.interface.implementer(colrev.process.SearchEndpoint)
class IndexSearchEndpoint:

    source_identifier = "index"
    mode = "individual"

    def __init__(self, *, search, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def run_search(self, search, params: dict, feed_file: Path) -> None:
        assert "selection_clause" in params

        if not feed_file.is_file():
            records = []
            imported_ids = []
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:

                feed_rd = search.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )
                records = feed_rd.values()

            imported_ids = [x["ID"] for x in records]

        local_index = search.review_manager.get_local_index()

        def retrieve_from_index(params) -> typing.List[typing.Dict]:

            # Note: we retrieve colrev_ids and full records afterwards
            # because the os.sql.query throws errors when selecting
            # complex fields like lists of alsoKnownAs fields

            query = (
                f"SELECT colrev_id FROM {local_index.RECORD_INDEX} "
                f"WHERE {params['selection_clause']}"
            )
            # TODO : update to opensearch standard (DSL?)
            # or use opensearch-sql plugin
            # https://github.com/opensearch-project/opensearch-py/issues/98
            # client.transport.perform_request
            #  ('POST', '/_plugins/_sql', body={'query': sql_str})
            # https://opensearch.org/docs/latest/search-plugins/sql/index/
            # see extract_references.py (methods repo)
            # resp = local_index.open_search.sql.query(body={"query": query})

            print("WARNING: not yet fully implemented.")
            quick_fix_query = (
                params["selection_clause"]
                .replace("title", "")
                .replace("'", "")
                .replace("%", "")
                .replace("like", "")
                .lstrip()
                .rstrip()
            )
            print(f"Working with quick-fix query: {quick_fix_query}")
            # input(query.replace(''))
            # resp = local_index.open_search.search(index=local_index.RECORD_INDEX,
            # body={"query":{"match_all":{}}})

            print("search currently restricted to title field")
            selected_fields = []
            if "title" in params["selection_clause"]:
                selected_fields.append("title")
            if "author" in params["selection_clause"]:
                selected_fields.append("author")
            if "fulltext" in params["selection_clause"]:
                selected_fields.append("fulltext")
            if "abstract" in params["selection_clause"]:
                selected_fields.append("abstract")

            # TODO : size is set to maximum.
            # We may iterate (using the from=... parameter)
            # pylint: disable=unexpected-keyword-arg
            # Note : search(...) accepts the size keyword (tested & works)
            # https://opensearch-project.github.io/opensearch-py/
            # api-ref/client.html#opensearchpy.OpenSearch.search
            resp = local_index.open_search.search(
                index=local_index.RECORD_INDEX,
                size=10000,
                body={
                    "query": {
                        "simple_query_string": {
                            "query": quick_fix_query,
                            "fields": selected_fields,
                        },
                    }
                },
            )

            # TODO : extract the following into a convenience function of search
            # (maybe even run in parallel/based on whole list and
            # select based on ?colrev_ids?)

            records_to_import = []
            for hit in tqdm(resp["hits"]["hits"]):
                record = hit["_source"]
                if "fulltext" in record:
                    del record["fulltext"]
                # print(record)

                # pylint: disable=possibly-unused-variable
                rec_df = pd.DataFrame.from_records([record])
                try:
                    query = f"SELECT * FROM rec_df WHERE {params['selection_clause']}"
                    res = ps.sqldf(query, locals())
                except PandaSQLException:
                    continue
                if len(res) > 0:
                    # if res...: append
                    records_to_import.append(record)
                    # input('matched')

                # else:
                # input('not_matched')

                # input(hit)

            # IDs_to_retrieve = [item for sublist in resp["rows"] for item in sublist]

            # records_to_import = []
            # for ID_to_retrieve in IDs_to_retrieve:

            #     hash = hashlib.sha256(ID_to_retrieve.encode("utf-8")).hexdigest()
            #     res = local_index.open_search.get(index=local_index.RECORD_INDEX, id=hash)
            #     record_to_import = res["_source"]
            #     record_to_import = {k: str(v) for k, v in record_to_import.items()}
            #     record_to_import = {
            #         k: v for k, v in record_to_import.items() if "None" != v
            #     }
            #     record_to_import = local_index.prep_record_for_return(
            #         record=record_to_import, include_file=False
            #     )

            #     if "" == params['selection_clause']:
            #         records_to_import.append(record_to_import)
            #     else:
            #         rec_df = pd.DataFrame.from_records([record_to_import])
            #         query = f"SELECT * FROM rec_df WHERE {params['selection_clause']}"
            #         res = ps.sqldf(query, locals())
            #         input(res)
            #         # if res...: append
            #         records_to_import.append(record_to_import)

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
            "screening_criteria",
        ]
        records = [
            {key: item[key] for key in item.keys() if key not in keys_to_drop}
            for item in records
        ]

        if len(records) > 0:
            records_dict = {r["ID"]: r for r in records}
            search.save_feed_file(records_dict, feed_file)

        else:
            print("No records found")

    def validate_params(self, query: str) -> None:
        print("not yet imlemented")


@zope.interface.implementer(colrev.process.SearchEndpoint)
class PDFSearchEndpoint:

    source_identifier = "{{file}}"
    mode = "all"

    pdf_preparation = None

    def __init__(self, *, search, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def run_search(self, search, params: dict, feed_file: Path) -> None:

        skip_duplicates = True

        self.pdf_preparation = colrev.pdf_prep.PDFPreparation(
            review_manager=search.review_manager, notify_state_transition_process=False
        )

        def update_if_pdf_renamed(
            record_dict: dict, records: typing.Dict, search_source: Path
        ) -> bool:
            updated = True
            not_updated = False

            c_rec_l = [
                r
                for r in records.values()
                if f"{search_source}/{record_dict['ID']}"
                in r["colrev_origin"].split(";")
            ]
            if len(c_rec_l) == 1:
                c_rec = c_rec_l.pop()
                if "colrev_pdf_id" in c_rec:
                    cpid = c_rec["colrev_pdf_id"]
                    pdf_fp = search.review_manager.path / Path(record_dict["file"])
                    pdf_path = pdf_fp.parents[0]
                    potential_pdfs = pdf_path.glob("*.pdf")
                    # print(f'search cpid {cpid}')
                    for potential_pdf in potential_pdfs:
                        cpid_potential_pdf = colrev.record.Record.get_colrev_pdf_id(
                            review_manager=search.review_manager, pdf_path=potential_pdf
                        )

                        # print(f'cpid_potential_pdf {cpid_potential_pdf}')
                        if cpid == cpid_potential_pdf:
                            record_dict["file"] = str(
                                potential_pdf.relative_to(search.review_manager.path)
                            )
                            c_rec["file"] = str(
                                potential_pdf.relative_to(search.review_manager.path)
                            )
                            return updated
            return not_updated

        def remove_records_if_pdf_no_longer_exists() -> None:

            search.review_manager.logger.debug("Checking for PDFs that no longer exist")

            if not feed_file.is_file():
                return

            with open(feed_file, encoding="utf8") as target_db:

                search_rd = search.review_manager.dataset.load_records_dict(
                    load_str=target_db.read()
                )

            records = {}
            if search.review_manager.paths["RECORDS_FILE"].is_file():
                records = search.review_manager.dataset.load_records_dict()

            to_remove: typing.List[str] = []
            for record_dict in search_rd.values():
                x_pdf_path = search.review_manager.path / Path(record_dict["file"])
                if not x_pdf_path.is_file():
                    if records:
                        updated = update_if_pdf_renamed(record_dict, records, feed_file)
                        if updated:
                            continue
                    to_remove = to_remove + [
                        f"{feed_file.name}/{id}" for id in search_rd.keys()
                    ]

            search_rd = {x["ID"]: x for x in search_rd.values() if x_pdf_path.is_file()}
            if len(search_rd.values()) != 0:
                search.review_manager.dataset.save_records_dict_to_file(
                    records=search_rd, save_path=feed_file
                )

            if search.review_manager.paths["RECORDS_FILE"].is_file():
                # Note : origins may contain multiple links
                # but that should not be a major issue in indexing repositories

                to_remove = []
                source_ids = list(search_rd.keys())
                for record in records.values():
                    if str(feed_file.name) in record["colrev_origin"]:
                        if not any(
                            x.split("/")[1] in source_ids
                            for x in record["colrev_origin"].split(";")
                        ):
                            print("REMOVE " + record["colrev_origin"])
                            to_remove.append(record["colrev_origin"])

                for record_dict in to_remove:
                    search.review_manager.logger.debug(
                        f"remove from index (PDF path no longer exists): {record_dict}"
                    )
                    search.review_manager.report_logger.info(
                        f"remove from index (PDF path no longer exists): {record_dict}"
                    )

                records = {
                    k: v
                    for k, v in records.items()
                    if v["colrev_origin"] not in to_remove
                }
                search.review_manager.dataset.save_records_dict(records=records)
                search.review_manager.dataset.add_record_changes()

            return

        def get_pdf_links(*, bib_file: Path) -> list:
            pdf_list = []
            if bib_file.is_file():
                with open(bib_file, encoding="utf8") as file:
                    line = file.readline()
                    while line:
                        if "file" == line.lstrip()[:4]:
                            pdf_file = line[line.find("{") + 1 : line.rfind("}")]
                            pdf_list.append(Path(pdf_file))
                        line = file.readline()
            return pdf_list

        def get_pdf_cpid_path(path) -> typing.List[str]:
            cpid = colrev.record.Record.get_colrev_pdf_id(
                review_manager=search.review_manager, pdf_path=path
            )
            return [str(path), str(cpid)]

        if not feed_file.is_file():
            records = []
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:
                feed_rd = search.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )
                records = list(feed_rd.values())

        def fix_filenames() -> None:
            overall_pdfs = path.glob("**/*.pdf")
            for pdf in overall_pdfs:
                if "  " in str(pdf):
                    pdf.rename(str(pdf).replace("  ", " "))

        path = Path(params["scope"]["path"])

        fix_filenames()

        remove_records_if_pdf_no_longer_exists()

        indexed_pdf_paths = get_pdf_links(bib_file=feed_file)
        #  + get_pdf_links(review_manager.paths["RECORDS_FILE"])

        indexed_pdf_path_str = "\n  ".join([str(x) for x in indexed_pdf_paths])
        search.review_manager.logger.debug(f"indexed_pdf_paths: {indexed_pdf_path_str}")

        overall_pdfs = path.glob("**/*.pdf")

        # Note: sets are more efficient:
        pdfs_to_index = list(set(overall_pdfs).difference(set(indexed_pdf_paths)))

        if skip_duplicates:
            search.review_manager.logger.info("Calculate PDF hashes to skip duplicates")
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
            search.review_manager.logger.error(
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
            search.review_manager.logger.info(
                f"Skipping PDFs with _ocr.pdf/_wo_cp.pdf: {fp_to_skip_str}"
            )
            pdfs_to_index = [
                x for x in pdfs_to_index if str(x) not in filepaths_to_skip
            ]

        # pdfs_to_index = list(set(overall_pdfs) - set(indexed_pdf_paths))
        # pdfs_to_index = ['/home/path/file.pdf']
        pdfs_to_index_str = "\n  ".join([str(x) for x in pdfs_to_index])
        search.review_manager.logger.debug(f"pdfs_to_index: {pdfs_to_index_str}")

        if len(pdfs_to_index) > 0:
            grobid_service = search.review_manager.get_grobid_service()
            grobid_service.start()
        else:
            search.review_manager.logger.info("No additional PDFs to index")
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
                partial_path = Path(record["file"]).parents[0]
                if "year" == sub_dir_pattern:
                    r_sub_dir_pattern = re.compile("([1-3][0-9]{3})")
                    # Note: for year-patterns, we allow subfolders
                    # (eg., conference tracks)
                    match = r_sub_dir_pattern.search(str(partial_path))
                    if match is not None:
                        year = match.group(1)
                        record["year"] = year

                if "volume_number" == sub_dir_pattern:
                    r_sub_dir_pattern = re.compile("([0-9]{1,3})(_|/)([0-9]{1,2})")
                    match = r_sub_dir_pattern.search(str(partial_path))
                    if match is not None:
                        volume = match.group(1)
                        number = match.group(3)
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

            if colrev.record.RecordState.md_prepared == record.get(
                "colrev_status", "NA"
            ):
                return record

            pdf_path = search.review_manager.path / Path(record["file"])

            # Note: activate the following when new grobid version is released (> 0.7)
            # Note: we have more control and transparency over the consolidation
            # if we do it in the colrev process
            # header_data = {"consolidateHeader": "0"}

            # # https://github.com/kermitt2/grobid/issues/837
            # r = requests.post(
            #     GROBID_SERVICE.GROBID_URL() + "/api/processHeaderDocument",
            #     headers={"Accept": "application/x-bibtex"},
            #     params=header_data,
            #     files=dict(input=open(pdf_path, "rb"), encoding="utf8"),
            # )

            # if 200 == r.status_code:
            #     rec_d = review_manager.dataset.
            #               load_records_dict(load_str=r.text)
            #     record = rec_d.values()[0]
            #     return record
            # if 500 == r.status_code:
            #     review_manager.logger.error(f"Not a readable
            #           pdf file: {pdf_path.name}")
            #     print(f"Grobid: {r.text}")
            #     return {}

            # print(f"Status: {r.status_code}")
            # print(f"Response: {r.text}")
            # return {}

            tei = search.review_manager.get_tei(
                pdf_path=pdf_path,
            )

            extracted_record = tei.get_metadata()

            for key, val in extracted_record.items():
                if val:
                    record[key] = str(val)

            with open(pdf_path, "rb") as file:
                parser = PDFParser(file)
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

                environment_manager = search.review_manager.get_environment_manager()
                # to allow users to update/reindex with newer version:
                record["grobid-version"] = environment_manager.docker_images[
                    "lfoppiano/grobid"
                ]
                return record

        def index_pdf(*, pdf_path: Path) -> dict:

            search.review_manager.report_logger.info(
                f" extract metadata from {pdf_path}"
            )
            search.review_manager.logger.info(f" extract metadata from {pdf_path}")

            record_dict: typing.Dict[str, typing.Any] = {
                "file": str(pdf_path),
                "ENTRYTYPE": "misc",
            }
            try:
                record_dict = get_record_from_pdf_grobid(record=record_dict)

                with open(pdf_path, "rb") as file:
                    parser = PDFParser(file)
                    document = PDFDocument(parser)
                    pages_in_file = resolve1(document.catalog["Pages"])["Count"]
                    if pages_in_file < 6:
                        record = colrev.record.Record(data=record_dict)
                        record.get_text_from_pdf(
                            project_path=search.review_manager.path
                        )
                        record_dict = record.get_data()
                        if "text_from_pdf" in record_dict:
                            text: str = record_dict["text_from_pdf"]
                            if "bookreview" in text.replace(" ", "").lower():
                                record_dict["ENTRYTYPE"] = "misc"
                                record_dict["note"] = "Book review"
                            if "erratum" in text.replace(" ", "").lower():
                                record_dict["ENTRYTYPE"] = "misc"
                                record_dict["note"] = "Erratum"
                            if "correction" in text.replace(" ", "").lower():
                                record_dict["ENTRYTYPE"] = "misc"
                                record_dict["note"] = "Correction"
                            if "contents" in text.replace(" ", "").lower():
                                record_dict["ENTRYTYPE"] = "misc"
                                record_dict["note"] = "Contents"
                            if "withdrawal" in text.replace(" ", "").lower():
                                record_dict["ENTRYTYPE"] = "misc"
                                record_dict["note"] = "Withdrawal"
                            del record_dict["text_from_pdf"]
                        # else:
                        #     print(f'text extraction error in {record_dict["ID"]}')
                        if "pages_in_file" in record_dict:
                            del record_dict["pages_in_file"]

                    record_dict = {
                        k: v for k, v in record_dict.items() if v is not None
                    }
                    record_dict = {k: v for k, v in record_dict.items() if v != "NA"}

                    # add details based on path
                    record_dict = update_fields_based_on_pdf_dirs(record_dict)

            except colrev_exceptions.TEIException:
                pass

            return record_dict

        batch_size = 10
        pdf_batches = [
            pdfs_to_index[i * batch_size : (i + 1) * batch_size]
            for i in range((len(pdfs_to_index) + batch_size - 1) // batch_size)
        ]

        record_id = int(search.review_manager.dataset.get_next_id(bib_file=feed_file))
        for pdf_batch in pdf_batches:

            lenrec = len(indexed_pdf_paths)
            if len(list(overall_pdfs)) > 0:
                search.review_manager.logger.info(
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
                    record_id += 1
                    new_r["ID"] = f"{record_id}".rjust(10, "0")

                    if "colrev_status" in new_r:
                        if colrev.record.Record(data=new_r).masterdata_is_curated():
                            del new_r["colrev_status"]
                        else:
                            new_r["colrev_status"] = str(new_r["colrev_status"])

            records = records + new_records

        if len(records) > 0:
            records_dict = {r["ID"]: r for r in records}
            search.save_feed_file(records_dict, feed_file)

        else:
            print("No records found")

    def validate_params(self, query: str) -> None:
        if " SCOPE " not in query:
            raise colrev_exceptions.InvalidQueryException(
                "PDFS_DIR queries require a SCOPE section"
            )

        scope = query[query.find(" SCOPE ") :]
        if "path" not in scope:
            raise colrev_exceptions.InvalidQueryException(
                "PDFS_DIR queries require a path field in the SCOPE section"
            )

        # Note: WITH .. is optional.
