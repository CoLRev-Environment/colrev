#! /usr/bin/env python
"""CoLRev search feed: store and update origin records and update main records."""
from __future__ import annotations

import json
import time
from copy import deepcopy
from random import randint

from pybtex.database.input import bibtex

import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.settings
import colrev.ui_cli.cli_colors as colors


# Keep in mind the need for lock-mechanisms, e.g., in concurrent prep operations
class GeneralOriginFeed:
    """A general-purpose Origin feed"""

    # pylint: disable=too-many-instance-attributes

    nr_added: int = 0
    nr_changed: int = 0

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        search_source: colrev.settings.SearchSource,
        source_identifier: str,
        update_only: bool,
    ):
        self.source = search_source
        self.feed_file = search_source.get_corresponding_bib_file()

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
        self.review_manager = review_manager
        self.origin_prefix = self.source.get_origin_prefix()

        self.__available_ids = {}
        self.__max_id = 1
        if not self.feed_file.is_file():
            self.feed_records = {}
        else:
            with open(self.feed_file, encoding="utf8") as bibtex_file:
                self.feed_records = self.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )

            self.__available_ids = {
                x[self.source_identifier]: x["ID"]
                for x in self.feed_records.values()
                if self.source_identifier in x
            }
            self.__max_id = (
                max(
                    [
                        int(x["ID"])
                        for x in self.feed_records.values()
                        if x["ID"].isdigit()
                    ]
                    + [1]
                )
                + 1
            )

    def set_id(self, *, record_dict: dict) -> dict:
        """Set incremental record ID
        If self.source_identifier is in record_dict, it is updated, otherwise added as a new record.
        """

        if self.source_identifier not in record_dict:
            raise colrev_exceptions.NotFeedIdentifiableException()

        if record_dict[self.source_identifier] in self.__available_ids:
            record_dict["ID"] = self.__available_ids[
                record_dict[self.source_identifier]
            ]
        else:
            record_dict["ID"] = str(self.__max_id).rjust(6, "0")

        return record_dict

    def add_record(self, *, record: colrev.record.Record) -> bool:
        """Add a record to the feed and set its colrev_origin"""

        # Feed:
        feed_record_dict = record.data.copy()
        added_new = True
        if feed_record_dict[self.source_identifier] in self.__available_ids:
            added_new = False
        else:
            self.__max_id += 1

        if "colrev_data_provenance" in feed_record_dict:
            del feed_record_dict["colrev_data_provenance"]
        if "colrev_masterdata_provenance" in feed_record_dict:
            del feed_record_dict["colrev_masterdata_provenance"]
        if "colrev_status" in feed_record_dict:
            del feed_record_dict["colrev_status"]

        self.__available_ids[
            feed_record_dict[self.source_identifier]
        ] = feed_record_dict["ID"]

        if self.update_only:
            # ignore time_variant_fields
            # (otherwise, fields in recent records would be more up-to-date)
            for key in colrev.record.Record.time_variant_fields:
                if feed_record_dict["ID"] in self.feed_records:
                    if key in self.feed_records[feed_record_dict["ID"]]:
                        feed_record_dict[key] = self.feed_records[
                            feed_record_dict["ID"]
                        ][key]
                    else:
                        if key in feed_record_dict:
                            del feed_record_dict[key]

        self.feed_records[feed_record_dict["ID"]] = feed_record_dict

        # Original record
        colrev_origin = f"{self.origin_prefix}/{record.data['ID']}"
        record.data["colrev_origin"] = [colrev_origin]
        record.add_provenance_all(source=colrev_origin)

        return added_new

    def print_post_run_search_infos(self, *, records: dict) -> None:
        """Print the search infos (after running the search)"""
        if self.nr_added > 0:
            self.review_manager.logger.info(
                f"{colors.GREEN}Retrieved {self.nr_added} records{colors.END}"
            )
        else:
            self.review_manager.logger.info(
                f"{colors.GREEN}No additional records retrieved{colors.END}"
            )

        if self.nr_changed > 0:
            self.review_manager.logger.info(
                f"{colors.GREEN}Updated {self.nr_changed} records{colors.END}"
            )
        else:
            if records:
                self.review_manager.logger.info(
                    f"{colors.GREEN}Records (data/records.bib) up-to-date{colors.END}"
                )

    def save_feed_file(self) -> None:
        """Save the feed file"""

        search_operation = self.review_manager.get_search_operation()
        if len(self.feed_records) > 0:
            self.feed_file.parents[0].mkdir(parents=True, exist_ok=True)
            self.review_manager.dataset.save_records_dict_to_file(
                records=self.feed_records, save_path=self.feed_file
            )

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
                except (FileExistsError, OSError, json.decoder.JSONDecodeError):
                    search_operation.review_manager.logger.debug("Wait for git")
                    time.sleep(randint(1, 15))  # nosec

    def __have_changed(self, *, record_a_orig: dict, record_b_orig: dict) -> bool:
        # To ignore changes introduced by saving/loading the feed-records,
        # we parse and load them in the following.
        record_a = deepcopy(record_a_orig)
        record_b = deepcopy(record_b_orig)

        bibtex_str = self.review_manager.dataset.parse_bibtex_str(
            recs_dict_in={record_a["ID"]: record_a}
        )
        parser = bibtex.Parser()
        bib_data = parser.parse_string(bibtex_str)
        record_a = list(
            self.review_manager.dataset.parse_records_dict(
                records_dict=bib_data.entries
            ).values()
        )[0]

        bibtex_str = self.review_manager.dataset.parse_bibtex_str(
            recs_dict_in={record_b["ID"]: record_b}
        )
        parser = bibtex.Parser()
        bib_data = parser.parse_string(bibtex_str)
        record_b = list(
            self.review_manager.dataset.parse_records_dict(
                records_dict=bib_data.entries
            ).values()
        )[0]

        # Note : record_a can have more keys (that's ok)
        changed = False
        for key, value in record_b.items():
            if key in colrev.record.Record.provenance_keys + ["ID", "curation_ID"]:
                continue
            if key not in record_a:
                return True
            if record_a[key] != value:
                return True
        return changed

    def __get_record_based_on_origin(self, origin: str, records: dict) -> dict:
        for main_record_dict in records.values():
            if origin in main_record_dict["colrev_origin"]:
                return main_record_dict
        return {}

    def __update_existing_record_retract(
        self, *, record: colrev.record.Record, main_record_dict: dict
    ) -> bool:
        if record.check_potential_retracts():
            self.review_manager.logger.info(
                f"{colors.GREEN}Found paper retract: "
                f"{main_record_dict['ID']}{colors.END}"
            )
            main_record = colrev.record.Record(data=main_record_dict)
            main_record.prescreen_exclude(reason="retracted", print_warning=True)
            main_record.remove_field(key="warning")
            return True
        return False

    def __update_existing_record_forthcoming(
        self, *, record: colrev.record.Record, main_record_dict: dict
    ) -> None:
        if "forthcoming" == main_record_dict.get(
            "year", ""
        ) and "forthcoming" != record.data.get("year", ""):
            self.review_manager.logger.info(
                f"{colors.GREEN}Update published forthcoming paper: "
                f"{record.data['ID']}{colors.END}"
            )
            # prepared_record = crossref_prep.prepare(prep_operation, record)
            main_record_dict["year"] = record.data["year"]
            record = colrev.record.PrepRecord(data=main_record_dict)

    def __update_existing_record_fields(
        self,
        *,
        record_dict: dict,
        main_record_dict: dict,
        prev_record_dict_version: dict,
        update_time_variant_fields: bool,
        origin: str,
        source: colrev.settings.SearchSource,
    ) -> None:
        for key, value in record_dict.items():
            if (
                not update_time_variant_fields
                and key in colrev.record.Record.time_variant_fields
            ):
                continue

            if key in ["curation_ID"]:
                continue

            if key in colrev.record.Record.provenance_keys + ["ID"]:
                continue

            if key not in main_record_dict:
                if key in main_record_dict.get("colrev_masterdata_provenance", {}):
                    if (
                        main_record_dict["colrev_masterdata_provenance"][key]["source"]
                        == "colrev_curation.masterdata_restrictions"
                        and main_record_dict["colrev_masterdata_provenance"][key][
                            "note"
                        ]
                        == "not-missing"
                    ):
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
                if source.get_origin_prefix() != "md_curated.bib":
                    if prev_record_dict_version.get(key, "NA") != main_record_dict.get(
                        key, "OTHER"
                    ):
                        continue
                main_record = colrev.record.Record(data=main_record_dict)
                if value.replace(" - ", ": ") == main_record.data[key].replace(
                    " - ", ": "
                ):
                    continue
                if key == "url" and "dblp.org" in value and key in main_record.data:
                    continue
                main_record.update_field(
                    key=key,
                    value=value,
                    source=origin,
                    keep_source_if_equal=True,
                    append_edit=False,
                )

    def __forthcoming_published(self, *, record_dict: dict, prev_record: dict) -> bool:
        # Forthcoming paper published if volume and number are assigned
        # i.e., no longer UNKNOWN
        if (
            record_dict.get("volume", "") != "UNKNOWN"
            and prev_record.get("volume", "UNKNOWN") == "UNKNOWN"
            and record_dict.get("number", "") != "UNKNOWN"
            and prev_record.get("volume", "UNKNOWN") == "UNKNOWN"
        ):
            return True
        return False

    def update_existing_record(
        self,
        *,
        records: dict,
        record_dict: dict,
        prev_record_dict_version: dict,
        source: colrev.settings.SearchSource,
        update_time_variant_fields: bool,
    ) -> bool:
        """Convenience function to update existing records (main data/records.bib)"""

        origin = f"{source.get_origin_prefix()}/{record_dict['ID']}"
        main_record_dict = self.__get_record_based_on_origin(
            origin=origin, records=records
        )

        if main_record_dict == {}:
            self.review_manager.logger.debug(f"Could not update {record_dict['ID']}")
            return False

        # TBD: in curated masterdata repositories?

        record = colrev.record.Record(data=record_dict)
        changed = self.__update_existing_record_retract(
            record=record, main_record_dict=main_record_dict
        )
        self.__update_existing_record_forthcoming(
            record=record, main_record_dict=main_record_dict
        )

        if (
            "CURATED" in main_record_dict.get("colrev_masterdata_provenance", {})
            and "md_curated.bib" != source.get_origin_prefix()
        ):
            return False

        similarity_score = colrev.record.Record.get_record_similarity(
            record_a=colrev.record.Record(data=record_dict),
            record_b=colrev.record.Record(data=prev_record_dict_version),
        )
        dict_diff = colrev.record.Record(data=record_dict).get_diff(
            other_record=colrev.record.Record(data=prev_record_dict_version)
        )

        self.__update_existing_record_fields(
            record_dict=record_dict,
            main_record_dict=main_record_dict,
            prev_record_dict_version=prev_record_dict_version,
            update_time_variant_fields=update_time_variant_fields,
            origin=origin,
            source=source,
        )

        if self.__have_changed(
            record_a_orig=main_record_dict, record_b_orig=prev_record_dict_version
        ) or self.__have_changed(  # Note : not (yet) in the main records but changed
            record_a_orig=record_dict, record_b_orig=prev_record_dict_version
        ):
            changed = True
            if self.__forthcoming_published(
                record_dict=record_dict, prev_record=prev_record_dict_version
            ):
                self.review_manager.logger.info(
                    f" {colors.GREEN}forthcoming paper published: "
                    f"{main_record_dict['ID']}{colors.END}"
                )
            elif similarity_score > 0.98:
                self.review_manager.logger.info(f" check/update {origin}")
            else:
                self.review_manager.logger.info(
                    f" {colors.RED} check/update {origin} leads to substantial changes "
                    f"({similarity_score}) in {main_record_dict['ID']}:{colors.END}"
                )
                self.review_manager.p_printer.pprint(
                    [x for x in dict_diff if "change" == x[0]]
                )

        return changed
