#! /usr/bin/env python
"""SearchSource: OpenAlex"""
from __future__ import annotations

import logging
import typing
from multiprocessing import Lock
from pathlib import Path

from pydantic import Field

import colrev.env.environment_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.search_api_feed
import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.packages.open_alex.src import open_alex_api

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class OpenAlexSearchSource(base_classes.SearchSourcePackageBaseClass):
    """OpenAlex API"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    endpoint = "colrev.open_alex"
    source_identifier = "openalex_id"
    search_types = [SearchType.MD]

    ci_supported: bool = Field(default=True)
    heuristic_status = SearchSourceHeuristicStatus.oni
    _availability_exception_message = "OpenAlex"

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

        self.open_alex_lock = Lock()

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for OpenAlex"""

        result = {"confidence": 0.0}

        return result

    @classmethod
    def add_endpoint(
        cls,
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""

        raise colrev_exceptions.PackageParameterError(
            f"Cannot add OpenAlex endpoint with query {params}"
        )

    def check_availability(self) -> None:
        """Check status (availability) of the OpenAlex API"""

        try:
            _, email = (
                colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git()
            )
            api = open_alex_api.OpenAlexAPI(email=email)
            retrieved_record = api.get_record(open_alex_id="W2741809807")
            if not retrieved_record.data:
                raise colrev_exceptions.ServiceNotAvailableException(
                    self._availability_exception_message
                )
        except (open_alex_api.OpenAlexAPIError, KeyError) as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                self._availability_exception_message
            ) from exc

    def _get_masterdata_record(
        self,
        *,
        record: colrev.record.record.Record,
        prep_operation: colrev.ops.prep.Prep,
    ) -> colrev.record.record.Record:
        try:

            _, email = (
                colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git()
            )
            api = open_alex_api.OpenAlexAPI(email=email)
            retrieved_record = api.get_record(
                open_alex_id=record.data["colrev.open_alex.id"]
            )

            self.open_alex_lock.acquire(timeout=120)

            # Note : need to reload file because the object is not shared between processes
            open_alex_feed = colrev.ops.search_api_feed.SearchAPIFeed(
                source_identifier=self.source_identifier,
                search_source=self.search_source,
                update_only=False,
                prep_mode=True,
                records=prep_operation.review_manager.dataset.load_records_dict(),
                logger=self.logger,
                verbose_mode=self.verbose_mode,
            )

            open_alex_feed.add_update_record(retrieved_record)
            record.change_entrytype(
                new_entrytype=retrieved_record.data[Fields.ENTRYTYPE],
            )

            record.merge(
                retrieved_record,
                default_source=retrieved_record.data[Fields.ORIGIN][0],
            )
            prep_operation.review_manager.dataset.save_records_dict(
                open_alex_feed.get_records(),
            )
            open_alex_feed.save()
        except (
            colrev_exceptions.RecordNotParsableException,
            open_alex_api.OpenAlexAPIError,
        ):
            pass
        except Exception as exc:
            raise exc
        finally:
            try:
                self.open_alex_lock.release()
            except ValueError:
                pass

        return record

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 30,
    ) -> colrev.record.record.Record:
        """Retrieve masterdata from OpenAlex based on similarity with the record provided"""

        if "colrev.open_alex.id" in record.data:
            # Note: not yet implemented
            # https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
            # if len(record.data.get(Fields.TITLE, "")) < 35 and Fields.DOI not in record.data:
            #     return record
            # record = self._check_doi_masterdata(record=record)
            record = self._get_masterdata_record(
                record=record, prep_operation=prep_operation
            )

        return record

    def search(self, rerun: bool) -> None:
        """Run a search of OpenAlex"""

        # https://docs.openalex.org/api-entities/works

        raise NotImplementedError

    def load(self) -> dict:
        """Load the records from the SearchSource file"""

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
    ) -> colrev.record.record.Record:
        """Source-specific preparation for OpenAlex"""

        return record
