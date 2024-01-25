#! /usr/bin/env python
"""SearchSource: Crossref"""
from __future__ import annotations

import json
import re
import typing
import urllib
from copy import deepcopy
from curses.ascii import isalnum
from dataclasses import dataclass
from importlib.metadata import version
from multiprocessing import Lock
from pathlib import Path
from sqlite3 import OperationalError
from typing import Optional
from typing import TYPE_CHECKING

import inquirer
import requests
import zope.interface
from crossref.restful import Etiquette
from crossref.restful import Journals
from crossref.restful import Works
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from thefuzz import fuzz

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.search_sources.doi_org as doi_connector
import colrev.ops.built_in.search_sources.utils as connector_utils
import colrev.record
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import FieldValues

if TYPE_CHECKING:
    import colrev.ops.search
    import colrev.ops.prep

# pylint: disable=unused-argument
# pylint: disable=duplicate-code
# pylint: disable=too-many-lines

import typing
from copy import deepcopy
from dataclasses import dataclass
from multiprocessing import Lock
from pathlib import Path
from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from semanticscholar import SemanticScholar
from semanticscholar.PaginatedResults import PaginatedResults

import colrev.env.language_service
import colrev.env.package_manager
import colrev.env.environment_manager
import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.constants
from colrev.ops.built_in.search_sources.semanticscholarui import Semanticscholar_ui
import colrev.ops.built_in.search_sources.semanticscholar_utils as connector_utils
import colrev.record
import colrev.ops.load
import colrev.ops.load_utils_bib
import colrev.settings
from colrev.constants import Colors, Fields

# install zope package
# install package dacite

if TYPE_CHECKING:
    import colrev.ops.search
    import colrev.ops.prep


# pylint: disable=unused-argument
# pylint: disable=duplicate-code
# pylint: disable=too-many-lines


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class SemanticScholarSearchSource(JsonSchemaMixin):
    """Semantic Scholar API"""

    # Provide objects with classes
    __s2__: SemanticScholar
    __search_return__: PaginatedResults

    __limit = 100
    __offset = 0

    __api_url = "https://api.semanticscholar.org/graph/v1/paper/search?"

    endpoint = "colrev.semanticscholar"
    ci_supported: bool = True

    # SearchSourcePackageEndpointInterface constants
    docs_link = (
            "https://github.com/CoLRev-Environment/colrev/tree/main/"
            + "colrev/ops/built_in/search_sources/semanticscholar.md"
    )
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.oni
    search_types = [colrev.settings.SearchType.API]
    settings_class = colrev.env.package_manager.DefaultSourceSettings
    short_name = "S2"
    source_identifier = Fields.DOI

    SETTINGS = {
        "api_key": "packages.search_source.colrev.semanticscholar.api_key",
    }

    __availability_exception_message = f"Semantic Scholar ({Colors.ORANGE}check https://status.api.semanticscholar.org/{Colors.END})"

    __s2_UI__ = Semanticscholar_ui()
    __s2_filename = Path("data/search/md_semscholar.bib")

    def __init__(
            self,
            *,
            source_operation: colrev.operation.Operation,
            settings: typing.Optional[dict] = None,
    ) -> None:
        self.review_manager = source_operation.review_manager
        if settings:
            # Semantic Scholar as a search source
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )
        else:
            self.search_source = colrev.settings.SearchSource(
                endpoint="colrev.semanticscholar",
                filename=self.__s2_filename,
                search_type=colrev.settings.SearchType.API,
                search_parameters={},
                comment="",
            )
            self.s2_lock = Lock()

        self.language_service = colrev.env.language_service.LanguageService()
        __search_return__ = None

    @classmethod
    def get_etiquette(
            cls, *, review_manager: colrev.review_manager.ReviewManager
    ) -> Etiquette:
        """Get the etiquette for the crossref api"""
        _, email = review_manager.get_committer()
        return Etiquette(
            "CoLRev",
            version("colrev"),
            "https://github.com/CoLRev-Environment/colrev",
            email,
        )

    def check_availability(
            self, *, source_operation: colrev.operation.Operation
    ) -> None:
        """Check status (availability) of the Crossref API"""

        try:
            # pylint: disable=duplicate-code
            test_rec = {
                Fields.DOI: "10.17705/1cais.04607",
                Fields.AUTHOR: "Schryen, Guido and Wagner, Gerit and Benlian, Alexander "
                               "and Paré, Guy",
                Fields.TITLE: "A Knowledge Development Perspective on Literature Reviews: "
                              "Validation of a new Typology in the IS Field",
                Fields.ID: "SchryenEtAl2021",
                Fields.JOURNAL: "Communications of the Association for Information Systems",
                Fields.ENTRYTYPE: "article",
            }
            returned_record = self.crossref_query(
                record_input=colrev.record.PrepRecord(data=test_rec),
                jour_vol_iss_list=False,
                timeout=20,
            )[0]

            if 0 != len(returned_record.data):
                assert returned_record.data[Fields.TITLE] == test_rec[Fields.TITLE]
                assert returned_record.data[Fields.AUTHOR] == test_rec[Fields.AUTHOR]
            else:
                if not source_operation.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException(
                        self.__availability_exception_message
                    )
        except (requests.exceptions.RequestException, IndexError) as exc:
            print(exc)
            if not source_operation.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException(
                    self.__availability_exception_message
                ) from exc

    def __query(self, **kwargs) -> typing.Iterator[dict]:  # type: ignore
        """Get records from Crossref based on a bibliographic query"""

        works = Works(etiquette=self.etiquette)
        # use facets:
        # https://api.crossref.org/swagger-ui/index.html#/Works/get_works

        crossref_query_return = works.query(**kwargs).sort("deposited").order("desc")
        yield from crossref_query_return

    @classmethod
    def query_doi(cls, *, doi: str, etiquette: Etiquette) -> colrev.record.PrepRecord:
        """Get records from Crossref based on a doi query"""

        try:
            works = Works(etiquette=etiquette)
            crossref_query_return = works.doi(doi)
            if crossref_query_return is None:
                raise colrev_exceptions.RecordNotFoundInPrepSourceException(
                    msg="Record not found in crossref (based on doi)"
                )

            retrieved_record_dict = connector_utils.json_to_record(
                item=crossref_query_return
            )
            retrieved_record = colrev.record.PrepRecord(data=retrieved_record_dict)
            return retrieved_record

        except (requests.exceptions.RequestException,) as exc:
            raise colrev_exceptions.RecordNotFoundInPrepSourceException(
                msg="Record not found in crossref (based on doi)"
            ) from exc

    def __query_journal(self, *, rerun: bool) -> typing.Iterator[dict]:
        """Get records of a selected journal from Crossref"""

        journals = Journals(etiquette=self.etiquette)

        scope_filters = {}
        if (
                "scope" in self.search_source.search_parameters
                and "years" in self.search_source.search_parameters["scope"]
        ):
            year_from, year_to = self.search_source.search_parameters["scope"][
                "years"
            ].split("-")
            scope_filters["from-pub-date"] = year_from
            scope_filters["until-pub-date"] = year_to

        for issn in self.search_source.search_parameters["scope"][Fields.ISSN]:
            assert re.match(self.__ISSN_REGEX, issn)
            if rerun:
                # Note : the "deposited" field is not always provided.
                # only the general query will return all records.
                crossref_query_return = (
                    journals.works(issn).query().filter(**scope_filters)
                )
            else:
                crossref_query_return = (
                    journals.works(issn)
                    .query()
                    .filter(**scope_filters)
                    .sort("deposited")
                    .order("desc")
                )

            yield from crossref_query_return

    def __create_query_url(
            self, *, record: colrev.record.Record, jour_vol_iss_list: bool
    ) -> str:
        if jour_vol_iss_list:
            if not all(
                    x in record.data for x in [Fields.JOURNAL, Fields.VOLUME, Fields.NUMBER]
            ):
                raise colrev_exceptions.NotEnoughDataToIdentifyException
            params = {"rows": "50"}
            container_title = re.sub(r"[\W]+", " ", record.data[Fields.JOURNAL])
            params["query.container-title"] = container_title.replace("_", " ")

            query_field = ""
            if Fields.VOLUME in record.data:
                query_field = record.data[Fields.VOLUME]
            if Fields.NUMBER in record.data:
                query_field = query_field + "+" + record.data[Fields.NUMBER]
            params["query"] = query_field

        else:
            if Fields.TITLE not in record.data:
                raise colrev_exceptions.NotEnoughDataToIdentifyException()

            params = {"rows": "15"}
            if not isinstance(record.data.get(Fields.YEAR, ""), str) or not isinstance(
                    record.data.get(Fields.TITLE, ""), str
            ):
                print("year or title field not a string")
                print(record.data)
                raise AssertionError

            bibl = (
                    record.data[Fields.TITLE].replace("-", "_")
                    + " "
                    + record.data.get(Fields.YEAR, "")
            )
            bibl = re.sub(r"[\W]+", "", bibl.replace(" ", "_"))
            params["query.bibliographic"] = bibl.replace("_", " ")

            container_title = record.get_container_title()
            if "." not in container_title:
                container_title = container_title.replace(" ", "_")
                container_title = re.sub(r"[\W]+", "", container_title)
                params["query.container-title"] = container_title.replace("_", " ")

            author_last_names = [
                x.split(",")[0]
                for x in record.data.get(Fields.AUTHOR, "").split(" and ")
            ]
            author_string = " ".join(author_last_names)
            author_string = re.sub(r"[\W]+", "", author_string.replace(" ", "_"))
            params["query.author"] = author_string.replace("_", " ")

        url = self.__api_url + urllib.parse.urlencode(params)
        return url

    def __get_similarity(
            self, *, record: colrev.record.Record, retrieved_record_dict: dict
    ) -> float:
        title_similarity = fuzz.partial_ratio(
            retrieved_record_dict.get(Fields.TITLE, "NA").lower(),
            record.data.get(Fields.TITLE, "").lower(),
        )
        container_similarity = fuzz.partial_ratio(
            colrev.record.PrepRecord(data=retrieved_record_dict)
            .get_container_title()
            .lower(),
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

    def __prep_crossref_record(
            self,
            *,
            record: colrev.record.Record,
            prep_main_record: bool = True,
            crossref_source: str = "",
    ) -> None:
        if Fields.LANGUAGE in record.data:
            try:
                self.language_service.unify_to_iso_639_3_language_codes(record=record)
            except colrev_exceptions.InvalidLanguageCodeException:
                del record.data[Fields.LANGUAGE]

        doi_connector.DOIConnector.get_link_from_doi(
            review_manager=self.review_manager,
            record=record,
        )

        if (
                self.review_manager.settings.is_curated_masterdata_repo()
        ) and Fields.CITED_BY in record.data:
            del record.data[Fields.CITED_BY]

        if not prep_main_record:
            # Skip steps for feed records
            return

        if FieldValues.RETRACTED in record.data.get(
                "warning", ""
        ) or FieldValues.RETRACTED in record.data.get(Fields.PRESCREEN_EXCLUSION, ""):
            record.prescreen_exclude(reason=FieldValues.RETRACTED)
            record.remove_field(key="warning")
        else:
            assert "" != crossref_source
            record.set_masterdata_complete(
                source=crossref_source,
                masterdata_repository=self.review_manager.settings.is_curated_repo(),
            )
            record.set_status(target_state=colrev.record.RecordState.md_prepared)

    def __get_crossref_query_items(
            self, *, record: colrev.record.Record, jour_vol_iss_list: bool, timeout: int
    ) -> list:
        # Note : only returning a multiple-item list for jour_vol_iss_list
        try:
            url = self.__create_query_url(
                record=record, jour_vol_iss_list=jour_vol_iss_list
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
                return []

            data = json.loads(ret.text)

        # pylint: disable=duplicate-code
        except OperationalError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            ) from exc
        except (
                colrev_exceptions.NotEnoughDataToIdentifyException,
                json.decoder.JSONDecodeError,
                requests.exceptions.RequestException,
        ):
            return []

        return data["message"].get("items", [])

    def crossref_query(
            self,
            *,
            record_input: colrev.record.Record,
            jour_vol_iss_list: bool = False,
            timeout: int = 40,
    ) -> list:
        """Retrieve records from Crossref based on a query"""

        record = record_input.copy_prep_rec()
        record_list, most_similar, most_similar_record = [], 0.0, {}
        for item in self.__get_crossref_query_items(
                record=record, jour_vol_iss_list=jour_vol_iss_list, timeout=timeout
        ):
            try:
                retrieved_record_dict = connector_utils.json_to_record(item=item)
                similarity = self.__get_similarity(
                    record=record, retrieved_record_dict=retrieved_record_dict
                )
                retrieved_record = colrev.record.PrepRecord(data=retrieved_record_dict)

                # source = (
                #     f'https://api.crossref.org/works/{retrieved_record.data[Fields.DOI]}'
                # )
                # retrieved_record.add_provenance_all(source=source)

                # record.set_masterdata_complete(source=source)

                if jour_vol_iss_list:
                    record_list.append(retrieved_record)
                elif most_similar < similarity:
                    most_similar = similarity
                    most_similar_record = retrieved_record.get_data()
            except colrev_exceptions.RecordNotParsableException:
                pass

        if not jour_vol_iss_list:
            if most_similar_record:
                record_list = [colrev.record.PrepRecord(data=most_similar_record)]

        return record_list

    def __get_masterdata_record(
            self,
            prep_operation: colrev.ops.prep.Prep,
            record: colrev.record.Record,
            timeout: int,
            save_feed: bool,
    ) -> colrev.record.Record:
        try:
            if Fields.DOI in record.data:
                retrieved_record = self.query_doi(
                    doi=record.data[Fields.DOI], etiquette=self.etiquette
                )
            else:
                retrieved_records = self.crossref_query(
                    record_input=record,
                    jour_vol_iss_list=False,
                    timeout=timeout,
                )
                retrieved_record = retrieved_records.pop()

                retries = 0
                while (
                        not retrieved_record
                        and retries < prep_operation.max_retries_on_error
                ):
                    retries += 1

                    retrieved_records = self.crossref_query(
                        record_input=record,
                        jour_vol_iss_list=False,
                        timeout=timeout,
                    )
                    retrieved_record = retrieved_records.pop()

            if (
                    0 == len(retrieved_record.data)
                    or Fields.DOI not in retrieved_record.data
            ):
                raise colrev_exceptions.RecordNotFoundInPrepSourceException(
                    msg="Record not found in crossref"
                )

            similarity = colrev.record.PrepRecord.get_retrieval_similarity(
                record_original=record, retrieved_record_original=retrieved_record
            )
            # prep_operation.review_manager.logger.debug("Found matching record")
            # prep_operation.review_manager.logger.debug(
            #     f"crossref similarity: {similarity} "
            #     f"(>{prep_operation.retrieval_similarity})"
            # )
            self.review_manager.logger.debug(
                f"crossref similarity: {similarity} "
                f"(<{prep_operation.retrieval_similarity})"
            )
            if similarity < prep_operation.retrieval_similarity:
                return record

            try:
                self.crossref_lock.acquire(timeout=120)

                # Note : need to reload file because the object is not shared between processes
                crossref_feed = self.search_source.get_feed(
                    review_manager=self.review_manager,
                    source_identifier=self.source_identifier,
                    update_only=False,
                )

                crossref_feed.set_id(record_dict=retrieved_record.data)
                crossref_feed.add_record(record=retrieved_record)

                record.merge(
                    merging_record=retrieved_record,
                    default_source=retrieved_record.data[Fields.ORIGIN][0],
                )

                self.__prep_crossref_record(
                    record=record,
                    crossref_source=retrieved_record.data[Fields.ORIGIN][0],
                )

                if save_feed:
                    crossref_feed.save_feed_file()

            except (
                    colrev_exceptions.InvalidMerge,
                    colrev_exceptions.NotFeedIdentifiableException,
            ):
                pass
            finally:
                try:
                    self.crossref_lock.release()
                except ValueError:
                    pass

            return record

        except (
                requests.exceptions.RequestException,
                OSError,
                IndexError,
                colrev_exceptions.RecordNotFoundInPrepSourceException,
                colrev_exceptions.RecordNotParsableException,
        ) as exc:
            if prep_operation.review_manager.verbose_mode:
                print(exc)

        return record

    def __check_doi_masterdata(
            self, record: colrev.record.Record
    ) -> colrev.record.Record:
        try:
            retrieved_record = self.query_doi(
                doi=record.data[Fields.DOI], etiquette=self.etiquette
            )
            similarity = colrev.record.PrepRecord.get_retrieval_similarity(
                record_original=record,
                retrieved_record_original=retrieved_record,
                same_record_type_required=False,
            )
            if similarity < 0.7:
                # self.review_manager.logger.error(
                #     f" mismatching metadata (record/doi-record): {record.data['doi']} "
                #     + f"(similarity: {similarity})"
                # )
                record.remove_field(key=Fields.DOI)
                # record.print_citation_format()
                # retrieved_record.print_citation_format()

        except (
                requests.exceptions.RequestException,
                OSError,
                IndexError,
                colrev_exceptions.RecordNotFoundInPrepSourceException,
                colrev_exceptions.RecordNotParsableException,
        ):
            pass

        return record

    def __validate_api_params(self) -> None:
        source = self.search_source

        if not all(x in ["query", "scope"] for x in source.search_parameters):
            raise colrev_exceptions.InvalidQueryException(
                "Crossref search_parameters supports query or scope/issn field"
            )

        if "scope" in source.search_parameters:
            if Fields.ISSN in source.search_parameters["scope"]:
                assert isinstance(source.search_parameters["scope"][Fields.ISSN], list)
                for issn_field in source.search_parameters["scope"][Fields.ISSN]:
                    if not re.match(self.__ISSN_REGEX, issn_field):
                        raise colrev_exceptions.InvalidQueryException(
                            f"Crossref journal issn ({issn_field}) not matching required format"
                        )
            elif "years" in source.search_parameters["scope"]:
                years_field = source.search_parameters["scope"]["years"]
                if not re.match(self.__YEAR_SCOPE_REGEX, years_field):
                    raise colrev_exceptions.InvalidQueryException(
                        f"Scope (years) ({years_field}) not matching required format"
                    )
            else:
                raise colrev_exceptions.InvalidQueryException(
                    "Query missing valid parameters"
                )

        if "query" in source.search_parameters:
            # Note: not yet implemented/supported
            if " AND " in source.search_parameters["query"]:
                raise colrev_exceptions.InvalidQueryException(
                    "AND not supported in CROSSREF query"
                )

    def __validate_source(self) -> None:
        """Validate the SearchSource (parameters etc.)"""
        source = self.search_source
        self.review_manager.logger.debug(f"Validate SearchSource {source.filename}")

        if source.search_type not in self.search_types:
            raise colrev_exceptions.InvalidQueryException(
                f"Crossref search_type should be in {self.search_types}"
            )

        if source.search_type == colrev.settings.SearchType.API:
            self.__validate_api_params()

        self.review_manager.logger.debug(f"SearchSource {source.filename} validated")

    def __get_crossref_query_return(self, *, rerun: bool) -> typing.Iterator[dict]:
        params = self.search_source.search_parameters

        if "query" in params and "mode" not in params:
            crossref_query = {"bibliographic": params["query"].replace(" ", "+")}
            # potential extension : add the container_title:
            # crossref_query_return = works.query(
            #     container_title=
            #       "Journal of the Association for Information Systems"
            # )
            yield from self.__query(**crossref_query)
        elif "scope" in params and Fields.ISSN in params["scope"]:
            if Fields.ISSN in params["scope"]:
                yield from self.__query_journal(rerun=rerun)
            # raise NotImplemented

    def __restore_url(
            self,
            *,
            record: colrev.record.Record,
            feed: colrev.ops.search_feed.GeneralOriginFeed,
    ) -> None:
        """Restore the url from the feed if it exists
        (url-resolution is not always available)"""
        if record.data[Fields.ID] not in feed.feed_records:
            return
        prev_url = feed.feed_records[record.data[Fields.ID]].get(Fields.URL, None)
        if prev_url is None:
            return
        record.data[Fields.URL] = prev_url

    def __run_md_search(
            self,
            *,
            crossref_feed: colrev.ops.search_feed.GeneralOriginFeed,
            rerun: bool,
    ) -> None:
        records = self.review_manager.dataset.load_records_dict()

        for feed_record_dict in crossref_feed.feed_records.values():
            feed_record = colrev.record.Record(data=feed_record_dict)

            try:
                retrieved_record = self.query_doi(
                    doi=feed_record_dict[Fields.DOI], etiquette=self.etiquette
                )

                if retrieved_record.data[Fields.DOI] != feed_record.data[Fields.DOI]:
                    continue

                crossref_feed.set_id(record_dict=retrieved_record.data)
            except (
                    colrev_exceptions.RecordNotFoundInPrepSourceException,
                    colrev_exceptions.NotFeedIdentifiableException,
            ):
                continue

            self.__prep_crossref_record(record=retrieved_record, prep_main_record=False)

            prev_record_dict_version = {}
            if retrieved_record.data[Fields.ID] in crossref_feed.feed_records:
                prev_record_dict_version = crossref_feed.feed_records[
                    retrieved_record.data[Fields.ID]
                ]

            self.__restore_url(record=retrieved_record, feed=crossref_feed)
            crossref_feed.add_record(record=retrieved_record)

            crossref_feed.update_existing_record(
                records=records,
                record_dict=retrieved_record.data,
                prev_record_dict_version=prev_record_dict_version,
                source=self.search_source,
                update_time_variant_fields=rerun,
            )

        crossref_feed.print_post_run_search_infos(records=records)
        crossref_feed.save_feed_file()
        self.review_manager.dataset.save_records_dict(records=records)

    def __scope_excluded(self, *, retrieved_record_dict: dict) -> bool:
        if (
                "scope" not in self.search_source.search_parameters
                or "years" not in self.search_source.search_parameters["scope"]
        ):
            return False
        year_from, year_to = self.search_source.search_parameters["scope"][
            "years"
        ].split("-")
        if not retrieved_record_dict.get(Fields.YEAR, -1000).isdigit():
            return True
        if (
                int(year_from)
                < int(retrieved_record_dict.get(Fields.YEAR, -1000))
                < int(year_to)
        ):
            return False
        return True

    def __run_keyword_exploration_search(
            self,
            crossref_feed: colrev.ops.search_feed.GeneralOriginFeed,
    ) -> None:
        works = Works(etiquette=self.etiquette)

        def retrieve_exploratory_papers(keyword: str) -> typing.Iterator[dict]:
            crossref_query_return = works.query(bibliographic=keyword.replace(" ", "+"))
            yield from crossref_query_return

        records = self.review_manager.dataset.load_records_dict()
        available_dois = [x[Fields.DOI] for x in records.values() if Fields.DOI in x]

        covered_keywords = [
            x["explored_keyword"] for x in crossref_feed.feed_records.values()
        ]

        for keyword in self.search_source.search_parameters["query"].split(" OR "):
            self.review_manager.logger.info(f"Explore '{keyword}'")
            # Skip keywords that were already explored
            if keyword in covered_keywords:
                continue
            nr_added = 0
            for item in retrieve_exploratory_papers(keyword=keyword):
                try:
                    retrieved_record_dict = connector_utils.json_to_record(item=item)

                    # Skip papers that do not have the keyword in the title
                    if keyword not in retrieved_record_dict.get(
                            Fields.TITLE, ""
                    ).lower().replace("-", " "):
                        continue

                    # Skip papers that were already retrieved
                    if retrieved_record_dict[Fields.DOI] in available_dois:
                        continue
                    retrieved_record_dict["explored_keyword"] = keyword
                    crossref_feed.set_id(record_dict=retrieved_record_dict)
                    retrieved_record = colrev.record.Record(data=retrieved_record_dict)
                    self.__prep_crossref_record(
                        record=retrieved_record, prep_main_record=False
                    )

                    self.__restore_url(record=retrieved_record, feed=crossref_feed)

                    added = crossref_feed.add_record(record=retrieved_record)

                    if added:
                        nr_added += 1
                        self.review_manager.logger.info(
                            " retrieve " + retrieved_record.data[Fields.DOI]
                        )
                    if nr_added >= 10:
                        break

                except (
                        colrev_exceptions.RecordNotParsableException,
                        colrev_exceptions.NotFeedIdentifiableException,
                        KeyError  # error in crossref package:
                        # if len(result['message']['items']) == 0:
                        # KeyError: 'items'
                ):
                    pass
                if nr_added < 10:
                    self.review_manager.logger.info(
                        f"Only {nr_added} papers found to resample keyword '{keyword}'"
                    )

        crossref_feed.print_post_run_search_infos(records=records)

        crossref_feed.save_feed_file()
        self.review_manager.dataset.save_records_dict(records=records)

        self.review_manager.dataset.add_changes(path=self.search_source.filename)
        self.review_manager.create_commit(msg="Run search")

    def __potentially_overlapping_issn_search(self) -> bool:
        params = self.search_source.search_parameters
        if "scope" not in params:
            return False
        if Fields.ISSN not in params["scope"]:
            return False
        return len(params["scope"][Fields.ISSN]) > 1

    def keyword_search(self, *, params: dict, rerun: bool) -> PaginatedResults:
        query = None
        year = None
        publication_types = None
        venue = None
        fields_of_study = None
        open_access_pdf = None

        for key, value in params.items():
            if key == "query":
                query = value
            elif key == "year":
                year = value
            elif key == "publication_types":
                publication_types = value
            elif key == "venue":
                venue = value
            elif key == "fields_of_study":
                fields_of_study = value
            elif key == "open_access_pdf":
                open_access_pdf = value

        record_return = self.__s2__.search_paper(
            query=query,
            year=year,
            publication_types=publication_types,
            venue=venue,
            fields_of_study=fields_of_study,
            open_access_pdf=open_access_pdf,
        )

        self.review_manager.logger.info(
            str(record_return.total)
            + ' records have been found.'
        )

        return record_return

    def paper_search(self, *, params: dict, rerun: bool) -> PaginatedResults:
        for key, value in params.items():
            if key == "paper_ids":
                record_return = self.__s2__.get_papers(value)
            elif key == "query":
                record_return = self.__s2__.search_paper(value)
            else:
                self.review_manager.logger.info(
                    'Search type "Search for paper" is not available with your parameters.\n'
                    + "Search parameter: "
                    + value
                )
        return record_return

    def author_search(self, *, params: dict, rerun: bool) -> PaginatedResults:
        for key, value in params.items():
            if key == "author_ids":
                record_return = self.__s2__.get_authors(value)
            elif key == "queryList":
                record_return = self.__s2__.search_author(value)
            else:
                self.review_manager.logger.info(
                    '\nSearch type "Search for author" is not available with your parameters.\n'
                    + "Search parameter: "
                    + value
                )
        return record_return

    def __run_api_search(
            self,
            *,
            crossref_feed: colrev.ops.search_feed.GeneralOriginFeed,
            rerun: bool,
    ) -> None:
        if rerun:
            self.review_manager.logger.info(
                "Performing a search of the full history (may take time)"
            )

        if self.search_source.search_parameters.get("mode", "") == "resample_keywords":
            self.__run_keyword_exploration_search(crossref_feed=crossref_feed)
            return

        # could print statistics (retrieve 4/200) based on the crossref header (nr records)
        records = self.review_manager.dataset.load_records_dict()
        try:
            for item in self.__get_crossref_query_return(rerun=rerun):
                try:
                    retrieved_record_dict = connector_utils.json_to_record(item=item)
                    if self.__scope_excluded(
                            retrieved_record_dict=retrieved_record_dict
                    ):
                        continue

                    crossref_feed.set_id(record_dict=retrieved_record_dict)
                    prev_record_dict_version = {}
                    if retrieved_record_dict[Fields.ID] in crossref_feed.feed_records:
                        prev_record_dict_version = deepcopy(
                            crossref_feed.feed_records[retrieved_record_dict[Fields.ID]]
                        )

                    retrieved_record = colrev.record.Record(data=retrieved_record_dict)
                    self.__prep_crossref_record(
                        record=retrieved_record, prep_main_record=False
                    )

                    self.__restore_url(record=retrieved_record, feed=crossref_feed)

                    added = crossref_feed.add_record(record=retrieved_record)

                    if added:
                        self.review_manager.logger.info(
                            " retrieve " + retrieved_record.data[Fields.DOI]
                        )
                    else:
                        crossref_feed.update_existing_record(
                            records=records,
                            record_dict=retrieved_record.data,
                            prev_record_dict_version=prev_record_dict_version,
                            source=self.search_source,
                            update_time_variant_fields=rerun,
                        )

                    # Note : only retrieve/update the latest deposits (unless in rerun mode)
                    if (
                            not added
                            and not rerun
                            and not self.__potentially_overlapping_issn_search()
                    ):
                        # problem: some publishers don't necessarily
                        # deposit papers chronologically
                        self.review_manager.logger.debug("Break condition")
                        break
                except (
                        colrev_exceptions.RecordNotParsableException,
                        colrev_exceptions.NotFeedIdentifiableException,
                ):
                    pass
        except KeyError as exc:
            print(exc)
            # KeyError  # error in crossref package:
            # if len(result['message']['items']) == 0:
            # KeyError: 'items'

        crossref_feed.print_post_run_search_infos(records=records)

        crossref_feed.save_feed_file()
        self.review_manager.dataset.save_records_dict(records=records)

    def __get_api_key(self) -> str:
        api_key = self.review_manager.environment_manager.get_settings_by_key(
            self.SETTINGS["api_key"]
        )

        if api_key == "None" or api_key is None:
            api_key = self.__s2_UI__.get_api_key()
        else:
            api_key = self.__s2_UI__.get_api_key(api_key)

        self.review_manager.environment_manager.update_registry(
            self.SETTINGS["api_key"], api_key
        )

        return api_key

    def run_search(self, rerun: bool) -> None:
        """Run a search of Crossref"""

        # get the api key
        s2_api_key = self.__get_api_key()
        if s2_api_key:
            self.__s2__ = SemanticScholar(api_key=s2_api_key)
        else:
            self.__s2__ = SemanticScholar()

        # validate source

        # load file because the object is not shared between processes
        s2_feed = self.search_source.get_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        if rerun:
            self.review_manager.logger.info(
                "Performing a search of the full history (may take time)"
            )
        records = self.review_manager.dataset.load_records_dict()
        try:
            # get the search parameters from the user
            search_subject = self.__s2_UI__.searchSubject
            params = self.__s2_UI__.searchParams

            # Get Semantic Scholar API depending on the search subject and look for search parameters
            if search_subject == "keyword":
                __search_return__ = self.keyword_search(
                    params=params, rerun=rerun
                )
            elif search_subject == "paper":
                __search_return__ = self.paper_search(
                    params=params, rerun=rerun
                )
            elif search_subject == "author":
                __search_return__ = self.author_search(
                    params=params["params"], rerun=rerun
                )
            else:
                self.review_manager.logger.info(
                    "No search parameters were found."
                )
        except KeyError as exc:
            print(exc)
            # KeyError  # error in semanticscholar package:

        for item in __search_return__:
            try:
                retrieved_record_dict = connector_utils.s2_dict_to_record(
                    item=item
                )

                s2_feed.set_id(record_dict=retrieved_record_dict)
                prev_record_dict_version = {}
                if retrieved_record_dict[Fields.ID] in s2_feed.feed_records:
                    prev_record_dict_version = deepcopy(
                        s2_feed.feed_records[retrieved_record_dict[Fields.ID]]
                    )

                retrieved_record = colrev.record.Record(data=retrieved_record_dict)

                added = s2_feed.add_record(record=retrieved_record)

                if added:
                    self.review_manager.logger.info(
                        " retrieve " + retrieved_record.data[Fields.DOI]
                    )
                else:
                    s2_feed.update_existing_record(
                        records=records,
                        record_dict=retrieved_record.data,
                        prev_record_dict_version=prev_record_dict_version,
                        source=self.search_source,
                        update_time_variant_fields=rerun,
                    )

            except (
                    colrev_exceptions.RecordNotParsableException,
                    colrev_exceptions.NotFeedIdentifiableException,
            ):
                pass

        s2_feed.print_post_run_search_infos(records=records)
        s2_feed.save_feed_file()
        self.review_manager.dataset.save_records_dict(records=records)

    @classmethod
    def __add_toc_interactively(
            cls, *, operation: colrev.ops.search.Search
    ) -> colrev.settings.SearchSource:
        print("Get ISSN from https://portal.issn.org/issn/search")

        j_name = input("Enter journal name to lookup the ISSN:")
        journals = Journals()
        ret = journals.query(j_name)

        questions = [
            inquirer.List(
                Fields.JOURNAL,
                message="Select journal:",
                choices=[{x[Fields.TITLE]: x["ISSN"]} for x in ret],
            ),
        ]
        answers = inquirer.prompt(questions)
        issn = list(answers[Fields.JOURNAL].values())[0][0]

        filename = operation.get_unique_filename(
            file_path_string=f"crossref_issn_{issn}"
        )
        add_source = colrev.settings.SearchSource(
            endpoint="colrev.crossref",
            filename=filename,
            search_type=colrev.settings.SearchType.TOC,
            search_parameters={"scope": {Fields.ISSN: [issn]}},
            comment="",
        )
        return add_source

    @classmethod
    def add_endpoint(
            cls,
            operation: colrev.ops.search.Search,
            params: dict,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        # get search parameters from the user interface
        cls.__s2_UI__.main_ui()
        search_params = cls.__s2_UI__.searchParams

        filename = operation.get_unique_filename(
            file_path_string=f"semanticscholar_{search_params}",
        )

        add_source = colrev.settings.SearchSource(
            endpoint="colrev.semanticscholar",
            filename=filename,
            search_type=colrev.settings.SearchType.API,
            search_parameters=search_params,
            comment="",
        )
        return add_source

    # Aktuell noch von crossref - muss noch verändert werden
    def get_masterdata(
            self,
            prep_operation: colrev.ops.prep.Prep,
            record: colrev.record.Record,
            save_feed: bool = True,
            timeout: int = 30,
    ) -> colrev.record.Record:
        """Out of scope"""
        pass


    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Semantic Scholar"""
        result = {"confidence": 0.0}
        return result

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""
        if self.search_source.filename.suffix == ".bib":
            records = colrev.ops.load_utils_bib.load_bib_file(
                load_operation=load_operation, source=self.search_source
            )
            return records

    # Aktuell noch von crossref - muss noch verändert werden
    def prepare(
            self, record: colrev.record.PrepRecord, source: colrev.settings.SearchSource
    ) -> colrev.record.PrepRecord:
        """Source-specific preparation for Crossref"""
        pass

