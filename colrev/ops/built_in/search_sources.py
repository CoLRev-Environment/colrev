#! /usr/bin/env python
import re
import typing
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

import dacite
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

import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.database_connectors
import colrev.ops.search
import colrev.process
import colrev.record

# pylint: disable=unused-argument

# TODO
# IEEEXplore
# JSTOR
# CINAHL
# Psychinfo

# VirtualHealthLibrary
# BielefeldAcademicSearchEngine

# paywalled:
# EbscoHost
# ProQuest
# ScienceDirect
# OVID

# challenging:
# ClinicalTrialsGov (no bibliographic data?!)

# AMiner
# arXiv
# CiteSeerX
# DirectoryOfOpenAccessJournals
# EducationResourcesInformationCenter
# SemanticScholar
# SpringerLinks
# WorldCat
# WorldWideScience


# Heuristics:
# TODO : we should consider all records
# (e.g., the first record with url=ais... may be misleading)
# TBD: applying heuristics before bibtex-conversion?
# -> test bibtex conversion before? (otherwise: abort import/warn?)
# TODO : deal with misleading file extensions.


def apply_field_mapping(
    *, record: colrev.record.PrepRecord, mapping: dict
) -> colrev.record.PrepRecord:
    """Convenience function for the prep scripts"""

    mapping = {k.lower(): v.lower() for k, v in mapping.items()}
    prior_keys = list(record.data.keys())
    # Note : warning: do not create a new dict.
    for key in prior_keys:
        if key.lower() in mapping:
            record.rename_field(key=key, new_key=mapping[key.lower()])

    return record


def drop_fields(
    *, record: colrev.record.PrepRecord, drop=list
) -> colrev.record.PrepRecord:
    """Convenience function for the prep scripts"""

    for key_to_drop in drop:
        record.remove_field(key=key_to_drop)
    return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class UnknownSearchSource:

    settings_class = colrev.process.DefaultSourceSettings

    source_identifier = "unknown_source"
    source_identifier_search = "unknown_source"
    search_mode = "individual"

    def __init__(self, *, source_operation, settings: dict) -> None:
        converters = {Path: Path, Enum: Enum}
        self.settings = from_dict(
            data_class=self.settings_class,
            data=settings,
            config=dacite.Config(type_hooks=converters, cast=[Enum]),  # type: ignore
        )
        converters = {Path: Path, Enum: Enum}
        self.settings = from_dict(
            data_class=self.settings_class,
            data=settings,
            config=dacite.Config(type_hooks=converters, cast=[Enum]),  # type: ignore
        )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        # TODO
        result = {"confidence": 0, "source_identifier": cls.source_identifier}

        return result

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        search_operation.review_manager.logger.info(
            "Automated search not (yet) supported."
        )

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.PrepRecord) -> colrev.record.Record:

        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class AISeLibrarySearchSource:

    settings_class = colrev.process.DefaultSourceSettings

    source_identifier = "https://aisel.aisnet.org/"
    source_identifier_search = "https://aisel.aisnet.org/"
    search_mode = "individual"

    def __init__(self, *, source_operation, settings: dict) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0, "source_identifier": cls.source_identifier}
        nr_ais_links = data.count("https://aisel.aisnet.org/")
        nr_items = data.count("\n@")
        result["confidence"] = nr_ais_links / nr_items

        return result

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        search_operation.review_manager.logger.info(
            "Automated search not (yet) supported."
        )

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.PrepRecord) -> colrev.record.Record:
        ais_mapping: dict = {}
        record = apply_field_mapping(record=record, mapping=ais_mapping)

        # Note : simple heuristic
        # but at the moment, AISeLibrary only indexes articles and conference papers
        if (
            record.data.get("volume", "UNKNOWN") != "UNKNOWN"
            or record.data.get("number", "UNKNOWN") != "UNKNOWN"
        ) and not any(
            x in record.data.get("journal", "")
            for x in [
                "HICSS",
                "ICIS",
                "ECIS",
                "AMCIS",
                "Proceedings",
                "All Sprouts Content",
            ]
        ):
            record.data["ENTRYTYPE"] = "article"
            if "journal" not in record.data and "booktitle" in record.data:
                record.rename_field(key="booktitle", new_key="journal")
            if (
                "journal" not in record.data
                and "title" in record.data
                and "chapter" in record.data
            ):
                record.rename_field(key="title", new_key="journal")
                record.rename_field(key="chapter", new_key="title")
                record.remove_field(key="publisher")

        else:
            record.data["ENTRYTYPE"] = "inproceedings"
            record.remove_field(key="publisher")
            if record.data.get("volume", "") == "UNKNOWN":
                record.remove_field(key="volume")
            if record.data.get("number", "") == "UNKNOWN":
                record.remove_field(key="number")

            if (
                "booktitle" not in record.data
                and "title" in record.data
                and "chapter" in record.data
            ):

                record.rename_field(key="title", new_key="booktitle")
                record.rename_field(key="chapter", new_key="title")

            if "journal" in record.data and "booktitle" not in record.data:
                record.rename_field(key="journal", new_key="booktitle")

            if record.data.get("booktitle", "") in [
                "Research-in-Progress Papers",
                "Research Papers",
            ]:
                if "https://aisel.aisnet.org/ecis" in record.data.get("url", ""):
                    record.update_field(
                        key="booktitle", value="ECIS", source="prep_ais_source"
                    )

        if record.data.get("journal", "") == "Management Information Systems Quarterly":
            record.update_field(
                key="journal", value="MIS Quarterly", source="prep_ais_source"
            )

        if "inproceedings" == record.data["ENTRYTYPE"]:
            if "ICIS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="International Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "PACIS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="Pacific-Asia Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "ECIS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="European Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "AMCIS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="Americas Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "HICSS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="Hawaii International Conference on System Sciences",
                    source="prep_ais_source",
                )
            if "MCIS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="Mediterranean Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "ACIS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="Australasian Conference on Information Systems",
                    source="prep_ais_source",
                )

        if "abstract" in record.data:
            if "N/A" == record.data["abstract"]:
                record.remove_field(key="abstract")
        if "author" in record.data:
            record.update_field(
                key="author",
                value=record.data["author"].replace("\n", " "),
                source="prep_ais_source",
                keep_source_if_equal=True,
            )

        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class GoogleScholarSearchSource:
    settings_class = colrev.process.DefaultSourceSettings
    source_identifier = "https://scholar.google.com/"

    source_identifier_search = "https://scholar.google.com/"
    search_mode = "individual"

    def __init__(self, *, source_operation, settings: dict) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0, "source_identifier": cls.source_identifier}
        if "related = {https://scholar.google.com/scholar?q=relat" in data:
            result["confidence"] = 0.7
            return result
        return result

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        search_operation.review_manager.logger.info(
            "Automated search not (yet) supported."
        )

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class WebOfScienceSearchSource:
    settings_class = colrev.process.DefaultSourceSettings
    source_identifier = (
        "https://www.webofscience.com/wos/woscc/full-record/" + "{{unique-id}}"
    )

    source_identifier_search = (
        "https://www.webofscience.com/wos/woscc/full-record/" + "{{unique-id}}"
    )

    search_mode = "individual"

    def __init__(self, *, source_operation, settings: dict) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:

        result = {"confidence": 0, "source_identifier": cls.source_identifier}

        if "Unique-ID = {WOS:" in data:
            result["confidence"] = 0.7
            return result
        if "UT_(Unique_WOS_ID) = {WOS:" in data:
            result["confidence"] = 0.7
            return result
        if "@article{ WOS:" in data:
            result["confidence"] = 1.0
            return result

        return result

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        search_operation.review_manager.logger.info(
            "Automated search not (yet) supported."
        )

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class ScopusSearchSource:
    settings_class = colrev.process.DefaultSourceSettings
    source_identifier = "{{url}}"

    source_identifier_search = "{{url}}"

    search_mode = "individual"

    def __init__(self, *, source_operation, settings: dict) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0, "source_identifier": cls.source_identifier}
        if "source={Scopus}," in data:
            result["confidence"] = 1.0
            return result
        return result

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        search_operation.review_manager.logger.info(
            "Automated search not (yet) supported."
        )

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        if "document_type" in record.data:
            if record.data["document_type"] == "Conference Paper":
                record.data["ENTRYTYPE"] = "inproceedings"
                if "journal" in record.data:
                    record.rename_field(key="journal", new_key="booktitle")
            elif record.data["document_type"] == "Conference Review":
                record.data["ENTRYTYPE"] = "proceedings"
                if "journal" in record.data:
                    record.rename_field(key="journal", new_key="booktitle")

            elif record.data["document_type"] == "Article":
                record.data["ENTRYTYPE"] = "article"

            record.remove_field(key="document_type")

        if "Start_Page" in record.data and "End_Page" in record.data:
            if record.data["Start_Page"] != "nan" and record.data["End_Page"] != "nan":
                record.data["pages"] = (
                    record.data["Start_Page"] + "--" + record.data["End_Page"]
                )
                record.data["pages"] = record.data["pages"].replace(".0", "")
                record.remove_field(key="Start_Page")
                record.remove_field(key="End_Page")

        if "note" in record.data:
            if "cited By " in record.data["note"]:
                record.rename_field(key="note", new_key="cited_by")
                record.data["cited_by"] = record.data["cited_by"].replace(
                    "cited By ", ""
                )

        if "author" in record.data:
            record.data["author"] = record.data["author"].replace("; ", " and ")

        drop = ["source"]
        for field_to_drop in drop:
            record.remove_field(key=field_to_drop)

        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class ACMDigitalLibrarySearchSource:
    settings_class = colrev.process.DefaultSourceSettings
    # Note : the ID contains the doi
    source_identifier = "https://dl.acm.org/doi/{{ID}}"
    source_identifier_search = "https://dl.acm.org/doi/{{ID}}"
    search_mode = "individual"

    def __init__(self, *, source_operation, settings: dict) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0, "source_identifier": cls.source_identifier}

        # Simple heuristic:
        if "publisher = {Association for Computing Machinery}," in data:
            result["confidence"] = 0.7
            return result
        # We may also check whether the ID=doi=url
        return result

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        search_operation.review_manager.logger.info(
            "Automated search not (yet) supported."
        )

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:
        # TODO (if any)
        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class PubMedSearchSource:
    settings_class = colrev.process.DefaultSourceSettings
    source_identifier = "https://pubmed.ncbi.nlm.nih.gov/{{pmid}}"
    source_identifier_search = "https://pubmed.ncbi.nlm.nih.gov/{{pmid}}"
    search_mode = "individual"

    def __init__(self, *, source_operation, settings: dict) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0, "source_identifier": cls.source_identifier}

        # Simple heuristic:
        if "PMID,Title,Authors,Citation,First Author,Journal/Book," in data:
            result["confidence"] = 1.0
            return result
        if "PMID- " in data:
            result["confidence"] = 0.7
            return result

        return result

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        search_operation.review_manager.logger.info(
            "Automated search not (yet) supported."
        )

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        if "first_author" in record.data:
            record.remove_field(key="first_author")
        if "journal/book" in record.data:
            record.rename_field(key="journal/book", new_key="journal")
        if "UNKNOWN" == record.data.get("author") and "authors" in record.data:
            record.remove_field(key="author")
            record.rename_field(key="authors", new_key="author")

        if "UNKNOWN" == record.data.get("year"):
            record.remove_field(key="year")
            if "publication_year" in record.data:
                record.rename_field(key="publication_year", new_key="year")

        if "author" in record.data:
            record.data["author"] = colrev.record.PrepRecord.format_author_field(
                input_string=record.data["author"]
            )

        # TBD: how to distinguish other types?
        record.change_entrytype(new_entrytype="article")
        record.import_provenance(source_identifier=self.source_identifier)

        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class WileyOnlineLibrarySearchSource:
    settings_class = colrev.process.DefaultSourceSettings
    source_identifier = "{{url}}"

    source_identifier_search = "{{url}}"
    search_mode = "individual"

    def __init__(self, *, source_operation, settings: dict) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        search_operation.review_manager.logger.info(
            "Automated search not (yet) supported."
        )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0, "source_identifier": cls.source_identifier}

        # Simple heuristic:
        if "eprint = {https://onlinelibrary.wiley.com/doi/pdf/" in data:
            result["confidence"] = 0.7
            return result

        return result

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:
        # TODO (if any)
        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class DBLPSearchSource:
    # settings_class = colrev.process.DefaultSourceSettings
    source_identifier = "{{biburl}}"

    source_identifier_search = "{{dblp_key}}"
    search_mode = "all"

    @dataclass
    class DBLPSearchSourceSettings:
        # pylint: disable=duplicate-code
        name: str
        filename: Path
        search_type: colrev.settings.SearchType
        source_name: str
        source_identifier: str
        search_parameters: dict
        load_conversion_script: dict
        comment: typing.Optional[str]

        _details = {
            "search_parameters": {
                "tooltip": "Currently supports a scope item "
                "with venue_key and journal_abbreviated fields."
            },
        }

    settings_class = DBLPSearchSourceSettings

    def __init__(
        self,
        *,
        source_operation,
        settings: dict,
    ) -> None:
        # maybe : validate/assert that the venue_key is available
        if "scope" not in settings["search_parameters"]:
            raise colrev_exceptions.InvalidQueryException(
                "scope required in search_parameters"
            )
        if "venue_key" not in settings["search_parameters"]["scope"]:
            raise colrev_exceptions.InvalidQueryException(
                "venue_key required in search_parameters/scope"
            )
        if "journal_abbreviated" not in settings["search_parameters"]["scope"]:
            raise colrev_exceptions.InvalidQueryException(
                "journal_abbreviated required in search_parameters/scope"
            )
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        params = self.settings.search_parameters
        feed_file = self.settings.filename

        # https://dblp.org/search/publ/api?q=ADD_TITLE&format=json

        search_operation.review_manager.logger.info(f"Retrieve DBLP: {params}")

        available_ids = []
        max_id = 1
        if not feed_file.is_file():
            records: list = []
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:
                feed_rd = search_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )
                records = list(feed_rd.values())

            available_ids = [x["dblp_key"] for x in records if "dblp_key" in x]
            max_id = max([int(x["ID"]) for x in records if x["ID"].isdigit()] + [1]) + 1

        try:
            api_url = "https://dblp.org/search/publ/api?q="

            # Note : journal_abbreviated is the abbreviated venue_key
            # TODO : tbd how the abbreviated venue_key can be retrieved
            # https://dblp.org/rec/journals/jais/KordzadehW17.html?view=bibtex

            start = 1980
            if len(records) > 100 and not search_operation.review_manager.force_mode:
                start = datetime.now().year - 2
            records_dict = {r["ID"]: r for r in records}
            for year in range(start, datetime.now().year):
                search_operation.review_manager.logger.info(f"Retrieving year {year}")
                query = params["scope"]["journal_abbreviated"] + "+" + str(year)
                # query = params['scope']["venue_key"] + "+" + str(year)
                nr_retrieved = 0
                batch_size = 250
                dblp_connector = colrev.ops.built_in.database_connectors.DBLPConnector
                while True:
                    url = (
                        api_url
                        + query.replace(" ", "+")
                        + f"&format=json&h={batch_size}&f={nr_retrieved}"
                    )
                    nr_retrieved += batch_size
                    search_operation.review_manager.logger.debug(url)

                    retrieved = False
                    for retrieved_record in dblp_connector.retrieve_dblp_records(
                        review_manager=search_operation.review_manager, url=url
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

                    if len(records) == 0:
                        continue

                    records_dict = {r["ID"]: r for r in records}
                search_operation.save_feed_file(
                    records=records_dict, feed_file=feed_file
                )

        except UnicodeEncodeError:
            print("UnicodeEncodeError - this needs to be fixed at some time")
        except (
            requests.exceptions.ReadTimeout,
            requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError,
        ):
            pass

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0, "source_identifier": cls.source_identifier}
        # Simple heuristic:
        if "bibsource = {dblp computer scienc" in data:
            result["confidence"] = 1.0
            return result
        return result

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:
        # TODO (if any)
        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class TransportResearchInternationalDocumentation:
    settings_class = colrev.process.DefaultSourceSettings
    source_identifier = "{{biburl}}"

    def __init__(self, *, source_operation, settings: dict) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0, "source_identifier": cls.source_identifier}
        # Simple heuristic:
        if "UR  - https://trid.trb.org/view/" in data:
            result["confidence"] = 0.9
            return result
        return result

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:
        # TODO (if any)
        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class CrossrefSourceSearchSource:
    """Performs a search using the Crossref API"""

    settings_class = colrev.process.DefaultSourceSettings
    source_identifier = "{{doi}}"

    source_identifier_search = "https://api.crossref.org/works/{{doi}}"
    search_mode = "all"

    def __init__(self, *, source_operation, settings: dict) -> None:
        if not any(
            x in settings["search_parameters"]["scope"]
            for x in ["query", "journal_issn"]
        ):
            raise colrev_exceptions.InvalidQueryException(
                "Crossref search_parameters/scope requires a query or journal_issn field"
            )

        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        params = self.settings.search_parameters
        feed_file = self.settings.filename
        # pylint: disable=import-outside-toplevel
        from colrev.ops.built_in.database_connectors import (
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
                records = search_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )

            available_ids = [x["doi"] for x in records.values() if "doi" in x]
            max_id = (
                max([int(x["ID"]) for x in records.values() if x["ID"].isdigit()] + [1])
                + 1
            )
        crossref_connector = CrossrefConnector(
            review_manager=search_operation.review_manager
        )

        def get_crossref_query_return(params) -> typing.Iterator[dict]:
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
            for record_dict in get_crossref_query_return(params):
                if record_dict["doi"].upper() not in available_ids:

                    # Note : discard "empty" records
                    if "" == record_dict.get("author", "") and "" == record_dict.get(
                        "title", ""
                    ):
                        continue

                    search_operation.review_manager.logger.info(
                        " retrieved " + record_dict["doi"]
                    )
                    record_dict["ID"] = str(max_id).rjust(6, "0")

                    prep_record = colrev.record.PrepRecord(data=record_dict)
                    DOIConnector.get_link_from_doi(
                        record=prep_record,
                        review_manager=search_operation.review_manager,
                    )
                    record_dict = prep_record.get_data()

                    available_ids.append(record_dict["doi"])
                    records[record_dict["ID"]] = record_dict
                    max_id += 1
        except (requests.exceptions.JSONDecodeError, KeyError) as exc:
            # TODO : watch issue
            # https://github.com/fabiobatalha/crossrefapi/issues/46
            if "504 Gateway Time-out" in str(exc):
                raise colrev_exceptions.ServiceNotAvailableException(
                    "Crossref (check https://status.crossref.org/)"
                )
            raise colrev_exceptions.ServiceNotAvailableException(
                f"Crossref (check https://status.crossref.org/) ({exc})"
            )
        search_operation.save_feed_file(records=records, feed_file=feed_file)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        # TODO
        result = {"confidence": 0, "source_identifier": cls.source_identifier}

        return result

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class BackwardSearchSource:
    """Performs a backward search extracting references from PDFs using GROBID
    Scope: all included papers with colrev_status in (rev_included, rev_synthesized)
    """

    settings_class = colrev.process.DefaultSourceSettings
    source_identifier = "{{cited_by_file}} (references)"

    source_identifier_search = "{{cited_by_file}} (references)"
    search_mode = "individual"

    def __init__(self, *, source_operation, settings: dict) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)
        self.grobid_service = source_operation.review_manager.get_grobid_service()
        self.grobid_service.start()

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        params = self.settings.search_parameters
        feed_file = self.settings.filename

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

        if not search_operation.review_manager.dataset.records_file.is_file():
            print("No records imported. Cannot run backward search yet.")
            return

        records = search_operation.review_manager.dataset.load_records_dict()

        if feed_file.is_file():
            with open(feed_file, encoding="utf8") as bibtex_file:
                if bibtex_file.read() == "":
                    feed_file_records = []
                else:
                    feed_rd = search_operation.review_manager.dataset.load_records_dict(
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

            search_operation.review_manager.logger.info(
                f'Running backward search for {record["ID"]} ({record["file"]})'
            )

            pdf_path = search_operation.review_manager.path / Path(record["file"])
            if not Path(pdf_path).is_file():
                search_operation.review_manager.logger.error(
                    f'File not found for {record["ID"]}'
                )
                continue

            # pylint: disable=consider-using-with
            options = {"consolidateHeader": "0", "consolidateCitations": "0"}
            ret = requests.post(
                self.grobid_service.GROBID_URL + "/api/processReferences",
                files=dict(input=open(pdf_path, "rb"), encoding="utf8"),
                data=options,
                headers={"Accept": "application/x-bibtex"},
            )

            new_records_dict = (
                search_operation.review_manager.dataset.load_records_dict(
                    load_str=ret.text
                )
            )
            new_records = list(new_records_dict.values())
            for new_record in new_records:
                # IDs have to be distinct
                new_record["ID"] = record["ID"] + "_backward_search_" + new_record["ID"]
                new_record["cited_by"] = record["ID"]
                new_record["cited_by_file"] = record["file"]
                if new_record["ID"] not in [r["ID"] for r in feed_file_records]:
                    feed_file_records.append(new_record)

        records_dict = {r["ID"]: r for r in feed_file_records}
        search_operation.save_feed_file(records=records_dict, feed_file=feed_file)
        search_operation.review_manager.dataset.add_changes(path=feed_file)

        if search_operation.review_manager.dataset.has_changes():
            search_operation.review_manager.create_commit(
                msg="Backward search", script_call="colrev search"
            )
        else:
            print("No new records added.")

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0, "source_identifier": cls.source_identifier}
        if str(filename).endswith("_ref_list.pdf"):
            result["confidence"] = 1.0
            return result
        return result

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class ColrevProjectSearchSource:
    """Performs a search in a CoLRev project"""

    settings_class = colrev.process.DefaultSourceSettings
    # TODO : add a colrev_projet_origin field and use it as the identifier?
    source_identifier = "project"
    source_identifier_search = "project"
    search_mode = "individual"

    def __init__(self, *, source_operation, settings: dict) -> None:
        if "url" not in settings["search_parameters"]:
            raise colrev_exceptions.InvalidQueryException(
                "url field required in search_parameters"
            )
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        params = self.settings.search_parameters
        feed_file = self.settings.filename

        if not feed_file.is_file():
            records = []
            imported_ids = []
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:
                feed_rd = search_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )
                records = list(feed_rd.values())

            imported_ids = [x["ID"] for x in records]

        project_review_manager = search_operation.review_manager.get_review_manager(
            path_str=params["scope"]["url"]
        )
        project_review_manager.get_load_operation(
            notify_state_transition_operation=False,
        )
        search_operation.review_manager.logger.info(
            f'Loading records from {params["scope"]["url"]}'
        )
        records_to_import = project_review_manager.dataset.load_records_dict()
        records_to_import = {
            ID: rec for ID, rec in records_to_import.items() if ID not in imported_ids
        }
        records_to_import_list = [
            {k: str(v) for k, v in r.items()} for r in records_to_import.values()
        ]

        search_operation.review_manager.logger.info("Importing selected records")
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
            search_operation.review_manager.dataset.import_file(record=record_to_import)

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

            search_operation.save_feed_file(records=records_dict, feed_file=feed_file)

        else:
            print("No records retrieved.")

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        # TODO
        result = {"confidence": 0, "source_identifier": cls.source_identifier}

        return result

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class LocalIndexSearchSource:
    """Performs a search in the LocalIndex"""

    settings_class = colrev.process.DefaultSourceSettings
    # TODO : add a colrev_projet_origin field and use it as the identifier?
    source_identifier = "index"
    source_identifier_search = "index"
    search_mode = "individual"

    def __init__(self, *, source_operation, settings: dict) -> None:
        if "selection_clause" not in settings["search_parameters"]:
            raise colrev_exceptions.InvalidQueryException(
                "selection_clause required in search_parameters"
            )
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        params = self.settings.search_parameters
        feed_file = self.settings.filename

        records: list = []
        imported_ids = []
        if feed_file.is_file():
            with open(feed_file, encoding="utf8") as bibtex_file:
                feed_rd = search_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )
                records = list(feed_rd.values())

            imported_ids = [x["ID"] for x in records]

        local_index = search_operation.review_manager.get_local_index()

        def retrieve_from_index(params) -> typing.List[dict]:

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

                # pylint: disable=possibly-unused-variable
                rec_df = pd.DataFrame.from_records([record])
                try:
                    query = f"SELECT * FROM rec_df WHERE {params['selection_clause']}"
                    res = ps.sqldf(query, locals())
                except PandaSQLException:
                    continue
                if len(res) > 0:
                    records_to_import.append(record)

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
            search_operation.save_feed_file(records=records_dict, feed_file=feed_file)

        else:
            print("No records found")

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        # TODO
        result = {"confidence": 0, "source_identifier": cls.source_identifier}

        return result

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class PDFSearchSource:
    settings_class = colrev.process.DefaultSourceSettings
    source_identifier = "{{file}}"
    source_identifier_search = "{{file}}"
    search_mode = "all"

    def __init__(self, *, source_operation, settings: dict) -> None:

        if "sub_dir_pattern" in settings["search_parameters"]:
            if settings["search_parameters"]["sub_dir_pattern"] != [
                "NA",
                "volume_number",
                "year",
                "volume",
            ]:
                raise colrev_exceptions.InvalidQueryException(
                    "sub_dir_pattern not in [NA, volume_number, year, volume]"
                )

        if "scope" not in settings["search_parameters"]:
            raise colrev_exceptions.InvalidQueryException(
                "scope required in search_parameters"
            )
        if "path" not in settings["search_parameters"]["scope"]:
            raise colrev_exceptions.InvalidQueryException(
                "path required in search_parameters/scope"
            )

        self.settings = from_dict(data_class=self.settings_class, data=settings)
        self.source_operation = source_operation
        self.pdf_preparation_operation = (
            source_operation.review_manager.get_pdf_prep_operation(
                notify_state_transition_operation=False
            )
        )

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        params = self.settings.search_parameters
        feed_file = self.settings.filename

        skip_duplicates = True

        def update_if_pdf_renamed(
            record_dict: dict, records: dict, search_source: Path
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
                    pdf_fp = search_operation.review_manager.path / Path(
                        record_dict["file"]
                    )
                    pdf_path = pdf_fp.parents[0]
                    potential_pdfs = pdf_path.glob("*.pdf")

                    for potential_pdf in potential_pdfs:
                        cpid_potential_pdf = colrev.record.Record.get_colrev_pdf_id(
                            review_manager=search_operation.review_manager,
                            pdf_path=potential_pdf,
                        )

                        if cpid == cpid_potential_pdf:
                            record_dict["file"] = str(
                                potential_pdf.relative_to(
                                    search_operation.review_manager.path
                                )
                            )
                            c_rec["file"] = str(
                                potential_pdf.relative_to(
                                    search_operation.review_manager.path
                                )
                            )
                            return updated
            return not_updated

        def remove_records_if_pdf_no_longer_exists() -> None:

            search_operation.review_manager.logger.debug(
                "Checking for PDFs that no longer exist"
            )

            if not feed_file.is_file():
                return

            with open(feed_file, encoding="utf8") as target_db:

                search_rd = search_operation.review_manager.dataset.load_records_dict(
                    load_str=target_db.read()
                )

            records = {}
            if search_operation.review_manager.dataset.records_file.is_file():
                records = search_operation.review_manager.dataset.load_records_dict()

            to_remove: typing.List[str] = []
            for record_dict in search_rd.values():
                x_pdf_path = search_operation.review_manager.path / Path(
                    record_dict["file"]
                )
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
                search_operation.review_manager.dataset.save_records_dict_to_file(
                    records=search_rd, save_path=feed_file
                )

            if search_operation.review_manager.dataset.records_file.is_file():
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
                    search_operation.review_manager.logger.debug(
                        f"remove from index (PDF path no longer exists): {record_dict}"
                    )
                    search_operation.review_manager.report_logger.info(
                        f"remove from index (PDF path no longer exists): {record_dict}"
                    )

                records = {
                    k: v
                    for k, v in records.items()
                    if v["colrev_origin"] not in to_remove
                }
                search_operation.review_manager.dataset.save_records_dict(
                    records=records
                )
                search_operation.review_manager.dataset.add_record_changes()

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
                review_manager=search_operation.review_manager, pdf_path=path
            )
            return [str(path), str(cpid)]

        if not feed_file.is_file():
            records = []
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:
                feed_rd = search_operation.review_manager.dataset.load_records_dict(
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

        indexed_pdf_path_str = "\n  ".join([str(x) for x in indexed_pdf_paths])
        search_operation.review_manager.logger.debug(
            f"indexed_pdf_paths: {indexed_pdf_path_str}"
        )

        overall_pdfs = path.glob("**/*.pdf")

        # Note: sets are more efficient:
        pdfs_to_index = list(set(overall_pdfs).difference(set(indexed_pdf_paths)))

        if skip_duplicates:
            search_operation.review_manager.logger.info(
                "Calculate PDF hashes to skip duplicates"
            )
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
            search_operation.review_manager.logger.error(
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
            search_operation.review_manager.logger.info(
                f"Skipping PDFs with _ocr.pdf/_wo_cp.pdf: {fp_to_skip_str}"
            )
            pdfs_to_index = [
                x for x in pdfs_to_index if str(x) not in filepaths_to_skip
            ]

        # pdfs_to_index = list(set(overall_pdfs) - set(indexed_pdf_paths))
        # pdfs_to_index = ['/home/path/file.pdf']
        pdfs_to_index_str = "\n  ".join([str(x) for x in pdfs_to_index])
        search_operation.review_manager.logger.debug(
            f"pdfs_to_index: {pdfs_to_index_str}"
        )

        if len(pdfs_to_index) > 0:
            grobid_service = search_operation.review_manager.get_grobid_service()
            grobid_service.start()
        else:
            search_operation.review_manager.logger.info("No additional PDFs to index")
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

            pdf_path = search_operation.review_manager.path / Path(record["file"])
            tei = search_operation.review_manager.get_tei(
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

                environment_manager = (
                    search_operation.review_manager.get_environment_manager()
                )
                # to allow users to update/reindex with newer version:
                record["grobid-version"] = environment_manager.docker_images[
                    "lfoppiano/grobid"
                ]
                return record

        def index_pdf(*, pdf_path: Path) -> dict:

            search_operation.review_manager.report_logger.info(
                f" extract metadata from {pdf_path}"
            )
            search_operation.review_manager.logger.info(
                f" extract metadata from {pdf_path}"
            )

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
                        record.set_text_from_pdf(
                            project_path=search_operation.review_manager.path
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

        record_id = int(
            search_operation.review_manager.dataset.get_next_id(bib_file=feed_file)
        )
        for pdf_batch in pdf_batches:

            lenrec = len(indexed_pdf_paths)
            if len(list(overall_pdfs)) > 0:
                search_operation.review_manager.logger.info(
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
            search_operation.save_feed_file(records=records_dict, feed_file=feed_file)

        else:
            print("No records found")

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0, "source_identifier": cls.source_identifier}

        if filename.suffix == ".pdf" and not BackwardSearchSource.heuristic(
            filename=filename, data=data
        ):
            result["confidence"] = 1.0
            return result

        return result

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        return record


if __name__ == "__main__":
    pass
