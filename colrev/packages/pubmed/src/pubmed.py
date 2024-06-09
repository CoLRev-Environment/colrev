#! /usr/bin/env python
"""SearchSource: Pubmed"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from multiprocessing import Lock
from pathlib import Path
from sqlite3 import OperationalError
from urllib.parse import urlparse
from xml.etree import ElementTree  # nosec
from xml.etree.ElementTree import Element  # nosec

import pandas as pd
import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from lxml import etree
from lxml import html
from lxml.etree import XMLSyntaxError

import colrev.exceptions as colrev_exceptions
import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record
import colrev.record.record_prep
import colrev.record.record_similarity
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import RecordState
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class PubMedSearchSource(JsonSchemaMixin):
    """Pubmed"""

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    source_identifier = "pubmedid"
    search_types = [
        SearchType.DB,
        SearchType.API,
        SearchType.MD,
    ]
    endpoint = "colrev.pubmed"

    ci_supported: bool = True
    heuristic_status = SearchSourceHeuristicStatus.supported
    short_name = "PubMed"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/packages/search_sources/pubmed.md"
    )
    db_url = "https://pubmed.ncbi.nlm.nih.gov/"
    _pubmed_md_filename = Path("data/search/md_pubmed.bib")

    def __init__(
        self,
        *,
        source_operation: colrev.process.operation.Operation,
        settings: typing.Optional[dict] = None,
    ) -> None:
        self.review_manager = source_operation.review_manager
        if settings:
            # Pubmed as a search_source
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )
        else:
            # Pubmed as an md-prep source
            pubmed_md_source_l = [
                s
                for s in self.review_manager.settings.sources
                if s.filename == self._pubmed_md_filename
            ]
            if pubmed_md_source_l:
                self.search_source = pubmed_md_source_l[0]
            else:
                self.search_source = colrev.settings.SearchSource(
                    endpoint=self.endpoint,
                    filename=self._pubmed_md_filename,
                    search_type=SearchType.MD,
                    search_parameters={},
                    comment="",
                )

            self.pubmed_lock = Lock()

        self.source_operation = source_operation
        self.quality_model = self.review_manager.get_qm()
        _, self.email = self.review_manager.get_committer()

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Pubmed"""

        result = {"confidence": 0.0}

        # Simple heuristic:
        if "PMID,Title,Authors,Citation,First Author,Journal/Book," in data:
            result["confidence"] = 1.0
            return result
        if "PMID- " in data:
            result["confidence"] = 0.7
            return result

        if "pmid " in data:
            if data.count(" pmid ") > data.count("\n@"):
                result["confidence"] = 1.0

        return result

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: str,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""

        params_dict = {}
        if params:
            if params.startswith("http"):
                params_dict = {Fields.URL: params}
            else:
                for item in params.split(";"):
                    key, value = item.split("=")
                    params_dict[key] = value

        search_type = operation.select_search_type(
            search_types=cls.search_types, params=params_dict
        )

        if search_type == SearchType.DB:
            search_source = operation.create_db_source(
                search_source_cls=cls,
                params=params_dict,
            )

        elif search_type == SearchType.API:
            if len(params_dict) == 0:
                search_source = operation.create_api_source(endpoint=cls.endpoint)

            # pylint: disable=colrev-missed-constant-usage
            elif "url" in params_dict:
                host = urlparse(params_dict["url"]).hostname

                if host and host.endswith("pubmed.ncbi.nlm.nih.gov"):
                    query = {
                        "query": params_dict["url"].replace(
                            "https://pubmed.ncbi.nlm.nih.gov/?term=", ""
                        )
                    }

                    filename = operation.get_unique_filename(file_path_string="pubmed")
                    # params = (
                    # "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term="
                    #     + params
                    # )
                    search_source = colrev.settings.SearchSource(
                        endpoint=cls.endpoint,
                        filename=filename,
                        search_type=SearchType.API,
                        search_parameters=query,
                        comment="",
                    )
            else:
                raise NotImplementedError

        else:
            raise NotImplementedError

        operation.add_source_and_search(search_source)
        return search_source

    def _validate_source(self) -> None:
        """Validate the SearchSource (parameters etc.)"""

        source = self.search_source
        self.review_manager.logger.debug(f"Validate SearchSource {source.filename}")

        if source.filename.name != self._pubmed_md_filename.name:
            if "query" not in source.search_parameters:
                raise colrev_exceptions.InvalidQueryException(
                    f"Source missing query search_parameter ({source.filename})"
                )

            # if "query_file" in source.search_parameters:
            # ...

        self.review_manager.logger.debug(f"SearchSource {source.filename} validated")

    def check_availability(
        self, *, source_operation: colrev.process.operation.Operation
    ) -> None:
        """Check status (availability) of the Pubmed API"""

        try:
            # pylint: disable=duplicate-code
            test_rec = {
                Fields.AUTHOR: "Nazzaro, P and Manzari, M and Merlo, M and Triggiani, R and "
                "Scarano, A and Ciancio, L and Pirrelli, A",
                Fields.TITLE: "Distinct and combined vascular effects of ACE blockade and "
                "HMG-CoA reductase inhibition in hypertensive subjects",
                Fields.ENTRYTYPE: "article",
                "pubmedid": "10024335",
            }
            returned_record_dict = self._pubmed_query_id(
                pubmed_id=test_rec["pubmedid"],
                timeout=20,
            )

            if returned_record_dict:
                assert returned_record_dict[Fields.TITLE] == test_rec[Fields.TITLE]
                assert returned_record_dict[Fields.AUTHOR] == test_rec[Fields.AUTHOR]
            else:
                if not self.review_manager.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException("Pubmed")
        except (requests.exceptions.RequestException, IndexError, KeyError) as exc:
            print(exc)
            if not self.review_manager.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException("Pubmed") from exc

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

    def _get_pubmed_ids(self, query: str, retstart: int, page: int) -> typing.List[str]:
        headers = {"user-agent": f"{__name__} (mailto:{self.email})"}
        session = self.review_manager.get_cached_session()
        if not query.startswith("https://pubmed.ncbi.nlm.nih.gov/?term="):
            query = "https://pubmed.ncbi.nlm.nih.gov/?term=" + query
        url = query + f"&retstart={retstart}&page={page}"
        ret = session.request("GET", url, headers=headers, timeout=30)
        ret.raise_for_status()
        if ret.status_code != 200:
            # review_manager.logger.debug(
            #     f"crossref_query failed with status {ret.status_code}"
            # )
            return []

        root = html.fromstring(str.encode(ret.text))
        meta_tags = root.findall(".//meta[@name='log_displayeduids']")
        displayed_uids = [tag.get("content") for tag in meta_tags][0].split(",")
        return displayed_uids

    def _pubmed_query_id(
        self,
        *,
        pubmed_id: str,
        timeout: int = 60,
    ) -> dict:
        """Retrieve records from Pubmed based on a query"""

        try:
            database = "pubmed"
            url = (
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?"
                + f"db={database}&id={pubmed_id}&rettype=xml&retmode=text"
            )

            headers = {"user-agent": f"{__name__} (mailto:{self.email})"}
            session = self.review_manager.get_cached_session()

            # review_manager.logger.debug(url)
            ret = session.request("GET", url, headers=headers, timeout=timeout)
            ret.raise_for_status()
            if ret.status_code != 200:
                # review_manager.logger.debug(
                #     f"crossref_query failed with status {ret.status_code}"
                # )
                return {"pubmed_id": pubmed_id}

            root = etree.fromstring(str.encode(ret.text))
            retrieved_record = self._pubmed_xml_to_record(root=root)
            if not retrieved_record:
                return {"pubmed_id": pubmed_id}
        except requests.exceptions.RequestException:
            return {"pubmed_id": pubmed_id}
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
        return retrieved_record

    def _get_masterdata_record(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool,
        timeout: int,
    ) -> colrev.record.record.Record:
        try:
            retrieved_record_dict = self._pubmed_query_id(
                pubmed_id=record.data["pubmedid"],
                timeout=timeout,
            )

            retries = 0
            while (
                not retrieved_record_dict
                and retries < prep_operation.max_retries_on_error
            ):
                retries += 1

                retrieved_record_dict = self._pubmed_query_id(
                    pubmed_id=record.data["pubmedid"],
                    timeout=timeout,
                )

            if not retrieved_record_dict:
                raise colrev_exceptions.RecordNotFoundInPrepSourceException(
                    msg="Pubmed: no records retrieved"
                )

            retrieved_record = colrev.record.record.Record(retrieved_record_dict)

            if not colrev.record.record_similarity.matches(record, retrieved_record):
                return record

            try:
                self.pubmed_lock.acquire(timeout=60)

                # Note : need to reload file because the object is not shared between processes
                pubmed_feed = self.search_source.get_api_feed(
                    review_manager=self.review_manager,
                    source_identifier=self.source_identifier,
                    update_only=False,
                    prep_mode=True,
                )

                pubmed_feed.add_update_record(retrieved_record)

                record.merge(
                    retrieved_record,
                    default_source=retrieved_record.data[Fields.ORIGIN][0],
                )

                record.set_masterdata_complete(
                    source=retrieved_record.data[Fields.ORIGIN][0],
                    masterdata_repository=self.review_manager.settings.is_curated_repo(),
                )
                record.set_status(RecordState.md_prepared)
                if save_feed:
                    pubmed_feed.save()
                try:
                    self.pubmed_lock.release()
                except ValueError:
                    pass

                return record
            except (colrev_exceptions.NotFeedIdentifiableException,):
                try:
                    self.pubmed_lock.release()
                except ValueError:
                    pass

                return record

        except (
            requests.exceptions.RequestException,
            OSError,
            IndexError,
            colrev_exceptions.RecordNotFoundInPrepSourceException,
            colrev_exceptions.RecordNotParsableException,
        ):
            pass
        return record

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        """Retrieve masterdata from Pubmed based on similarity with the record provided"""

        # To test the metadata provided for a particular pubmed-id use:
        # https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=10075143&rettype=xml&retmode=text

        if (
            len(record.data.get(Fields.TITLE, "")) < 35
            and Fields.PUBMED_ID not in record.data
        ):
            return record

        # at this point, we coujld validate metadata
        # if "pubmedid" not in record.data:
        #    record = self._check_doi_masterdata(record=record)

        # remove the following if we match basd on similarity
        if Fields.PUBMED_ID not in record.data:
            return record

        record = self._get_masterdata_record(
            prep_operation=prep_operation,
            record=record,
            timeout=timeout,
            save_feed=save_feed,
        )

        return record

    def _get_pubmed_query_return(self) -> typing.Iterator[dict]:
        params = self.search_source.search_parameters

        retstart = 10
        page = 1
        while True:
            pubmed_ids = self._get_pubmed_ids(
                query=params["query"], retstart=retstart, page=page
            )
            if not pubmed_ids:
                break
            for pubmed_id in pubmed_ids:
                yield self._pubmed_query_id(pubmed_id=pubmed_id)

            page += 1

    def _run_api_search(
        self,
        *,
        pubmed_feed: colrev.ops.search_api_feed.SearchAPIFeed,
        rerun: bool,
    ) -> None:
        if rerun:
            self.review_manager.logger.info(
                "Performing a search of the full history (may take time)"
            )

        try:
            for record_dict in self._get_pubmed_query_return():
                try:
                    # Note : discard "empty" records
                    if "" == record_dict.get(
                        Fields.AUTHOR, ""
                    ) and "" == record_dict.get(Fields.TITLE, ""):
                        self.review_manager.logger.warning(
                            f"Skipped record: {record_dict}"
                        )
                        continue
                    prep_record = colrev.record.record_prep.PrepRecord(record_dict)

                    if Fields.D_PROV in prep_record.data:
                        del prep_record.data[Fields.D_PROV]

                    added = pubmed_feed.add_update_record(prep_record)

                    # Note : only retrieve/update the latest deposits (unless in rerun mode)
                    if not added and not rerun:
                        # problem: some publishers don't necessarily
                        # deposit papers chronologically
                        break
                except colrev_exceptions.NotFeedIdentifiableException:
                    print("Cannot set id for record")
                    continue

            pubmed_feed.save()

        except requests.exceptions.JSONDecodeError as exc:
            # watch github issue:
            # https://github.com/fabiobatalha/crossrefapi/issues/46
            if "504 Gateway Time-out" in str(exc):
                raise colrev_exceptions.ServiceNotAvailableException(
                    "Crossref (check https://status.crossref.org/)"
                )
            raise colrev_exceptions.ServiceNotAvailableException(
                f"Crossref (check https://status.crossref.org/) ({exc})"
            )

    def _run_md_search(
        self,
        *,
        pubmed_feed: colrev.ops.search_api_feed.SearchAPIFeed,
    ) -> None:

        for feed_record_dict in pubmed_feed.feed_records.values():
            feed_record = colrev.record.record.Record(feed_record_dict)

            try:
                retrieved_record_dict = self._pubmed_query_id(
                    pubmed_id=feed_record_dict["pubmedid"]
                )

                if retrieved_record_dict["pubmedid"] != feed_record.data["pubmedid"]:
                    continue
                retrieved_record = colrev.record.record.Record(retrieved_record_dict)
                pubmed_feed.add_update_record(retrieved_record)
            except (
                colrev_exceptions.RecordNotFoundInPrepSourceException,
                colrev_exceptions.NotFeedIdentifiableException,
            ):
                continue

        pubmed_feed.save()

    def search(self, rerun: bool) -> None:
        """Run a search of Pubmed"""

        self._validate_source()

        pubmed_feed = self.search_source.get_api_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        if self.search_source.search_type == SearchType.MD:
            self._run_md_search(pubmed_feed=pubmed_feed)

        elif self.search_source.search_type == SearchType.API:
            self._run_api_search(
                pubmed_feed=pubmed_feed,
                rerun=rerun,
            )

        elif self.search_source.search_type == SearchType.DB:
            self.source_operation.run_db_search(  # type: ignore
                search_source_cls=self.__class__,
                source=self.search_source,
            )
            return
        else:
            raise NotImplementedError

    def _load_csv(self) -> dict:
        def entrytype_setter(record_dict: dict) -> None:
            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE

        def field_mapper(record_dict: dict) -> None:
            record_dict[Fields.TITLE] = record_dict.pop("Title", "")
            record_dict[Fields.JOURNAL] = record_dict.pop("Journal/Book", "")
            record_dict[Fields.YEAR] = record_dict.pop("Publication Year", "")
            record_dict[Fields.URL] = record_dict.pop("URL", "")
            record_dict[Fields.DOI] = record_dict.pop("DOI", "")
            record_dict[f"{self.endpoint}.nihms_id"] = record_dict.pop("NIHMS ID", "")
            record_dict[Fields.PUBMED_ID] = record_dict.pop("PMID", "")
            record_dict[Fields.PMCID] = record_dict.pop("PMCID", "")
            record_dict[f"{self.endpoint}.create_date"] = record_dict.pop(
                "Create Date", ""
            )

            author_list = record_dict.pop("Authors", "").split(", ")
            for i, author_part in enumerate(author_list):
                author_field_parts = author_part.split(" ")
                author_list[i] = (
                    author_field_parts[0] + ", " + " ".join(author_field_parts[1:])
                )
            record_dict[Fields.AUTHOR] = " and ".join(author_list)

            if "Citation" in record_dict:
                details_part = record_dict["Citation"]
                details_part = details_part[details_part.find(";") + 1 :]
                details_part = details_part[: details_part.find(".")]
                if ":" in details_part:
                    record_dict[Fields.PAGES] = details_part[
                        details_part.find(":") + 1 :
                    ]
                    details_part = details_part[: details_part.find(":")]
                if "(" in details_part:
                    record_dict[Fields.NUMBER] = details_part[
                        details_part.find("(") + 1 : -1
                    ]
                    details_part = details_part[: details_part.find("(")]
                record_dict[Fields.VOLUME] = details_part

            record_dict.pop("First Author", None)
            record_dict.pop("Citation", None)

            for key in list(record_dict.keys()):
                value = record_dict[key]
                record_dict[key] = str(value)
                if value == "" or pd.isna(value):
                    del record_dict[key]

        records = colrev.loader.load_utils.load(
            filename=self.search_source.filename,
            unique_id_field="PMID",
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            logger=self.review_manager.logger,
        )
        return records

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".csv":
            return self._load_csv()

        if self.search_source.filename.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=self.search_source.filename,
                logger=self.review_manager.logger,
            )
            return records

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.record.Record:
        """Source-specific preparation for Pubmed"""

        if "colrev.pubmed.first_author" in record.data:
            record.remove_field(key="colrev.pubmed.first_author")

        if Fields.AUTHOR in record.data:
            record.data[Fields.AUTHOR] = (
                colrev.record.record_prep.PrepRecord.format_author_field(
                    record.data[Fields.AUTHOR]
                )
            )

        return record
