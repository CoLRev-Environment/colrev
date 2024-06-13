#! /usr/bin/env python
"""SearchSource: Crossref"""
from __future__ import annotations

import json
import re
import typing
import urllib
from dataclasses import dataclass
from importlib.metadata import version
from multiprocessing import Lock
from pathlib import Path
from sqlite3 import OperationalError

import inquirer
import requests
import zope.interface
from crossref.restful import Etiquette
from crossref.restful import Journals
from crossref.restful import Works
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from rapidfuzz import fuzz

import colrev.env.environment_manager
import colrev.env.language_service
import colrev.exceptions as colrev_exceptions
import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.packages.crossref.src.utils as connector_utils
import colrev.packages.doi_org.src.doi_org as doi_connector
import colrev.record.record
import colrev.record.record_prep
import colrev.record.record_similarity
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import RecordState
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType

if typing.TYPE_CHECKING:  # pragma: no cover
    import colrev.settings

# pylint: disable=unused-argument
# pylint: disable=duplicate-code
# pylint: disable=too-many-lines


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class CrossrefSearchSource(JsonSchemaMixin):
    """Crossref API"""

    _ISSN_REGEX = r"^\d{4}-?\d{3}[\dxX]$"
    _YEAR_SCOPE_REGEX = r"^\d{4}-\d{4}$"

    # https://github.com/CrossRef/rest-api-doc
    _api_url = "https://api.crossref.org/works?"

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    endpoint = "colrev.crossref"
    source_identifier = Fields.DOI
    # "https://api.crossref.org/works/{{doi}}"
    search_types = [
        SearchType.API,
        SearchType.MD,
        SearchType.TOC,
    ]

    ci_supported: bool = True
    heuristic_status = SearchSourceHeuristicStatus.oni
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/packages/search_sources/crossref.md"
    )
    short_name = "Crossref"
    _crossref_md_filename = Path("data/search/md_crossref.bib")

    _availability_exception_message = (
        f"Crossref ({Colors.ORANGE}check https://status.crossref.org/{Colors.END})"
    )

    def __init__(
        self,
        *,
        source_operation: colrev.process.operation.Operation,
        settings: typing.Optional[dict] = None,
    ) -> None:
        self.review_manager = source_operation.review_manager
        if settings:
            # Crossref as a search_source
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )
        else:
            # Crossref as an md-prep source
            crossref_md_source_l = [
                s
                for s in self.review_manager.settings.sources
                if s.filename == self._crossref_md_filename
            ]
            if crossref_md_source_l:
                self.search_source = crossref_md_source_l[0]
            else:
                self.search_source = colrev.settings.SearchSource(
                    endpoint="colrev.crossref",
                    filename=self._crossref_md_filename,
                    search_type=SearchType.MD,
                    search_parameters={},
                    comment="",
                )

            self.crossref_lock = Lock()

        self.language_service = colrev.env.language_service.LanguageService()

        self.etiquette = self.get_etiquette()
        self.email = self.review_manager.get_committer()

    @classmethod
    def get_etiquette(cls) -> Etiquette:
        """Get the etiquette for the crossref api"""
        _, email = (
            colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git()
        )
        return Etiquette(
            "CoLRev",
            version("colrev"),
            "https://github.com/CoLRev-Environment/colrev",
            email,
        )

    def check_availability(
        self, *, source_operation: colrev.process.operation.Operation
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
                record_input=colrev.record.record_prep.PrepRecord(test_rec),
                jour_vol_iss_list=False,
                timeout=20,
            )[0]

            if 0 != len(returned_record.data):
                assert returned_record.data[Fields.TITLE] == test_rec[Fields.TITLE]
                assert returned_record.data[Fields.AUTHOR] == test_rec[Fields.AUTHOR]
            else:
                if not self.review_manager.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException(
                        self._availability_exception_message
                    )
        except (requests.exceptions.RequestException, IndexError) as exc:
            print(exc)
            if not self.review_manager.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException(
                    self._availability_exception_message
                ) from exc

    def _query(self, **kwargs) -> typing.Iterator[dict]:  # type: ignore
        """Get records from Crossref based on a bibliographic query"""

        works = Works(etiquette=self.etiquette)
        # use facets:
        # https://api.crossref.org/swagger-ui/index.html#/Works/get_works

        crossref_query_return = works.query(**kwargs).sort("deposited").order("desc")
        yield from crossref_query_return

    @classmethod
    def query_doi(
        cls, *, doi: str, etiquette: Etiquette
    ) -> colrev.record.record_prep.PrepRecord:
        """Get records from Crossref based on a doi query"""

        try:
            works = Works(etiquette=etiquette)
            crossref_query_return = works.doi(doi)
            if crossref_query_return is None:
                raise colrev_exceptions.RecordNotFoundInPrepSourceException(
                    msg="Record not found in crossref (based on doi)"
                )

            retrieved_record = connector_utils.json_to_record(
                item=crossref_query_return
            )
            return retrieved_record

        except (requests.exceptions.RequestException,) as exc:
            raise colrev_exceptions.RecordNotFoundInPrepSourceException(
                msg="Record not found in crossref (based on doi)"
            ) from exc

    def _query_journal(self, *, rerun: bool) -> typing.Iterator[dict]:
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
            assert re.match(self._ISSN_REGEX, issn)
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

    def _create_query_url(
        self, *, record: colrev.record.record.Record, jour_vol_iss_list: bool
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

        url = self._api_url + urllib.parse.urlencode(params)
        return url

    def _get_similarity(
        self, *, record: colrev.record.record.Record, retrieved_record_dict: dict
    ) -> float:
        title_similarity = fuzz.partial_ratio(
            retrieved_record_dict.get(Fields.TITLE, "NA").lower(),
            record.data.get(Fields.TITLE, "").lower(),
        )
        container_similarity = fuzz.partial_ratio(
            colrev.record.record_prep.PrepRecord(retrieved_record_dict)
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

    def _prep_crossref_record(
        self,
        *,
        record: colrev.record.record.Record,
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
            record.set_status(RecordState.md_prepared)

    def _get_crossref_query_items(
        self,
        *,
        record: colrev.record.record.Record,
        jour_vol_iss_list: bool,
        timeout: int,
    ) -> list:
        # Note : only returning a multiple-item list for jour_vol_iss_list
        try:
            url = self._create_query_url(
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
        record_input: colrev.record.record.Record,
        jour_vol_iss_list: bool = False,
        timeout: int = 40,
    ) -> list:
        """Retrieve records from Crossref based on a query"""

        record = record_input.copy_prep_rec()
        record_list, most_similar, most_similar_record = [], 0.0, {}
        for item in self._get_crossref_query_items(
            record=record, jour_vol_iss_list=jour_vol_iss_list, timeout=timeout
        ):
            try:
                retrieved_record = connector_utils.json_to_record(item=item)
                similarity = self._get_similarity(
                    record=record, retrieved_record_dict=retrieved_record.data
                )

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
                record_list = [
                    colrev.record.record_prep.PrepRecord(most_similar_record)
                ]

        return record_list

    def _get_masterdata_record(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        timeout: int,
        save_feed: bool,
    ) -> colrev.record.record.Record:
        try:
            try:
                retrieved_record = self.query_doi(
                    doi=record.data[Fields.DOI], etiquette=self.etiquette
                )
            except (colrev_exceptions.RecordNotFoundInPrepSourceException, KeyError):

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

            # if (
            #     0 == len(retrieved_record.data)
            #     or Fields.DOI not in retrieved_record.data
            # ):
            #     raise colrev_exceptions.RecordNotFoundInPrepSourceException(
            #         msg="Record not found in crossref"
            #     )

            if not colrev.record.record_similarity.matches(record, retrieved_record):
                return record

            try:
                self.crossref_lock.acquire(timeout=120)

                # Note : need to reload file because the object is not shared between processes
                crossref_feed = self.search_source.get_api_feed(
                    review_manager=self.review_manager,
                    source_identifier=self.source_identifier,
                    update_only=False,
                    prep_mode=True,
                )

                crossref_feed.add_update_record(retrieved_record)

                record.merge(
                    retrieved_record,
                    default_source=retrieved_record.data[Fields.ORIGIN][0],
                )

                self._prep_crossref_record(
                    record=record,
                    crossref_source=retrieved_record.data[Fields.ORIGIN][0],
                )

                if save_feed:
                    crossref_feed.save()

            except colrev_exceptions.NotFeedIdentifiableException:
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

    def _check_doi_masterdata(
        self, record: colrev.record.record.Record
    ) -> colrev.record.record.Record:
        try:
            retrieved_record = self.query_doi(
                doi=record.data[Fields.DOI], etiquette=self.etiquette
            )
            if not colrev.record.record_similarity.matches(record, retrieved_record):
                record.remove_field(key=Fields.DOI)

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
        timeout: int = 30,
    ) -> colrev.record.record.Record:
        """Retrieve masterdata from Crossref based on similarity with the record provided"""

        # To test the metadata provided for a particular DOI use:
        # https://api.crossref.org/works/DOI
        if len(record.data.get(Fields.TITLE, "")) < 5 and Fields.DOI not in record.data:
            return record

        if Fields.DOI in record.data:
            record = self._check_doi_masterdata(record=record)

        record = self._get_masterdata_record(
            prep_operation=prep_operation,
            record=record,
            timeout=timeout,
            save_feed=save_feed,
        )

        return record

    def _validate_api_params(self) -> None:
        source = self.search_source

        if not all(x in ["query", "scope"] for x in source.search_parameters):
            raise colrev_exceptions.InvalidQueryException(
                "Crossref search_parameters supports query or scope/issn field"
            )

        if "scope" in source.search_parameters:
            if Fields.ISSN in source.search_parameters["scope"]:
                assert isinstance(source.search_parameters["scope"][Fields.ISSN], list)
                for issn_field in source.search_parameters["scope"][Fields.ISSN]:
                    if not re.match(self._ISSN_REGEX, issn_field):
                        raise colrev_exceptions.InvalidQueryException(
                            f"Crossref journal issn ({issn_field}) not matching required format"
                        )
            elif "years" in source.search_parameters["scope"]:
                years_field = source.search_parameters["scope"]["years"]
                if not re.match(self._YEAR_SCOPE_REGEX, years_field):
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

    def _validate_source(self) -> None:
        """Validate the SearchSource (parameters etc.)"""
        source = self.search_source
        self.review_manager.logger.debug(f"Validate SearchSource {source.filename}")

        if source.search_type not in self.search_types:
            raise colrev_exceptions.InvalidQueryException(
                f"Crossref search_type should be in {self.search_types}"
            )

        if source.search_type == SearchType.API:
            self._validate_api_params()

        self.review_manager.logger.debug(f"SearchSource {source.filename} validated")

    def _get_crossref_query_return(self, *, rerun: bool) -> typing.Iterator[dict]:
        params = self.search_source.search_parameters

        if "query" in params and "mode" not in params:
            crossref_query = {"bibliographic": params["query"].replace(" ", "+")}
            # potential extension : add the container_title:
            # crossref_query_return = works.query(
            #     container_title=
            #       "Journal of the Association for Information Systems"
            # )
            yield from self._query(**crossref_query)
        elif "scope" in params and Fields.ISSN in params["scope"]:
            if Fields.ISSN in params["scope"]:
                yield from self._query_journal(rerun=rerun)
            # raise NotImplemented

    def _restore_url(
        self,
        *,
        record: colrev.record.record.Record,
        feed: colrev.ops.search_api_feed.SearchAPIFeed,
    ) -> None:
        """Restore the url from the feed if it exists
        (url-resolution is not always available)"""
        prev_record = feed.get_prev_feed_record(record)
        prev_url = prev_record.data.get(Fields.URL, None)
        if prev_url is None:
            return
        record.data[Fields.URL] = prev_url

    def _run_md_search(
        self,
        *,
        crossref_feed: colrev.ops.search_api_feed.SearchAPIFeed,
    ) -> None:

        for feed_record_dict in crossref_feed.feed_records.values():
            try:
                feed_record = colrev.record.record.Record(feed_record_dict)
                retrieved_record = self.query_doi(
                    doi=feed_record_dict[Fields.DOI], etiquette=self.etiquette
                )

                if retrieved_record.data[Fields.DOI] != feed_record.data[Fields.DOI]:
                    continue

                self._prep_crossref_record(
                    record=retrieved_record, prep_main_record=False
                )

                self._restore_url(record=retrieved_record, feed=crossref_feed)
                crossref_feed.add_update_record(retrieved_record)

            except (
                colrev_exceptions.RecordNotFoundInPrepSourceException,
                colrev_exceptions.NotFeedIdentifiableException,
            ):
                continue

        crossref_feed.save()

    def _scope_excluded(self, *, retrieved_record_dict: dict) -> bool:
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

    def _run_keyword_exploration_search(
        self,
        crossref_feed: colrev.ops.search_api_feed.SearchAPIFeed,
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
                    retrieved_record = connector_utils.json_to_record(item=item)

                    # Skip papers that do not have the keyword in the title
                    if keyword not in retrieved_record.data.get(
                        Fields.TITLE, ""
                    ).lower().replace("-", " "):
                        continue

                    # Skip papers that were already retrieved
                    if retrieved_record.data[Fields.DOI] in available_dois:
                        continue
                    retrieved_record.data["explored_keyword"] = keyword
                    self._prep_crossref_record(
                        record=retrieved_record, prep_main_record=False
                    )

                    self._restore_url(record=retrieved_record, feed=crossref_feed)

                    added = crossref_feed.add_update_record(
                        retrieved_record=retrieved_record
                    )

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
                    KeyError,  # error in crossref package:
                    # if len(result['message']['items']) == 0:
                    # KeyError: 'items'
                ):
                    pass
                if nr_added < 10:
                    self.review_manager.logger.info(
                        f"Only {nr_added} papers found to resample keyword '{keyword}'"
                    )

        crossref_feed.save()

        self.review_manager.dataset.add_changes(self.search_source.filename)
        self.review_manager.dataset.create_commit(msg="Run search")

    def _potentially_overlapping_issn_search(self) -> bool:
        params = self.search_source.search_parameters
        if "scope" not in params:
            return False
        if Fields.ISSN not in params["scope"]:
            return False
        return len(params["scope"][Fields.ISSN]) > 1

    def _get_len(self, query: str) -> int:
        works = Works(etiquette=self.etiquette)
        return works.query(**{"bibliographic": query}).count()

    def _run_api_search(
        self,
        *,
        crossref_feed: colrev.ops.search_api_feed.SearchAPIFeed,
        rerun: bool,
    ) -> None:
        if rerun:
            self.review_manager.logger.info(
                "Performing a search of the full history (may take time)"
            )

        if self.search_source.search_parameters.get("mode", "") == "resample_keywords":
            self._run_keyword_exploration_search(crossref_feed=crossref_feed)
            return

        if "query" in self.search_source.search_parameters:
            # Note: we may warn users when creating large queries and print (1/300) progress
            n_recs = self._get_len(self.search_source.search_parameters["query"])
            self.review_manager.logger.info(f"Retrieve {n_recs} records overall")
        try:
            for item in self._get_crossref_query_return(rerun=rerun):
                try:
                    retrieved_record = connector_utils.json_to_record(item=item)
                    if self._scope_excluded(
                        retrieved_record_dict=retrieved_record.data
                    ):
                        continue

                    self._prep_crossref_record(
                        record=retrieved_record, prep_main_record=False
                    )

                    self._restore_url(record=retrieved_record, feed=crossref_feed)

                    added = crossref_feed.add_update_record(
                        retrieved_record=retrieved_record
                    )

                    # Note : only retrieve/update the latest deposits (unless in rerun mode)
                    if (
                        not added
                        and not rerun
                        and not self._potentially_overlapping_issn_search()
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
        except RuntimeError as exc:
            print(exc)

        crossref_feed.save()

    def search(self, rerun: bool) -> None:
        """Run a search of Crossref"""

        self._validate_source()

        crossref_feed = self.search_source.get_api_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        try:
            if self.search_source.search_type in [
                SearchType.API,
                SearchType.TOC,
            ]:
                self._run_api_search(
                    crossref_feed=crossref_feed,
                    rerun=rerun,
                )
            elif self.search_source.search_type == SearchType.MD:
                self._run_md_search(
                    crossref_feed=crossref_feed,
                )
            else:
                raise NotImplementedError

        except requests.exceptions.RequestException as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                self._availability_exception_message
            ) from exc

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Crossref"""

        result = {"confidence": 0.0}

        return result

    @classmethod
    def _parse_params(cls, params: str) -> dict:
        params_dict = {}
        if params:
            if params.startswith("http"):
                params_dict = {Fields.URL: params}
            else:
                for item in params.split(";"):
                    key, value = item.split("=")
                    params_dict[key] = value

        if "issn" in params_dict:
            params_dict["scope"] = {Fields.ISSN: [params_dict["issn"]]}  # type: ignore
            del params_dict["issn"]
        return params_dict

    @classmethod
    def _select_search_type(
        cls, operation: colrev.ops.search.Search, params_dict: dict
    ) -> SearchType:
        if list(params_dict) == ["scope"]:
            search_type = SearchType.TOC
        elif "query" in params_dict:
            search_type = SearchType.API
        elif Fields.URL in params_dict:
            search_type = SearchType.API
        else:
            search_type = operation.select_search_type(
                search_types=cls.search_types, params=params_dict
            )

        return search_type

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: str,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint"""

        params_dict = cls._parse_params(params)

        search_type = cls._select_search_type(operation, params_dict)

        if search_type == SearchType.API:
            if len(params_dict) == 0:
                search_source = operation.create_api_source(endpoint=cls.endpoint)
            else:
                if Fields.URL in params_dict:
                    query = {
                        "query": (
                            params_dict[Fields.URL]
                            .replace("https://search.crossref.org/?q=", "")
                            .replace("&from_ui=yes", "")
                            .lstrip("+")
                        )
                    }
                else:
                    query = params_dict

                filename = operation.get_unique_filename(file_path_string="crossref")
                search_source = colrev.settings.SearchSource(
                    endpoint="colrev.crossref",
                    filename=filename,
                    search_type=SearchType.API,
                    search_parameters=query,
                    comment="",
                )

        elif search_type == SearchType.TOC:
            if len(params_dict) == 0:
                search_source = cls._add_toc_interactively(operation=operation)
            else:
                filename = operation.get_unique_filename(file_path_string="crossref")
                search_source = colrev.settings.SearchSource(
                    endpoint="colrev.crossref",
                    filename=filename,
                    search_type=SearchType.TOC,
                    search_parameters=params_dict,
                    comment="",
                )

        else:
            raise NotImplementedError

        operation.add_source_and_search(search_source)
        return search_source

    @classmethod
    def _add_toc_interactively(
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
            search_type=SearchType.TOC,
            search_parameters={"scope": {Fields.ISSN: [issn]}},
            comment="",
        )
        return add_source

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=self.search_source.filename,
                logger=self.review_manager.logger,
                unique_id_field="ID",
            )
            return records

        raise NotImplementedError

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        source: colrev.settings.SearchSource,
    ) -> colrev.record.record_prep.PrepRecord:
        """Source-specific preparation for Crossref"""
        source_item = [
            x
            for x in record.data[Fields.ORIGIN]
            if str(source.filename).replace("data/search/", "") in x
        ]
        if source_item:
            record.set_masterdata_complete(
                source=source_item[0],
                masterdata_repository=self.review_manager.settings.is_curated_repo(),
            )
        return record
