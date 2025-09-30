#! /usr/bin/env python
"""SearchSource: Pubmed"""
from __future__ import annotations

import logging
import typing
from multiprocessing import Lock
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from pydantic import Field
from search_query.parser import parse

import colrev.env.environment_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.search_api_feed
import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
import colrev.record.record_prep
import colrev.record.record_similarity
import colrev.search_file
import colrev.utils
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import RecordState
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search_api_feed import create_api_source
from colrev.ops.search_db import create_db_source
from colrev.ops.search_db import run_db_search
from colrev.packages.pubmed.src import pubmed_api

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class PubMedSearchSource(base_classes.SearchSourcePackageBaseClass):
    """Pubmed"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    source_identifier = "pubmedid"
    search_types = [
        SearchType.DB,
        SearchType.API,
        SearchType.MD,
    ]
    endpoint = "colrev.pubmed"

    ci_supported: bool = Field(default=True)
    heuristic_status = SearchSourceHeuristicStatus.supported

    db_url = "https://pubmed.ncbi.nlm.nih.gov/"
    _availability_exception_message = "Pubmed"

    def __init__(
        self,
        *,
        search_file: colrev.search_file.ExtendedSearchFile,
        logger: typing.Optional[logging.Logger] = None,
        verbose_mode: bool = False,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.verbose_mode = verbose_mode

        self.search_source = search_file
        self.validate_source(self.search_source)

        self.pubmed_lock = Lock()

        _, self.email = (
            colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git()
        )

    @classmethod
    def validate_source(
        cls, search_source: colrev.search_file.ExtendedSearchFile
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        print(f"Validate SearchSource {search_source.search_results_path}")

        if search_source.version != cls.CURRENT_SYNTAX_VERSION:
            raise colrev_exceptions.InvalidQueryException(
                f"PubMed version should be {cls.CURRENT_SYNTAX_VERSION}, "
                f"found {search_source.version}"
            )

        # if source.search_results_path.name != self._pubmed_md_filename.name:
        #     if "query" not in source.search_string:
        #         raise colrev_exceptions.InvalidQueryException(
        #             f"Source missing query search_parameter ({source.search_results_path})"
        #         )

        # if "query_file" in source.search_string:
        # ...

        if search_source.search_type == SearchType.DB:
            print(f"Validating search string: {search_source.search_string}")
            # TODO : TBD: pass version to search-query?
            parse(search_source.search_string, platform="pubmed")

        # if search_source.search_type == SearchType.API:
        #     print(f'Validating search string: {search_source.search_parameters}')
        #     parse(search_source.search_parameters, platform="pubmed_api")

        print("SearchSource %s validated", search_source.search_results_path)

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
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""

        params_dict = {}
        if params:
            if params.startswith("http"):
                params_dict = {Fields.URL: params}
            else:
                for item in params.split(";"):
                    key, value = item.split("=")
                    params_dict[key] = value

        search_type = colrev.utils.select_search_type(
            search_types=cls.search_types, params=params_dict
        )

        if search_type == SearchType.DB:
            search_source = create_db_source(
                path=path,
                platform=cls.endpoint,
                params=params_dict,
                add_to_git=True,
                logger=logger,
            )

            search_source.version = cls.CURRENT_SYNTAX_VERSION

        elif search_type == SearchType.API:
            if len(params_dict) == 0:
                search_source = create_api_source(platform=cls.endpoint, path=path)
                api_term_url = (
                    "https://eutils.ncbi.nlm.nih.gov/"
                    + "entrez/eutils/esearch.fcgi?db=pubmed&term="
                    + search_source.search_string
                )
                search_source.search_parameters = {
                    "url": api_term_url,
                }
                search_source.search_string = ""
                search_source.version = cls.CURRENT_SYNTAX_VERSION

            # pylint: disable=colrev-missed-constant-usage
            elif "url" in params_dict:
                host = urlparse(params_dict["url"]).hostname

                if host and host.endswith("pubmed.ncbi.nlm.nih.gov"):

                    filename = colrev.utils.get_unique_filename(
                        base_path=path,
                        file_path_string="pubmed",
                    )
                    # params = (
                    # "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term="
                    #     + params
                    # )
                    search_source = colrev.search_file.ExtendedSearchFile(
                        platform=cls.endpoint,
                        search_results_path=filename,
                        search_type=SearchType.API,
                        search_string=params_dict["url"],
                        comment="",
                        version=cls.CURRENT_SYNTAX_VERSION,
                    )

                    search_source.search_parameters = {
                        "url": params_dict["url"],
                    }
                    search_source.version = cls.CURRENT_SYNTAX_VERSION
                else:
                    raise NotImplementedError
            else:
                raise NotImplementedError

            # search_source.search_parameters = {"query": search_source.search_string}
            # search_source.search_string = ""

        else:
            raise NotImplementedError
        return search_source

    def check_availability(self) -> None:
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

            api = pubmed_api.PubmedAPI(
                url=self.search_source.search_parameters["url"],
                email=self.email,
                session=colrev.utils.get_cached_session(),
            )
            returned_record = api.query_id(pubmed_id=test_rec["pubmedid"])

            if returned_record:
                assert returned_record.data[Fields.TITLE] == test_rec[Fields.TITLE]
                assert returned_record.data[Fields.AUTHOR] == test_rec[Fields.AUTHOR]
            else:
                raise colrev_exceptions.ServiceNotAvailableException(
                    self._availability_exception_message
                )
        except (pubmed_api.PubmedAPIError, IndexError, KeyError) as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                self._availability_exception_message
            ) from exc

    def _get_masterdata_record(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool,
        timeout: int,
    ) -> colrev.record.record.Record:
        try:
            api = pubmed_api.PubmedAPI(
                url="",
                email=self.email,
                session=colrev.utils.get_cached_session(),
                logger=self.logger,
            )

            retrieved_record = api.query_id(pubmed_id=record.data["pubmedid"])

            if not retrieved_record:
                raise colrev_exceptions.RecordNotFoundInPrepSourceException(
                    msg="Pubmed: no records retrieved"
                )

            if not colrev.record.record_similarity.matches(record, retrieved_record):
                return record

            try:
                self.pubmed_lock.acquire(timeout=60)

                # Note : need to reload file because the object is not shared between processes
                pubmed_feed = colrev.ops.search_api_feed.SearchAPIFeed(
                    source_identifier=self.source_identifier,
                    search_source=self.search_source,
                    update_only=False,
                    prep_mode=True,
                    records=prep_operation.review_manager.dataset.load_records_dict(),
                    logger=self.logger,
                    verbose_mode=self.verbose_mode,
                )

                pubmed_feed.add_update_record(retrieved_record)

                record.merge(
                    retrieved_record,
                    default_source=retrieved_record.data[Fields.ORIGIN][0],
                )

                record.set_status(RecordState.md_prepared)

                if save_feed:
                    prep_operation.review_manager.dataset.save_records_dict(
                        pubmed_feed.get_records(),
                    )
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
            pubmed_api.PubmedAPIError,
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

    def _run_api_search(
        self,
        *,
        pubmed_feed: colrev.ops.search_api_feed.SearchAPIFeed,
        rerun: bool,
    ) -> None:
        if rerun:
            self.logger.info("Performing a search of the full history (may take time)")

        api = pubmed_api.PubmedAPI(
            url=self.search_source.search_parameters["url"],
            email=self.email,
            session=colrev.utils.get_cached_session(),
            logger=self.logger,
        )

        for record in api.get_query_return():
            try:
                # Note : discard "empty" records
                if "" == record.data.get(Fields.AUTHOR, "") and "" == record.data.get(
                    Fields.TITLE, ""
                ):
                    self.logger.warning(f"Skipped record: {record.data}")
                    continue
                prep_record = colrev.record.record_prep.PrepRecord(record.data)

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

    def _run_md_search(
        self,
        *,
        pubmed_feed: colrev.ops.search_api_feed.SearchAPIFeed,
    ) -> None:

        api = pubmed_api.PubmedAPI(
            url=self.search_source.search_string,
            email=self.email,
            session=colrev.utils.get_cached_session(),
            logger=self.logger,
        )

        for feed_record_dict in pubmed_feed.feed_records.values():
            feed_record = colrev.record.record.Record(feed_record_dict)

            try:
                retrieved_record = api.query_id(pubmed_id=feed_record_dict["pubmedid"])

                if retrieved_record.data["pubmedid"] == feed_record.data["pubmedid"]:
                    pubmed_feed.add_update_record(retrieved_record)

            except (
                colrev_exceptions.RecordNotFoundInPrepSourceException,
                colrev_exceptions.NotFeedIdentifiableException,
                colrev_exceptions.SearchSourceException,
            ):
                continue

        pubmed_feed.save()

    def search(self, rerun: bool) -> None:
        """Run a search of Pubmed"""

        pubmed_feed = colrev.ops.search_api_feed.SearchAPIFeed(
            source_identifier=self.source_identifier,
            search_source=self.search_source,
            update_only=(not rerun),
            logger=self.logger,
            verbose_mode=self.verbose_mode,
        )

        if self.search_source.search_type == SearchType.MD:
            self._run_md_search(pubmed_feed=pubmed_feed)

        elif self.search_source.search_type == SearchType.API:
            self._run_api_search(
                pubmed_feed=pubmed_feed,
                rerun=rerun,
            )

        elif self.search_source.search_type == SearchType.DB:
            run_db_search(
                db_url=self.db_url,
                source=self.search_source,
                add_to_git=True,
            )
            return
        else:
            raise NotImplementedError

    @classmethod
    def _load_csv(cls, *, filename: Path, logger: logging.Logger) -> dict:
        def entrytype_setter(record_dict: dict) -> None:
            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE

        def field_mapper(record_dict: dict) -> None:
            record_dict[Fields.TITLE] = record_dict.pop("Title", "")
            record_dict[Fields.JOURNAL] = record_dict.pop("Journal/Book", "")
            record_dict[Fields.YEAR] = record_dict.pop("Publication Year", "")
            record_dict[Fields.URL] = record_dict.pop("URL", "")
            record_dict[Fields.DOI] = record_dict.pop("DOI", "")
            record_dict[f"{cls.endpoint}.nihms_id"] = record_dict.pop("NIHMS ID", "")
            record_dict[Fields.PUBMED_ID] = record_dict.pop("PMID", "")
            record_dict[Fields.PMCID] = record_dict.pop("PMCID", "")
            record_dict[f"{cls.endpoint}.create_date"] = record_dict.pop(
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
            filename=filename,
            unique_id_field="PMID",
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            logger=logger,
        )
        return records

    def load(self) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.search_results_path.suffix == ".csv":
            return self._load_csv(
                filename=self.search_source.search_results_path, logger=self.logger
            )

        if self.search_source.search_results_path.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=self.search_source.search_results_path,
                logger=self.logger,
            )
            return records

        raise NotImplementedError

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
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
