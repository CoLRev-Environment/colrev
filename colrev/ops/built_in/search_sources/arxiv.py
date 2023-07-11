#! /usr/bin/env python
"""SearchSource: arXiv"""
from __future__ import annotations

import typing
import urllib.request
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
from defusedxml.lxml import fromstring

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.search
import colrev.record
# import feedparser

# added import for arXiv API

defusedxml.defuse_stdlib()


# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class ArXivSource:
    """SearchSource for arXiv"""

    # RN: turn search input into query
    # query = colrev.search.input()

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "arxivid"
    search_type = colrev.settings.SearchType.DB
    api_search_supported = True
    ci_supported: bool = True
    # heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "arXiv"  # ist es eig. eagal wie der Name ist?
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/arxiv.md"
    )
    __arxiv_md_filename = Path("data/search/md_arxiv.bib")

    # Added RN: expose metadata if in arXiv namespace
    # feedparser._FeedParserMixin.namespaces['http://a9.com/-/spec/opensearch/1.1/'] = 'opensearch'
    # feedparser._FeedParserMixin.namespaces['http://arxiv.org/schemas/atom'] = 'arxiv'

    def __init__(
        self,
        *,
        source_operation: colrev.operation.Operation,
        settings: Optional[dict] = None,
    ) -> None:
        if settings:
            # arXiv as a search_source
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )
        else:
            # arXiv as an md-prep source
            arxiv_md_source_l = [
                s
                for s in source_operation.review_manager.settings.sources
                if s.filename == self.__arxiv_md_filename
            ]
            if arxiv_md_source_l:
                self.search_source = arxiv_md_source_l[0]
            else:
                self.search_source = colrev.settings.SearchSource(
                    endpoint="colrev.arxiv",
                    filename=self.__arxiv_md_filename,
                    search_type=colrev.settings.SearchType.OTHER,
                    search_parameters={},
                    load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
                    comment="",
                )

            self.arxiv_lock = Lock()

        self.review_manager = source_operation.review_manager
        self.quality_model = self.review_manager.get_qm()
        _, self.email = source_operation.review_manager.get_committer()

    #   @classmethod
    #    def heuristic(cls, filename: Path, data: str) -> dict:
    #        """Source heuristic for ArXiv"""

    #        result = {"confidence": 0.0}

    # Simple heuristic:
    #        if "PMID,Title,Authors,Citation,First Author,Journal/Book," in data:
    #            result["confidence"] = 1.0
    #            return result
    #        if "PMID- " in data:
    #            result["confidence"] = 0.7
    #            return result

    #        if "pmid " in data:
    #            if data.count(" pmid ") > data.count("\n@"):
    #                result["confidence"] = 1.0

    #       return result

    @classmethod
    def add_endpoint(
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        host = urlparse(query).hostname

        if host and host.endswith("arxiv.org"):
            query = query.replace("https://arxiv.org/find/all/1/all:", " ")

            filename = search_operation.get_unique_filename(
                file_path_string=f"arxiv_{query.replace('&sort=', '')}"
            )

            # http://export.arxiv.org/api/{method_name}?{parameters}
            query = "https://export.arxiv.org/api/query?search_query=all:" + query
            add_source = colrev.settings.SearchSource(
                endpoint="colrev.arxiv",
                filename=filename,
                search_type=colrev.settings.SearchType.DB,
                search_parameters={"query": query},
                load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
                comment="",
            )
            return add_source

        raise NotImplementedError

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
        )

        if source.filename.name != self.__arxiv_md_filename.name:
            if "query" not in source.search_parameters:
                raise colrev_exceptions.InvalidQueryException(
                    f"Source missing query search_parameter ({source.filename})"
                )

            # if "query_file" in source.search_parameters:
            # ...

        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )

    def check_availability(
        self, *, source_operation: colrev.operation.Operation
    ) -> None:
        """Check status (availability) of the ArXiv API"""

        try:
            # pylint: disable=duplicate-code
            test_rec = {
                "author": "Wang, R E and Demszky, D ",
                "title": "Is ChatGPT a Good Teacher Coach?"
                "Measuring Zero-Shot Performance For Scoring and Providing Actionable Insights on Classroom Instruction ",
                "ENTRYTYPE": "article",  # might not be needed in ArXiv
                "arxivid": "arXiv:2306.03090",
            }
            returned_record_dict = self.__arxiv_query_id(
                arxiv_id=test_rec["arxivid"],
                timeout=20,
            )

            if returned_record_dict:
                assert returned_record_dict["title"] == test_rec["title"]
                assert returned_record_dict["author"] == test_rec["author"]
            else:
                if not source_operation.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException("ArXiv")
        except (requests.exceptions.RequestException, IndexError) as exc:
            print(exc)
            if not source_operation.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException("ArXiv") from exc

    # RN
    @classmethod
    def feed_parsing(query):
        # Added to expose metadata in arXiv namespace
        # feedparser._FeedParserMixin.namespaces['http://a9.com/-/spec/opensearch/1.1/'] = 'opensearch'
        # feedparser._FeedParserMixin.namespaces['http://arxiv.org/schemas/atom'] = 'arxiv'

        # Get request
        response = urllib.urloben(query).read()

        feed = feedparser.parse(response)

        # Run through each entry, and print out information
        for entry in feed.entries:
            print("e-print metadata")
            print("arxiv-id: %s" % entry.id.split("/abs/")[-1])
            print("Published: %s" % entry.published)
            print("Title:  %s" % entry.title)

            # feedparser v4.1 only grabs the first author
            author_string = entry.author

            # grab the affiliation in <arxiv:affiliation> if present
            # - this will only grab the first affiliation encountered
            #   (the first affiliation for the first author)
            # Please email the list with a way to get all of this information!
            try:
                author_string += " (%s)" % entry.arxiv_affiliation
            except AttributeError:
                pass

            # feedparser v5.0.1 correctly handles multiple authors, print them all
            try:
                print(
                    "Authors:  %s" % ", ".join(author.name for author in entry.authors)
                )
            except AttributeError:
                pass

    # RN
    @classmethod
    def __get_author_string(query):
        author = ArXivSource.feed_parsing(query).author_string
        return author

    # RN
    @classmethod
    def __get_title_string(query):
        title = ArXivSource.feed_parsing(query).entry_title
        return title

    # @classmethod
    # def __get_author_string_from_node(cls, *, author_node: Element) -> str:
    #    authors_string = ""
    #    author_last_name_node = author_node.find("LastName")
    #    if author_last_name_node is not None:
    #        if author_last_name_node.text is not None:
    #            authors_string += author_last_name_node.text
    #    author_fore_name_node = author_node.find("ForeName")
    #    if author_fore_name_node is not None:
    #        if author_fore_name_node.text is not None:
    #            authors_string += ", "
    #            authors_string += author_fore_name_node.text
    #    return authors_string

    # @classmethod
    # def __get_author_string(cls, *, root) -> str:  # type: ignore
    #    authors_list = []
    #    for author_node in root.xpath(
    #        "/ArXivArticleSet/ArXivArticle/Citation/Article/AuthorList/Author"
    #    ):
    #        authors_list.append(
    #            cls.__get_author_string_from_node(author_node=author_node)
    #        )
    #    return " and ".join(authors_list)

    # @classmethod
    # def __get_title_string(cls, *, root) -> str:  # type: ignore
    #    title = root.xpath(
    #        "/ArXivArticleSet/ArXivArticle/Citation/Article/ArticleTitle"
    #    )
    #    if title:
    #        title = title[0].text.strip().rstrip(".")
    #    return title

    # @classmethod
    # def __get_abstract_string(cls, *, root) -> str:  # type: ignore
    #    abstract = root.xpath(
    #        "/ArXivArticleSet/ArXivArticle/Citation/Article/Abstract"
    #    )
    #    if abstract:
    #        return ElementTree.tostring(abstract[0], encoding="unicode")
    #    return ""

    @classmethod
    def __arxiv_xml_to_record(cls, *, root) -> dict:  # type: ignore
        retrieved_record_dict: dict = {"ENTRYTYPE": "misc"}

        arxiv_article = root.find("ArXivArticle")
        if arxiv_article is None:
            return {}
        if arxiv_article.find("Citation") is None:
            return {}

        retrieved_record_dict.update(title=cls.__get_title_string(root=root))
        retrieved_record_dict.update(author=cls.__get_author_string(root=root))

        journal_path = "/ArXivArticleSet/ArXivArticle/Citation/Article/Journal"  # Citation? reicht das als Ersatz?
        journal_name = root.xpath(journal_path + "/ISOAbbreviation")
        if journal_name:
            retrieved_record_dict.update(ENTRYTYPE="article")
            retrieved_record_dict.update(journal=journal_name[0].text)

        volume = root.xpath(journal_path + "/JournalIssue/Volume")
        if volume:
            retrieved_record_dict.update(volume=volume[0].text)

        number = root.xpath(journal_path + "/JournalIssue/Issue")
        if number:
            retrieved_record_dict.update(number=number[0].text)

        year = root.xpath(journal_path + "/JournalIssue/PubDate/Year")
        if year:
            retrieved_record_dict.update(year=year[0].text)

        retrieved_record_dict.update(volume=cls.__get_abstract_string(root=root))

        article_id_list = root.xpath(
            "/ArXivArticleSet/ArXivArticle/ArXivData/ArticleIdList"  # wie kammst du auf die Bennenung?
        )
        for article_id in article_id_list[0]:
            id_type = article_id.attrib.get("IdType")
            if article_id.attrib.get("IdType") == "arxiv":
                retrieved_record_dict.update(arxivid=article_id.text.upper())
            elif article_id.attrib.get("IdType") == "doi":
                retrieved_record_dict.update(doi=article_id.text.upper())
            else:
                retrieved_record_dict[id_type] = article_id.text

        retrieved_record_dict = {
            k: v for k, v in retrieved_record_dict.items() if v != ""
        }

        return retrieved_record_dict

    ## TODO
    def __get_arxiv_ids(self, query: str, retstart: int) -> typing.List[str]:
        headers = {"user-agent": f"{__name__} (mailto:{self.email})"}
        session = self.review_manager.get_cached_session()

        # added RN
        url = query + " "

        # change this to api call?
        # ret = session.request(
        #    "GET", query + f"&retstart={retstart}", headers=headers, timeout=30
        # )

        ret = urllib.urloben(url)

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

    def __arxiv_query_id(
        self,
        *,
        arxiv_id: str,
        timeout: int = 60,
    ) -> dict:
        """Retrieve records from ArXiv based on a query"""

        # Query using ID List prefix ?? - wo hast du das gefunden?
        try:
            prefix = "id_list"
            url = (
                "https://export.arxiv.org/api/query?search_query="
                + f"list={prefix}:&id={arxiv_id}"
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
                return {"arxiv_id": arxiv_id}

            root = fromstring(str.encode(ret.text))
            retrieved_record = self.__arxiv_xml_to_record(root=root)
            if not retrieved_record:
                return {"arxiv_id": arxiv_id}
        except requests.exceptions.RequestException:
            return {"arxiv_id": arxiv_id}
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
            retrieved_record_dict = self.__arxiv_query_id(
                arxiv_id=record.data["arxivid"],
                timeout=timeout,
            )

            retries = 0
            while (
                not retrieved_record_dict
                and retries < prep_operation.max_retries_on_error
            ):
                retries += 1

                retrieved_record_dict = self.__arxiv_query_id(
                    arxiv_id=record.data["arxivid"],
                    timeout=timeout,
                )

            if not retrieved_record_dict:
                raise colrev_exceptions.RecordNotFoundInPrepSourceException(
                    msg="ArXiv: no records retrieved"
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
                f"arxiv similarity: {similarity} "
                f"(<{prep_operation.retrieval_similarity})"
            )

            try:
                self.arxiv_lock.acquire(timeout=60)

                # Note : need to reload file because the object is not shared between processes
                arxiv_feed = self.search_source.get_feed(
                    review_manager=self.review_manager,
                    source_identifier=self.source_identifier,
                    update_only=False,
                )

                arxiv_feed.set_id(record_dict=retrieved_record.data)
                arxiv_feed.add_record(record=retrieved_record)

                record.merge(
                    merging_record=retrieved_record,
                    default_source=retrieved_record.data["colrev_origin"][0],
                )

                record.set_masterdata_complete(
                    source=retrieved_record.data["colrev_origin"][0],
                    masterdata_repository=self.review_manager.settings.is_curated_repo(),
                )
                record.set_status(target_state=colrev.record.RecordState.md_prepared)
                if save_feed:
                    arxiv_feed.save_feed_file()
                self.arxiv_lock.release()
                return record
            except (
                colrev_exceptions.InvalidMerge,
                colrev_exceptions.NotFeedIdentifiableException,
            ):
                self.arxiv_lock.release()
                return record

        except (
            requests.exceptions.RequestException,
            OSError,
            IndexError,
            colrev_exceptions.RecordNotFoundInPrepSourceException,
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
        """Retrieve masterdata fromArXiv based on similarity with the record provided"""

        if len(record.data.get("title", "")) < 35 and "arxivid" not in record.data:
            return record

        # remove the following if we match basd on similarity
        if "arxivid" not in record.data:
            return record

        record = self.__get_masterdata_record(
            prep_operation=prep_operation,
            record=record,
            timeout=timeout,
            save_feed=save_feed,
        )

        return record

    def __get_arxiv_query_return(self) -> typing.Iterator[dict]:
        params = self.search_source.search_parameters

        retstart = 0
        while True:
            arxiv_ids = self.__get_arxiv_ids(query=params["query"], retstart=retstart)
            if not arxiv_ids:
                break
            for arxiv_id in arxiv_ids:
                yield self.__arxiv_query_id(arxiv_id=arxiv_id)

            retstart += 20

    def __run_parameter_search(
        self,
        *,
        search_operation: colrev.ops.search.Search,
        arxiv_feed: colrev.ops.search.GeneralOriginFeed,
        rerun: bool,
    ) -> None:
        if rerun:
            search_operation.review_manager.logger.info(
                "Performing a search of the full history (may take time)"
            )

        records = search_operation.review_manager.dataset.load_records_dict()
        try:
            for record_dict in self.__get_arxiv_query_return():
                # Note : discard "empty" records
                if "" == record_dict.get("author", "") and "" == record_dict.get(
                    "title", ""
                ):
                    search_operation.review_manager.logger.warning(
                        f"Skipped record: {record_dict}"
                    )
                    continue
                try:
                    arxiv_feed.set_id(record_dict=record_dict)
                except colrev_exceptions.NotFeedIdentifiableException:
                    continue

                prev_record_dict_version = {}
                if record_dict["ID"] in arxiv_feed.feed_records:
                    prev_record_dict_version = deepcopy(
                        arxiv_feed.feed_records[record_dict["ID"]]
                    )

                prep_record = colrev.record.PrepRecord(data=record_dict)

                if "colrev_data_provenance" in prep_record.data:
                    del prep_record.data["colrev_data_provenance"]

                added = arxiv_feed.add_record(record=prep_record)

                if added:
                    search_operation.review_manager.logger.info(
                        " retrieve arxiv-id=" + prep_record.data["arxivid"]
                    )
                    arxiv_feed.nr_added += 1
                else:
                    changed = search_operation.update_existing_record(
                        records=records,
                        record_dict=prep_record.data,
                        prev_record_dict_version=prev_record_dict_version,
                        source=self.search_source,
                        update_time_variant_fields=rerun,
                    )
                    if changed:
                        arxiv_feed.nr_changed += 1

                # Note : only retrieve/update the latest deposits (unless in rerun mode)
                if not added and not rerun:
                    # problem: some publishers don't necessarily
                    # deposit papers chronologically
                    break

            arxiv_feed.print_post_run_search_infos(records=records)
            arxiv_feed.save_feed_file()
            search_operation.review_manager.dataset.save_records_dict(records=records)
            search_operation.review_manager.dataset.add_record_changes()

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

    def __run_md_search_update(
        self,
        *,
        search_operation: colrev.ops.search.Search,
        arxiv_feed: colrev.ops.search.GeneralOriginFeed,
    ) -> None:
        records = search_operation.review_manager.dataset.load_records_dict()

        for feed_record_dict in arxiv_feed.feed_records.values():
            feed_record = colrev.record.Record(data=feed_record_dict)

            try:
                retrieved_record = self.__arxiv_query_id(
                    arxiv_id=feed_record_dict["arxivid"]
                )

                if retrieved_record["arxivid"] != feed_record.data["arxivid"]:
                    continue

                arxiv_feed.set_id(record_dict=retrieved_record)
            except (
                colrev_exceptions.RecordNotFoundInPrepSourceException,
                colrev_exceptions.NotFeedIdentifiableException,
            ):
                continue

            prev_record_dict_version = {}
            if retrieved_record["ID"] in arxiv_feed.feed_records:
                prev_record_dict_version = arxiv_feed.feed_records[
                    retrieved_record["ID"]
                ]

            arxiv_feed.add_record(record=colrev.record.Record(data=retrieved_record))

            changed = search_operation.update_existing_record(
                records=records,
                record_dict=retrieved_record,
                prev_record_dict_version=prev_record_dict_version,
                source=self.search_source,
                update_time_variant_fields=True,
            )
            if changed:
                arxiv_feed.nr_changed += 1

        arxiv_feed.save_feed_file()
        arxiv_feed.print_post_run_search_infos(records=records)
        search_operation.review_manager.dataset.save_records_dict(records=records)
        search_operation.review_manager.dataset.add_record_changes()

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of ArXiv"""

        arxiv_feed = self.search_source.get_feed(
            review_manager=search_operation.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        if self.search_source.is_md_source() or self.search_source.is_quasi_md_source():
            self.__run_md_search_update(
                search_operation=search_operation,
                arxiv_feed=arxiv_feed,
            )

        else:
            self.__run_parameter_search(
                search_operation=search_operation,
                arxiv_feed=arxiv_feed,
                rerun=rerun,
            )

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for ArXiv"""

        for record in records.values():
            if "author" in record and record["author"].count(",") >= 1:
                author_list = record["author"].split(", ")
                for i, author_part in enumerate(author_list):
                    author_field_parts = author_part.split(" ")
                    author_list[i] = (
                        author_field_parts[0] + ", " + " ".join(author_field_parts[1:])
                    )

                record["author"] = " and ".join(author_list)
            if "first_author" in record:
                del record["first_author"]
            if "citation" in record:
                del record["citation"]
            if "create_date" in record:
                del record["create_date"]
            if record.get("journal", "") != "":
                record["ENTRYTYPE"] = "article"
            if record.get("pii", "pii").lower() == record.get("doi", "doi").lower():
                del record["pii"]

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for ArXiv"""

        if "first_author" in record.data:
            record.remove_field(key="first_author")
        if "journal/book" in record.data:
            record.rename_field(key="journal/book", new_key="journal")
        if record.data.get("author") == "UNKNOWN" and "authors" in record.data:
            record.remove_field(key="author")
            record.rename_field(key="authors", new_key="author")

        if record.data.get("year") == "UNKNOWN":
            record.remove_field(key="year")
            if "publication_year" in record.data:
                record.rename_field(key="publication_year", new_key="year")

        if "author" in record.data:
            record.data["author"] = colrev.record.PrepRecord.format_author_field(
                input_string=record.data["author"]
            )

        # TBD: how to distinguish other types?
        record.change_entrytype(new_entrytype="article", qm=self.quality_model)

        return record
