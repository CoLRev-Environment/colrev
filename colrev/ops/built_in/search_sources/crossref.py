#! /usr/bin/env python
"""SearchSource: Crossref"""
from __future__ import annotations

import json
import re
import typing
import urllib
from copy import deepcopy
from dataclasses import dataclass
from importlib.metadata import version
from multiprocessing import Lock
from pathlib import Path
from sqlite3 import OperationalError
from typing import Optional

import requests
import timeout_decorator
import zope.interface
from crossref.restful import Etiquette
from crossref.restful import Journals
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from thefuzz import fuzz

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.search_sources.doi_org as doi_connector
import colrev.ops.built_in.search_sources.utils as connector_utils
import colrev.record
import colrev.ui_cli.cli_colors as colors

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.search
        import colrev.ops.prep

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class CrossrefSearchSource(JsonSchemaMixin):
    """SearchSource for the Crossref API"""

    __issn_regex = r"^\d{4}-?\d{3}[\dxX]$"

    # https://github.com/CrossRef/rest-api-doc
    __api_url = "https://api.crossref.org/works?"

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "doi"
    # "https://api.crossref.org/works/{{doi}}"
    search_type = colrev.settings.SearchType.DB
    api_search_supported = True
    ci_supported: bool = True
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.oni
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/crossref.md"
    )
    short_name = "Crossref"
    __crossref_md_filename = Path("data/search/md_crossref.bib")

    def __init__(
        self,
        *,
        source_operation: colrev.operation.Operation,
        settings: Optional[dict] = None,
    ) -> None:
        if settings:
            # Crossref as a search_source
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )
        else:
            # Crossref as an md-prep source
            crossref_md_source_l = [
                s
                for s in source_operation.review_manager.settings.sources
                if s.filename == self.__crossref_md_filename
            ]
            if crossref_md_source_l:
                self.search_source = crossref_md_source_l[0]
            else:
                self.search_source = colrev.settings.SearchSource(
                    endpoint="colrev.crossref",
                    filename=self.__crossref_md_filename,
                    search_type=colrev.settings.SearchType.OTHER,
                    search_parameters={},
                    load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
                    comment="",
                )

            self.crossref_lock = Lock()

        self.language_service = colrev.env.language_service.LanguageService()

        _, self.email = source_operation.review_manager.get_committer()

        self.etiquette = Etiquette(
            "CoLRev",
            version("colrev"),
            "https://github.com/CoLRev-Environment/colrev",
            self.email,
        )
        self.review_manager = source_operation.review_manager

    def check_availability(
        self, *, source_operation: colrev.operation.Operation
    ) -> None:
        """Check status (availability) of the Crossref API"""

        try:
            # pylint: disable=duplicate-code
            test_rec = {
                "doi": "10.17705/1cais.04607",
                "author": "Schryen, Guido and Wagner, Gerit and Benlian, Alexander "
                "and Paré, Guy",
                "title": "A Knowledge Development Perspective on Literature Reviews: "
                "Validation of a new Typology in the IS Field",
                "ID": "SchryenEtAl2021",
                "journal": "Communications of the Association for Information Systems",
                "ENTRYTYPE": "article",
            }
            returned_record = self.crossref_query(
                review_manager=source_operation.review_manager,
                record_input=colrev.record.PrepRecord(data=test_rec),
                jour_vol_iss_list=False,
                timeout=20,
            )[0]

            if 0 != len(returned_record.data):
                assert returned_record.data["title"] == test_rec["title"]
                assert returned_record.data["author"] == test_rec["author"]
            else:
                if not source_operation.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException("CROSSREF")
        except (requests.exceptions.RequestException, IndexError) as exc:
            print(exc)
            if not source_operation.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException(
                    "CROSSREF"
                ) from exc

    @timeout_decorator.timeout(800, use_signals=False)
    def __query(self, **kwargs) -> typing.Iterator[dict]:  # type: ignore
        """Get records from Crossref based on a bibliographic query"""

        # pylint: disable=import-outside-toplevel
        from crossref.restful import Works

        works = Works(etiquette=self.etiquette)
        # use facets:
        # https://api.crossref.org/swagger-ui/index.html#/Works/get_works

        crossref_query_return = works.query(**kwargs).sort("deposited").order("desc")
        for item in crossref_query_return:
            yield connector_utils.json_to_record(item=item)

    @timeout_decorator.timeout(40, use_signals=False)
    def query_doi(self, *, doi: str) -> colrev.record.PrepRecord:
        """Get records from Crossref based on a doi query"""

        # pylint: disable=import-outside-toplevel
        from crossref.restful import Works

        works = Works(etiquette=self.etiquette)
        try:
            crossref_query_return = works.doi(doi)
        except (
            requests.exceptions.JSONDecodeError,
            requests.exceptions.ConnectTimeout,
        ) as exc:
            raise colrev_exceptions.RecordNotFoundInPrepSourceException() from exc
        if crossref_query_return is None:
            raise colrev_exceptions.RecordNotFoundInPrepSourceException()
        retrieved_record_dict = connector_utils.json_to_record(
            item=crossref_query_return
        )
        retrieved_record = colrev.record.PrepRecord(data=retrieved_record_dict)

        return retrieved_record

    @timeout_decorator.timeout(500, use_signals=False)
    def __query_journal(
        self, *, journal_issn: str, rerun: bool
    ) -> typing.Iterator[dict]:
        """Get records of a selected journal from Crossref"""

        # pylint: disable=import-outside-toplevel

        assert re.match(self.__issn_regex, journal_issn)

        journals = Journals(etiquette=self.etiquette)
        if rerun:
            # Note : the "deposited" field is not always provided.
            # only the general query will return all records.
            crossref_query_return = journals.works(journal_issn).query()
        else:
            crossref_query_return = (
                journals.works(journal_issn).query().sort("deposited").order("desc")
            )

        for item in crossref_query_return:
            yield connector_utils.json_to_record(item=item)

    def __create_query_url(
        self, *, record: colrev.record.Record, jour_vol_iss_list: bool
    ) -> str:
        if jour_vol_iss_list:
            params = {"rows": "50"}
            container_title = re.sub(r"[\W]+", " ", record.data["journal"])
            params["query.container-title"] = container_title.replace("_", " ")

            query_field = ""
            if "volume" in record.data:
                query_field = record.data["volume"]
            if "number" in record.data:
                query_field = query_field + "+" + record.data["number"]
            params["query"] = query_field

        else:
            if "title" not in record.data:
                raise colrev_exceptions.NotEnoughDataToIdentifyException()

            params = {"rows": "15"}
            if not isinstance(record.data.get("year", ""), str) or not isinstance(
                record.data.get("title", ""), str
            ):
                print("year or title field not a string")
                print(record.data)
                raise AssertionError

            bibl = (
                record.data["title"].replace("-", "_")
                + " "
                + record.data.get("year", "")
            )
            bibl = re.sub(r"[\W]+", "", bibl.replace(" ", "_"))
            params["query.bibliographic"] = bibl.replace("_", " ")

            container_title = record.get_container_title()
            if "." not in container_title:
                container_title = container_title.replace(" ", "_")
                container_title = re.sub(r"[\W]+", "", container_title)
                params["query.container-title"] = container_title.replace("_", " ")

            author_last_names = [
                x.split(",")[0] for x in record.data.get("author", "").split(" and ")
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
            retrieved_record_dict.get("title", "NA").lower(),
            record.data.get("title", "").lower(),
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
    ) -> colrev.record.Record:
        if "language" in record.data:
            try:
                self.language_service.unify_to_iso_639_3_language_codes(record=record)
            except colrev_exceptions.InvalidLanguageCodeException:
                del record.data["language"]

        doi_connector.DOIConnector.get_link_from_doi(
            review_manager=self.review_manager,
            record=record,
        )

        if not prep_main_record:
            # Skip steps for feed records
            return record

        if "retracted" in record.data.get(
            "warning", ""
        ) or "retracted" in record.data.get("prescreen_exclusion", ""):
            record.prescreen_exclude(reason="retracted")
            record.remove_field(key="warning")
        else:
            assert "" != crossref_source
            record.set_masterdata_complete(source=crossref_source)
            record.set_status(target_state=colrev.record.RecordState.md_prepared)

        return record

    def crossref_query(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        record_input: colrev.record.Record,
        jour_vol_iss_list: bool = False,
        timeout: int = 40,
    ) -> list:
        """Retrieve records from Crossref based on a query"""

        # pylint: disable=too-many-branches
        # pylint: disable=too-many-statements
        # pylint: disable=too-many-locals

        # Note : only returning a multiple-item list for jour_vol_iss_list

        record_list = []
        most_similar, most_similar_record = 0.0, {}
        try:
            record = record_input.copy_prep_rec()

            url = self.__create_query_url(
                record=record, jour_vol_iss_list=jour_vol_iss_list
            )
            headers = {"user-agent": f"{__name__} (mailto:{self.email})"}
            session = review_manager.get_cached_session()

            # review_manager.logger.debug(url)
            ret = session.request("GET", url, headers=headers, timeout=timeout)
            ret.raise_for_status()
            if ret.status_code != 200:
                # review_manager.logger.debug(
                #     f"crossref_query failed with status {ret.status_code}"
                # )
                return []

            data = json.loads(ret.text)
            for item in data["message"]["items"]:
                if "title" not in item:
                    continue

                retrieved_record_dict = connector_utils.json_to_record(item=item)

                similarity = self.__get_similarity(
                    record=record, retrieved_record_dict=retrieved_record_dict
                )

                retrieved_record = colrev.record.PrepRecord(data=retrieved_record_dict)

                # source = (
                #     f'https://api.crossref.org/works/{retrieved_record.data["doi"]}'
                # )
                # retrieved_record.add_provenance_all(source=source)

                # record.set_masterdata_complete(source=source)

                if jour_vol_iss_list:
                    record_list.append(retrieved_record)
                elif most_similar < similarity:
                    most_similar = similarity
                    most_similar_record = retrieved_record.get_data()
        except (
            colrev_exceptions.NotEnoughDataToIdentifyException,
            json.decoder.JSONDecodeError,
            requests.exceptions.RequestException,
        ):
            pass
        # pylint: disable=duplicate-code
        except OperationalError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            ) from exc

        if not jour_vol_iss_list:
            if most_similar_record:
                record_list = [colrev.record.PrepRecord(data=most_similar_record)]

        return record_list

    # def __check_journal(
    #     self,
    #     prep_operation: colrev.ops.prep.Prep,
    #     record: colrev.record.Record,
    #     timeout: int,
    #     save_feed: bool,
    # ) -> colrev.record.Record:
    #     """When there is no doi, journal names can be checked against crossref"""

    #     if record.data["ENTRYTYPE"] == "article":
    #         # If type article and doi not in record and
    #         # journal name not found in journal-query: notify
    #         journals = Journals(etiquette=self.etiquette)
    #         # record.data["journal"] = "Information Systems Research"
    #         found = False
    #         ret = journals.query(record.data["journal"])
    #         for rets in ret:
    #             if rets["title"]:
    #                 found = True
    #                 break
    #         if not found:
    #             record.add_masterdata_provenance_note(
    #                 key="journal", note="quality_defect:journal not in crossref"
    #             )

    #     return record

    def __get_masterdata_record(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        timeout: int,
        save_feed: bool,
    ) -> colrev.record.Record:
        try:
            if "doi" in record.data:
                retrieved_record = self.query_doi(doi=record.data["doi"])
            else:
                retrieved_records = self.crossref_query(
                    review_manager=self.review_manager,
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
                        review_manager=self.review_manager,
                        record_input=record,
                        jour_vol_iss_list=False,
                        timeout=timeout,
                    )
                    retrieved_record = retrieved_records.pop()

            if 0 == len(retrieved_record.data) or "doi" not in retrieved_record.data:
                raise colrev_exceptions.RecordNotFoundInPrepSourceException()

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
                self.crossref_lock.acquire(timeout=60)

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
                    default_source=retrieved_record.data["colrev_origin"][0],
                )

                record = self.__prep_crossref_record(
                    record=record,
                    crossref_source=retrieved_record.data["colrev_origin"][0],
                )

                if save_feed:
                    crossref_feed.save_feed_file()
                self.crossref_lock.release()
                return record
            except (
                colrev_exceptions.InvalidMerge,
                colrev_exceptions.NotFeedIdentifiableException,
            ):
                self.crossref_lock.release()
                return record

        except (
            requests.exceptions.RequestException,
            OSError,
            IndexError,
            colrev_exceptions.RecordNotFoundInPrepSourceException,
        ) as exc:
            if prep_operation.review_manager.verbose_mode:
                print(exc)

        return record

    def __check_doi_masterdata(
        self, record: colrev.record.Record
    ) -> colrev.record.Record:
        try:
            retrieved_record = self.query_doi(doi=record.data["doi"])
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
                record.remove_field(key="doi")
                # record.print_citation_format()
                # retrieved_record.print_citation_format()

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
        timeout: int = 30,
    ) -> colrev.record.Record:
        """Retrieve masterdata from Crossref based on similarity with the record provided"""

        # To test the metadata provided for a particular DOI use:
        # https://api.crossref.org/works/DOI

        # https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
        if len(record.data.get("title", "")) < 35 and "doi" not in record.data:
            return record

        if "doi" in record.data:
            record = self.__check_doi_masterdata(record=record)

        record = self.__get_masterdata_record(
            prep_operation=prep_operation,
            record=record,
            timeout=timeout,
            save_feed=save_feed,
        )

        # Note: this should be optional
        # if "doi" not in record.data:
        #     record = self.__check_journal(
        #         prep_operation=prep_operation,
        #         record=record,
        #         timeout=timeout,
        #         save_feed=save_feed,
        #     )

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

        if source.filename.name != self.__crossref_md_filename.name:
            if not any(x in source.search_parameters for x in ["query", "scope"]):
                raise colrev_exceptions.InvalidQueryException(
                    "Crossref search_parameters requires a query or journal_issn field"
                )

            if "scope" in source.search_parameters:
                if "journal_issn" in source.search_parameters["scope"]:
                    issn_field = source.search_parameters["scope"]["journal_issn"]
                    if not re.match(
                        "[0-9][0-9][0-9][0-9][-]?[0-9][0-9][0-9][X0-9]", issn_field
                    ):
                        raise colrev_exceptions.InvalidQueryException(
                            f"Crossref journal issn ({issn_field}) not matching required format"
                        )
                else:
                    raise colrev_exceptions.InvalidQueryException(
                        "Query missing valid parameters"
                    )

            elif "query" in source.search_parameters:
                # Note: not yet implemented/supported
                if " AND " in source.search_parameters["query"]:
                    raise colrev_exceptions.InvalidQueryException(
                        "AND not supported in CROSSREF query"
                    )

            else:
                raise colrev_exceptions.InvalidQueryException(
                    "Query missing valid parameters"
                )

            if source.search_type not in [
                colrev.settings.SearchType.DB,
                colrev.settings.SearchType.TOC,
            ]:
                raise colrev_exceptions.InvalidQueryException(
                    "Crossref search_type should be in [DB,TOC]"
                )

        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )

    def __get_crossref_query_return(self, *, rerun: bool) -> typing.Iterator[dict]:
        params = self.search_source.search_parameters

        if "scope" in params:
            if "journal_issn" in params["scope"]:
                for journal_issn in params["scope"]["journal_issn"].split("|"):
                    yield from self.__query_journal(
                        journal_issn=journal_issn, rerun=rerun
                    )
        else:
            if "query" in params:
                crossref_query = {"bibliographic": params["query"]}
                # potential extension : add the container_title:
                # crossref_query_return = works.query(
                #     container_title=
                #       "Journal of the Association for Information Systems"
                # )
                yield from self.__query(**crossref_query)

    def __run_md_search_update(
        self,
        *,
        search_operation: colrev.ops.search.Search,
        crossref_feed: colrev.ops.search.GeneralOriginFeed,
    ) -> None:
        records = search_operation.review_manager.dataset.load_records_dict()

        nr_changed = 0
        for feed_record_dict in crossref_feed.feed_records.values():
            feed_record = colrev.record.Record(data=feed_record_dict)

            try:
                retrieved_record = self.query_doi(doi=feed_record_dict["doi"])

                if retrieved_record.data["doi"] != feed_record.data["doi"]:
                    continue

                crossref_feed.set_id(record_dict=retrieved_record.data)
            except (
                colrev_exceptions.RecordNotFoundInPrepSourceException,
                colrev_exceptions.NotFeedIdentifiableException,
            ):
                continue

            prev_record_dict_version = {}
            if retrieved_record.data["ID"] in crossref_feed.feed_records:
                prev_record_dict_version = crossref_feed.feed_records[
                    retrieved_record.data["ID"]
                ]

            crossref_feed.add_record(record=retrieved_record)

            changed = search_operation.update_existing_record(
                records=records,
                record_dict=retrieved_record.data,
                prev_record_dict_version=prev_record_dict_version,
                source=self.search_source,
                update_time_variant_fields=True,
            )
            if changed:
                nr_changed += 1

        if nr_changed > 0:
            self.review_manager.logger.info(
                f"{colors.GREEN}Updated {nr_changed} "
                f"records based on Crossref{colors.END}"
            )
        else:
            if records:
                self.review_manager.logger.info(
                    f"{colors.GREEN}Records (data/records.bib) up-to-date with Crossref{colors.END}"
                )

        crossref_feed.save_feed_file()
        search_operation.review_manager.dataset.save_records_dict(records=records)
        search_operation.review_manager.dataset.add_record_changes()

    def __run_parameter_search(
        self,
        *,
        search_operation: colrev.ops.search.Search,
        crossref_feed: colrev.ops.search.GeneralOriginFeed,
        rerun: bool,
    ) -> None:
        # pylint: disable=too-many-branches

        if rerun:
            search_operation.review_manager.logger.info(
                "Performing a search of the full history (may take time)"
            )

        records = search_operation.review_manager.dataset.load_records_dict()
        nr_retrieved, nr_changed = 0, 0

        try:
            # for record_dict in tqdm(
            #     self.__get_crossref_query_return(),
            #     total=len(crossref_feed.feed_records),
            # ):
            for record_dict in self.__get_crossref_query_return(rerun=rerun):
                # Note : discard "empty" records
                if "" == record_dict.get("author", "") and "" == record_dict.get(
                    "title", ""
                ):
                    continue
                try:
                    crossref_feed.set_id(record_dict=record_dict)
                except colrev_exceptions.NotFeedIdentifiableException:
                    continue

                prev_record_dict_version = {}
                if record_dict["ID"] in crossref_feed.feed_records:
                    prev_record_dict_version = deepcopy(
                        crossref_feed.feed_records[record_dict["ID"]]
                    )

                prep_record = colrev.record.Record(data=record_dict)
                prep_record = self.__prep_crossref_record(
                    record=prep_record, prep_main_record=False
                )

                if "colrev_data_provenance" in prep_record.data:
                    del prep_record.data["colrev_data_provenance"]

                if (
                    search_operation.review_manager.settings.is_curated_masterdata_repo()
                ):
                    if "cited_by" in prep_record.data:
                        del prep_record.data["cited_by"]

                added = crossref_feed.add_record(record=prep_record)

                if added:
                    search_operation.review_manager.logger.info(
                        " retrieve " + prep_record.data["doi"]
                    )
                    nr_retrieved += 1
                else:
                    changed = search_operation.update_existing_record(
                        records=records,
                        record_dict=prep_record.data,
                        prev_record_dict_version=prev_record_dict_version,
                        source=self.search_source,
                        update_time_variant_fields=rerun,
                    )
                    if changed:
                        nr_changed += 1

                # Note : only retrieve/update the latest deposits (unless in rerun mode)
                if not added and not rerun:
                    # problem: some publishers don't necessarily
                    # deposit papers chronologically
                    break

            if nr_retrieved > 0:
                search_operation.review_manager.logger.info(
                    f"{colors.GREEN}Retrieved {nr_retrieved} records{colors.END}"
                )
            else:
                search_operation.review_manager.logger.info(
                    f"{colors.GREEN}No additional records retrieved{colors.END}"
                )

            if nr_changed > 0:
                self.review_manager.logger.info(
                    f"{colors.GREEN}Updated {nr_changed} records{colors.END}"
                )
            else:
                if records:
                    self.review_manager.logger.info(
                        f"{colors.GREEN}Records (data/records.bib) up-to-date{colors.END}"
                    )

            crossref_feed.save_feed_file()
            search_operation.review_manager.dataset.save_records_dict(records=records)
            search_operation.review_manager.dataset.add_record_changes()

        except (
            requests.exceptions.Timeout,
            requests.exceptions.JSONDecodeError,
        ) as exc:
            # watch github issue:
            # https://github.com/fabiobatalha/crossrefapi/issues/46
            if "504 Gateway Time-out" in str(exc):
                raise colrev_exceptions.ServiceNotAvailableException(
                    f"Crossref ({colors.ORANGE}check https://status.crossref.org/{colors.END})"
                )
            raise colrev_exceptions.ServiceNotAvailableException(
                f"Crossref ({colors.ORANGE}check https://status.crossref.org/{colors.END})"
            )

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of Crossref"""

        crossref_feed = self.search_source.get_feed(
            review_manager=search_operation.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        if self.search_source.is_md_source() or self.search_source.is_quasi_md_source():
            self.__run_md_search_update(
                search_operation=search_operation,
                crossref_feed=crossref_feed,
            )

        else:
            self.__run_parameter_search(
                search_operation=search_operation,
                crossref_feed=crossref_feed,
                rerun=rerun,
            )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Crossref"""

        result = {"confidence": 0.0}

        return result

    @classmethod
    def add_endpoint(
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> typing.Optional[colrev.settings.SearchSource]:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        if "https://search.crossref.org/?q=" in query:
            query = (
                query.replace("https://search.crossref.org/?q=", "")
                .replace("&from_ui=yes", "")
                .lstrip("+")
            )

            filename = search_operation.get_unique_filename(
                file_path_string=f"crossref_{query}"
            )
            add_source = colrev.settings.SearchSource(
                endpoint="colrev.crossref",
                filename=filename,
                search_type=colrev.settings.SearchType.DB,
                search_parameters={"query": query},
                load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
                comment="",
            )
            return add_source
        if "crossref:jissn=" in query.replace("colrev.", ""):
            query = query.replace("crossref:jissn=", "").replace("colrev.", "")

            filename = search_operation.get_unique_filename(
                file_path_string=f"crossref_jissn_{query}"
            )
            add_source = colrev.settings.SearchSource(
                endpoint="colrev.crossref",
                filename=filename,
                search_type=colrev.settings.SearchType.DB,
                search_parameters={"scope": {"journal_issn": query}},
                load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
                comment="",
            )
            return add_source

        return None

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for Crossref"""

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for Crossref"""

        source_item = [
            x
            for x in record.data["colrev_origin"]
            if str(source.filename).replace("data/search/", "") in x
        ]
        if source_item:
            record.set_masterdata_complete(source=source_item[0])

        return record


if __name__ == "__main__":
    pass
