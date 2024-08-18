#! /usr/bin/env python
"""SearchSource: Crossref"""
from __future__ import annotations

import datetime
import re
import typing
from dataclasses import dataclass
from multiprocessing import Lock
from pathlib import Path

import inquirer
import requests
import zope.interface
from crossref.restful import Journals
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.environment_manager
import colrev.env.language_service
import colrev.exceptions as colrev_exceptions
import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
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
from colrev.packages.crossref.src import crossref_api


if typing.TYPE_CHECKING:  # pragma: no cover
    import colrev.settings

# pylint: disable=unused-argument
# pylint: disable=duplicate-code
# pylint: disable=too-many-lines


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class CrossrefSearchSource(JsonSchemaMixin):
    """Crossref API"""

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    endpoint = "colrev.crossref"
    source_identifier = Fields.DOI

    search_types = [
        SearchType.API,
        SearchType.MD,
        SearchType.TOC,
    ]

    ci_supported: bool = True
    heuristic_status = SearchSourceHeuristicStatus.oni

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
        self.search_source = self._get_search_source(settings)
        self.crossref_lock = Lock()
        self.language_service = colrev.env.language_service.LanguageService()
        self.api = crossref_api.CrossrefAPI(params=self.search_source.search_parameters)

    def _get_search_source(
        self, settings: typing.Optional[dict]
    ) -> colrev.settings.SearchSource:
        if settings:
            # Crossref as a search_source
            return from_dict(data_class=self.settings_class, data=settings)

        # Crossref as an md-prep source
        crossref_md_source_l = [
            s
            for s in self.review_manager.settings.sources
            if s.filename == self._crossref_md_filename
        ]
        if crossref_md_source_l:
            return crossref_md_source_l[0]

        return colrev.settings.SearchSource(
            endpoint="colrev.crossref",
            filename=self._crossref_md_filename,
            search_type=SearchType.MD,
            search_parameters={},
            comment="",
        )

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

            returned_record = self.api.crossref_query(
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
                    if not re.match(self.api.ISSN_REGEX, issn_field):
                        raise colrev_exceptions.InvalidQueryException(
                            f"Crossref journal issn ({issn_field}) not matching required format"
                        )
            elif "years" in source.search_parameters["scope"]:
                years_field = source.search_parameters["scope"]["years"]
                if not re.match(self.api.YEAR_SCOPE_REGEX, years_field):
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
                retrieved_record = self.api.query_doi(doi=feed_record_dict[Fields.DOI])

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

    def _potentially_overlapping_issn_search(self) -> bool:
        params = self.search_source.search_parameters
        if "scope" not in params:
            return False
        if Fields.ISSN not in params["scope"]:
            return False
        return len(params["scope"][Fields.ISSN]) > 1

    def _run_api_search(
        self,
        *,
        crossref_feed: colrev.ops.search_api_feed.SearchAPIFeed,
        rerun: bool,
    ) -> None:

        self.api.rerun = rerun

        nrecs = self.api.get_len()
        self.review_manager.logger.info(f"Retrieve {nrecs} records")
        if rerun:
            estimated_time = nrecs * 0.5
            estimated_time_formatted = str(datetime.timedelta(seconds=estimated_time))
            self.review_manager.logger.info(
                f"Estimated time: {estimated_time_formatted}"
            )
        else:
            self.review_manager.logger.info(
                "Note: only retrieve/update the latest deposits (unless in rerun mode)"
            )

        try:
            for retrieved_record in self.api.get_records():
                try:
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
                except colrev_exceptions.NotFeedIdentifiableException:
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

    def _get_masterdata_record(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        timeout: int,
        save_feed: bool,
    ) -> colrev.record.record.Record:
        try:
            try:
                retrieved_record = self.api.query_doi(doi=record.data[Fields.DOI])
            except (colrev_exceptions.RecordNotFoundInPrepSourceException, KeyError):

                retrieved_records = self.api.crossref_query(
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

                    retrieved_records = self.api.crossref_query(
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
            retrieved_record = self.api.query_doi(doi=record.data[Fields.DOI])
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
