#! /usr/bin/env python
"""Pubmed API"""
import datetime
import logging
import time
import typing
from sqlite3 import OperationalError
from xml.etree import ElementTree  # nosec
from xml.etree.ElementTree import Element  # nosec

import requests
from lxml import etree
from lxml import html
from lxml.etree import XMLSyntaxError

import colrev.exceptions as colrev_exceptions
import colrev.record.record_prep
from colrev.constants import Fields


# pylint: disable=too-few-public-methods


class PubmedAPI:
    """Connector for the Pubmed API"""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        parameters: dict,
        email: str,
        session: requests.Session,
        timeout: int = 60,
        logger: typing.Optional[logging.Logger] = None,
    ):
        self.email = email
        self.session = session
        self._timeout = timeout
        self.params = parameters

        self.headers = {"user-agent": f"{__name__} (mailto:{self.email})"}

        if logger is not None:
            self.logger = logger
        else:
            self.logger = logging.getLogger(__name__)

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
    def _get_author_string(cls, *, root) -> str:  # type: ignore
        authors_list = []
        for author_node in root.xpath(
            "/PubmedArticleSet/PubmedArticle/MedlineCitation/Article/AuthorList/Author"
        ):
            authors_list.append(
                cls._get_author_string_from_node(author_node=author_node)
            )
        return " and ".join(authors_list)

    @classmethod
    def _get_title_string(cls, *, root) -> str:  # type: ignore
        title = root.xpath(
            "/PubmedArticleSet/PubmedArticle/MedlineCitation/Article/ArticleTitle"
        )
        if title:
            if title[0].text:
                title = title[0].text.strip().rstrip(".")
                if title.startswith("[") and title.endswith("]"):
                    title = title[1:-1]
                return title
        return ""

    @classmethod
    def _get_abstract_string(cls, *, root) -> str:  # type: ignore
        abstract = root.xpath(
            "/PubmedArticleSet/PubmedArticle/MedlineCitation/Article/Abstract"
        )
        if abstract:
            return ElementTree.tostring(abstract[0], encoding="unicode")
        return ""

    # pylint: disable=colrev-missed-constant-usage
    @classmethod
    def _pubmed_xml_to_record(cls, *, root) -> dict:  # type: ignore
        retrieved_record_dict: dict = {Fields.ENTRYTYPE: "misc"}

        pubmed_article = root.find("PubmedArticle")
        if pubmed_article is None:
            return {}
        if pubmed_article.find("MedlineCitation") is None:
            return {}

        retrieved_record_dict[Fields.TITLE] = cls._get_title_string(root=root)
        retrieved_record_dict[Fields.AUTHOR] = cls._get_author_string(root=root)

        journal_path = "/PubmedArticleSet/PubmedArticle/MedlineCitation/Article/Journal"
        journal_name = root.xpath(journal_path + "/ISOAbbreviation")
        if journal_name:
            retrieved_record_dict[Fields.ENTRYTYPE] = "article"
            retrieved_record_dict[Fields.JOURNAL] = journal_name[0].text

        volume = root.xpath(journal_path + "/JournalIssue/Volume")
        if volume:
            retrieved_record_dict[Fields.VOLUME] = volume[0].text

        number = root.xpath(journal_path + "/JournalIssue/Issue")
        if number:
            retrieved_record_dict[Fields.NUMBER] = number[0].text

        year = root.xpath(journal_path + "/JournalIssue/PubDate/Year")
        if year:
            retrieved_record_dict[Fields.YEAR] = year[0].text

        retrieved_record_dict[Fields.ABSTRACT] = cls._get_abstract_string(root=root)

        article_id_list = root.xpath(
            "/PubmedArticleSet/PubmedArticle/PubmedData/ArticleIdList"
        )
        for article_id in article_id_list[0]:
            id_type = article_id.attrib.get("IdType")
            if article_id.attrib.get("IdType") == "pubmed":
                retrieved_record_dict["pubmedid"] = article_id.text.upper()
            elif article_id.attrib.get("IdType") == "doi":
                retrieved_record_dict[Fields.DOI] = article_id.text.upper()
            else:
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

                root = etree.fromstring(str.encode(ret.text))
                retrieved_record_dict = self._pubmed_xml_to_record(root=root)
                if not retrieved_record_dict:
                    raise colrev_exceptions.SearchSourceException(
                        "Pubmed record not found"
                    )
                retrieved_record = colrev.record.record.Record(retrieved_record_dict)
                return retrieved_record
        except requests.exceptions.RequestException as exc:
            raise colrev_exceptions.SearchSourceException(
                "Pubmed record not found"
            ) from exc
        except XMLSyntaxError as exc:
            raise colrev_exceptions.RecordNotParsableException(
                "Error parsing xml"
            ) from exc
        # pylint: disable=duplicate-code
        except OperationalError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            ) from exc

    def _get_pubmed_ids(self, query: str, retstart: int, page: int) -> dict:

        if not query.startswith("https://pubmed.ncbi.nlm.nih.gov/?term="):
            query = "https://pubmed.ncbi.nlm.nih.gov/?term=" + query
        url = query + f"&retstart={retstart}&page={page}"
        ret = self.session.request("GET", url, headers=self.headers, timeout=30)
        ret.raise_for_status()
        # if ret.status_code != 200:
        #     # review_manager.logger.debug(
        #     #     f"crossref_query failed with status {ret.status_code}"
        #     # )
        #     return []

        root = html.fromstring(str.encode(ret.text))
        meta_tags = root.findall(".//meta[@name='log_displayeduids']")
        displayed_uids = [tag.get("content") for tag in meta_tags][0].split(",")

        total_results_items = root.xpath(
            "//div[@class='results-amount']//span[@class='value']/text()"
        )
        total_results = int(total_results_items[0].replace(",", ""))
        # total_results = [int(result.replace(',', '')) for result in total_results]

        return {"uids": displayed_uids, "totalResults": total_results}

    def get_query_return(self) -> typing.Iterator[colrev.record.record.Record]:
        """Retrieve records from Pubmed based on a query"""

        retstart = 10
        page = 1
        while True:
            ret = self._get_pubmed_ids(
                query=self.params["query"], retstart=retstart, page=page
            )
            if page == 1:
                # pylint: disable=logging-fstring-interpolation
                total_results = ret["totalResults"]
                self.logger.info(f"Total results: {total_results}")
                expected_time = datetime.timedelta(seconds=total_results / 3)
                expected_time_seconds = round(expected_time.total_seconds())
                hours, remainder = divmod(expected_time_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                expected_time_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                self.logger.info("Rate limit: 3 requests per second")
                self.logger.info(f"Expected time [hh:mm:ss]: {expected_time_formatted}")

            pubmed_ids = ret["uids"]
            if not pubmed_ids:
                break
            for pubmed_id in pubmed_ids:
                time.sleep(0.5)  # to avoid 429 error (pubmed allows 3rps)
                yield self.query_id(pubmed_id=pubmed_id)

            page += 1
