#! /usr/bin/env python
"""SearchSource: Pubmed"""
from __future__ import annotations

import typing
from copy import deepcopy
from dataclasses import dataclass
from multiprocessing import Lock
from pathlib import Path
from sqlite3 import OperationalError
from typing import Optional
from urllib.parse import urlparse
from xml.etree import ElementTree  # nosec
from xml.etree.ElementTree import Element  # nosec

import defusedxml
import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from defusedxml.lxml import fromstring
from lxml.etree import XMLSyntaxError

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.load_utils_table
import colrev.ops.search
import colrev.record
from colrev.constants import Fields
from colrev.constants import FieldValues

defusedxml.defuse_stdlib()


# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class PubMedSearchSource(JsonSchemaMixin):
    """Pubmed"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "pubmedid"
    search_types = [
        colrev.settings.SearchType.DB,
        colrev.settings.SearchType.API,
        colrev.settings.SearchType.MD,
    ]
    endpoint = "colrev.pubmed"

    ci_supported: bool = True
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "PubMed"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/pubmed.md"
    )
    db_url = "https://pubmed.ncbi.nlm.nih.gov/"
    __pubmed_md_filename = Path("data/search/md_pubmed.bib")

    def __init__(
        self,
        *,
        source_operation: colrev.operation.Operation,
        settings: Optional[dict] = None,
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
                if s.filename == self.__pubmed_md_filename
            ]
            if pubmed_md_source_l:
                self.search_source = pubmed_md_source_l[0]
            else:
                self.search_source = colrev.settings.SearchSource(
                    endpoint=self.endpoint,
                    filename=self.__pubmed_md_filename,
                    search_type=colrev.settings.SearchType.MD,
                    search_parameters={},
                    comment="",
                )

            self.pubmed_lock = Lock()

        self.operation = source_operation
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
        params: dict,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        search_type = operation.select_search_type(
            search_types=cls.search_types, params=params
        )

        if search_type == colrev.settings.SearchType.DB:
            return operation.add_db_source(
                search_source_cls=cls,
                params=params,
            )

        if search_type == colrev.settings.SearchType.API:
            if len(params) == 0:
                add_source = operation.add_api_source(endpoint=cls.endpoint)
                return add_source

            # pylint: disable=colrev-missed-constant-usage
            if "url" in params:
                host = urlparse(params["url"]).hostname

                if host and host.endswith("pubmed.ncbi.nlm.nih.gov"):
                    params = params["url"].replace(
                        "https://pubmed.ncbi.nlm.nih.gov/?term=", ""
                    )

                    filename = operation.get_unique_filename(file_path_string="pubmed")
                    # params = (
                    # "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term="
                    #     + params
                    # )
                    add_source = colrev.settings.SearchSource(
                        endpoint=cls.endpoint,
                        filename=filename,
                        search_type=colrev.settings.SearchType.API,
                        search_parameters={"query": params},
                        comment="",
                    )
                    return add_source

            raise NotImplementedError

        raise NotImplementedError

    def __validate_source(self) -> None:
        """Validate the SearchSource (parameters etc.)"""

        source = self.search_source
        self.review_manager.logger.debug(f"Validate SearchSource {source.filename}")

        if source.filename.name != self.__pubmed_md_filename.name:
            if "query" not in source.search_parameters:
                raise colrev_exceptions.InvalidQueryException(
                    f"Source missing query search_parameter ({source.filename})"
                )

            # if "query_file" in source.search_parameters:
            # ...

        self.review_manager.logger.debug(f"SearchSource {source.filename} validated")

    def check_availability(
        self, *, source_operation: colrev.operation.Operation
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
            returned_record_dict = self.__pubmed_query_id(
                pubmed_id=test_rec["pubmedid"],
                timeout=20,
            )

            if returned_record_dict:
                assert returned_record_dict[Fields.TITLE] == test_rec[Fields.TITLE]
                assert returned_record_dict[Fields.AUTHOR] == test_rec[Fields.AUTHOR]
            else:
                if not source_operation.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException("Pubmed")
        except (requests.exceptions.RequestException, IndexError) as exc:
            print(exc)
            if not source_operation.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException("Pubmed") from exc

    @classmethod
    def __get_author_string_from_node(cls, *, author_node: Element) -> str:
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
    def __get_author_string(cls, *, root) -> str:  # type: ignore
        authors_list = []
        for author_node in root.xpath(
            "/PubmedArticleSet/PubmedArticle/MedlineCitation/Article/AuthorList/Author"
        ):
            authors_list.append(
                cls.__get_author_string_from_node(author_node=author_node)
            )
        return " and ".join(authors_list)

    @classmethod
    def __get_title_string(cls, *, root) -> str:  # type: ignore
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
    def __get_abstract_string(cls, *, root) -> str:  # type: ignore
        abstract = root.xpath(
            "/PubmedArticleSet/PubmedArticle/MedlineCitation/Article/Abstract"
        )
        if abstract:
            return ElementTree.tostring(abstract[0], encoding="unicode")
        return ""

    # pylint: disable=colrev-missed-constant-usage
    @classmethod
    def __pubmed_xml_to_record(cls, *, root) -> dict:  # type: ignore
        retrieved_record_dict: dict = {Fields.ENTRYTYPE: "misc"}

        pubmed_article = root.find("PubmedArticle")
        if pubmed_article is None:
            return {}
        if pubmed_article.find("MedlineCitation") is None:
            return {}

        retrieved_record_dict[Fields.TITLE] = cls.__get_title_string(root=root)
        retrieved_record_dict[Fields.AUTHOR] = cls.__get_author_string(root=root)

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

        retrieved_record_dict[Fields.ABSTRACT] = cls.__get_abstract_string(root=root)

        article_id_list = root.xpath(
            "/PubmedArticleSet/PubmedArticle/PubmedData/ArticleIdList"
        )
        for article_id in article_id_list[0]:
            id_type = article_id.attrib.get("IdType")
            if article_id.attrib.get("IdType") == "pubmed":
                retrieved_record_dict[Fields.PUBMED_ID] = article_id.text.upper()
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

    def __get_pubmed_ids(self, query: str, retstart: int) -> typing.List[str]:
        headers = {"user-agent": f"{__name__} (mailto:{self.email})"}
        session = self.review_manager.get_cached_session()
        if not query.startswith("https://pubmed.ncbi.nlm.nih.gov/?term="):
            query = "https://pubmed.ncbi.nlm.nih.gov/?term=" + query
        ret = session.request(
            "GET", query + f"&retstart={retstart}", headers=headers, timeout=30
        )

        ret.raise_for_status()
        if ret.status_code != 200:
            # review_manager.logger.debug(
            #     f"crossref_query failed with status {ret.status_code}"
            # )
            return []

        root = fromstring(str.encode(ret.text))
        return [
            x.text
            for x_el in root.findall("IdList")
            for x in x_el
            if x.text is not None
        ]

    def __pubmed_query_id(
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

            root = fromstring(str.encode(ret.text))
            retrieved_record = self.__pubmed_xml_to_record(root=root)
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

    def __get_masterdata_record(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool,
        timeout: int,
    ) -> colrev.record.Record:
        try:
            retrieved_record_dict = self.__pubmed_query_id(
                pubmed_id=record.data["pubmedid"],
                timeout=timeout,
            )

            retries = 0
            while (
                not retrieved_record_dict
                and retries < prep_operation.max_retries_on_error
            ):
                retries += 1

                retrieved_record_dict = self.__pubmed_query_id(
                    pubmed_id=record.data["pubmedid"],
                    timeout=timeout,
                )

            if not retrieved_record_dict:
                raise colrev_exceptions.RecordNotFoundInPrepSourceException(
                    msg="Pubmed: no records retrieved"
                )

            retrieved_record = colrev.record.Record(data=retrieved_record_dict)

            similarity = colrev.record.PrepRecord.get_retrieval_similarity(
                record_original=record, retrieved_record_original=retrieved_record
            )
            # prep_operation.review_manager.logger.debug("Found matching record")
            # prep_operation.review_manager.logger.debug(
            #     f"crossref similarity: {similarity} "
            #     f"(>{prep_operation.retrieval_similarity})"
            # )
            self.review_manager.logger.debug(
                f"pubmed similarity: {similarity} "
                f"(<{prep_operation.retrieval_similarity})"
            )

            try:
                self.pubmed_lock.acquire(timeout=60)

                # Note : need to reload file because the object is not shared between processes
                pubmed_feed = self.search_source.get_feed(
                    review_manager=self.review_manager,
                    source_identifier=self.source_identifier,
                    update_only=False,
                )

                pubmed_feed.set_id(record_dict=retrieved_record.data)
                pubmed_feed.add_record(record=retrieved_record)

                record.merge(
                    merging_record=retrieved_record,
                    default_source=retrieved_record.data[Fields.ORIGIN][0],
                )

                record.set_masterdata_complete(
                    source=retrieved_record.data[Fields.ORIGIN][0],
                    masterdata_repository=self.review_manager.settings.is_curated_repo(),
                )
                record.set_status(target_state=colrev.record.RecordState.md_prepared)
                if save_feed:
                    pubmed_feed.save_feed_file()
                try:
                    self.pubmed_lock.release()
                except ValueError:
                    pass

                return record
            except (
                colrev_exceptions.InvalidMerge,
                colrev_exceptions.NotFeedIdentifiableException,
            ):
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

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.Record:
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
        #    record = self.__check_doi_masterdata(record=record)

        # remove the following if we match basd on similarity
        if Fields.PUBMED_ID not in record.data:
            return record

        record = self.__get_masterdata_record(
            prep_operation=prep_operation,
            record=record,
            timeout=timeout,
            save_feed=save_feed,
        )

        return record

    def __get_pubmed_query_return(self) -> typing.Iterator[dict]:
        params = self.search_source.search_parameters

        retstart = 0
        while True:
            pubmed_ids = self.__get_pubmed_ids(query=params["query"], retstart=retstart)
            if not pubmed_ids:
                break
            for pubmed_id in pubmed_ids:
                yield self.__pubmed_query_id(pubmed_id=pubmed_id)

            retstart += 20

    def __run_api_search(
        self,
        *,
        pubmed_feed: colrev.ops.search_feed.GeneralOriginFeed,
        rerun: bool,
    ) -> None:
        if rerun:
            self.review_manager.logger.info(
                "Performing a search of the full history (may take time)"
            )

        records = self.review_manager.dataset.load_records_dict()
        try:
            for record_dict in self.__get_pubmed_query_return():
                # Note : discard "empty" records
                if "" == record_dict.get(Fields.AUTHOR, "") and "" == record_dict.get(
                    Fields.TITLE, ""
                ):
                    self.review_manager.logger.warning(f"Skipped record: {record_dict}")
                    continue
                try:
                    pubmed_feed.set_id(record_dict=record_dict)
                except colrev_exceptions.NotFeedIdentifiableException:
                    continue

                prev_record_dict_version = {}
                if record_dict[Fields.ID] in pubmed_feed.feed_records:
                    prev_record_dict_version = deepcopy(
                        pubmed_feed.feed_records[record_dict[Fields.ID]]
                    )

                prep_record = colrev.record.PrepRecord(data=record_dict)

                if Fields.D_PROV in prep_record.data:
                    del prep_record.data[Fields.D_PROV]

                added = pubmed_feed.add_record(record=prep_record)

                if added:
                    self.review_manager.logger.info(
                        " retrieve pubmed-id=" + prep_record.data["pubmedid"]
                    )
                else:
                    pubmed_feed.update_existing_record(
                        records=records,
                        record_dict=prep_record.data,
                        prev_record_dict_version=prev_record_dict_version,
                        source=self.search_source,
                        update_time_variant_fields=rerun,
                    )

                # Note : only retrieve/update the latest deposits (unless in rerun mode)
                if not added and not rerun:
                    # problem: some publishers don't necessarily
                    # deposit papers chronologically
                    break

            pubmed_feed.print_post_run_search_infos(records=records)
            pubmed_feed.save_feed_file()
            self.review_manager.dataset.save_records_dict(records=records)

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

    def __run_md_search(
        self,
        *,
        pubmed_feed: colrev.ops.search_feed.GeneralOriginFeed,
    ) -> None:
        records = self.review_manager.dataset.load_records_dict()

        for feed_record_dict in pubmed_feed.feed_records.values():
            feed_record = colrev.record.Record(data=feed_record_dict)

            try:
                retrieved_record = self.__pubmed_query_id(
                    pubmed_id=feed_record_dict["pubmedid"]
                )

                if retrieved_record["pubmedid"] != feed_record.data["pubmedid"]:
                    continue

                pubmed_feed.set_id(record_dict=retrieved_record)
            except (
                colrev_exceptions.RecordNotFoundInPrepSourceException,
                colrev_exceptions.NotFeedIdentifiableException,
            ):
                continue

            prev_record_dict_version = {}
            if retrieved_record[Fields.ID] in pubmed_feed.feed_records:
                prev_record_dict_version = pubmed_feed.feed_records[
                    retrieved_record[Fields.ID]
                ]

            pubmed_feed.add_record(record=colrev.record.Record(data=retrieved_record))

            pubmed_feed.update_existing_record(
                records=records,
                record_dict=retrieved_record,
                prev_record_dict_version=prev_record_dict_version,
                source=self.search_source,
                update_time_variant_fields=True,
            )

        pubmed_feed.save_feed_file()
        pubmed_feed.print_post_run_search_infos(records=records)
        self.review_manager.dataset.save_records_dict(records=records)

    def run_search(self, rerun: bool) -> None:
        """Run a search of Pubmed"""

        self.__validate_source()

        pubmed_feed = self.search_source.get_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        if self.search_source.search_type == colrev.settings.SearchType.MD:
            self.__run_md_search(pubmed_feed=pubmed_feed)

        elif self.search_source.search_type == colrev.settings.SearchType.API:
            self.__run_api_search(
                pubmed_feed=pubmed_feed,
                rerun=rerun,
            )

        elif self.search_source.search_type == colrev.settings.SearchType.DB:
            self.operation.run_db_search()  # type: ignore

        else:
            raise NotImplementedError

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".csv":
            csv_loader = colrev.ops.load_utils_table.CSVLoader(
                load_operation=load_operation,
                source=self.search_source,
                unique_id_field="pmid",
            )
            table_entries = csv_loader.load_table_entries()
            records = csv_loader.convert_to_records(entries=table_entries)
            self.__load_fixes(records=records)
            return records

        if self.search_source.filename.suffix == ".bib":
            records = colrev.ops.load_utils_bib.load_bib_file(
                load_operation=load_operation, source=self.search_source
            )
            return records

        raise NotImplementedError

    def __load_fixes(
        self,
        records: typing.Dict,
    ) -> None:
        """Load fixes for Pubmed"""

        for record in records.values():
            if Fields.AUTHOR in record and record[Fields.AUTHOR].count(",") >= 1:
                author_list = record[Fields.AUTHOR].split(", ")
                for i, author_part in enumerate(author_list):
                    author_field_parts = author_part.split(" ")
                    author_list[i] = (
                        author_field_parts[0] + ", " + " ".join(author_field_parts[1:])
                    )

                record[Fields.AUTHOR] = " and ".join(author_list)
            if "first_author" in record:
                del record["first_author"]
            if record.get(Fields.JOURNAL, "") != "":
                record[Fields.ENTRYTYPE] = "article"
            if (
                record.get("pii", "pii").lower()
                == record.get(Fields.DOI, Fields.DOI).lower()
            ):
                del record["pii"]
            if record.get("nihms_id", "") == "nan":
                del record["nihms_id"]
            if "citation" in record:
                details_part = record["citation"]
                details_part = details_part[details_part.find(";") + 1 :]
                details_part = details_part[: details_part.find(".")]
                if ":" in details_part:
                    record[Fields.PAGES] = details_part[details_part.find(":") + 1 :]
                    details_part = details_part[: details_part.find(":")]
                if "(" in details_part:
                    record[Fields.NUMBER] = details_part[
                        details_part.find("(") + 1 : -1
                    ]
                    details_part = details_part[: details_part.find("(")]
                record[Fields.VOLUME] = details_part
                del record["citation"]
            if "journal/book" in record:
                record[Fields.JOURNAL] = record.pop("journal/book")

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for Pubmed"""

        if "colrev.pubmed.first_author" in record.data:
            record.remove_field(key="colrev.pubmed.first_author")
        if (
            record.data.get(Fields.AUTHOR) == FieldValues.UNKNOWN
            and "authors" in record.data
        ):
            record.remove_field(key=Fields.AUTHOR)
            record.rename_field(key="authors", new_key=Fields.AUTHOR)

        if record.data.get(Fields.YEAR) == FieldValues.UNKNOWN:
            record.remove_field(key=Fields.YEAR)
            if "colrev.pubmed.publication_year" in record.data:
                record.rename_field(
                    key="colrev.pubmed.publication_year", new_key=Fields.YEAR
                )

        if Fields.AUTHOR in record.data:
            record.data[Fields.AUTHOR] = colrev.record.PrepRecord.format_author_field(
                input_string=record.data[Fields.AUTHOR]
            )

        # TBD: how to distinguish other types?
        record.change_entrytype(new_entrytype="article", qm=self.quality_model)

        return record
