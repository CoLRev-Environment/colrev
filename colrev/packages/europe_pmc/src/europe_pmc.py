#! /usr/bin/env python
"""SearchSource: Europe PMC"""
from __future__ import annotations

import json
import typing
from dataclasses import dataclass
from multiprocessing import Lock
from pathlib import Path
from sqlite3 import OperationalError
from urllib.parse import quote
from urllib.parse import urlparse
from xml.etree.ElementTree import Element  # nosec

import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from lxml import etree
from rapidfuzz import fuzz

import colrev.exceptions as colrev_exceptions
import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record
import colrev.record.record_prep
import colrev.record.record_similarity
import colrev.settings
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import RecordState
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType

# pylint: disable=duplicate-code
# pylint: disable=unused-argument


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class EuropePMCSearchSource(JsonSchemaMixin):
    """Europe PMC"""

    # settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    source_identifier = Fields.EUROPE_PMC_ID
    search_types = [
        SearchType.API,
        SearchType.DB,
        SearchType.MD,
    ]
    endpoint = "colrev.europe_pmc"

    ci_supported: bool = True
    heuristic_status = SearchSourceHeuristicStatus.supported
    short_name = "Europe PMC"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/packages/search_sources/europe_pmc.md"
    )
    _europe_pmc_md_filename = Path("data/search/md_europe_pmc.bib")
    _SOURCE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/article/"
    _next_page_url: str = ""

    @dataclass
    class EuropePMCSearchSourceSettings(colrev.settings.SearchSource, JsonSchemaMixin):
        """Settings for EuropePMCSearchSource"""

        # pylint: disable=too-many-instance-attributes
        endpoint: str
        filename: Path
        search_type: SearchType
        search_parameters: dict
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
        source_operation: colrev.process.operation.Operation,
        settings: typing.Optional[dict] = None,
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
                if s.filename == self._europe_pmc_md_filename
            ]
            if europe_pmc_md_source_l:
                self.search_source = europe_pmc_md_source_l[0]
            else:
                self.search_source = colrev.settings.SearchSource(
                    endpoint=self.endpoint,
                    filename=self._europe_pmc_md_filename,
                    search_type=SearchType.MD,
                    search_parameters={},
                    comment="",
                )

            self.europe_pmc_lock = Lock()
        self.source_operation = source_operation

    # @classmethod
    # def check_status(cls, *, prep_operation: colrev.ops.prep.Prep) -> None:
    # ...

    @classmethod
    def _get_string_from_item(cls, *, item, key: str) -> str:  # type: ignore
        return_string = ""
        for selected_node in item.findall(key):
            return_string = selected_node.text
        return return_string

    # pylint: disable=colrev-missed-constant-usage
    @classmethod
    def _europe_pmc_xml_to_record(
        cls, *, item: Element
    ) -> colrev.record.record_prep.PrepRecord:
        retrieved_record_dict: dict = {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE}
        retrieved_record_dict[Fields.AUTHOR] = cls._get_string_from_item(
            item=item, key="authorString"
        )
        retrieved_record_dict[Fields.JOURNAL] = cls._get_string_from_item(
            item=item, key="journalTitle"
        )
        retrieved_record_dict[Fields.DOI] = cls._get_string_from_item(
            item=item, key="doi"
        )
        retrieved_record_dict[Fields.TITLE] = cls._get_string_from_item(
            item=item, key="title"
        )
        retrieved_record_dict[Fields.YEAR] = cls._get_string_from_item(
            item=item, key="pubYear"
        )
        retrieved_record_dict[Fields.VOLUME] = cls._get_string_from_item(
            item=item, key="journalVolume"
        )
        retrieved_record_dict[Fields.NUMBER] = cls._get_string_from_item(
            item=item, key="issue"
        )
        retrieved_record_dict[Fields.PUBMED_ID] = cls._get_string_from_item(
            item=item, key="pmid"
        )
        retrieved_record_dict[Fields.PMCID] = cls._get_string_from_item(
            item=item, key="pmcid"
        )

        retrieved_record_dict["epmc_source"] = cls._get_string_from_item(
            item=item, key="source"
        )
        retrieved_record_dict["epmc_id"] = cls._get_string_from_item(
            item=item, key="id"
        )
        retrieved_record_dict[Fields.EUROPE_PMC_ID] = (
            retrieved_record_dict.get("epmc_source", "NO_SOURCE")
            + "/"
            + retrieved_record_dict.get("epmc_id", "NO_ID")
        )
        retrieved_record_dict[Fields.ID] = retrieved_record_dict[Fields.EUROPE_PMC_ID]

        retrieved_record_dict = {
            k: v
            for k, v in retrieved_record_dict.items()
            if k not in ["epmc_id", "epmc_source"] and v != ""
        }

        record = colrev.record.record_prep.PrepRecord(retrieved_record_dict)
        return record

    @classmethod
    def _get_similarity(
        cls,
        *,
        record: colrev.record.record.Record,
        retrieved_record: colrev.record.record.Record,
    ) -> float:
        title_similarity = fuzz.partial_ratio(
            retrieved_record.data[Fields.TITLE].lower(),
            record.data.get(Fields.TITLE, "").lower(),
        )
        container_similarity = fuzz.partial_ratio(
            retrieved_record.get_container_title().lower(),
            record.get_container_title().lower(),
        )

        weights = [0.6, 0.4]
        similarities = [title_similarity, container_similarity]
        similarity = sum(similarities[g] * weights[g] for g in range(len(similarities)))
        return similarity

    def _get_europe_pmc_items(self, *, url: str, timeout: int) -> list:
        _, email = self.review_manager.get_committer()
        headers = {"user-agent": f"{__name__} (mailto:{email})"}
        session = self.review_manager.get_cached_session()
        self.review_manager.logger.debug(url)
        ret = session.request("GET", url, headers=headers, timeout=timeout)
        ret.raise_for_status()
        if ret.status_code != 200:
            return []

        root = etree.fromstring(str.encode(ret.text))
        result_list = root.findall("resultList")[0]

        self._next_page_url = "END"
        next_page_url_node = root.find("nextPageUrl")
        if next_page_url_node is not None:
            if next_page_url_node.text is not None:
                self._next_page_url = next_page_url_node.text

        return result_list.findall("result")

    def _europe_pmc_query(
        self,
        *,
        record_input: colrev.record.record.Record,
        most_similar_only: bool = True,
        timeout: int = 60,
    ) -> list:
        """Retrieve records from Europe PMC based on a query"""

        try:
            record = record_input.copy_prep_rec()

            url = (
                "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query="
                + quote(record.data[Fields.TITLE])
            )

            record_list = []
            while True:
                result_list = self._get_europe_pmc_items(url=url, timeout=timeout)
                most_similar, most_similar_record = 0.0, {}
                for result_item in result_list:
                    retrieved_record = self._europe_pmc_xml_to_record(item=result_item)

                    if Fields.TITLE not in retrieved_record.data:
                        continue

                    similarity = self._get_similarity(
                        record=record, retrieved_record=retrieved_record
                    )

                    source = f"{self._SOURCE_URL}{retrieved_record.data[Fields.EUROPE_PMC_ID]}"
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
                    url = self._next_page_url

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
            record_list = [colrev.record.record_prep.PrepRecord(most_similar_record)]

        return record_list

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,  # pylint: disable=unused-argument
    ) -> colrev.record.record.Record:
        """Retrieve masterdata from Europe PMC based on similarity with the record provided"""

        # pylint: disable=too-many-branches

        # https://www.ebi.ac.uk/europepmc/webservices/rest/article/MED/23245604

        try:
            if len(record.data.get(Fields.TITLE, "")) > 35:
                retries = 0
                while retries < prep_operation.max_retries_on_error:
                    retries += 1

                    retrieved_records = self._europe_pmc_query(
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

                if not colrev.record.record_similarity.matches(
                    record, retrieved_record
                ):
                    return record

                self.europe_pmc_lock.acquire(timeout=60)

                # Note : need to reload file because the object is not shared between processes
                europe_pmc_feed = self.search_source.get_api_feed(
                    review_manager=prep_operation.review_manager,
                    source_identifier=self.source_identifier,
                    update_only=False,
                    prep_mode=True,
                )
                try:
                    europe_pmc_feed.add_update_record(retrieved_record=retrieved_record)
                except colrev_exceptions.NotFeedIdentifiableException:
                    return record

                record.merge(
                    retrieved_record,
                    default_source=retrieved_record.data[Fields.ORIGIN][0],
                )

                record.set_masterdata_complete(
                    source=retrieved_record.data[Fields.ORIGIN][0],
                    masterdata_repository=self.review_manager.settings.is_curated_repo(),
                )
                record.set_status(RecordState.md_prepared)

                europe_pmc_feed.save()
                self.europe_pmc_lock.release()
                return record

        except requests.exceptions.RequestException:
            self.europe_pmc_lock.release()

        return record

    def _validate_source(self) -> None:
        """Validate the SearchSource (parameters etc.)"""

        source = self.search_source

        self.review_manager.logger.debug(f"Validate SearchSource {source.filename}")

        assert source.search_type in self.search_types

        if "query" not in source.search_parameters:
            raise colrev_exceptions.InvalidQueryException(
                "Query required in search_parameters"
            )

        self.review_manager.logger.debug(f"SearchSource {source.filename} validated")

    def search(self, rerun: bool) -> None:
        """Run a search of Europe PMC"""

        self._validate_source()
        # https://europepmc.org/RestfulWebService

        europe_pmc_feed = self.search_source.get_api_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        if self.search_source.search_type == SearchType.API:
            self._run_api_search(
                europe_pmc_feed=europe_pmc_feed,
                rerun=rerun,
            )

        elif self.search_source.search_type == SearchType.DB:
            self.source_operation.run_db_search(  # type: ignore
                search_source_cls=self.__class__,
                source=self.search_source,
            )

        # if self.search_source.search_type == colrev.settings.SearchSource.MD:
        # self._run_md_search_update(
        #     search_operation=search_operation,
        #     europe_pmc_feed=europe_pmc_feed,
        # )

        else:
            raise NotImplementedError

    def _run_api_search(
        self,
        *,
        europe_pmc_feed: colrev.ops.search_api_feed.SearchAPIFeed,
        rerun: bool,
    ) -> None:
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-nested-blocks

        try:
            params = self.search_source.search_parameters
            url = (
                "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query="
                + params["query"]
            )

            _, email = self.review_manager.get_committer()

            headers = {"user-agent": f"{__name__} (mailto:{email})"}
            session = self.review_manager.get_cached_session()

            while url != "END":
                self.review_manager.logger.debug(url)
                ret = session.request("GET", url, headers=headers, timeout=60)
                ret.raise_for_status()
                if ret.status_code != 200:
                    # review_manager.logger.debug(
                    #     f"europe_pmc failed with status {ret.status_code}"
                    # )
                    return

                root = etree.fromstring(str.encode(ret.text))
                result_list = root.findall("resultList")[0]

                for result_item in result_list.findall("result"):
                    retrieved_record = self._europe_pmc_xml_to_record(item=result_item)

                    if Fields.TITLE not in retrieved_record.data:
                        self.review_manager.logger.warning(
                            f"Skipped record: {retrieved_record.data}"
                        )
                        continue

                    source = f"{self._SOURCE_URL}{retrieved_record.data[Fields.EUROPE_PMC_ID]}"
                    retrieved_record.set_masterdata_complete(
                        source=source,
                        masterdata_repository=self.review_manager.settings.is_curated_repo(),
                    )

                    europe_pmc_feed.add_update_record(retrieved_record)

                url = "END"
                next_page_url_node = root.find("nextPageUrl")
                if next_page_url_node is not None:
                    if next_page_url_node.text is not None:
                        url = next_page_url_node.text

        except (requests.exceptions.RequestException, json.decoder.JSONDecodeError):
            pass
        except OperationalError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            ) from exc
        finally:
            europe_pmc_feed.save()

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Europe PMC"""

        result = {"confidence": 0.0}
        # pylint: disable=colrev-missed-constant-usage
        if "europe_pmc_id" in data:
            result["confidence"] = 1.0

        if "https://europepmc.org" in data:  # nosec
            if data.count("https://europepmc.org") >= data.count("\n@"):
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

        if len(params_dict) == 0:
            search_source = operation.create_api_source(endpoint=cls.endpoint)

        # pylint: disable=colrev-missed-constant-usage
        elif "url" in params_dict:
            host = urlparse(params_dict["url"]).hostname

            if host and host.endswith("europepmc.org"):
                query = params_dict["url"].replace(
                    "https://europepmc.org/search?query=", ""
                )
                filename = operation.get_unique_filename(file_path_string="europepmc")
                search_source = colrev.settings.SearchSource(
                    endpoint=cls.endpoint,
                    filename=filename,
                    search_type=SearchType.API,
                    search_parameters={"query": query},
                    comment="",
                )
        else:
            raise NotImplementedError

        operation.add_source_and_search(search_source)
        return search_source

    def _load_bib(self) -> dict:
        def field_mapper(record_dict: dict) -> None:
            for key in list(record_dict.keys()):
                if key not in ["ID", "ENTRYTYPE"]:
                    record_dict[key.lower()] = record_dict.pop(key)

        records = colrev.loader.load_utils.load(
            filename=self.search_source.filename,
            logger=self.review_manager.logger,
            unique_id_field="ID",
            field_mapper=field_mapper,
        )
        return records

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".bib":
            return self._load_bib()

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.record.Record:
        """Source-specific preparation for Europe PMC"""
        record.data[Fields.AUTHOR].rstrip(".")
        record.data[Fields.TITLE].rstrip(".")
        return record
