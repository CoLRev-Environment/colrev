#! /usr/bin/env python
"""Pubmed API"""
import datetime
import logging
import time
import typing
from sqlite3 import OperationalError
from xml.etree.ElementTree import Element  # nosec
from xml.etree.ElementTree import ParseError

import requests
from defusedxml import ElementTree as DefusedET

import colrev.exceptions as colrev_exceptions
import colrev.record.record
from colrev.constants import Fields


# pylint: disable=too-few-public-methods


class PubmedAPIError(Exception):
    """Exception raised for PubMed API errors."""


class PubmedAPI:
    """Connector for the Pubmed API"""

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        *,
        url: str,
        email: str,
        session: requests.Session,
        timeout: int = 60,
        logger: typing.Optional[logging.Logger] = None,
    ):
        self.email = email
        self.session = session
        self._timeout = timeout
        self.url = url

        self.headers = {"user-agent": f"{__name__} (mailto:{self.email})"}

        if logger is not None:
            self.logger = logger
        else:
            self.logger = logging.getLogger(__name__)

        self._retstart = 0
        self._retmax = 20

    @classmethod
    def _get_author_string_from_node(cls, *, author_node: Element) -> str:
        authors_string = ""
        author_last_name_node = author_node.find("LastName")
        if author_last_name_node is not None:
            if author_last_name_node.text is not None:
                authors_string += author_last_name_node.text
        author_fore_name_node = author_node.find("ForeName")
        if author_fore_name_node is not None:
            if author_fore_name_node.text is not None:
                authors_string += ", "
                authors_string += author_fore_name_node.text
        return authors_string

    @classmethod
    def _get_author_string(cls, *, root: Element) -> str:
        authors_list = []
        for author_node in root.findall(
            "./PubmedArticle/MedlineCitation/Article/AuthorList/Author"
        ):
            authors_list.append(
                cls._get_author_string_from_node(author_node=author_node)
            )
        return " and ".join(authors_list)

    @classmethod
    def _get_title_string(cls, *, root: Element) -> str:
        title_text = root.findtext(
            "./PubmedArticle/MedlineCitation/Article/ArticleTitle", ""
        )
        if title_text:
            title_text = title_text.strip().rstrip(".")
            if title_text.startswith("[") and title_text.endswith("]"):
                title_text = title_text[1:-1]
            return title_text
        return ""

    @classmethod
    def _get_abstract_string(cls, *, root: Element) -> str:
        abstract = root.find("./PubmedArticle/MedlineCitation/Article/Abstract")
        if abstract is not None:
            return DefusedET.tostring(abstract, encoding="unicode")
        return ""

    # pylint: disable=colrev-missed-constant-usage
    @classmethod
    def _pubmed_xml_to_record(cls, *, root: Element) -> dict:
        retrieved_record_dict: dict = {Fields.ENTRYTYPE: "misc"}

        pubmed_article = root.find("PubmedArticle")
        if pubmed_article is None:
            return {}
        if pubmed_article.find("MedlineCitation") is None:
            return {}

        retrieved_record_dict[Fields.TITLE] = cls._get_title_string(root=root)
        retrieved_record_dict[Fields.AUTHOR] = cls._get_author_string(root=root)

        journal = root.find("./PubmedArticle/MedlineCitation/Article/Journal")
        if journal is not None:
            journal_name = journal.findtext("ISOAbbreviation")
            if journal_name:
                retrieved_record_dict[Fields.ENTRYTYPE] = "article"
                retrieved_record_dict[Fields.JOURNAL] = journal_name

            volume = journal.findtext("JournalIssue/Volume")
            if volume:
                retrieved_record_dict[Fields.VOLUME] = volume

            number = journal.findtext("JournalIssue/Issue")
            if number:
                retrieved_record_dict[Fields.NUMBER] = number

            year = journal.findtext("JournalIssue/PubDate/Year")
            if year:
                retrieved_record_dict[Fields.YEAR] = year

        retrieved_record_dict[Fields.ABSTRACT] = cls._get_abstract_string(root=root)

        article_id_list = root.find("./PubmedArticle/PubmedData/ArticleIdList")
        if article_id_list is not None:
            for article_id in article_id_list:
                id_type = article_id.attrib.get("IdType")
                if id_type == "pubmed" and article_id.text:
                    retrieved_record_dict["pubmedid"] = article_id.text.upper()
                elif id_type == "doi" and article_id.text:
                    retrieved_record_dict[Fields.DOI] = article_id.text.upper()
                elif id_type and article_id.text:
                    retrieved_record_dict[id_type] = article_id.text

        retrieved_record_dict = {
            k: v for k, v in retrieved_record_dict.items() if v != ""
        }
        if (
            retrieved_record_dict.get("pii", "pii").lower()
            == retrieved_record_dict.get("doi", "doi").lower()
        ):
            del retrieved_record_dict["pii"]

        return retrieved_record_dict

    def query_id(self, *, pubmed_id: str) -> colrev.record.record.Record:
        """Retrieve records from Pubmed based on a query"""

        try:
            database = "pubmed"
            url = (
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?"
                + f"db={database}&id={pubmed_id}&rettype=xml&retmode=text"
            )

            while True:
                # review_manager.logger.debug(url)
                ret = self.session.request(
                    "GET", url, headers=self.headers, timeout=self._timeout
                )
                if ret.status_code == 429:
                    time.sleep(10)
                    continue
                ret.raise_for_status()
                if ret.status_code != 200:
                    # review_manager.logger.debug(
                    #     f"crossref_query failed with status {ret.status_code}"
                    # )
                    raise colrev_exceptions.SearchSourceException(
                        "Pubmed record not found"
                    )

                response_content = getattr(ret, "content", None)
                if response_content is None:
                    response_text = getattr(ret, "text", "")
                    response_content = response_text.encode("utf-8")
                root = DefusedET.fromstring(response_content)
                retrieved_record_dict = self._pubmed_xml_to_record(root=root)
                if not retrieved_record_dict:
                    self.logger.warning(
                        "Failed to retrieve Pubmed record %s", pubmed_id
                    )
                    self.logger.debug(root.text)
                    raise colrev_exceptions.RecordNotParsableException(
                        "Pubmed record not parsable"
                    )
                retrieved_record = colrev.record.record.Record(retrieved_record_dict)
                return retrieved_record
        except requests.exceptions.RequestException as exc:
            raise PubmedAPIError from exc
        except ParseError as exc:
            raise colrev_exceptions.RecordNotParsableException(
                "Error parsing xml"
            ) from exc
        # pylint: disable=duplicate-code
        except OperationalError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            ) from exc

    def _get_pubmed_ids(self) -> dict:
        """Call eSearch with JSON output using self._retstart/self._retmax."""
        params = {
            "retmode": "json",
            "retstart": self._retstart,
            "retmax": self._retmax,
        }
        while True:
            try:
                ret = self.session.request(
                    "GET", self.url, params=params, headers=self.headers, timeout=30
                )
                if ret.status_code == 429:
                    time.sleep(1.0)  # gentle backoff for eSearch
                    continue
                ret.raise_for_status()
                data = ret.json()
                es = data.get("esearchresult", {})
                return {
                    "uids": es.get("idlist", []),
                    "totalResults": int(es.get("count", 0)),
                }
            except requests.exceptions.RequestException as exc:  # pragma: no cover
                raise PubmedAPIError from exc

    def get_query_return(self) -> typing.Iterator[colrev.record.record.Record]:
        """Retrieve records from PubMed based on self.url (term already included)."""

        total_results = None
        seen = set()

        while True:
            page = self._get_pubmed_ids()

            ids = page["uids"]

            count = len(ids)
            start_1 = self._retstart + 1
            end_1 = self._retstart + count

            if total_results is None:
                total_results = page["totalResults"]
                self.logger.info("Total results: %s", total_results)
                expected_time = datetime.timedelta(
                    seconds=round(total_results / 3)
                )  # ~3 req/s
                self.logger.info("Rate limit: 3 requests per second")
                self.logger.info("Expected time [hh:mm:ss]: %s", expected_time)
                self.logger.info(
                    "Processing records %s–%s of %s", start_1, end_1, total_results
                )
            else:
                # print page nr of total and remaining time
                self.logger.info(
                    "Processing records %s–%s of %s", start_1, end_1, total_results
                )
                remaining_time = datetime.timedelta(
                    seconds=round((total_results - self._retstart) / 3)
                )  # ~3 req/s
                self.logger.info("Remaining time [hh:mm:ss]: %s", remaining_time)

            if not ids:
                break

            for pubmed_id in ids:
                if pubmed_id in seen:
                    continue
                seen.add(pubmed_id)
                time.sleep(0.5)  # keep per-ID efetch under ~3 rps
                try:
                    yield self.query_id(pubmed_id=pubmed_id)
                except colrev_exceptions.RecordNotParsableException:
                    pass

            # advance paging state by what we actually received
            self._retstart += len(ids)
            if total_results is not None and self._retstart >= total_results:
                break
