#! /usr/bin/env python
"""CoLRev search feed: store and update origin records and update main records."""
from __future__ import annotations

import json
import time
from copy import deepcopy
from random import randint

import colrev.exceptions as colrev_exceptions
import colrev.loader.load_utils
from colrev.constants import Colors
from colrev.constants import DefectCodes
from colrev.constants import Fields
from colrev.constants import FieldSet
from colrev.constants import FieldValues
from colrev.writer.write_utils import to_string
from colrev.writer.write_utils import write_file


# Keep in mind the need for lock-mechanisms, e.g., in concurrent prep operations
class SearchAPIFeed:
    """A general-purpose Origin feed"""

    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments

    _nr_added: int = 0
    _nr_changed: int = 0

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        source_identifier: str,
        search_source: colrev.settings.SearchSource,
        update_only: bool,
        update_time_variant_fields: bool = True,
        prep_mode: bool = False,
    ):
        self.source = search_source
        self.feed_file = search_source.filename

        # Note: the source_identifier identifies records in the search feed.
        # This could be a doi or link or database-specific ID (like WOS accession numbers)
        # The source_identifier can be stored in the main records.bib (it does not have to)
        # The record source_identifier (feed-specific) is used in search
        # or other operations (like prep)
        # In search operations, records are added/updated based on available_ids
        # (which maps source_identifiers to IDs used to generate the colrev_origin)
        # In other operations, records are linked through colrev_origins,
        # i.e., there is no need to store the source_identifier in the main records (redundantly)
        self.source_identifier = source_identifier

        # Note: corresponds to rerun (in search.main() and run_search())
        self.update_only = update_only
        self.update_time_variant_fields = update_time_variant_fields
        self.review_manager = review_manager
        self.origin_prefix = self.source.get_origin_prefix()

        self._available_ids = {}
        self._max_id = 1
        if not self.feed_file.is_file():
            self.feed_records = {}
        else:
            self.feed_records = colrev.loader.load_utils.loads(
                load_string=self.feed_file.read_text(encoding="utf8"),
                implementation="bib",
                logger=self.review_manager.logger,
            )

            self._available_ids = {
                x[self.source_identifier]: x[Fields.ID]
                for x in self.feed_records.values()
                if self.source_identifier in x
            }
            self._max_id = (
                max(
                    [
                        int(x[Fields.ID])
                        for x in self.feed_records.values()
                        if x[Fields.ID].isdigit()
                    ]
                    + [1]
                )
                + 1
            )
        self.prep_mode = prep_mode
        if not prep_mode:
            self.records = self.review_manager.dataset.load_records_dict()

    def _get_prev_record_version(
        self, *, retrieved_record: colrev.record.Record
    ) -> colrev.record.Record:
        """Get the previous record dict version"""
        self._set_id(record=retrieved_record)

        prev_record_dict_version = {}
        if retrieved_record.data[Fields.ID] in self.feed_records:
            prev_record_dict_version = deepcopy(
                self.feed_records[retrieved_record.data[Fields.ID]]
            )
        return colrev.record.Record(data=prev_record_dict_version)

    def _set_id(self, *, record: colrev.record.Record) -> None:
        """Set incremental record ID
        If self.source_identifier is in record_dict, it is updated, otherwise added as a new record.
        """

        if self.source_identifier not in record.data:
            raise colrev_exceptions.NotFeedIdentifiableException()

        if record.data[self.source_identifier] in self._available_ids:
            record.data[Fields.ID] = self._available_ids[
                record.data[self.source_identifier]
            ]
        else:
            record.data[Fields.ID] = str(self._max_id).rjust(6, "0")

    def add_update_record(self, *, retrieved_record: colrev.record.Record) -> bool:
        """Add or update a record in the api_search_feed and records"""

        prev_record_version = self._get_prev_record_version(
            retrieved_record=retrieved_record
        )
        added = self._add_record(record=retrieved_record)
        if not self.prep_mode:
            self._update_existing_record(
                retrieved_record=retrieved_record,
                prev_record_version=prev_record_version,
            )
        return added

    def get_prev_record_version(
        self, *, record: colrev.record.Record
    ) -> colrev.record.Record:
        """Get the previous record dict version"""
        record = deepcopy(record)
        self._set_id(record=record)
        prev_record_dict_version = {}
        if record.data[Fields.ID] in self.feed_records:
            prev_record_dict_version = deepcopy(
                self.feed_records[record.data[Fields.ID]]
            )
        return colrev.record.Record(data=prev_record_dict_version)

    def _add_record(self, *, record: colrev.record.Record) -> bool:
        """Add a record to the feed and set its colrev_origin"""

        self._set_id(record=record)

        # Feed:
        feed_record_dict = record.data.copy()
        added_new = True
        if feed_record_dict[self.source_identifier] in self._available_ids:
            added_new = False
        else:
            self._max_id += 1
            self._nr_added += 1

        for provenance_key in FieldSet.PROVENANCE_KEYS:
            if provenance_key in feed_record_dict:
                del feed_record_dict[provenance_key]

        self._available_ids[feed_record_dict[self.source_identifier]] = (
            feed_record_dict[Fields.ID]
        )

        if self.update_only:
            # ignore time_variant_fields
            # (otherwise, fields in recent records would be more up-to-date)
            for key in FieldSet.TIME_VARIANT_FIELDS:
                if feed_record_dict[Fields.ID] in self.feed_records:
                    if key in self.feed_records[feed_record_dict[Fields.ID]]:
                        feed_record_dict[key] = self.feed_records[
                            feed_record_dict[Fields.ID]
                        ][key]
                    else:
                        if key in feed_record_dict:
                            del feed_record_dict[key]

        self.feed_records[feed_record_dict[Fields.ID]] = feed_record_dict

        # Original record
        colrev_origin = f"{self.origin_prefix}/{record.data['ID']}"
        record.data[Fields.ORIGIN] = [colrev_origin]
        record.add_provenance_all(source=colrev_origin)

        return added_new

    def save(self) -> None:
        """Save the feed file and records, printing post-run search infos."""

        self._print_post_run_search_infos()
        search_operation = self.review_manager.get_search_operation()
        if len(self.feed_records) > 0:
            self.feed_file.parents[0].mkdir(parents=True, exist_ok=True)

            write_file(records_dict=self.feed_records, filename=self.feed_file)

            while True:
                try:
                    search_operation.review_manager.load_settings()
                    if self.source.filename.name not in [
                        s.filename.name
                        for s in search_operation.review_manager.settings.sources
                    ]:
                        search_operation.review_manager.settings.sources.append(
                            self.source
                        )
                        search_operation.review_manager.save_settings()

                    search_operation.review_manager.dataset.add_changes(
                        path=self.feed_file
                    )
                    break
                except (
                    FileExistsError,
                    OSError,
                    json.decoder.JSONDecodeError,
                ):  # pragma: no cover
                    search_operation.review_manager.logger.debug("Wait for git")
                    time.sleep(randint(1, 15))  # nosec

        if not self.prep_mode:
            self.review_manager.dataset.save_records_dict(records=self.records)

    def _have_changed(self, *, record_a_orig: dict, record_b_orig: dict) -> bool:
        # To ignore changes introduced by saving/loading the feed-records,
        # we parse and load them in the following.
        record_a = deepcopy(record_a_orig)
        record_b = deepcopy(record_b_orig)

        bibtex_str = to_string(
            records_dict={record_a[Fields.ID]: record_a}, implementation="bib"
        )
        record_a = list(
            colrev.loader.load_utils.loads(
                load_string=bibtex_str,
                implementation="bib",
                logger=self.review_manager.logger,
            ).values()
        )[0]

        bibtex_str = to_string(
            records_dict={record_b[Fields.ID]: record_b}, implementation="bib"
        )
        record_b = list(
            colrev.loader.load_utils.loads(
                load_string=bibtex_str,
                implementation="bib",
                logger=self.review_manager.logger,
            ).values()
        )[0]

        # Note : record_a can have more keys (that's ok)
        changed = False
        for key, value in record_b.items():
            if key in FieldSet.PROVENANCE_KEYS + [Fields.ID, Fields.CURATION_ID]:
                continue
            if key not in record_a:
                return True
            if record_a[key] != value:
                return True
        return changed

    def _get_record_based_on_origin(self, origin: str, records: dict) -> dict:
        for main_record_dict in records.values():
            if origin in main_record_dict[Fields.ORIGIN]:
                return main_record_dict
        return {}

    def _update_existing_record_retract(
        self, *, record: colrev.record.Record, main_record_dict: dict
    ) -> bool:
        if record.is_retracted():
            self.review_manager.logger.info(
                f"{Colors.GREEN}Found paper retract: "
                f"{main_record_dict['ID']}{Colors.END}"
            )
            main_record = colrev.record.Record(data=main_record_dict)
            main_record.prescreen_exclude(
                reason=FieldValues.RETRACTED, print_warning=True
            )
            main_record.remove_field(key="warning")
            return True
        return False

    def _update_existing_record_forthcoming(
        self, *, record: colrev.record.Record, main_record_dict: dict
    ) -> None:
        if "forthcoming" == main_record_dict.get(
            Fields.YEAR, ""
        ) and "forthcoming" != record.data.get(Fields.YEAR, ""):
            self.review_manager.logger.info(
                f"{Colors.GREEN}Update published forthcoming paper: "
                f"{record.data['ID']}{Colors.END}"
            )
            # prepared_record = crossref_prep.prepare(prep_operation, record)
            main_record_dict[Fields.YEAR] = record.data[Fields.YEAR]
            record = colrev.record.PrepRecord(data=main_record_dict)

    def _missing_ignored_field(self, main_record_dict: dict, key: str) -> bool:
        main_record = colrev.record.Record(data=main_record_dict)
        source = main_record.get_masterdata_provenance_source(key)
        notes = main_record.get_masterdata_provenance_notes(key)
        if (
            source == "colrev_curation.masterdata_restrictions"
            and f"IGNORE:{DefectCodes.MISSING}" in notes
        ):
            return True
        return False

    # pylint: disable=too-many-arguments
    def _update_existing_record_fields(
        self,
        *,
        record_dict: dict,
        main_record_dict: dict,
        prev_record_dict_version: dict,
        origin: str,
    ) -> None:
        for key, value in record_dict.items():
            if (
                not self.update_time_variant_fields
                and key in FieldSet.TIME_VARIANT_FIELDS
            ):
                continue

            if key in FieldSet.PROVENANCE_KEYS + [Fields.ID, Fields.CURATION_ID]:
                continue

            if key not in main_record_dict:
                if self._missing_ignored_field(main_record_dict, key):
                    continue

                main_record = colrev.record.Record(data=main_record_dict)
                main_record.update_field(
                    key=key,
                    value=value,
                    source=origin,
                    keep_source_if_equal=True,
                    append_edit=False,
                )
            else:
                if self.source.get_origin_prefix() != "md_curated.bib":
                    if prev_record_dict_version.get(key, "NA") != main_record_dict.get(
                        key, "OTHER"
                    ):
                        continue
                main_record = colrev.record.Record(data=main_record_dict)
                if value.replace(" - ", ": ") == main_record.data[key].replace(
                    " - ", ": "
                ):
                    continue
                if (
                    key == Fields.URL
                    and "dblp.org" in value
                    and key in main_record.data
                ):
                    continue
                main_record.update_field(
                    key=key,
                    value=value,
                    source=origin,
                    keep_source_if_equal=True,
                    append_edit=False,
                )

    def _forthcoming_published(self, *, record_dict: dict, prev_record: dict) -> bool:
        # Forthcoming paper published if volume and number are assigned
        # i.e., no longer UNKNOWN
        if record_dict[Fields.ENTRYTYPE] != "article":
            return False
        if (
            record_dict.get(Fields.VOLUME, "") != FieldValues.UNKNOWN
            and prev_record.get(Fields.VOLUME, FieldValues.UNKNOWN)
            == FieldValues.UNKNOWN
            and record_dict.get(Fields.NUMBER, "") != FieldValues.UNKNOWN
            and prev_record.get(Fields.VOLUME, FieldValues.UNKNOWN)
            == FieldValues.UNKNOWN
        ):
            return True
        return False

    # pylint: disable=too-many-arguments
    def _update_existing_record(
        self,
        *,
        retrieved_record: colrev.record.Record,
        prev_record_version: colrev.record.Record,
    ) -> bool:
        """Convenience function to update existing records (main data/records.bib)"""

        origin = f"{self.source.get_origin_prefix()}/{retrieved_record.data['ID']}"
        main_record_dict = self._get_record_based_on_origin(
            origin=origin, records=self.records
        )

        if main_record_dict == {}:
            self.review_manager.logger.debug(
                f"Could not update {retrieved_record.data['ID']}"
            )
            return False

        # TBD: in curated masterdata repositories?

        retrieved_record.prefix_non_standardized_field_keys(prefix=self.source.endpoint)
        changed = self._update_existing_record_retract(
            record=retrieved_record, main_record_dict=main_record_dict
        )
        self._update_existing_record_forthcoming(
            record=retrieved_record, main_record_dict=main_record_dict
        )

        if (
            colrev.record.Record(data=main_record_dict).masterdata_is_curated()
            and "md_curated.bib" != self.source.get_origin_prefix()
        ):
            return False

        similarity_score = colrev.record.Record.get_record_similarity(
            record_a=retrieved_record,
            record_b=prev_record_version,
        )
        dict_diff = retrieved_record.get_diff(other_record=prev_record_version)

        self._update_existing_record_fields(
            record_dict=retrieved_record.data,
            main_record_dict=main_record_dict,
            prev_record_dict_version=prev_record_version.data,
            origin=origin,
        )

        if self._have_changed(
            record_a_orig=main_record_dict, record_b_orig=prev_record_version.data
        ) or self._have_changed(  # Note : not (yet) in the main records but changed
            record_a_orig=retrieved_record.data, record_b_orig=prev_record_version.data
        ):
            changed = True
            self._nr_changed += 1
            if self._forthcoming_published(
                record_dict=retrieved_record.data, prev_record=prev_record_version.data
            ):
                self.review_manager.logger.info(
                    f" {Colors.GREEN}forthcoming paper published: "
                    f"{main_record_dict['ID']}{Colors.END}"
                )
            elif similarity_score > 0.98:
                self.review_manager.logger.info(f" check/update {origin}")
            else:
                self.review_manager.logger.info(
                    f" {Colors.RED} check/update {origin} leads to substantial changes "
                    f"({similarity_score}) in {main_record_dict['ID']}:{Colors.END}"
                )
                self.review_manager.p_printer.pprint(
                    [x for x in dict_diff if "change" == x[0]]
                )

        return changed

    def _print_post_run_search_infos(self) -> None:
        """Print the search infos (after running the search)"""
        if self._nr_added > 0:
            self.review_manager.logger.info(
                f"{Colors.GREEN}Retrieved {self._nr_added} records{Colors.END}"
            )
        else:
            self.review_manager.logger.info(
                f"{Colors.GREEN}No additional records retrieved{Colors.END}"
            )

        if self.prep_mode:
            # No need to print the following in prep mode
            # because the main records are not updated/saved
            return

        if self._nr_changed > 0:
            self.review_manager.logger.info(
                f"{Colors.GREEN}Updated {self._nr_changed} records{Colors.END}"
            )
        else:
            if self.records:
                self.review_manager.logger.info(
                    f"{Colors.GREEN}Records (data/records.bib) up-to-date{Colors.END}"
                )
