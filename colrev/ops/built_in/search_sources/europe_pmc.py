#! /usr/bin/env python
"""SearchSource: Europe PMC"""
from __future__ import annotations

import json
import typing
from dataclasses import dataclass
from multiprocessing import Lock
from pathlib import Path
from sqlite3 import OperationalError
from typing import Optional
from urllib.parse import quote
from xml.etree.ElementTree import Element

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
# pylint: disable=duplicate-code


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

    @dataclass
    class EuropePMCSearchSourceSettings(colrev.settings.SearchSource, JsonSchemaMixin):
        """Settings for EuropePMCSearchSource"""

        # pylint: disable=duplicate-code
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
    def __europe_pmc_xml_to_record(cls, *, item: Element) -> colrev.record.PrepRecord:
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-statements

        retrieved_record_dict: dict = {"ENTRYTYPE": "misc"}

        author_node = item.find("authorString")
        if author_node is not None:
            if author_node.text is not None:
                authors_string = colrev.record.PrepRecord.format_author_field(
                    input_string=author_node.text
                )
                retrieved_record_dict.update(author=authors_string)

        journal_node = item.find("journalTitle")
        if journal_node is not None:
            if journal_node.text is not None:
                retrieved_record_dict.update(journal=journal_node.text)
                retrieved_record_dict.update(ENTRYTYPE="article")

        doi_node = item.find("doi")
        if doi_node is not None:
            if doi_node.text is not None:
                retrieved_record_dict.update(doi=doi_node.text)

        title_node = item.find("title")
        if title_node is not None:
            if title_node.text is not None:
                retrieved_record_dict.update(title=title_node.text)

        year_node = item.find("pubYear")
        if year_node is not None:
            if year_node.text is not None:
                retrieved_record_dict.update(year=year_node.text)

        volume_node = item.find("journalVolume")
        if volume_node is not None:
            if volume_node.text is not None:
                retrieved_record_dict.update(volume=volume_node.text)

        number_node = item.find("issue")
        if number_node is not None:
            if number_node.text is not None:
                retrieved_record_dict.update(number=number_node.text)

        pmid_node = item.find("pmid")
        if pmid_node is not None:
            if pmid_node.text is not None:
                retrieved_record_dict.update(pmid=pmid_node.text)

        source_node = item.find("source")
        if source_node is not None:
            if source_node.text is not None:
                retrieved_record_dict.update(epmc_source=source_node.text)

        epmc_id_node = item.find("id")
        if epmc_id_node is not None:
            if epmc_id_node.text is not None:
                retrieved_record_dict.update(epmc_id=epmc_id_node.text)

        retrieved_record_dict["europe_pmc_id"] = (
            retrieved_record_dict.get("epmc_source", "NO_SOURCE")
            + "/"
            + retrieved_record_dict.get("epmc_id", "NO_ID")
        )
        retrieved_record_dict["ID"] = retrieved_record_dict["europe_pmc_id"]
        del retrieved_record_dict["epmc_id"]
        del retrieved_record_dict["epmc_source"]

        record = colrev.record.PrepRecord(data=retrieved_record_dict)

        # https://www.ebi.ac.uk/europepmc/webservices/rest/article/MED/23245604
        source = (
            "https://www.ebi.ac.uk/europepmc/webservices/rest/article/"
            f"{record.data['europe_pmc_id']}"
        )

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
        # logger.debug(f'record: {pp.pformat(record)}')
        # logger.debug(f'similarities: {similarities}')
        # logger.debug(f'similarity: {similarity}')
        # pp.pprint(retrieved_record_dict)
        return similarity

    @classmethod
    def europe_pcmc_query(
        cls,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        record_input: colrev.record.Record,
        most_similar_only: bool = True,
        timeout: int = 60,
    ) -> list:
        """Retrieve records from Europe PMC based on a query"""

        # pylint: disable=too-many-branches
        # pylint: disable=too-many-statements
        # pylint: disable=too-many-locals

        try:
            record = record_input.copy_prep_rec()

            url = (
                "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query="
                + quote(record.data["title"])
            )
            _, email = review_manager.get_committer()

            headers = {"user-agent": f"{__name__} (mailto:{email})"}
            record_list = []
            session = review_manager.get_cached_session()

            while url != "END":
                review_manager.logger.debug(url)
                ret = session.request("GET", url, headers=headers, timeout=timeout)
                ret.raise_for_status()
                if ret.status_code != 200:
                    # review_manager.logger.debug(
                    #     f"europe_pmc failed with status {ret.status_code}"
                    # )
                    return []

                most_similar, most_similar_record = 0.0, {}
                root = fromstring(str.encode(ret.text))
                result_list = root.findall("resultList")[0]

                for result_item in result_list.findall("result"):
                    retrieved_record = cls.__europe_pmc_xml_to_record(item=result_item)

                    if "title" not in retrieved_record.data:
                        continue

                    similarity = cls.__get_similarity(
                        record=record, retrieved_record=retrieved_record
                    )

                    source = (
                        "https://www.ebi.ac.uk/europepmc/webservices/rest/article/"
                        f"{retrieved_record.data['europe_pmc_id']}"
                    )
                    retrieved_record.set_masterdata_complete(source=source)

                    if not most_similar_only:
                        record_list.append(retrieved_record)

                    elif most_similar < similarity:
                        most_similar = similarity
                        most_similar_record = retrieved_record.get_data()

                url = "END"
                if not most_similar_only:
                    next_page_url_node = root.find("nextPageUrl")
                    if next_page_url_node is not None:
                        if next_page_url_node.text is not None:
                            url = next_page_url_node.text

        except json.decoder.JSONDecodeError:
            pass
        except requests.exceptions.RequestException:
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

                    retrieved_records = self.europe_pcmc_query(
                        review_manager=prep_operation.review_manager,
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
                    # prep_operation.review_manager.logger.debug("Found matching record")
                    # prep_operation.review_manager.logger.debug(
                    #     f"europe_pmc similarity: {similarity} "
                    #     f"(>{prep_operation.retrieval_similarity})"
                    # )

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
                        source=retrieved_record.data["colrev_origin"][0]
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

        try:
            for retrieved_record in self.europe_pcmc_query(
                review_manager=search_operation.review_manager,
                record_input=colrev.record.Record(
                    data={"title": self.search_source.search_parameters["query"]}
                ),
                most_similar_only=False,
            ):
                if "colrev_data_provenance" in retrieved_record.data:
                    del retrieved_record.data["colrev_data_provenance"]
                if "colrev_masterdata_provenance" in retrieved_record.data:
                    del retrieved_record.data["colrev_masterdata_provenance"]

                europe_pmc_feed.set_id(record_dict=retrieved_record.data)
                europe_pmc_feed.add_record(record=retrieved_record)

            europe_pmc_feed.save_feed_file()

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
        """Source heuristic for Europe PMC"""

        result = {"confidence": 0.0}
        if "europe_pmc_id" in data:
            result["confidence"] = 1.0

        return result

    @classmethod
    def add_endpoint(
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> typing.Optional[colrev.settings.SearchSource]:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        return None

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


if __name__ == "__main__":
    pass
