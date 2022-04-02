#! /usr/bin/env python
import collections
import html
import json
import logging
import re
import sys
import time
import typing
import urllib
from pathlib import Path
from urllib.parse import unquote

import bibtexparser
import dictdiffer
import git
import requests
import spacy
from alphabet_detector import AlphabetDetector
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from bs4 import BeautifulSoup
from nameparser import HumanName
from opensearchpy import NotFoundError
from p_tqdm import p_map
from thefuzz import fuzz

from colrev_core import utils
from colrev_core.environment import LocalIndex
from colrev_core.environment import RecordNotInIndexException
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.process import RecordState


class Preparation(Process):

    ad = AlphabetDetector()
    PAD = 0
    TIMEOUT = 10

    requests_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"
    }

    # https://www.crossref.org/blog/dois-and-matching-regular-expressions/
    doi_regex = re.compile(r"10\.\d{4,9}/[-._;/:A-Za-z0-9]*")

    # Based on https://en.wikipedia.org/wiki/BibTeX
    record_field_requirements = {
        "article": ["author", "title", "journal", "year", "volume", "number"],
        "inproceedings": ["author", "title", "booktitle", "year"],
        "incollection": ["author", "title", "booktitle", "publisher", "year"],
        "inbook": ["author", "title", "chapter", "publisher", "year"],
        "proceedings": ["booktitle", "editor"],
        "book": ["author", "title", "publisher", "year"],
        "phdthesis": ["author", "title", "school", "year"],
        "masterthesis": ["author", "title", "school", "year"],
        "techreport": ["author", "title", "institution", "year"],
        "unpublished": ["title", "author", "year"],
        "misc": ["author", "title", "year"],
    }

    # book, inbook: author <- editor

    record_field_inconsistencies: typing.Dict[str, typing.List[str]] = {
        "article": ["booktitle"],
        "inproceedings": ["volume", "issue", "number", "journal"],
        "incollection": [],
        "inbook": ["journal"],
        "book": ["volume", "issue", "number", "journal"],
        "phdthesis": ["volume", "issue", "number", "journal", "booktitle"],
        "masterthesis": ["volume", "issue", "number", "journal", "booktitle"],
        "techreport": ["volume", "issue", "number", "journal", "booktitle"],
        "unpublished": ["volume", "issue", "number", "journal", "booktitle"],
    }

    fields_to_keep = [
        "ID",
        "ENTRYTYPE",
        "author",
        "year",
        "title",
        "journal",
        "booktitle",
        "chapter",
        "series",
        "volume",
        "number",
        "pages",
        "doi",
        "abstract",
        "school",
        "editor",
        "book-group-author",
        "book-author",
        "keywords",
        "file",
        "status",
        "fulltext",
        "origin",
        "publisher",
        "dblp_key",
        "sem_scholar_id",
        "url",
        "metadata_source",
        "isbn",
        "address",
        "edition",
        "warning",
        "crossref",
        "date",
        "grobid-version",
        "colrev_pdf_id",
        "wos_accession_number",
        "link",
        "url",
        "crossmark",
        "warning",
        "note",
        "issn",
    ]
    fields_to_drop = [
        "type",
        "organization",
        "unique-id",
        "month",
        "researcherid-numbers",
        "orcid-numbers",
        "article-number",
        "author_keywords",
        "source",
        "affiliation",
        "document_type",
        "art_number",
        "language",
        "doc-delivery-number",
        "da",
        "usage-count-last-180-days",
        "usage-count-since-2013",
        "doc-delivery-number",
        "research-areas",
        "web-of-science-categories",
        "number-of-cited-references",
        "times-cited",
        "journal-iso",
        "oa",
        "keywords-plus",
        "funding-text",
        "funding-acknowledgement",
        "day",
        "related",
        "bibsource",
        "timestamp",
        "biburl",
        "man_prep_hints",
        "source_url",
    ]

    def __init__(
        self,
        REVIEW_MANAGER,
        force=False,
        similarity: float = 0.9,
        reprocess_state: RecordState = RecordState.md_imported,
        notify_state_transition_process: bool = True,
        debug: str = "NA",
    ):
        super().__init__(
            REVIEW_MANAGER,
            type=ProcessType.prep,
            fun=self.main,
            notify_state_transition_process=notify_state_transition_process,
            debug=(debug != "NA"),
        )
        self.notify_state_transition_process = notify_state_transition_process

        self.force_mode = force
        logging.getLogger("urllib3").setLevel(logging.ERROR)

        self.RETRIEVAL_SIMILARITY = similarity

        # if similarity == 0.0:  # if it has not been set use default
        # saved_args["RETRIEVAL_SIMILARITY"] = self.RETRIEVAL_SIMILARITY
        # RETRIEVAL_SIMILARITY = self.RETRIEVAL_SIMILARITY
        # else:
        #     reprocess_state = RecordState.md_needs_manual_preparation
        # saved_args["RETRIEVAL_SIMILARITY"] = similarity

        if reprocess_state == "":
            self.reprocess_state = RecordState.md_imported
        else:
            self.reprocess_state = reprocess_state

        self.CPUS = self.CPUS * 5
        self.NER = spacy.load("en_core_web_sm")

    def __meta_redirect(self, content: str):
        soup = BeautifulSoup(content, "lxml")
        result = soup.find("meta", attrs={"http-equiv": "REFRESH"})
        if result:
            wait, text = result["content"].split(";")
            if "http" in text:
                url = text[text.lower().find("http") :]
                url = unquote(url, encoding="utf-8", errors="replace")
                url = url[: url.find("?")]
                return str(url)
        return None

    def get_link_from_doi(self, record: dict) -> dict:

        url = f"https://www.doi.org/{record['doi']}"

        # TODO : retry for 50X
        # from requests.adapters import HTTPAdapter
        # from requests.adapters import Retry
        # example for testing: ({'doi':'10.1177/02683962221086300'})
        # s = requests.Session()
        # headers = {"user-agent": f"{__name__} (mailto:{self.EMAIL})"}
        # retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 502, 503, 504 ])
        # s.mount('https://', HTTPAdapter(max_retries=retries))
        # ret = s.get(url, headers=headers)
        # print(ret)

        try:
            ret = requests.get(url, headers=self.requests_headers, timeout=self.TIMEOUT)
            if 503 == ret.status_code:
                return record
            elif (
                200 == ret.status_code
                and "doi.org" not in ret.url
                and "linkinghub" not in ret.url
            ):
                url = ret.url
            else:
                # follow the chain of redirects
                while self.__meta_redirect(ret.content.decode("utf-8")):
                    url = self.__meta_redirect(ret.content.decode("utf-8"))
                    ret = requests.get(
                        url, "GET", headers=self.requests_headers, timeout=self.TIMEOUT
                    )
            record["url"] = str(url)
        except requests.exceptions.ConnectionError:
            pass
        return record

    def correct_recordtype(self, record: dict) -> dict:

        if self.__is_complete(record) and not self.__has_inconsistent_fields(record):
            return record

        if self.RETRIEVAL_SIMILARITY > 0.9:
            return record

        if (
            "dissertation" in record.get("fulltext", "NA").lower()
            and record["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = record["ENTRYTYPE"]
            record.update(ENTRYTYPE="phdthesis")
            self.REVIEW_MANAGER.report_logger.info(
                f' {record["ID"]}'.ljust(self.PAD, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("dissertation" in fulltext link)'
            )

        if (
            "thesis" in record.get("fulltext", "NA").lower()
            and record["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = record["ENTRYTYPE"]
            record.update(ENTRYTYPE="phdthesis")
            self.REVIEW_MANAGER.report_logger.info(
                f' {record["ID"]}'.ljust(self.PAD, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("thesis" in fulltext link)'
            )

        if (
            "This thesis" in record.get("abstract", "NA").lower()
            and record["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = record["ENTRYTYPE"]
            record.update(ENTRYTYPE="phdthesis")
            self.REVIEW_MANAGER.report_logger.info(
                f' {record["ID"]}'.ljust(self.PAD, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("thesis" in abstract)'
            )

        # Journal articles should not have booktitles/series set.
        if "article" == record["ENTRYTYPE"]:
            if "booktitle" in record:
                if "journal" not in record:
                    record.update(journal=record["booktitle"])
                    del record["booktitle"]
            if "series" in record:
                if "journal" not in record:
                    record.update(journal=record["series"])
                    del record["series"]

        if "article" == record["ENTRYTYPE"]:
            if "journal" not in record:
                if "series" in record:
                    journal_string = record["series"]
                    record.update(journal=journal_string)
                    del record["series"]

        return record

    def format_minor(self, record: dict) -> dict:

        fields_to_process = [
            "author",
            "year",
            "title",
            "journal",
            "booktitle",
            "series",
            "volume",
            "number",
            "pages",
            "doi",
            "abstract",
        ]
        for field in fields_to_process:
            if field in record:
                record[field] = (
                    str(record[field])
                    .replace("\n", " ")
                    .rstrip()
                    .lstrip()
                    .replace("{", "")
                    .replace("}", "")
                    .rstrip(",")
                )
                record[field] = re.sub(r"\s+", " ", record[field])

        if "title" in record:
            title_text = self.NER(record["title"])
            for word in title_text.ents:
                if word.text.islower():
                    if word.label_ in ["GPE", "NORP", "LOC", "ORG", "PERSON"]:
                        record["title"] = record["title"].replace(
                            word.text, word.text.title()
                        )

        if record.get("volume", "") == "ahead-of-print":
            del record["volume"]
        if record.get("number", "") == "ahead-of-print":
            del record["number"]

        return record

    def __title_if_mostly_upper(self, input_string: str) -> str:
        if not re.match(r"[a-zA-Z]+", input_string):
            return input_string

        if self.__percent_upper_chars(input_string) > 0.8:
            return input_string.capitalize()
        else:
            return input_string

    def format(self, record: dict) -> dict:

        fields_to_process = [
            "author",
            "year",
            "title",
            "journal",
            "booktitle",
            "series",
            "volume",
            "number",
            "pages",
            "doi",
            "abstract",
        ]
        for field in fields_to_process:
            if field in record:
                record[field] = (
                    record[field]
                    .replace("\n", " ")
                    .rstrip()
                    .lstrip()
                    .replace("{", "")
                    .replace("}", "")
                )

        if "author" in record:
            # DBLP appends identifiers to non-unique authors
            record.update(author=str(re.sub(r"[0-9]{4}", "", record["author"])))

            # fix name format
            if (1 == len(record["author"].split(" ")[0])) or (
                ", " not in record["author"]
            ):
                record.update(author=self.format_author_field(record["author"]))

        if "title" in record:
            record.update(title=re.sub(r"\s+", " ", record["title"]).rstrip("."))
            record.update(title=self.__title_if_mostly_upper(record["title"]))

        if "booktitle" in record:
            record.update(booktitle=self.__title_if_mostly_upper(record["booktitle"]))

            stripped_btitle = re.sub(r"\d{4}", "", record["booktitle"])
            stripped_btitle = re.sub(r"\d{1,2}th", "", stripped_btitle)
            stripped_btitle = re.sub(r"\d{1,2}nd", "", stripped_btitle)
            stripped_btitle = re.sub(r"\d{1,2}rd", "", stripped_btitle)
            stripped_btitle = re.sub(r"\d{1,2}st", "", stripped_btitle)
            stripped_btitle = re.sub(r"\([A-Z]{3,6}\)", "", stripped_btitle)
            stripped_btitle = stripped_btitle.replace("Proceedings of the", "").replace(
                "Proceedings", ""
            )
            stripped_btitle = stripped_btitle.lstrip().rstrip()
            record.update(booktitle=stripped_btitle)

        if "date" in record and "year" not in record:
            year = re.search(r"\d{4}", record["date"])
            if year:
                record["year"] = year.group(0)

        if "journal" in record:
            if len(record["journal"]) > 10:
                record.update(journal=self.__title_if_mostly_upper(record["journal"]))

        if "pages" in record:
            record.update(pages=self.__unify_pages_field(record["pages"]))
            if (
                not re.match(r"^\d*$", record["pages"])
                and not re.match(r"^\d*--\d*$", record["pages"])
                and not re.match(r"^[xivXIV]*--[xivXIV]*$", record["pages"])
            ):
                self.REVIEW_MANAGER.report_logger.info(
                    f' {record["ID"]}:'.ljust(self.PAD, " ")
                    + f'Unusual pages: {record["pages"]}'
                )

        if "doi" in record:
            record.update(doi=record["doi"].replace("http://dx.doi.org/", "").upper())

        if "number" not in record and "issue" in record:
            record.update(number=record["issue"])
            del record["issue"]

        if "url" in record and "fulltext" in record:
            if record["url"] == record["fulltext"]:
                del record["fulltext"]

        return record

    def get_record_from_local_index(self, record: dict) -> dict:

        LOCAL_INDEX = LocalIndex()

        retrieved = False
        try:
            retrieved_record = LOCAL_INDEX.retrieve(record, include_file=False)
            retrieved = True
        except (RecordNotInIndexException, NotFoundError):
            pass
            try:
                if "CURATED" == record.get("metadata_source", ""):
                    if "source_url" in record:  # do not change to other source

                        ind_rec = LOCAL_INDEX.retrieve(
                            record.copy(), include_file=False
                        )
                        if ind_rec["source_url"] == record["source_url"]:
                            # Keep all fields of the original record
                            retrieved_record = record
                            # Update the essential metadata
                            for key in self.fields_to_keep:
                                if key in ind_rec:
                                    retrieved_record = ind_rec[key]
                            # Add complementary fields if they are not yet avilable
                            for k, v in ind_rec.items():
                                if k not in retrieved_record:
                                    retrieved_record[k] = v
                        else:
                            self.REVIEW_MANAGER.logger.error(
                                "Error: curated record has other "
                                f'source_url in LocalIndex ({record["ID"]})'
                            )

                    else:
                        # update record metadata
                        retrieved_record = LOCAL_INDEX.retrieve(
                            record, include_file=False
                        )
                    retrieved = True
                else:
                    retrieved_record = LOCAL_INDEX.retrieve_from_toc(
                        record, self.RETRIEVAL_SIMILARITY, include_file=False
                    )
                    retrieved = True
            except (RecordNotInIndexException, NotFoundError):
                pass

        if retrieved:

            for k, v in retrieved_record.items():
                if k in ["origin", "ID", "grobid-version"]:
                    continue
                if "file" == k:
                    if "file" in record:
                        continue
                record[k] = v

            git_repo = git.Repo(str(self.REVIEW_MANAGER.path))
            cur_project_source_paths = [str(self.REVIEW_MANAGER.path)]
            for remote in git_repo.remotes:
                if remote.url:
                    shared_url = remote.url
                    shared_url = shared_url.rstrip(".git")
                    cur_project_source_paths.append(shared_url)
                    break

            if not any(
                x in cur_project_source_paths
                for x in retrieved_record.get("source_url", "").split(";")
            ):
                record["metadata_source"] = "CURATED"

            # Note : don't list the same repository as its own source_url
            # (source_url s should point to other/external repos)
            for cur_project_source_path in cur_project_source_paths:
                record["source_url"] = record["source_url"].replace(
                    cur_project_source_path, ""
                )
            if record["source_url"] == "":
                del record["source_url"]

            # extend fields_to_keep (to retrieve all fields from the index)
            for k in retrieved_record.keys():
                # Note : the source_url field will be removed at the end
                # but if we include it here, it will be printed to the
                # detailed report (and is available for tracing errors)
                if k not in self.fields_to_keep and k != "source_url":
                    self.fields_to_keep.append(k)

            record = LOCAL_INDEX.set_source_url_link(record)

        return record

    def __mostly_upper_case(self, input_string: str) -> bool:
        if not re.match(r"[a-zA-Z]+", input_string):
            return False
        input_string = input_string.replace(".", "").replace(",", "")
        words = input_string.split()
        return sum(word.isupper() for word in words) / len(words) > 0.8

    def format_author_field(self, input_string: str) -> str:

        input_string = input_string.replace("\n", " ")
        # DBLP appends identifiers to non-unique authors
        input_string = str(re.sub(r"[0-9]{4}", "", input_string))

        names = input_string.split(" and ")
        author_string = ""
        for name in names:
            # Note: https://github.com/derek73/python-nameparser
            # is very effective (maybe not perfect)

            parsed_name = HumanName(name)
            if self.__mostly_upper_case(
                input_string.replace(" and ", "").replace("Jr", "")
            ):
                parsed_name.capitalize(force=True)

            parsed_name.string_format = "{last} {suffix}, {first} {middle}"
            # '{last} {suffix}, {first} ({nickname}) {middle}'
            author_name_string = str(parsed_name).replace(" , ", ", ")
            # Note: there are errors for the following author:
            # JR Cromwell and HK Gardner
            # The JR is probably recognized as Junior.
            # Check whether this is fixed in the Grobid name parser

            if author_string == "":
                author_string = author_name_string
            else:
                author_string = author_string + " and " + author_name_string

        return author_string

    def __get_container_title(self, record: dict) -> str:
        container_title = "NA"
        if "ENTRYTYPE" not in record:
            container_title = record.get("journal", record.get("booktitle", "NA"))
        else:
            if "article" == record["ENTRYTYPE"]:
                container_title = record.get("journal", "NA")
            if "inproceedings" == record["ENTRYTYPE"]:
                container_title = record.get("booktitle", "NA")
            if "book" == record["ENTRYTYPE"]:
                container_title = record.get("title", "NA")
            if "inbook" == record["ENTRYTYPE"]:
                container_title = record.get("booktitle", "NA")
        return container_title

    def __unify_pages_field(self, input_string: str) -> str:
        if not isinstance(input_string, str):
            return input_string
        if not re.match(r"^\d*--\d*$", input_string) and "--" not in input_string:
            input_string = (
                input_string.replace("-", "--")
                .replace("–", "--")
                .replace("----", "--")
                .replace(" -- ", "--")
                .rstrip(".")
            )
        return input_string

    def get_md_from_doi(self, record: dict) -> dict:
        if "doi" not in record or "CURATED" == record.get("metadata_source", ""):
            return record
        record = self.retrieve_doi_metadata(record)
        if "title" in record:
            record["title"] = self.__title_if_mostly_upper(record["title"])
            record["title"] = record["title"].replace("\n", " ")
        record = self.get_link_from_doi(record)
        record.update(status=RecordState.md_prepared)
        record.update(metadata_source="DOI.ORG")
        return record

    def crossref_json_to_record(self, item: dict) -> dict:
        # Note: the format differst between crossref and doi.org
        record: dict = {}

        # Note : better use the doi-link resolution
        # if "link" in item:
        #     fulltext_link_l = [
        #         u["URL"] for u in item["link"] if "pdf" in u["content-type"]
        #     ]
        #     if len(fulltext_link_l) == 1:
        #         record["fulltext"] = fulltext_link_l.pop()
        #     item["link"] = [u for u in item["link"] if "pdf" not in u["content-type"]]
        #     if len(item["link"]) >= 1:
        #         link = item["link"][0]["URL"]
        #         if link != record.get("fulltext", ""):
        #             record["link"] = link

        if "title" in item:
            if isinstance(item["title"], list):
                if len(item["title"]) > 0:
                    retrieved_title = item["title"][0]
                    retrieved_title = re.sub(r"\s+", " ", str(retrieved_title))
                    retrieved_title = retrieved_title.replace("\n", " ")
                    record.update(title=retrieved_title)
            elif isinstance(item["title"], str):
                retrieved_title = item["title"]
                record.update(title=retrieved_title)

        container_title = ""
        if "container-title" in item:
            if isinstance(item["container-title"], list):
                if len(item["container-title"]) > 0:
                    container_title = item["container-title"][0]
            elif isinstance(item["container-title"], str):
                container_title = item["container-title"]

        if "type" in item:
            if "journal-article" == item.get("type", "NA"):
                record.update(ENTRYTYPE="article")
                if container_title is not None:
                    record.update(journal=container_title)
            if "proceedings-article" == item.get("type", "NA"):
                record.update(ENTRYTYPE="inproceedings")
                if container_title is not None:
                    record.update(booktitle=container_title)
            if "book" == item.get("type", "NA"):
                record.update(ENTRYTYPE="book")
                if container_title is not None:
                    record.update(series=container_title)

        if "DOI" in item:
            record.update(doi=item["DOI"].upper())

        authors = [
            f'{author["family"]}, {author.get("given", "")}'
            for author in item.get("author", "NA")
            if "family" in author
        ]
        authors_string = " and ".join(authors)
        # authors_string = format_author_field(authors_string)
        record.update(author=authors_string)

        try:
            if "published-print" in item:
                date_parts = item["published-print"]["date-parts"]
                record.update(year=str(date_parts[0][0]))
            elif "published-online" in item:
                date_parts = item["published-online"]["date-parts"]
                record.update(year=str(date_parts[0][0]))
        except KeyError:
            pass

        retrieved_pages = item.get("page", "")
        if retrieved_pages != "":
            # DOI data often has only the first page.
            if (
                not record.get("pages", "no_pages") in retrieved_pages
                and "-" in retrieved_pages
            ):
                record.update(pages=self.__unify_pages_field(str(retrieved_pages)))
        retrieved_volume = item.get("volume", "")
        if not retrieved_volume == "":
            record.update(volume=str(retrieved_volume))

        retrieved_number = item.get("issue", "")
        if "journal-issue" in item:
            if "issue" in item["journal-issue"]:
                retrieved_number = item["journal-issue"]["issue"]
        if not retrieved_number == "":
            record.update(number=str(retrieved_number))

        if "abstract" in item:
            retrieved_abstract = item["abstract"]
            if not retrieved_abstract == "":
                retrieved_abstract = re.sub(
                    r"<\/?jats\:[^>]*>", " ", retrieved_abstract
                )
                retrieved_abstract = re.sub(r"\s+", " ", retrieved_abstract)
                retrieved_abstract = str(retrieved_abstract).replace("\n", "")
                retrieved_abstract = retrieved_abstract.lstrip().rstrip()
                record.update(abstract=retrieved_abstract)

        if "content-domain" in item:
            if "crossmark" in item["content-domain"]:
                if item["content-domain"]["crossmark"]:
                    record["crossmark"] = "True"

        for k, v in record.items():
            record[k] = html.unescape(v).replace("{", "").replace("}", "")

        return record

    def __crossref_query(
        self, record: dict, jour_vol_iss_list: bool = False
    ) -> typing.List[typing.Dict]:
        # https://github.com/CrossRef/rest-api-doc
        api_url = "https://api.crossref.org/works?"

        if not jour_vol_iss_list:
            params = {"rows": "15"}
            bibl = record["title"].replace("-", "_") + " " + record.get("year", "")
            bibl = re.sub(r"[\W]+", "", bibl.replace(" ", "_"))
            params["query.bibliographic"] = bibl.replace("_", " ")

            container_title = self.__get_container_title(record)
            if "." not in container_title:
                container_title = container_title.replace(" ", "_")
                container_title = re.sub(r"[\W]+", "", container_title)
                params["query.container-title"] = container_title.replace("_", " ")

            author_last_names = [
                x.split(",")[0] for x in record.get("author", "").split(" and ")
            ]
            author_string = " ".join(author_last_names)
            author_string = re.sub(r"[\W]+", "", author_string.replace(" ", "_"))
            params["query.author"] = author_string.replace("_", " ")
        else:
            params = {"rows": "25"}
            container_title = re.sub(r"[\W]+", " ", record["journal"])
            params["query.container-title"] = container_title.replace("_", " ")

            query_field = ""
            if "volume" in record:
                query_field = record["volume"]
            if "number" in record:
                query_field = query_field + "+" + record["number"]
            params["query"] = query_field

        url = api_url + urllib.parse.urlencode(params)
        headers = {"user-agent": f"{__name__} (mailto:{self.EMAIL})"}
        record_list = []
        try:
            self.REVIEW_MANAGER.logger.debug(url)
            ret = requests.get(url, headers=headers, timeout=self.TIMEOUT)
            ret.raise_for_status()
            if ret.status_code != 200:
                self.REVIEW_MANAGER.logger.debug(
                    f"crossref_query failed with status {ret.status_code}"
                )
                return [{}]

            data = json.loads(ret.text)
            items = data["message"]["items"]
            most_similar = 0
            most_similar_record = {}
            for item in items:
                if "title" not in item:
                    continue

                retrieved_record = self.crossref_json_to_record(item)

                title_similarity = fuzz.partial_ratio(
                    retrieved_record["title"].lower(),
                    record.get("title", "").lower(),
                )
                container_similarity = fuzz.partial_ratio(
                    self.__get_container_title(retrieved_record).lower(),
                    self.__get_container_title(record).lower(),
                )
                weights = [0.6, 0.4]
                similarities = [title_similarity, container_similarity]

                similarity = sum(
                    similarities[g] * weights[g] for g in range(len(similarities))
                )
                # logger.debug(f'record: {pp.pformat(record)}')
                # logger.debug(f'similarities: {similarities}')
                # logger.debug(f'similarity: {similarity}')
                # pp.pprint(retrieved_record)

                if jour_vol_iss_list:
                    record_list.append(retrieved_record)
                if most_similar < similarity:
                    most_similar = similarity
                    most_similar_record = retrieved_record
        except json.decoder.JSONDecodeError:
            pass
        except requests.exceptions.ConnectionError:
            return [{}]

        if jour_vol_iss_list:
            return record_list
        else:
            return [most_similar_record]

    def __container_is_abbreviated(self, record: dict) -> bool:
        if "journal" in record:
            if record["journal"].count(".") > 2:
                return True
            if record["journal"].isupper():
                return True
        if "booktitle" in record:
            if record["booktitle"].count(".") > 2:
                return True
            if record["booktitle"].isupper():
                return True
        # add heuristics? (e.g., Hawaii Int Conf Syst Sci)
        return False

    def __abbreviate_container(self, record: dict, min_len: int) -> dict:
        if "journal" in record:
            record["journal"] = " ".join(
                [x[:min_len] for x in record["journal"].split(" ")]
            )
        return record

    def __get_abbrev_container_min_len(self, record: dict) -> int:
        min_len = -1
        if "journal" in record:
            min_len = min(len(x) for x in record["journal"].replace(".", "").split(" "))
        if "booktitle" in record:
            min_len = min(
                len(x) for x in record["booktitle"].replace(".", "").split(" ")
            )
        return min_len

    def get_retrieval_similarity(self, record: dict, retrieved_record: dict) -> float:

        if self.__container_is_abbreviated(record):
            min_len = self.__get_abbrev_container_min_len(record)
            self.__abbreviate_container(retrieved_record, min_len)
            self.__abbreviate_container(record, min_len)
        if self.__container_is_abbreviated(retrieved_record):
            min_len = self.__get_abbrev_container_min_len(retrieved_record)
            self.__abbreviate_container(record, min_len)
            self.__abbreviate_container(retrieved_record, min_len)

        if "title" in record:
            record["title"] = record["title"][:90]
        if "title" in retrieved_record:
            retrieved_record["title"] = retrieved_record["title"][:90]

        if "author" in record:
            record["author"] = utils.format_authors_string(record["author"])
            record["author"] = record["author"][:45]
        if "author" in retrieved_record:
            retrieved_record["author"] = utils.format_authors_string(
                retrieved_record["author"]
            )
            retrieved_record["author"] = retrieved_record["author"][:45]
        if not ("volume" in record and "volume" in retrieved_record):
            record["volume"] = "nan"
            retrieved_record["volume"] = "nan"
        if not ("number" in record and "number" in retrieved_record):
            record["number"] = "nan"
            retrieved_record["number"] = "nan"
        if not ("pages" in record and "pages" in retrieved_record):
            record["pages"] = "nan"
            retrieved_record["pages"] = "nan"
        # Sometimes, the number of pages is provided (not the range)
        elif not ("--" in record["pages"] and "--" in retrieved_record["pages"]):
            record["pages"] = "nan"
            retrieved_record["pages"] = "nan"

        if "editorial" in record.get("title", "NA").lower():
            if not all(x in record for x in ["volume", "number"]):
                return 0
        # pp.pprint(record)
        # pp.pprint(retrieved_record)
        similarity = utils.get_record_similarity(record, retrieved_record)

        return similarity

    def get_md_from_crossref(self, record: dict) -> dict:
        if "title" not in record or "CURATED" == record.get("metadata_source", ""):
            return record

        # To test the metadata provided for a particular DOI use:
        # https://api.crossref.org/works/DOI

        self.REVIEW_MANAGER.logger.debug(f'get_md_from_crossref({record["ID"]})')
        MAX_RETRIES_ON_ERROR = 3
        # https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
        if len(record["title"]) > 35:
            try:

                retrieved_record_list = self.__crossref_query(record)
                retrieved_record = retrieved_record_list.pop()
                retries = 0
                while not retrieved_record and retries < MAX_RETRIES_ON_ERROR:
                    retries += 1
                    retrieved_record_list = self.__crossref_query(record)
                    retrieved_record = retrieved_record_list.pop()

                if 0 == len(retrieved_record):
                    return record

                similarity = self.get_retrieval_similarity(
                    record.copy(), retrieved_record.copy()
                )
                if similarity > self.RETRIEVAL_SIMILARITY:
                    self.REVIEW_MANAGER.logger.debug("Found matching record")
                    self.REVIEW_MANAGER.logger.debug(
                        f"crossref similarity: {similarity} "
                        f"(>{self.RETRIEVAL_SIMILARITY})"
                    )
                    record = self.__fuse_best_fields(record, retrieved_record)
                    record = self.get_link_from_doi(record)
                    record.update(status=RecordState.md_prepared)
                    record.update(metadata_source="CROSSREF")

                else:
                    self.REVIEW_MANAGER.logger.debug(
                        f"crossref similarity: {similarity} "
                        f"(<{self.RETRIEVAL_SIMILARITY})"
                    )

            except requests.exceptions.HTTPError:
                pass
            except requests.exceptions.ReadTimeout:
                pass
            except KeyboardInterrupt:
                sys.exit()
        return record

    def get_year_from_vol_iss_jour_crossref(self, record: dict) -> dict:
        # The year depends on journal x volume x issue
        if not (
            ("journal" in record and "volume" in record and "number")
            and "year" not in record
        ):
            return record

        self.REVIEW_MANAGER.logger.debug(f'get_md_from_crossref({record["ID"]})')
        MAX_RETRIES_ON_ERROR = 3
        try:
            modified_record = record.copy()
            modified_record = {
                k: v
                for k, v in modified_record.items()
                if k in ["journal", "volume", "number"]
            }

            # http://api.crossref.org/works?
            # query.container-title=%22MIS+Quarterly%22&query=%2216+2%22

            retrieved_records_list = self.__crossref_query(
                record, jour_vol_iss_list=True
            )
            retries = 0
            while not retrieved_records_list and retries < MAX_RETRIES_ON_ERROR:
                retries += 1
                retrieved_records_list = self.__crossref_query(
                    record, jour_vol_iss_list=True
                )
            if 0 == len(retrieved_records_list):
                return record

            retrieved_records = [
                r
                for r in retrieved_records_list
                if r.get("volume", "NA") == record.get("volume", "NA")
                and r.get("journal", "NA") == record.get("journal", "NA")
                and r.get("number", "NA") == record.get("number", "NA")
            ]
            years = [r["year"] for r in retrieved_records]
            if len(years) == 0:
                return record
            most_common = max(years, key=years.count)
            self.REVIEW_MANAGER.logger.debug(most_common)
            self.REVIEW_MANAGER.logger.debug(years.count(most_common))
            if years.count(most_common) > 3:
                record["year"] = most_common
                record["metadata_source"] = "CROSSREF"
        except requests.exceptions.HTTPError:
            pass
        except requests.exceptions.ReadTimeout:
            pass
        except KeyboardInterrupt:
            sys.exit()

        return record

    def __sem_scholar_json_to_record(self, item: dict, record: dict) -> dict:
        retrieved_record: dict = {}
        if "authors" in item:
            authors_string = " and ".join(
                [author["name"] for author in item["authors"] if "name" in author]
            )
            authors_string = self.format_author_field(authors_string)
            retrieved_record.update(author=authors_string)
        if "abstract" in item:
            retrieved_record.update(abstract=item["abstract"])
        if "doi" in item:
            retrieved_record.update(doi=str(item["doi"]).upper())
        if "title" in item:
            retrieved_record.update(title=item["title"])
        if "year" in item:
            retrieved_record.update(year=item["year"])
        # Note: semantic scholar does not provide data on the type of venue.
        # we therefore use the original ENTRYTYPE
        if "venue" in item:
            if "journal" in record:
                retrieved_record.update(journal=item["venue"])
            if "booktitle" in record:
                retrieved_record.update(booktitle=item["venue"])
        if "url" in item:
            retrieved_record.update(sem_scholar_id=item["url"])

        keys_to_drop = []
        for key, value in retrieved_record.items():
            retrieved_record[key] = str(value).replace("\n", " ").lstrip().rstrip()
            if value in ["", "None"] or value is None:
                keys_to_drop.append(key)
        for key in keys_to_drop:
            del retrieved_record[key]
        return retrieved_record

    def get_doi_from_sem_scholar(self, record: dict) -> dict:

        enrich_only = False
        if "doi" in record:
            enrich_only = True

        try:
            search_api_url = (
                "https://api.semanticscholar.org/graph/v1/paper/search?query="
            )
            url = search_api_url + record.get("title", "").replace(" ", "+")
            self.REVIEW_MANAGER.logger.debug(url)
            headers = {"user-agent": f"{__name__} (mailto:{self.EMAIL})"}
            ret = requests.get(url, headers=headers, timeout=self.TIMEOUT)
            ret.raise_for_status()

            data = json.loads(ret.text)
            items = data["data"]
            if len(items) == 0:
                return record
            if "paperId" not in items[0]:
                return record

            paper_id = items[0]["paperId"]
            record_retrieval_url = (
                "https://api.semanticscholar.org/v1/paper/" + paper_id
            )
            self.REVIEW_MANAGER.logger.debug(record_retrieval_url)
            ret_ent = requests.get(
                record_retrieval_url, headers=headers, timeout=self.TIMEOUT
            )
            ret_ent.raise_for_status()
            item = json.loads(ret_ent.text)
            retrieved_record = self.__sem_scholar_json_to_record(item, record)

            red_record_copy = record.copy()
            for key in ["volume", "number", "number", "pages"]:
                if key in red_record_copy:
                    del red_record_copy[key]
            # self.REVIEW_MANAGER.pp.pprint(retrieved_record)

            similarity = self.get_retrieval_similarity(
                red_record_copy, retrieved_record.copy()
            )
            if similarity > self.RETRIEVAL_SIMILARITY:
                self.REVIEW_MANAGER.logger.debug("Found matching record")
                self.REVIEW_MANAGER.logger.debug(
                    f"scholar similarity: {similarity} "
                    f"(>{self.RETRIEVAL_SIMILARITY})"
                )

                if not enrich_only:
                    record = self.__fuse_best_fields(record, retrieved_record)
                if record.get("doi", "") == "NONE":
                    del record["doi"]
            else:
                self.REVIEW_MANAGER.logger.debug(
                    f"scholar similarity: {similarity} "
                    f"(<{self.RETRIEVAL_SIMILARITY})"
                )
        except requests.exceptions.ReadTimeout:
            pass
        except KeyError:
            pass
        except requests.exceptions.HTTPError:
            pass
        except UnicodeEncodeError:
            self.REVIEW_MANAGER.logger.error(
                "UnicodeEncodeError - this needs to be fixed at some time"
            )
            pass
        except requests.exceptions.ConnectionError:
            pass
        return record

    def __open_library_json_to_record(self, item: dict) -> dict:
        retrieved_record: dict = {}

        if "author_name" in item:
            authors_string = " and ".join(
                [self.format_author_field(author) for author in item["author_name"]]
            )
            retrieved_record.update(author=authors_string)
        if "publisher" in item:
            retrieved_record.update(publisher=str(item["publisher"][0]))
        if "title" in item:
            retrieved_record.update(title=str(item["title"]))
        if "publish_year" in item:
            retrieved_record.update(year=str(item["publish_year"][0]))
        if "edition_count" in item:
            retrieved_record.update(edition=str(item["edition_count"]))
        if "seed" in item:
            if "/books/" in item["seed"][0]:
                retrieved_record.update(ENTRYTYPE="book")
        if "publish_place" in item:
            retrieved_record.update(address=str(item["publish_place"][0]))
        if "isbn" in item:
            retrieved_record.update(isbn=str(item["isbn"][0]))

        return retrieved_record

    def get_md_from_open_library(self, record: dict) -> dict:

        if record.get("ENTRYTYPE", "NA") != "book" or "CURATED" == record.get(
            "metadata_source", ""
        ):
            return record

        try:
            if "isbn" in record:
                isbn = record["isbn"].replace("-", "").replace(" ", "")
                url = f"https://openlibrary.org/isbn/{isbn}.json"
                ret = requests.get(
                    url, headers=self.requests_headers, timeout=self.TIMEOUT
                )
                ret.raise_for_status()
                self.REVIEW_MANAGER.logger.debug(url)
                if '"error": "notfound"' in ret.text:
                    del record["isbn"]

                item = json.loads(ret.text)

            if "isbn" not in record:
                base_url = "https://openlibrary.org/search.json?"
                url = ""
                if record.get("author", "NA").split(",")[0]:
                    url = (
                        base_url + "&author=" + record.get("author", "NA").split(",")[0]
                    )
                if "inbook" == record["ENTRYTYPE"] and "editor" in record:
                    if record.get("editor", "NA").split(",")[0]:
                        url = (
                            base_url
                            + "&author="
                            + record.get("editor", "NA").split(",")[0]
                        )
                if base_url not in url:
                    return record

                title = record.get("title", record.get("booktitle", "NA"))
                if len(title) < 10:
                    return record
                if ":" in title:
                    title = title[: title.find(":")]  # To catch sub-titles
                url = url + "&title=" + title.replace(" ", "+")
                ret = requests.get(
                    url, headers=self.requests_headers, timeout=self.TIMEOUT
                )
                ret.raise_for_status()
                self.REVIEW_MANAGER.logger.debug(url)

                # if we have an exact match, we don't need to check the similarity
                if '"numFoundExact": true,' not in ret.text:
                    return record

                data = json.loads(ret.text)
                items = data["docs"]
                if not items:
                    return record
                item = items[0]

            retrieved_record = self.__open_library_json_to_record(item)

            for key, val in retrieved_record.items():
                record[key] = val
            record.update(metadata_source="OPEN_LIBRARY")
            if "title" in record and "booktitle" in record:
                del record["booktitle"]
        except requests.exceptions.ReadTimeout:
            pass
        except requests.exceptions.HTTPError:
            pass
        except UnicodeEncodeError:
            self.REVIEW_MANAGER.logger.error(
                "UnicodeEncodeError - this needs to be fixed at some time"
            )
            pass
        except requests.exceptions.ConnectionError:
            pass
        return record

    def __get_dblp_venue(self, venue_string: str, type: str) -> str:
        # Note : venue_string should be like "behaviourIT"
        # Note : journals that have been renamed seem to return the latest
        # journal name. Example:
        # https://dblp.org/db/journals/jasis/index.html
        venue = venue_string
        api_url = "https://dblp.org/search/venue/api?q="
        url = api_url + venue_string.replace(" ", "+") + "&format=json"
        headers = {"user-agent": f"{__name__} (mailto:{self.EMAIL})"}
        try:
            ret = requests.get(url, headers=headers, timeout=self.TIMEOUT)
            ret.raise_for_status()
            data = json.loads(ret.text)
            if "hit" not in data["result"]["hits"]:
                return ""
            hits = data["result"]["hits"]["hit"]
            for hit in hits:
                if hit["info"]["type"] != type:
                    continue
                if f"/{venue_string.lower()}/" in hit["info"]["url"].lower():
                    venue = hit["info"]["venue"]
                    break

            venue = re.sub(r" \(.*?\)", "", venue)
        except requests.exceptions.ConnectionError:
            pass
        return venue

    def dblp_json_to_record(self, item: dict) -> dict:
        # To test in browser:
        # https://dblp.org/search/publ/api?q=ADD_TITLE&format=json

        retrieved_record = {}
        if "Withdrawn Items" == item["type"]:
            if "journals" == item["key"][:8]:
                item["type"] = "Journal Articles"
            if "conf" == item["key"][:4]:
                item["type"] = "Conference and Workshop Papers"
            retrieved_record["warning"] = "Withdrawn (according to DBLP)"
        if "Journal Articles" == item["type"]:
            retrieved_record["ENTRYTYPE"] = "article"
            lpos = item["key"].find("/") + 1
            rpos = item["key"].rfind("/")
            jour = item["key"][lpos:rpos]
            retrieved_record["journal"] = self.__get_dblp_venue(jour, "Journal")
        if "Conference and Workshop Papers" == item["type"]:
            retrieved_record["ENTRYTYPE"] = "inproceedings"
            retrieved_record["booktitle"] = self.__get_dblp_venue(
                item["venue"], "Conference or Workshop"
            )
        if "title" in item:
            retrieved_record["title"] = item["title"].rstrip(".")
        if "year" in item:
            retrieved_record["year"] = item["year"]
        if "volume" in item:
            retrieved_record["volume"] = item["volume"]
        if "number" in item:
            retrieved_record["number"] = item["number"]
        if "pages" in item:
            retrieved_record["pages"] = item["pages"].replace("-", "--")
        if "authors" in item:
            if "author" in item["authors"]:
                if isinstance(item["authors"]["author"], dict):
                    author_string = item["authors"]["author"]["text"]
                else:
                    authors_nodes = [
                        author
                        for author in item["authors"]["author"]
                        if isinstance(author, dict)
                    ]
                    authors = [x["text"] for x in authors_nodes if "text" in x]
                    author_string = " and ".join(authors)
                author_string = self.format_author_field(author_string)
                retrieved_record["author"] = author_string

        if "key" in item:
            retrieved_record["dblp_key"] = item["key"]

        if "doi" in item:
            retrieved_record["doi"] = item["doi"].upper()
        if "ee" in item:
            if "https://doi.org" not in item["ee"]:
                retrieved_record["url"] = item["ee"]

        for k, v in retrieved_record.items():
            retrieved_record[k] = html.unescape(v).replace("{", "").replace("}", "")

        return retrieved_record

    def __retrieve_dblp_items(self, query: str) -> list:

        api_url = "https://dblp.org/search/publ/api?q="
        items = []

        query = re.sub(r"[\W]+", " ", query.replace(" ", "_"))
        url = api_url + query.replace(" ", "+") + "&format=json"
        headers = {"user-agent": f"{__name__}  (mailto:{self.EMAIL})"}
        self.REVIEW_MANAGER.logger.debug(url)
        ret = requests.get(url, headers=headers, timeout=self.TIMEOUT)
        ret.raise_for_status()
        if ret.status_code == 500:
            return []

        data = json.loads(ret.text)
        if "hits" not in data["result"]:
            return []
        if "hit" not in data["result"]["hits"]:
            return []
        hits = data["result"]["hits"]["hit"]
        items = [hit["info"] for hit in hits]
        return items

    def get_md_from_dblp(self, record: dict) -> dict:
        if "dblp_key" in record:
            return record

        try:
            query = "" + record.get("title", "").replace("-", "_")
            # Note: queries combining title+author/journal do not seem to work any more
            # if "author" in record:
            #     query = query + "_" + record["author"].split(",")[0]
            # if "booktitle" in record:
            #     query = query + "_" + record["booktitle"]
            # if "journal" in record:
            #     query = query + "_" + record["journal"]
            # if "year" in record:
            #     query = query + "_" + record["year"]

            items = self.__retrieve_dblp_items(query)

            if len(items) == 0:
                return record

            for item in items:
                retrieved_record = self.dblp_json_to_record(item)
                # self.REVIEW_MANAGER.pp.pprint(retrieved_record)

                similarity = self.get_retrieval_similarity(
                    record.copy(), retrieved_record.copy()
                )

                if similarity > self.RETRIEVAL_SIMILARITY:
                    self.REVIEW_MANAGER.logger.debug("Found matching record")
                    self.REVIEW_MANAGER.logger.debug(
                        f"dblp similarity: {similarity} "
                        f"(>{self.RETRIEVAL_SIMILARITY})"
                    )
                    record = self.__fuse_best_fields(record, retrieved_record)
                    record["dblp_key"] = "https://dblp.org/rec/" + item["key"]
                    record.update(status=RecordState.md_prepared)
                else:
                    self.REVIEW_MANAGER.logger.debug(
                        f"dblp similarity: {similarity} "
                        f"(<{self.RETRIEVAL_SIMILARITY})"
                    )
        except requests.exceptions.HTTPError:
            pass
        except UnicodeEncodeError:
            pass
        except requests.exceptions.ReadTimeout:
            pass
        except requests.exceptions.ConnectionError:
            pass
        return record

    def __percent_upper_chars(self, input_string: str) -> float:
        return sum(map(str.isupper, input_string)) / len(input_string)

    def __select_best_author(self, default: str, candidate: str) -> str:
        best_author = default

        default_mostly_upper = self.__percent_upper_chars(default) > 0.8
        candidate_mostly_upper = self.__percent_upper_chars(candidate) > 0.8

        if default_mostly_upper and not candidate_mostly_upper:
            best_author = candidate

        # Heuristics for missing first names (e.g., in doi.org/crossref metadata)
        if ", and " in default and ", and " not in candidate:
            return candidate
        if "," == default.rstrip()[-1:] and "," != candidate.rstrip()[-1:]:
            best_author = candidate

        self.REVIEW_MANAGER.logger.debug(
            f"best_author({default}, \n"
            f"                                      {candidate}) = \n"
            f"                                      {best_author}"
        )
        return best_author

    def __select_best_pages(self, default: str, candidate: str) -> str:
        best_pages = default
        if "--" in candidate and "--" not in default:
            best_pages = candidate

        self.REVIEW_MANAGER.logger.debug(
            f"best_pages({default}, {candidate}) = {best_pages}"
        )

        return best_pages

    def __select_best_title(self, default: str, candidate: str) -> str:
        best_title = default

        default_upper = self.__percent_upper_chars(default)
        candidate_upper = self.__percent_upper_chars(candidate)

        # Relatively simple rule...
        # catches cases when default is all upper or title case
        if default_upper > candidate_upper:
            best_title = candidate

        self.REVIEW_MANAGER.logger.debug(
            f"best_title({default},\n"
            f"                                      {candidate}) = \n"
            f"                                      {best_title}"
        )

        return best_title

    def __select_best_journal(self, default: str, candidate: str) -> str:

        best_journal = default

        default_upper = self.__percent_upper_chars(default)
        candidate_upper = self.__percent_upper_chars(candidate)

        # Simple heuristic to avoid abbreviations
        if "." in default and "." not in candidate:
            best_journal = candidate
        # Relatively simple rule...
        # catches cases when default is all upper or title case
        if default_upper > candidate_upper:
            best_journal = candidate

        self.REVIEW_MANAGER.logger.debug(
            f"best_journal({default}, \n"
            f"                                      {candidate}) = \n"
            f"                                      {best_journal}"
        )

        return best_journal

    def __fuse_best_fields(self, record: dict, merging_record: dict) -> dict:
        """Apply heuristics to create a fusion of the best fields based on
        quality heuristics"""

        self.REVIEW_MANAGER.logger.debug(
            "Fuse retrieved record " "(select fields with the highest quality)"
        )
        self.REVIEW_MANAGER.logger.debug(self.REVIEW_MANAGER.pp.pformat(merging_record))
        for key, val in merging_record.items():
            if val:
                if "author" == key:
                    if "author" in record:
                        if record["author"] != merging_record["author"]:
                            record["author"] = self.__select_best_author(
                                record["author"], merging_record["author"]
                            )
                    else:
                        record["author"] = str(val)
                elif "pages" == key:
                    if "pages" in record:
                        if record["pages"] != merging_record["pages"]:
                            record["pages"] = self.__select_best_pages(
                                record["pages"], merging_record["pages"]
                            )
                    else:
                        record["pages"] = str(val)
                elif "title" == key:
                    if "title" in record:
                        if record["title"] != merging_record["title"]:
                            record["title"] = self.__select_best_title(
                                record["title"], merging_record["title"]
                            )
                    else:
                        record["title"] = str(val)
                elif "journal" == key:
                    if "journal" in record:
                        if record["journal"] != merging_record["journal"]:
                            record["journal"] = self.__select_best_journal(
                                record["journal"], merging_record["journal"]
                            )
                    else:
                        record["journal"] = str(val)
                else:
                    record[key] = str(val)

        return record

    def retrieve_doi_metadata(self, record: dict) -> dict:
        if "doi" not in record:
            return record

        # for testing:
        # curl -iL -H "accept: application/vnd.citationstyles.csl+json"
        # -H "Content-Type: application/json" http://dx.doi.org/10.1111/joop.12368

        # For exceptions:
        orig_record = record.copy()
        try:
            url = "http://dx.doi.org/" + record["doi"]
            self.REVIEW_MANAGER.logger.debug(url)
            headers = {"accept": "application/vnd.citationstyles.csl+json"}
            ret = requests.get(url, headers=headers, timeout=self.TIMEOUT)
            ret.raise_for_status()
            if ret.status_code != 200:
                self.REVIEW_MANAGER.report_logger.info(
                    f' {record["ID"]}'.ljust(self.PAD, " ")
                    + "metadata for "
                    + f'doi  {record["doi"]} not (yet) available'
                )
                return record

            retrieved_json = json.loads(ret.text)
            retrieved_record = self.crossref_json_to_record(retrieved_json)
            record = self.__fuse_best_fields(record, retrieved_record)

        except json.decoder.JSONDecodeError:
            pass
        except requests.exceptions.HTTPError:
            pass
        except requests.exceptions.ReadTimeout:
            pass
        except requests.exceptions.ConnectionError:
            pass
            return orig_record
        return record

    def get_doi_from_urls(self, record: dict) -> dict:

        url = record.get("url", record.get("fulltext", "NA"))
        if "NA" != url:
            try:
                self.REVIEW_MANAGER.logger.debug(f"Retrieve doi-md from {url}")
                headers = {"user-agent": f"{__name__}  (mailto:{self.EMAIL})"}
                ret = requests.get(url, headers=headers, timeout=self.TIMEOUT)
                ret.raise_for_status()
                res = re.findall(self.doi_regex, ret.text)
                if res:
                    if len(res) == 1:
                        ret_dois = res[0]
                    else:
                        counter = collections.Counter(res)
                        ret_dois = counter.most_common()

                    if not ret_dois:
                        return record
                    for doi, freq in ret_dois:
                        retrieved_record = {"doi": doi.upper(), "ID": record["ID"]}
                        retrieved_record = self.retrieve_doi_metadata(retrieved_record)
                        similarity = self.get_retrieval_similarity(
                            record.copy(), retrieved_record.copy()
                        )
                        if similarity > self.RETRIEVAL_SIMILARITY:
                            for key, val in retrieved_record.items():
                                record[key] = val

                            self.REVIEW_MANAGER.report_logger.debug(
                                "Retrieved metadata based on doi from"
                                f' website: {record["doi"]}'
                            )
                            record.update(metadata_source="LINKED_URL")

            except requests.exceptions.ConnectionError:
                pass
            except Exception:
                pass
        return record

    def __missing_fields(self, record: dict) -> list:
        missing_fields = []
        if record["ENTRYTYPE"] in self.record_field_requirements.keys():
            reqs = self.record_field_requirements[record["ENTRYTYPE"]]
            missing_fields = [
                x for x in reqs if x not in record.keys() or "" == record[x]
            ]
        else:
            missing_fields = ["no field requirements defined"]
        return missing_fields

    def __is_complete(self, record: dict) -> bool:
        sufficiently_complete = False
        if record["ENTRYTYPE"] in self.record_field_requirements.keys():
            if len(self.__missing_fields(record)) == 0:
                sufficiently_complete = True
        return sufficiently_complete

    def __get_inconsistencies(self, record: dict) -> list:
        inconsistent_fields = []
        if record["ENTRYTYPE"] in self.record_field_inconsistencies.keys():
            incons_fields = self.record_field_inconsistencies[record["ENTRYTYPE"]]
            inconsistent_fields = [x for x in incons_fields if x in record]
        # Note: a thesis should be single-authored
        if "thesis" in record["ENTRYTYPE"] and " and " in record.get("author", ""):
            inconsistent_fields.append("author")
        return inconsistent_fields

    def __has_inconsistent_fields(self, record: dict) -> bool:
        found_inconsistencies = False
        if record["ENTRYTYPE"] in self.record_field_inconsistencies.keys():
            inconsistencies = self.__get_inconsistencies(record)
            if inconsistencies:
                found_inconsistencies = True
        return found_inconsistencies

    def __get_incomplete_fields(self, record: dict) -> list:
        incomplete_fields = []
        for key in record.keys():
            if key in ["title", "journal", "booktitle", "author"]:
                if record[key].endswith("...") or record[key].endswith("…"):
                    incomplete_fields.append(key)
        if record.get("author", "").endswith("and others"):
            incomplete_fields.append("author")
        return incomplete_fields

    def __has_incomplete_fields(self, record: dict) -> bool:
        if len(self.__get_incomplete_fields(record)) > 0:
            return True
        return False

    def drop_fields(self, record: dict) -> dict:
        for key in list(record):
            if "NA" == record[key]:
                del record[key]
            if key not in self.fields_to_keep:
                record.pop(key)
                # warn if fields are dropped that are not in fields_to_drop
                if key not in self.fields_to_drop:
                    self.REVIEW_MANAGER.report_logger.info(f"Dropped {key} field")
        for key in list(record):
            if "" == record[key]:
                del record[key]

        if "publisher" in record:
            if "researchgate.net" == record["publisher"]:
                del record["publisher"]
        return record

    def remove_broken_IDs(self, record: dict) -> dict:

        if not self.FIRST_ROUND:
            return record

        if "doi" in record:
            # https://www.crossref.org/blog/dois-and-matching-regular-expressions/
            d = re.match(r"^10.\d{4,9}\/", record["doi"])
            if not d:
                del record["doi"]
        if "isbn" in record:
            isbn = record["isbn"].replace("-", "").replace(" ", "")
            url = f"https://openlibrary.org/isbn/{isbn}.json"
            ret = requests.get(url, headers=self.requests_headers, timeout=self.TIMEOUT)
            if '"error": "notfound"' in ret.text:
                del record["isbn"]

        return record

    def global_ids_consistency_check(self, record: dict) -> dict:
        """When metadata provided by DOI/crossref or on the website (url) differs from
        the record: set status to md_needs_manual_preparation."""

        if not self.FIRST_ROUND:
            return record

        if "doi" in record:
            doi_md = self.get_md_from_doi(record.copy())
            # self.REVIEW_MANAGER.pp.pprint(doi_md)
            for k, v in doi_md.items():
                if not isinstance(v, str):
                    continue
                if k in record:
                    if fuzz.partial_ratio(record[k], doi_md[k]) < 70:
                        record["status"] = RecordState.md_needs_manual_preparation
                        record[
                            "man_prep_hints"
                        ] = f"Disagreement with doi metadata ({k}: {v})"

        if "url" in record:
            url_md = self.retrieve_md_from_url(record["url"])
            # self.REVIEW_MANAGER.pp.pprint(url_md)
            for k, v in url_md.items():
                if not isinstance(v, str):
                    continue
                if k in record:
                    print(fuzz.partial_ratio(record[k], url_md[k]))
                    if fuzz.partial_ratio(record[k], url_md[k]) < 70:
                        record["status"] = RecordState.md_needs_manual_preparation
                        record[
                            "man_prep_hints"
                        ] = f"Disagreement with url metadata ({k}: {v})"

        # self.REVIEW_MANAGER.pp.pprint(record)

        return record

    def remove_urls_with_500_errors(self, record: dict) -> dict:

        if not self.FIRST_ROUND:
            return record

        try:
            if "url" in record:
                r = requests.get(
                    record["url"], headers=self.requests_headers, timeout=self.TIMEOUT
                )
                if r.status_code >= 500:
                    del record["url"]
        except (
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
        ):
            pass
        try:
            if "fulltext" in record:
                r = requests.get(
                    record["fulltext"],
                    headers=self.requests_headers,
                    timeout=self.TIMEOUT,
                )
                if r.status_code >= 500:
                    del record["fulltext"]
        except (
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
        ):
            pass

        return record

    def exclude_non_latin_alphabets(self, record: dict) -> dict:

        str_to_check = " ".join(
            [
                record.get("title", ""),
                record.get("author", ""),
                record.get("journal", ""),
                record.get("booktitle", ""),
            ]
        )
        if not self.ad.only_alphabet_chars(str_to_check, "LATIN"):
            record["status"] = RecordState.rev_prescreen_excluded
            record["prescreen_exclusion"] = "script:non_latin_alphabet"

        return record

    def __check_potential_retracts(self, record: dict) -> dict:
        retrieved_record = self.get_md_from_crossref(record.copy())
        if retrieved_record.get("crossmark", "") == "True":
            record["status"] = RecordState.md_needs_manual_preparation
            record["man_prep_hints"] = "crossmark_restriction_potential_retract"
        if retrieved_record.get("warning", "") == "Withdrawn (according to DBLP)":
            record["status"] = RecordState.md_needs_manual_preparation
            record["man_prep_hints"] = "Withdrawn (according to DBLP)"
        return record

    def __read_next_record_str(self) -> typing.Iterator[str]:
        with open(self.REVIEW_MANAGER.paths["MAIN_REFERENCES"]) as f:
            data = ""
            first_entry_processed = False
            while True:
                line = f.readline()
                if not line:
                    break
                if line[:1] == "%" or line == "\n":
                    continue
                if line[:1] != "@":
                    data += line
                else:
                    if first_entry_processed:
                        yield data
                    else:
                        first_entry_processed = True
                    data = line
            yield data

    def get_crossref_record(self, record) -> dict:
        # Note : the ID of the crossrefed record may have changed.
        # we need to trace based on the origin
        crossref_origin = record["origin"]
        crossref_origin = crossref_origin[: crossref_origin.rfind("/")]
        crossref_origin = crossref_origin + "/" + record["crossref"]
        for record_string in self.__read_next_record_str():
            if crossref_origin in record_string:
                parser = BibTexParser(customization=convert_to_unicode)
                db = bibtexparser.loads(record_string, parser=parser)
                record = db.entries[0]
                if record["origin"] == crossref_origin:
                    return record
        return {}

    def resolve_crossrefs(self, record: dict) -> dict:
        if "crossref" in record:
            crossref_record = self.get_crossref_record(record)
            if 0 != len(crossref_record):
                for k, v in crossref_record.items():
                    if k not in record:
                        record[k] = v
        return record

    def log_notifications(self, record: dict, unprepared_record: dict) -> dict:

        msg = ""

        change = 1 - utils.get_record_similarity(record.copy(), unprepared_record)
        if change > 0.1:
            self.REVIEW_MANAGER.report_logger.info(
                f' {record["ID"]}'.ljust(self.PAD, " ")
                + f"Change score: {round(change, 2)}"
            )

        if not self.__is_complete(record):
            self.REVIEW_MANAGER.report_logger.info(
                f' {record["ID"]}'.ljust(self.PAD, " ")
                + f'{str(record["ENTRYTYPE"]).title()} '
                f"missing {self.__missing_fields(record)}"
            )
            msg += f"missing: {self.__missing_fields(record)}"

        if self.__has_inconsistent_fields(record):
            self.REVIEW_MANAGER.report_logger.info(
                f' {record["ID"]}'.ljust(self.PAD, " ")
                + f'{str(record["ENTRYTYPE"]).title()} '
                f"with {self.__get_inconsistencies(record)} field(s)"
                " (inconsistent"
            )
            msg += f'; {record["ENTRYTYPE"]} but {self.__get_inconsistencies(record)}'

        if self.__has_incomplete_fields(record):
            self.REVIEW_MANAGER.report_logger.info(
                f' {record["ID"]}'.ljust(self.PAD, " ")
                + f"Incomplete fields {self.__get_incomplete_fields(record)}"
            )
            msg += f"; incomplete: {self.__get_incomplete_fields(record)}"
        if change > 0.1:
            msg += f"; change-score: {change}"

        if msg != "":
            if "man_prep_hints" not in record:
                record["man_prep_hints"] = ""
            else:
                record["man_prep_hints"] = record["man_prep_hints"] + ";"
            record["man_prep_hints"] = record["man_prep_hints"] + msg.strip(";").lstrip(
                " "
            )

        return record

    def remove_nicknames(self, record: dict) -> dict:
        if "author" in record:
            # Replace nicknames in parentheses
            record["author"] = re.sub(r"\([^)]*\)", "", record["author"])
            record["author"] = record["author"].replace("  ", " ")
        return record

    def remove_redundant_fields(self, record: dict) -> dict:
        if "article" == record["ENTRYTYPE"]:
            if "journal" in record and "booktitle" in record:
                if (
                    fuzz.partial_ratio(
                        record["journal"].lower(), record["booktitle"].lower()
                    )
                    / 100
                    > 0.9
                ):
                    del record["booktitle"]
        if "inproceedings" == record["ENTRYTYPE"]:
            if "journal" in record and "booktitle" in record:
                if (
                    fuzz.partial_ratio(
                        record["journal"].lower(), record["booktitle"].lower()
                    )
                    / 100
                    > 0.9
                ):
                    del record["journal"]
        return record

    def update_metadata_status(self, record: dict) -> dict:
        record = self.__check_potential_retracts(record)
        if "crossmark" in record:
            return record
        if "CURATED" == record["metadata_source"]:
            record.update(status=RecordState.md_prepared)
            return record

        self.REVIEW_MANAGER.logger.debug(
            f'is_complete({record["ID"]}): {self.__is_complete(record)}'
        )

        self.REVIEW_MANAGER.logger.debug(
            f'has_inconsistent_fields({record["ID"]}): '
            f"{self.__has_inconsistent_fields(record)}"
        )
        self.REVIEW_MANAGER.logger.debug(
            f'has_incomplete_fields({record["ID"]}): '
            f"{self.__has_incomplete_fields(record)}"
        )

        if not self.__is_complete(record):
            record.update(status=RecordState.md_needs_manual_preparation)
        elif self.__has_incomplete_fields(record):
            record.update(status=RecordState.md_needs_manual_preparation)
        elif self.__has_inconsistent_fields(record):
            record.update(status=RecordState.md_needs_manual_preparation)
        else:
            record.update(status=RecordState.md_prepared)

        return record

    def prepare(self, item: dict) -> dict:

        record = item["record"]

        if "CURATED" == record.get("metadata_source", ""):
            return record

        # if RecordState.md_imported != record["status"]:
        if record["status"] not in [
            RecordState.md_imported,
            RecordState.md_prepared,
            RecordState.md_needs_manual_preparation,
        ]:
            return record

        #  preparation_record will change and eventually replace record (if successful)
        preparation_record = record.copy()
        # unprepared_record will not change (for diffs)
        unprepared_record = record.copy()

        # Note: we require (almost) perfect matches for the scripts.
        # Cases with higher dissimilarity will be handled in the prep_man.py
        # Note : the record should always be the first element of the list.
        # Note : we need to rerun all preparation scripts because records are not stored
        # if not prepared successfully.

        # Note: for these scripts, only the similarity changes.
        prep_scripts: typing.List[typing.Dict[str, typing.Any]] = [
            {
                "script": self.remove_urls_with_500_errors,
                "params": [preparation_record],
            },
            {
                "script": self.remove_broken_IDs,
                "params": [preparation_record],
            },
            {
                "script": self.resolve_crossrefs,
                "params": [preparation_record],
            },
            {
                "script": self.global_ids_consistency_check,
                "params": [preparation_record],
            },
            {
                "script": self.correct_recordtype,
                "params": [preparation_record],
            },
            {
                "script": self.format,
                "params": [preparation_record],
            },
            {
                "script": self.get_doi_from_sem_scholar,
                "params": [preparation_record],
                "source_correction_hint": "fill out the online form: "
                "https://www.semanticscholar.org/faq#correct-error",
            },
            {"script": self.get_doi_from_urls, "params": [preparation_record]},
            {
                "script": self.get_md_from_doi,
                "params": [preparation_record],
                "source_correction_hint": "ask the publisher to correct the metadata"
                " (see https://www.crossref.org/blog/"
                "metadata-corrections-updates-and-additions-in-metadata-manager/",
            },
            {
                "script": self.get_md_from_crossref,
                "params": [preparation_record],
                "source_correction_hint": "ask the publisher to correct the metadata"
                " (see https://www.crossref.org/blog/"
                "metadata-corrections-updates-and-additions-in-metadata-manager/",
            },
            {
                "script": self.get_md_from_dblp,
                "params": [preparation_record],
                "source_correction_hint": "send and email to dblp@dagstuhl.de"
                " (see https://dblp.org/faq/How+can+I+correct+errors+in+dblp.html)",
            },
            {
                "script": self.get_record_from_local_index,
                "params": [preparation_record],
                "source_correction_hint": "correct the metadata in the source "
                "repository (as linked in the source_url field)",
            },
            {
                "script": self.get_md_from_open_library,
                "params": [preparation_record],
                "source_correction_hint": "ask the publisher to correct the metadata"
                " (see https://www.crossref.org/blog/"
                "metadata-corrections-updates-and-additions-in-metadata-manager/",
            },
            {
                "script": self.get_year_from_vol_iss_jour_crossref,
                "params": [preparation_record],
                "source_correction_hint": "ask the publisher to correct the metadata"
                " (see https://www.crossref.org/blog/"
                "metadata-corrections-updates-and-additions-in-metadata-manager/",
            },
            {
                "script": self.remove_nicknames,
                "params": [preparation_record],
            },
            {
                "script": self.remove_redundant_fields,
                "params": [preparation_record],
            },
            {
                "script": self.format_minor,
                "params": [preparation_record],
            },
            {
                "script": self.exclude_non_latin_alphabets,
                "params": [preparation_record],
            },
            {
                "script": self.drop_fields,
                "params": [preparation_record],
            },
            {
                "script": self.update_metadata_status,
                "params": [preparation_record],
            },
        ]

        short_form = self.drop_fields(record.copy())

        preparation_details = []
        preparation_details.append(
            f'prepare({record["ID"]})'
            + f" called with: \n{self.REVIEW_MANAGER.pp.pformat(short_form)}\n\n"
        )

        for prep_script in prep_scripts:

            prior = preparation_record.copy()

            if self.DEBUG_MODE:
                self.REVIEW_MANAGER.logger.info(
                    f'{prep_script["script"].__name__}(...) called'
                )
            if [] == prep_script["params"]:
                prep_script["script"]()
            else:
                prep_script["script"](*prep_script["params"])

            diffs = list(dictdiffer.diff(prior, preparation_record))
            if diffs:
                # self.REVIEW_MANAGER.pp.pprint(preparation_record)
                change_report = (
                    f'{prep_script["script"].__name__}'
                    f'({prep_script["params"][0]["ID"]})'
                    f" changed:\n{self.REVIEW_MANAGER.pp.pformat(diffs)}\n"
                )
                preparation_details.append(change_report)
                if self.DEBUG_MODE:
                    self.REVIEW_MANAGER.logger.info(change_report)
                    self.REVIEW_MANAGER.logger.info(
                        "To correct errors in the script,"
                        " open an issue at "
                        "https://github.com/geritwagner/colrev_core/issues"
                    )
                    if "source_correction_hint" in prep_script:
                        self.REVIEW_MANAGER.logger.info(
                            "To correct potential errors at source,"
                            f" {prep_script['source_correction_hint']}"
                        )
                    input("Press Enter to continue")
                    print("\n")
            else:
                self.REVIEW_MANAGER.logger.debug(
                    f"{prep_script['script'].__name__} changed: -"
                )
                if self.DEBUG_MODE:
                    print("\n")
                    time.sleep(0.7)

            if RecordState.rev_prescreen_excluded == preparation_record[
                "status"
            ] or "Disagreement with " in preparation_record.get("man_prep_hints", ""):
                record = preparation_record.copy()
                break

        if (
            preparation_record["status"]
            in [RecordState.md_prepared, RecordState.rev_prescreen_excluded]
            or "crossmark" in preparation_record
        ):
            record = preparation_record.copy()
            if "crossmark" in preparation_record:
                record = self.log_notifications(record, unprepared_record)

            # TBD: rely on colrev prep --debug ID (instead of printing everyting?)
            # for preparation_detail in preparation_details:
            #     self.REVIEW_MANAGER.report_logger.info(preparation_detail)

        if "low_confidence" == item["mode"]["name"]:
            record = preparation_record.copy()
            if RecordState.md_needs_manual_preparation == preparation_record["status"]:
                record = self.log_notifications(record, unprepared_record)

        return record

    def __log_details(self, preparation_batch: list) -> None:

        nr_recs = len(
            [
                record
                for record in preparation_batch
                if record["status"] == RecordState.md_needs_manual_preparation
            ]
        )
        if nr_recs > 0:
            self.REVIEW_MANAGER.report_logger.info(
                f"Statistics: {nr_recs} records not prepared"
            )

        nr_recs = len(
            [
                record
                for record in preparation_batch
                if record["status"] == RecordState.rev_prescreen_excluded
            ]
        )
        if nr_recs > 0:
            self.REVIEW_MANAGER.report_logger.info(
                f"Statistics: {nr_recs} records (prescreen) excluded "
                "(non-latin alphabet)"
            )

        return

    def reset(self, record_list: typing.List[dict]):
        from colrev_core.prep_man import PrepMan

        record_list = [
            r
            for r in record_list
            if str(r["status"])
            in [
                str(RecordState.md_prepared),
                str(RecordState.md_needs_manual_preparation),
            ]
        ]

        for r in [
            r
            for r in record_list
            if str(r["status"])
            not in [
                str(RecordState.md_prepared),
                str(RecordState.md_needs_manual_preparation),
            ]
        ]:
            msg = (
                f"{r['ID']}: status must be md_prepared/md_needs_manual_preparation "
                + f'(is {r["status"]})'
            )
            self.REVIEW_MANAGER.logger.error(msg)
            self.REVIEW_MANAGER.report_logger.error(msg)

        record_reset_list = [[record, record.copy()] for record in record_list]

        MAIN_REFERENCES_RELATIVE = self.REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]
        git_repo = git.Repo(str(self.REVIEW_MANAGER.paths["REPO_DIR"]))
        revlist = (
            (
                commit.hexsha,
                commit.message,
                (commit.tree / str(MAIN_REFERENCES_RELATIVE)).data_stream.read(),
            )
            for commit in git_repo.iter_commits(paths=str(MAIN_REFERENCES_RELATIVE))
        )

        for commit_id, cmsg, filecontents in list(revlist):
            cmsg_l1 = str(cmsg).split("\n")[0]
            if "colrev load" not in cmsg:
                print(f"Skip {str(commit_id)} (non-load commit) - {str(cmsg_l1)}")
                continue
            print(f"Check {str(commit_id)} - {str(cmsg_l1)}")
            prior_db = bibtexparser.loads(filecontents)
            for prior_record in prior_db.entries:
                if str(prior_record["status"]) != str(RecordState.md_imported):
                    continue
                for record_to_unmerge, record in record_reset_list:

                    if any(
                        o in prior_record["origin"] for o in record["origin"].split(";")
                    ):
                        self.REVIEW_MANAGER.report_logger.info(
                            f'reset({record["ID"]}) to'
                            f"\n{self.REVIEW_MANAGER.pp.pformat(prior_record)}\n\n"
                        )
                        # Note : we don't want to restore the old ID...
                        current_id = record_to_unmerge["ID"]
                        record_to_unmerge.clear()
                        for k, v in prior_record.items():
                            record_to_unmerge[k] = v
                        record_to_unmerge["ID"] = current_id
                        break
                # Stop if all original records have been found
                if (
                    len([x["status"] != "md_imported" for x, y in record_reset_list])
                    == 0
                ):
                    break

        PREP_MAN = PrepMan(self.REVIEW_MANAGER)
        # TODO : double-check! resetting the prep does not necessarily mean
        # that wrong records were merged...
        # TODO : if any record_to_unmerge['status'] != RecordState.md_imported:
        # retrieve the original record from the search/source file
        for record_to_unmerge, record in record_reset_list:
            PREP_MAN.append_to_non_dupe_db(record_to_unmerge, record)
            record_to_unmerge.update(status=RecordState.md_needs_manual_preparation)

        return

    def reset_records(self, reset_ids: list) -> None:

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()
        records_to_reset = []
        for reset_id in reset_ids:
            record_list = [x for x in records if x["ID"] == reset_id]
            if len(record_list) != 1:
                print(f"Error: record not found (ID={reset_id})")
                continue
            records_to_reset.append(record_list.pop())

        self.reset(records_to_reset)

        saved_args = {"reset_records": ",".join(reset_ids)}
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)
        # self.REVIEW_MANAGER.format_references()
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        self.REVIEW_MANAGER.create_commit(
            "Reset metadata for manual preparation", saved_args=saved_args
        )
        return

    def reset_ids(self) -> None:

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()

        git_repo = self.REVIEW_MANAGER.REVIEW_DATASET.get_repo()
        MAIN_REFERENCES_RELATIVE = self.REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]
        revlist = (
            ((commit.tree / str(MAIN_REFERENCES_RELATIVE)).data_stream.read())
            for commit in git_repo.iter_commits(paths=str(MAIN_REFERENCES_RELATIVE))
        )
        filecontents = next(revlist)  # noqa
        prior_bib_db = bibtexparser.loads(filecontents)

        for record in records:
            prior_record_l = [
                x for x in prior_bib_db.entries if x["origin"] == record["origin"]
            ]
            if len(prior_record_l) != 1:
                continue
            prior_record = prior_record_l.pop()
            record["ID"] = prior_record["ID"]

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)

        return

    def set_ids(
        self,
    ) -> None:

        self.REVIEW_MANAGER.REVIEW_DATASET.set_IDs()
        self.REVIEW_MANAGER.create_commit("Set IDs")

        return

    def update_doi_md(
        self,
    ) -> None:

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()
        for record in records:
            if "doi" in record and record.get("journal", "") == "MIS Quarterly":
                record = self.get_md_from_doi(record)
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        self.REVIEW_MANAGER.create_commit("Update metadata based on DOIs")
        return

    def polish(self, input_sim: float = 0.9) -> None:
        import collections
        from colrev_core.tei import TEI, TEI_Exception
        from tqdm import tqdm

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()

        refs = []
        for tei_file in Path("tei").glob("*.tei.xml"):
            try:
                TEI_INSTANCE = TEI(
                    self.REVIEW_MANAGER,
                    tei_path=tei_file,
                    notify_state_transition_process=False,
                )
                refs.extend(TEI_INSTANCE.get_bibliography())
            except TEI_Exception:
                pass

        self.RETRIEVAL_SIMILARITY = input_sim

        for record in tqdm(records):

            previous_status = record["status"]
            # TODO : the source_url should be a list (with newlines)?
            record = self.get_record_from_local_index(record)
            record["status"] = previous_status

            continue
            if "CURATED" == record.get("metadata_source", ""):
                continue
            if "doi" in record:
                continue
            print(record["ID"])

            if "title" in record:

                title_text = self.NER(record["title"])
                for word in title_text.ents:
                    if word.text.islower():
                        if word.label_ in ["GPE", "NORP", "LOC", "ORG", "PERSON"]:
                            record["title"] = record["title"].replace(
                                word.text, word.text.title()
                            )

            if "doi" not in record:
                previous_status = record["status"]
                record = self.get_md_from_crossref(record)
                record["status"] = previous_status

            if "dblp_key" not in record:
                previous_status = record["status"]
                record = self.get_md_from_dblp(record)
                record["status"] = previous_status

            # polish based on TEI
            if record["status"] not in [
                RecordState.rev_included,
                RecordState.rev_synthesized,
            ]:
                continue

            title_variations = []
            journal_variations = []

            for ref in refs:
                if record["ID"] == ref["ID"]:
                    if "title" in ref:
                        title_variations.append(ref["title"])
                    if "journal" in ref:
                        journal_variations.append(ref["journal"])

            if len(title_variations) > 2:
                title_counter = collections.Counter(title_variations)
                record["title"] = title_counter.most_common()[0][0]

            if len(journal_variations) > 2 and "journal" in record:
                journal_counter = collections.Counter(journal_variations)
                record["journal"] = journal_counter.most_common()[0][0]

        if self.REVIEW_MANAGER.REVIEW_DATASET.has_changes():
            self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)
            self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
            self.REVIEW_MANAGER.create_commit("Polish metadata")

        return

    def get_data(self):
        from colrev_core.process import RecordState

        rsl = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
        nr_tasks = len([x for x in rsl if RecordState.md_imported == x[1]])

        PAD = min((max(len(x[0]) for x in rsl) + 2), 35)

        items = self.REVIEW_MANAGER.REVIEW_DATASET.read_next_record(
            conditions=[
                {"status": RecordState.md_imported},
                {"status": RecordState.md_prepared},
                {"status": RecordState.md_needs_manual_preparation},
            ],
        )

        prior_ids = [x[0] for x in rsl if str(RecordState.md_imported) == x[1]]

        prep_data = {
            "nr_tasks": nr_tasks,
            "PAD": PAD,
            "items": items,
            "prior_ids": prior_ids,
        }
        self.REVIEW_MANAGER.logger.debug(self.REVIEW_MANAGER.pp.pformat(prep_data))
        return prep_data

    def retrieve_md_from_url(self, url: str) -> dict:
        from colrev_core.load import Loader

        LOADER = Loader(self.REVIEW_MANAGER, notify_state_transition_process=False)
        LOADER.start_zotero_translators()

        content_type_header = {"Content-type": "text/plain"}
        headers = {**self.requests_headers, **content_type_header}
        et = requests.post(
            "http://127.0.0.1:1969/web",
            headers=headers,
            data=url,
        )

        record: typing.Dict = {}
        try:
            items = json.loads(et.content.decode())
            if len(items) == 0:
                return record
            item = items[0]
            # self.REVIEW_MANAGER.pp.pprint(item)
            record["ID"] = item["key"]
            record["ENTRYTYPE"] = "article"  # default
            if "journalArticle" == item.get("itemType", ""):
                record["ENTRYTYPE"] = "article"
                if "publicationTitle" in item:
                    record["journal"] = item["publicationTitle"]
                if "volume" in item:
                    record["volume"] = item["volume"]
                if "issue" in item:
                    record["number"] = item["issue"]
            if "conferencePaper" == item.get("itemType", ""):
                record["ENTRYTYPE"] = "inproceedings"
                if "proceedingsTitle" in item:
                    record["booktitle"] = item["proceedingsTitle"]
            if "creators" in item:
                author_str = ""
                for creator in item["creators"]:
                    author_str += (
                        " and "
                        + creator.get("lastName", "")
                        + ", "
                        + creator.get("firstName", "")
                    )
                author_str = author_str[5:]  # drop the first " and "
                record["author"] = author_str
            if "title" in item:
                record["title"] = (
                    item["title"]
                    .replace("<b>", "")
                    .replace("</b>", "")
                    .replace("<i>", "")
                    .replace("</i>", "")
                )
            if "doi" in item:
                record["doi"] = item["doi"]
            if "date" in item:
                year = re.search(r"\d{4}", item["date"])
                if year:
                    record["year"] = year.group(0)
            if "pages" in item:
                record["pages"] = item["pages"]
            if "url" in item:
                if "https://doi.org/" in item["url"]:
                    record["doi"] = item["url"].replace("https://doi.org/", "")
                    ret_rec = self.get_link_from_doi({"doi": record["doi"]})
                    if "https://doi.org/" not in ret_rec["url"]:
                        record["url"] = ret_rec["url"]
                else:
                    record["url"] = item["url"]

            if "tags" in item:
                if len(item["tags"]) > 0:
                    keywords = ", ".join([k["tag"] for k in item["tags"]])
                    record["keywords"] = keywords
        except json.decoder.JSONDecodeError:
            pass
        except KeyError:
            pass
        return record

    def print_doi_metadata(self, doi: str) -> None:

        record = self.get_md_from_doi({"doi": doi})
        self.REVIEW_MANAGER.pp.pprint(record)

        if "url" in record:
            print("Metadata retrieved from website:")
            retrieved_record = self.retrieve_md_from_url(record["url"])
            self.REVIEW_MANAGER.pp.pprint(retrieved_record)

        return

    def set_to_reprocess(self, reprocess_state: RecordState):
        # Note: resetting needs_manual_preparation to imported would also be
        # consistent with the check_valid_transitions because it will either
        # transition to prepared or to needs_manual_preparation

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()
        [
            r.update(status=RecordState.md_imported)
            for r in records
            if reprocess_state == r["status"]
        ]
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)
        return

    def __get_pdf_source_data(self, PDF_INDICES, item):

        for PDF_INDEX in PDF_INDICES:
            if not PDF_INDEX:
                continue
            if PDF_INDEX["filename"] in item["origin"]:
                return PDF_INDEX
        return {}

    def __batch(self, items, mode: dict):

        batch = []
        for item in items:
            batch.append(
                {
                    "record": item,
                    "mode": mode,
                }
            )
        return batch

    def __load_prep_data_for_debug(self, debug_id: str) -> typing.Dict:

        self.REVIEW_MANAGER.logger.info("Data passed to the scripts")
        records = []
        debug_ids = debug_id.split(",")
        REVIEW_DATASET = self.REVIEW_MANAGER.REVIEW_DATASET
        original_records = list(
            REVIEW_DATASET.read_next_record(conditions=[{"ID": ID} for ID in debug_ids])
        )
        # self.REVIEW_MANAGER.logger.info("Current record")
        # self.REVIEW_MANAGER.pp.pprint(original_records)
        records = REVIEW_DATASET.retrieve_records_from_history(
            original_records, RecordState.md_imported
        )
        self.REVIEW_MANAGER.logger.info("Imported record (retrieved from history)")
        self.REVIEW_MANAGER.pp.pprint(records)
        input("Press Enter to continue")
        print("\n\n")
        prep_data = {
            "nr_tasks": len(debug_ids),
            "PAD": len(debug_id),
            "items": records,
            "prior_ids": [debug_id],
        }
        return prep_data

    def check_DBs_availability(self) -> None:
        from urllib3.exceptions import NewConnectionError
        from requests.exceptions import ConnectionError

        try:
            test_rec = {
                "doi": "10.17705/1cais.04607",
                "author": "Schryen, Guido and Wagner, Gerit and Benlian, Alexander "
                "and Paré, Guy",
                "title": "A Knowledge Development Perspective on Literature Reviews: "
                "Validation of a new Typology in the IS Field",
                "ID": "SchryenEtAl2021",
                "journal": "Communications of the Association for Information Systems",
            }
            returned_rec = self.__crossref_query(test_rec.copy())[0]
            if 0 != len(returned_rec):
                assert returned_rec["title"] == test_rec["title"]
                assert returned_rec["author"] == test_rec["author"]
            else:
                if not self.force_mode:
                    raise ServiceNotAvailableException("CROSSREF")
        except (ConnectionError, NewConnectionError):
            pass
            if not self.force_mode:
                raise ServiceNotAvailableException("CROSSREF")

        try:
            test_rec = {
                "doi": "10.17705/1cais.04607",
                "author": "Schryen, Guido and Wagner, Gerit and Benlian, Alexander "
                "and Paré, Guy",
                "title": "A Knowledge Development Perspective on Literature Reviews - "
                "Validation of a new Typology in the IS Field.",
                "ID": "SchryenEtAl2021",
                "journal": "Communications of the Association for Information Systems",
                "volume": "46",
                "year": "2020",
            }
            returned_rec = self.get_md_from_dblp(test_rec.copy())
            if 0 != len(returned_rec):
                assert returned_rec["title"] == test_rec["title"]
                assert returned_rec["author"] == test_rec["author"]
            else:
                if not self.force_mode:
                    raise ServiceNotAvailableException("DBLP")
        except (ConnectionError, NewConnectionError):
            pass
            if not self.force_mode:
                raise ServiceNotAvailableException("DBLP")

        test_rec = {
            "ENTRYTYPE": "book",
            "isbn": "9781446201435",
            # 'author': 'Ridley, Diana',
            "title": "The Literature Review A Stepbystep Guide For Students",
            "ID": "Ridley2012",
            "year": "2012",
        }
        try:
            url = f"https://openlibrary.org/isbn/{test_rec['isbn']}.json"
            ret = requests.get(url, headers=self.requests_headers, timeout=self.TIMEOUT)
            if ret.status_code != 200:
                if not self.force_mode:
                    raise ServiceNotAvailableException("OPENLIBRARY")
        except (ConnectionError, NewConnectionError):
            pass
            if not self.force_mode:
                raise ServiceNotAvailableException("OPENLIBRARY")

        return

    def main(
        self,
        reprocess_state: RecordState = RecordState.md_imported,
        keep_ids: bool = False,
        debug_id: str = "NA",
    ) -> None:
        saved_args = locals()

        self.check_DBs_availability()

        if self.DEBUG_MODE:
            print("\n\n\n")
            self.REVIEW_MANAGER.logger.info("Start debug prep\n")
            self.REVIEW_MANAGER.logger.info(
                "The script will replay the preparation procedures"
                " step-by-step, allow you to identify potential errors, trace them to "
                "their origin and correct them."
            )
            input("\nPress Enter to continue")
            print("\n\n")

        if not keep_ids:
            del saved_args["keep_ids"]
        if reprocess_state == RecordState.md_imported:
            del saved_args["reprocess_state"]

        if reprocess_state != RecordState.md_imported:
            self.set_to_reprocess(reprocess_state)

        modes = [
            {"name": "high_confidence", "similarity": 0.99},
            {"name": "medium_confidence", "similarity": 0.9},
            {"name": "low_confidence", "similarity": 0.80},
        ]

        self.FIRST_ROUND = True

        for mode in modes:
            self.REVIEW_MANAGER.logger.info(f"Prepare ({mode['name']})")

            self.RETRIEVAL_SIMILARITY = mode["similarity"]  # type: ignore
            saved_args["similarity"] = self.RETRIEVAL_SIMILARITY
            self.REVIEW_MANAGER.report_logger.debug(
                f"Set RETRIEVAL_SIMILARITY={self.RETRIEVAL_SIMILARITY}"
            )

            if self.DEBUG_MODE:
                prepare_data = self.__load_prep_data_for_debug(debug_id)
                if "high_confidence" == mode["name"]:
                    self.REVIEW_MANAGER.logger.info(
                        "In this round, we set "
                        "a very conservative similarity threshold "
                        f"({self.RETRIEVAL_SIMILARITY})"
                    )
                else:
                    self.REVIEW_MANAGER.logger.info(
                        "In this round, we lower the similarity "
                        f"threshold ({self.RETRIEVAL_SIMILARITY})"
                    )
                input("Press Enter to continue")
                print("\n\n")
            else:
                prepare_data = self.get_data()
            # self.REVIEW_MANAGER.logger.debug(f"prepare_data: "
            # f"{self.REVIEW_MANAGER.pp.pformat(prepare_data)}")
            self.PAD = prepare_data["PAD"]

            preparation_batch = self.__batch(prepare_data["items"], mode)

            if self.DEBUG_MODE:
                # Note: preparation_batch is not turned into a list of records.
                preparation_batch_items = preparation_batch
                preparation_batch = []
                for item in preparation_batch_items:
                    r = self.prepare(item)
                    preparation_batch.append(r)
            else:
                preparation_batch = p_map(self.prepare, preparation_batch)

            if not self.DEBUG_MODE:
                self.REVIEW_MANAGER.REVIEW_DATASET.save_record_list_by_ID(
                    preparation_batch
                )

                self.__log_details(preparation_batch)

                # Multiprocessing mixes logs of different records.
                # For better readability:
                preparation_batch_IDs = [x["ID"] for x in preparation_batch]
                self.REVIEW_MANAGER.reorder_log(preparation_batch_IDs)

                records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()
                self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)
                self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

                self.REVIEW_MANAGER.create_commit(
                    f"Prepare records ({mode['name']})", saved_args=saved_args
                )
                self.REVIEW_MANAGER.reset_log()
                print()

            self.FIRST_ROUND = False

        if not keep_ids and not self.DEBUG_MODE:
            self.REVIEW_MANAGER.REVIEW_DATASET.set_IDs()
            self.REVIEW_MANAGER.create_commit("Set IDs", saved_args=saved_args)

        return


class ServiceNotAvailableException(Exception):
    def __init__(self, msg: str):
        self.message = msg
        super().__init__(f"Service not available: {self.message}")


if __name__ == "__main__":
    pass
