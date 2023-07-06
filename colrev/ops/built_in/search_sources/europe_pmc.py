#! /usr/bin/env python
"""SearchSource: Europe PMC"""
from __future__ import annotations

import json
import typing
from copy import deepcopy
from dataclasses import dataclass
from multiprocessing import Lock
from pathlib import Path
from sqlite3 import OperationalError
from typing import Optional
from urllib.parse import quote
from urllib.parse import urlparse
from xml.etree.ElementTree import Element  # nosec

import defusedxml
import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from defusedxml.ElementTree import fromstring
from thefuzz import fuzz

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.search
import colrev.record
import colrev.settings

# defuse std xml lib
defusedxml.defuse_stdlib()


# pylint: disable=duplicate-code
# pylint: disable=unused-argument


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class EuropePMCSearchSource(JsonSchemaMixin):
    """SearchSource for Europe PMC"""

    # settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "europe_pmc_id"
    search_type = colrev.settings.SearchType.DB
    api_search_supported = True
    ci_supported: bool = True
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "Europe PMC"
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/europe_pmc.md"
    )
    __europe_pmc_md_filename = Path("data/search/md_europe_pmc.bib")
    __SOURCE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/article/"
    __next_page_url: str = ""

    @dataclass
    class EuropePMCSearchSourceSettings(colrev.settings.SearchSource, JsonSchemaMixin):
        """Settings for EuropePMCSearchSource"""

        # pylint: disable=too-many-instance-attributes
        endpoint: str
        filename: Path
        search_type: colrev.settings.SearchType
        search_parameters: dict
        load_conversion_package_endpoint: dict
        comment: typing.Optional[str]

        _details = {
            "search_parameters": {
                "tooltip": "Currently supports a scope item "
                "with venue_key and journal_abbreviated fields."
            },
        }

    settings_class = EuropePMCSearchSourceSettings

    def __init__(
        self,
        *,
        source_operation: colrev.operation.Operation,
        settings: Optional[dict] = None,
    ) -> None:
        self.review_manager = source_operation.review_manager
        if settings:
            # EuropePMC as a search_source
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )
        else:
            # EuropePMC as an md-prep source
            europe_pmc_md_source_l = [
                s
                for s in source_operation.review_manager.settings.sources
                if s.filename == self.__europe_pmc_md_filename
            ]
            if europe_pmc_md_source_l:
                self.search_source = europe_pmc_md_source_l[0]
            else:
                self.search_source = colrev.settings.SearchSource(
                    endpoint="colrev.europe_pmc",
                    filename=self.__europe_pmc_md_filename,
                    search_type=colrev.settings.SearchType.OTHER,
                    search_parameters={},
                    load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
                    comment="",
                )

            self.europe_pmc_lock = Lock()

    # @classmethod
    # def check_status(cls, *, prep_operation: colrev.ops.prep.Prep) -> None:
    # ...

    @classmethod
    def __get_string_from_item(cls, *, item, key: str) -> str:  # type: ignore
        return_string = ""
        for selected_node in item.findall(key):
            return_string = selected_node.text
        return return_string

    @classmethod
    def __europe_pmc_xml_to_record(cls, *, item: Element) -> colrev.record.PrepRecord:
        retrieved_record_dict: dict = {"ENTRYTYPE": "article"}

        retrieved_record_dict.update(
            author=cls.__get_string_from_item(item=item, key="authorString")
        )
        retrieved_record_dict.update(
            journal=cls.__get_string_from_item(item=item, key="journalTitle")
        )
        retrieved_record_dict.update(
            doi=cls.__get_string_from_item(item=item, key="doi")
        )
        retrieved_record_dict.update(
            title=cls.__get_string_from_item(item=item, key="title")
        )
        retrieved_record_dict.update(
            title=cls.__get_string_from_item(item=item, key="title")
        )
        retrieved_record_dict.update(
            year=cls.__get_string_from_item(item=item, key="pubYear")
        )
        retrieved_record_dict.update(
            volume=cls.__get_string_from_item(item=item, key="journalVolume")
        )

        retrieved_record_dict.update(
            number=cls.__get_string_from_item(item=item, key="issue")
        )
        retrieved_record_dict.update(
            pmid=cls.__get_string_from_item(item=item, key="pmid")
        )
        retrieved_record_dict.update(
            epmc_source=cls.__get_string_from_item(item=item, key="source")
        )

        retrieved_record_dict.update(
            epmc_id=cls.__get_string_from_item(item=item, key="id")
        )

        retrieved_record_dict["europe_pmc_id"] = (
            retrieved_record_dict.get("epmc_source", "NO_SOURCE")
            + "/"
            + retrieved_record_dict.get("epmc_id", "NO_ID")
        )

        retrieved_record_dict["ID"] = retrieved_record_dict["europe_pmc_id"]
        retrieved_record_dict = {
            k: v
            for k, v in retrieved_record_dict.items()
            if k not in ["epmc_id", "epmc_source"] and v != ""
        }

        record = colrev.record.PrepRecord(data=retrieved_record_dict)

        # https://www.ebi.ac.uk/europepmc/webservices/rest/article/MED/23245604
        source = f"{cls.__SOURCE_URL}{record.data['europe_pmc_id']}"

        record.add_provenance_all(source=source)
        return record

    @classmethod
    def __get_similarity(
        cls,
        *,
        record: colrev.record.Record,
        retrieved_record: colrev.record.Record,
    ) -> float:
        title_similarity = fuzz.partial_ratio(
            retrieved_record.data["title"].lower(),
            record.data.get("title", "").lower(),
        )
        container_similarity = fuzz.partial_ratio(
            retrieved_record.get_container_title().lower(),
            record.get_container_title().lower(),
        )

        weights = [0.6, 0.4]
        similarities = [title_similarity, container_similarity]
        similarity = sum(similarities[g] * weights[g] for g in range(len(similarities)))
        return similarity

    def __get_europe_pmc_items(self, *, url: str, timeout: int) -> list:
        _, email = self.review_manager.get_committer()
        headers = {"user-agent": f"{__name__} (mailto:{email})"}
        session = self.review_manager.get_cached_session()
        self.review_manager.logger.debug(url)
        ret = session.request("GET", url, headers=headers, timeout=timeout)
        ret.raise_for_status()
        if ret.status_code != 200:
            return []

        root = fromstring(str.encode(ret.text))
        result_list = root.findall("resultList")[0]

        self.__next_page_url = "END"
        next_page_url_node = root.find("nextPageUrl")
        if next_page_url_node is not None:
            if next_page_url_node.text is not None:
                self.__next_page_url = next_page_url_node.text

        return result_list.findall("result")

    def __europe_pmc_query(
        self,
        *,
        record_input: colrev.record.Record,
        most_similar_only: bool = True,
        timeout: int = 60,
    ) -> list:
        """Retrieve records from Europe PMC based on a query"""

        try:
            record = record_input.copy_prep_rec()

            url = (
                "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query="
                + quote(record.data["title"])
            )

            record_list = []
            while True:
                result_list = self.__get_europe_pmc_items(url=url, timeout=timeout)
                most_similar, most_similar_record = 0.0, {}
                for result_item in result_list:
                    retrieved_record = self.__europe_pmc_xml_to_record(item=result_item)

                    if "title" not in retrieved_record.data:
                        continue

                    similarity = self.__get_similarity(
                        record=record, retrieved_record=retrieved_record
                    )

                    source = (
                        f"{self.__SOURCE_URL}{retrieved_record.data['europe_pmc_id']}"
                    )
                    retrieved_record.set_masterdata_complete(
                        source=source,
                        masterdata_repository=self.review_manager.settings.is_curated_repo(),
                    )

                    if not most_similar_only:
                        record_list.append(retrieved_record)

                    elif most_similar < similarity:
                        most_similar = similarity
                        most_similar_record = retrieved_record.get_data()

                url = "END"
                if not most_similar_only:
                    url = self.__next_page_url

                if url == "END":
                    break

        except (requests.exceptions.RequestException, json.decoder.JSONDecodeError):
            return []
        except OperationalError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            ) from exc

        if most_similar_only:
            record_list = [colrev.record.PrepRecord(data=most_similar_record)]

        return record_list

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,  # pylint: disable=unused-argument
    ) -> colrev.record.Record:
        """Retrieve masterdata from Europe PMC based on similarity with the record provided"""

        # pylint: disable=too-many-branches

        # https://www.ebi.ac.uk/europepmc/webservices/rest/article/MED/23245604

        try:
            if len(record.data.get("title", "")) > 35:
                retries = 0
                while retries < prep_operation.max_retries_on_error:
                    retries += 1

                    retrieved_records = self.__europe_pmc_query(
                        record_input=record,
                        timeout=timeout,
                    )
                    if retrieved_records:
                        retrieved_record = retrieved_records.pop()
                        break

                if not retrieved_records:
                    return record
                if 0 == len(retrieved_record.data):
                    return record

                similarity = colrev.record.PrepRecord.get_retrieval_similarity(
                    record_original=record, retrieved_record_original=retrieved_record
                )

                if similarity > prep_operation.retrieval_similarity:
                    self.europe_pmc_lock.acquire(timeout=60)

                    # Note : need to reload file because the object is not shared between processes
                    europe_pmc_feed = self.search_source.get_feed(
                        review_manager=prep_operation.review_manager,
                        source_identifier=self.source_identifier,
                        update_only=False,
                    )

                    try:
                        europe_pmc_feed.set_id(record_dict=retrieved_record.data)
                    except colrev_exceptions.NotFeedIdentifiableException:
                        return record

                    europe_pmc_feed.add_record(record=retrieved_record)

                    record.merge(
                        merging_record=retrieved_record,
                        default_source=retrieved_record.data["colrev_origin"][0],
                    )

                    record.set_masterdata_complete(
                        source=retrieved_record.data["colrev_origin"][0],
                        masterdata_repository=self.review_manager.settings.is_curated_repo(),
                    )
                    record.set_status(
                        target_state=colrev.record.RecordState.md_prepared
                    )

                    europe_pmc_feed.save_feed_file()
                    self.europe_pmc_lock.release()
                    return record

        except (requests.exceptions.RequestException, colrev_exceptions.InvalidMerge):
            self.europe_pmc_lock.release()

        return record

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
        )

        if "query" not in source.search_parameters:
            raise colrev_exceptions.InvalidQueryException(
                "Query required in search_parameters"
            )

        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of Europe PMC"""

        # https://europepmc.org/RestfulWebService

        search_operation.review_manager.logger.info(
            f"Retrieve Europe PMC: {self.search_source.search_parameters}"
        )

        europe_pmc_feed = self.search_source.get_feed(
            review_manager=search_operation.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        if self.search_source.is_md_source() or self.search_source.is_quasi_md_source():
            print("Not yet implemented")
            # self.__run_md_search_update(
            #     search_operation=search_operation,
            #     europe_pmc_feed=europe_pmc_feed,
            # )

        else:
            self.__run_parameter_search(
                search_operation=search_operation,
                europe_pmc_feed=europe_pmc_feed,
                rerun=rerun,
            )

    def __run_parameter_search(
        self,
        *,
        search_operation: colrev.ops.search.Search,
        europe_pmc_feed: colrev.ops.search.GeneralOriginFeed,
        rerun: bool,
    ) -> None:
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-nested-blocks

        try:
            params = self.search_source.search_parameters
            url = params["query"]

            _, email = self.review_manager.get_committer()

            headers = {"user-agent": f"{__name__} (mailto:{email})"}
            session = self.review_manager.get_cached_session()

            records = search_operation.review_manager.dataset.load_records_dict()

            while url != "END":
                self.review_manager.logger.debug(url)
                ret = session.request("GET", url, headers=headers, timeout=60)
                ret.raise_for_status()
                if ret.status_code != 200:
                    # review_manager.logger.debug(
                    #     f"europe_pmc failed with status {ret.status_code}"
                    # )
                    return

                root = fromstring(str.encode(ret.text))
                result_list = root.findall("resultList")[0]

                for result_item in result_list.findall("result"):
                    retrieved_record = self.__europe_pmc_xml_to_record(item=result_item)

                    prev_record_dict_version = {}
                    if retrieved_record.data["ID"] in europe_pmc_feed.feed_records:
                        prev_record_dict_version = deepcopy(
                            europe_pmc_feed.feed_records[retrieved_record.data["ID"]]
                        )
                    if "title" not in retrieved_record.data:
                        search_operation.review_manager.logger.warning(
                            f"Skipped record: {retrieved_record.data}"
                        )
                        continue

                    source = (
                        f"{self.__SOURCE_URL}{retrieved_record.data['europe_pmc_id']}"
                    )
                    retrieved_record.set_masterdata_complete(
                        source=source,
                        masterdata_repository=self.review_manager.settings.is_curated_repo(),
                    )

                    europe_pmc_feed.set_id(record_dict=retrieved_record.data)
                    added = europe_pmc_feed.add_record(record=retrieved_record)

                    if added:
                        search_operation.review_manager.logger.info(
                            " retrieve europe_pmc_id="
                            + retrieved_record.data["europe_pmc_id"]
                        )
                        europe_pmc_feed.nr_added += 1
                    else:
                        changed = search_operation.update_existing_record(
                            records=records,
                            record_dict=retrieved_record.data,
                            prev_record_dict_version=prev_record_dict_version,
                            source=self.search_source,
                            update_time_variant_fields=rerun,
                        )
                        if changed:
                            europe_pmc_feed.nr_changed += 1

                url = "END"
                next_page_url_node = root.find("nextPageUrl")
                if next_page_url_node is not None:
                    if next_page_url_node.text is not None:
                        url = next_page_url_node.text

            europe_pmc_feed.print_post_run_search_infos(records=records)
        except (requests.exceptions.RequestException, json.decoder.JSONDecodeError):
            pass
        except OperationalError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            ) from exc
        finally:
            europe_pmc_feed.save_feed_file()

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Europe PMC"""

        result = {"confidence": 0.0}
        if "europe_pmc_id" in data:
            result["confidence"] = 1.0

        if "https://europepmc.org" in data:  # nosec
            if data.count("https://europepmc.org") >= data.count("\n@"):
                result["confidence"] = 1.0

        return result

    @classmethod
    def add_endpoint(
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        host = urlparse(query).hostname

        if host and host.endswith("europepmc.org"):
            query = query.replace("https://europepmc.org/search?query=", "")

            filename = search_operation.get_unique_filename(
                file_path_string="europepmc"
            )
            query = (
                "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=" + query
            )
            add_source = colrev.settings.SearchSource(
                endpoint="colrev.europe_pmc",
                filename=filename,
                search_type=colrev.settings.SearchType.DB,
                search_parameters={"query": query},
                load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
                comment="",
            )
            return add_source

        raise NotImplementedError

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for Europe PMC"""

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for Europe PMC"""
        record.data["author"].rstrip(".")
        record.data["title"].rstrip(".")
        return record
