#! /usr/bin/env python
"""CoLRev prep operation: Prepare record metadata."""
from __future__ import annotations

import inspect
import logging
import multiprocessing as mp
import time
import typing
from copy import deepcopy
from datetime import datetime
from datetime import timedelta
from multiprocessing import Value
from multiprocessing.pool import ThreadPool as Pool
from pathlib import Path
from typing import Optional

import timeout_decorator
from requests.exceptions import ConnectionError as requests_ConnectionError
from requests.exceptions import ReadTimeout

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.record
import colrev.settings
import colrev.ui_cli.cli_colors as colors

# pylint: disable=too-many-lines

# logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("requests_cache").setLevel(logging.ERROR)

PREP_COUNTER = Value("i", 0)


class Prep(colrev.operation.Operation):
    """Prepare records (metadata)"""

    # pylint: disable=too-many-instance-attributes

    timeout = 30
    max_retries_on_error = 3

    retrieval_similarity: float

    first_round: bool
    last_round: bool

    debug_mode: bool

    pad: int

    polish: bool

    prep_package_endpoints: dict[str, typing.Any]

    requests_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"
    }

    # pylint: disable=duplicate-code
    fields_to_keep = [
        "ID",
        "ENTRYTYPE",
        "colrev_status",
        "colrev_origin",
        "colrev_masterdata_provenance",
        "colrev_data_provenance",
        "colrev_pid",
        "author",
        "year",
        "title",
        "journal",
        "booktitle",
        "chapter",
        "series",
        "volume",
        "number",
        "pages",
        "doi",
        "abstract",
        "school",
        "editor",
        "book-group-author",
        "book-author",
        "keywords",
        "file",
        "fulltext",
        "publisher",
        "dblp_key",
        "sem_scholar_id",
        "url",
        "isbn",
        "address",
        "edition",
        "warning",
        "crossref",
        "date",
        "wos_accession_number",
        "link",
        "url",
        "crossmark",
        "warning",
        "note",
        "issn",
        "language",
        "howpublished",
        "cited_by",
        "cited_by_file",
    ]

    __cpu = 1
    __prep_commit_id = "HEAD"

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
        retrieval_similarity: float = 1.0,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.prep,
            notify_state_transition_operation=notify_state_transition_operation,
        )
        self.notify_state_transition_operation = notify_state_transition_operation

        self.fields_to_keep += self.review_manager.settings.prep.fields_to_keep

        self.retrieval_similarity = retrieval_similarity

        self.polish = False
        self.debug_mode = False
        self.pad = 0
        self.__stats: typing.Dict[str, typing.List[timedelta]] = {}

    def __add_stats(
        self, *, prep_round_package_endpoint: dict, start_time: datetime
    ) -> None:
        if prep_round_package_endpoint["endpoint"] not in self.__stats:
            self.__stats[prep_round_package_endpoint["endpoint"]] = [
                datetime.now() - start_time
            ]
        else:
            self.__stats[prep_round_package_endpoint["endpoint"]].append(
                datetime.now() - start_time
            )

    def __print_stats(self) -> None:
        if self.review_manager.verbose_mode:
            print("Runtime statistics (averages)")
            averaged_list = [
                {
                    "script": script,
                    "average": sum(deltalist, timedelta(0)) / len(deltalist),
                }
                for script, deltalist in self.__stats.items()
            ]
            for item in sorted(
                averaged_list,
                key=lambda k: k["average"],  # type: ignore
                reverse=True,
            ):
                average_time_str = (
                    f"{item['average'].seconds}."  # type: ignore
                    f"{item['average'].microseconds}"  # type: ignore
                )
                average_time = float(average_time_str)
                average_time = round(average_time, 2)
                average_time_str = f"{average_time:.2f}"
                print(
                    f"{item['script']} ".ljust(50, " ")
                    + ":"
                    + f"{average_time_str} s".rjust(10, " ")
                )
            print()

    def __print_diffs_for_debug(
        self,
        *,
        prior: colrev.record.PrepRecord,
        preparation_record: colrev.record.PrepRecord,
        prep_package_endpoint: colrev.env.package_manager.PrepPackageEndpointInterface,
    ) -> None:
        if not self.debug_mode:
            return

        diffs = prior.get_diff(other_record=preparation_record)
        if diffs:
            change_report = (
                f"{prep_package_endpoint}"
                f' on {preparation_record.data["ID"]}'
                " changed:\n"
                f"{colors.ORANGE}{self.review_manager.p_printer.pformat(diffs)}{colors.END}\n"
            )

            self.review_manager.logger.info(change_report)
            self.review_manager.logger.info(
                "To correct errors in the endpoint,"
                " open an issue at "
                "https://github.com/CoLRev-Environment/colrev/issues"
            )
            self.review_manager.logger.info(
                "To correct potential errors at source,"
                f" {prep_package_endpoint.source_correction_hint}"
            )
            input("Press Enter to continue")
            print("\n")
        else:
            self.review_manager.logger.debug(
                f"{prep_package_endpoint}"
                f' on {preparation_record.data["ID"]}'
                " changed: -"
            )
            print("\n")
            time.sleep(0.1)

    def __package_prep(
        self,
        prep_round_package_endpoint: dict,
        record: colrev.record.PrepRecord,
        preparation_record: colrev.record.PrepRecord,
    ) -> None:
        try:
            if (
                prep_round_package_endpoint["endpoint"].lower()
                not in self.prep_package_endpoints
            ):
                return
            endpoint = self.prep_package_endpoints[
                prep_round_package_endpoint["endpoint"].lower()
            ]

            if self.debug_mode:
                self.review_manager.logger.info(
                    f"{endpoint.settings.endpoint}(...) called"
                )

            prior = preparation_record.copy_prep_rec()

            start_time = datetime.now()
            preparation_record = endpoint.prepare(self, preparation_record)
            self.__add_stats(
                start_time=start_time,
                prep_round_package_endpoint=prep_round_package_endpoint,
            )

            self.__print_diffs_for_debug(
                prior=prior,
                preparation_record=preparation_record,
                prep_package_endpoint=endpoint,
            )

            if endpoint.always_apply_changes:
                record.update_by_record(update_record=preparation_record)

            if preparation_record.preparation_save_condition():
                record.update_by_record(update_record=preparation_record)
                if not self.polish:
                    record.update_masterdata_provenance()

            if preparation_record.preparation_break_condition() and not self.polish:
                record.update_by_record(update_record=preparation_record)
                raise colrev_exceptions.PreparationBreak
        except (timeout_decorator.timeout_decorator.TimeoutError, ReadTimeout):
            self.__add_stats(
                start_time=start_time,
                prep_round_package_endpoint=prep_round_package_endpoint,
            )
            if self.review_manager.verbose_mode:
                self.review_manager.logger.error(
                    f" {colors.RED}{record.data['ID']}".ljust(45)
                    + f"{endpoint.settings.endpoint}(...) timed out{colors.END}{colors.END}"
                )

        except colrev_exceptions.ServiceNotAvailableException as exc:
            if self.review_manager.force_mode:
                self.__add_stats(
                    start_time=start_time,
                    prep_round_package_endpoint=prep_round_package_endpoint,
                )
                self.review_manager.logger.error(exc)
            else:
                raise exc

    def __print_post_package_prep_info(
        self,
        record: colrev.record.PrepRecord,
        item: dict,
        prior_state: colrev.record.RecordState,
    ) -> None:
        # pylint: disable=redefined-outer-name,invalid-name
        with PREP_COUNTER.get_lock():
            PREP_COUNTER.value += 1  # type: ignore
        progress = ""
        if item["nr_items"] > 100:
            progress = f"({PREP_COUNTER.value}/{item['nr_items']}) ".rjust(  # type: ignore
                12, " "
            )

        if record.preparation_break_condition():
            if (
                colrev.record.RecordState.rev_prescreen_excluded
                == record.data["colrev_status"]
            ):
                if self.review_manager.verbose_mode:
                    self.review_manager.logger.info(
                        f" {colors.RED}{record.data['ID']}".ljust(46)
                        + f"Detected: {record.data.get('prescreen_exclusion', 'NA')}"
                        + f"{colors.END}"
                    )
                target_state = colrev.record.RecordState.rev_prescreen_excluded
                if self.polish:
                    target_state = prior_state
                self.review_manager.logger.info(
                    f" {colors.RED}{record.data['ID']}".ljust(46)
                    + f"{progress}{prior_state} →  {target_state}"
                    + f"{colors.END}"
                )
            else:
                target_state = colrev.record.RecordState.md_needs_manual_preparation
                if self.polish:
                    target_state = prior_state
                self.review_manager.logger.info(
                    f" {colors.ORANGE}{record.data['ID']}".ljust(46)
                    + f"{progress}{prior_state} →  {target_state}{colors.END}"
                )

        elif record.preparation_save_condition():
            curation_addition = "   "
            if record.masterdata_is_curated():
                curation_addition = " ✔ "
            target_state = colrev.record.RecordState.md_prepared
            if self.polish:
                target_state = prior_state
            self.review_manager.logger.info(
                f" {colors.GREEN}{record.data['ID']}".ljust(46)
                + f"{progress}{prior_state} →  {target_state}{colors.END}{curation_addition}"
            )
        else:
            target_state = colrev.record.RecordState.md_needs_manual_preparation
            if self.polish:
                target_state = prior_state
            self.review_manager.logger.info(
                f" {colors.ORANGE}{record.data['ID']}".ljust(46)
                + f"{progress}{prior_state} →  {target_state}{colors.END}"
            )

    def __post_package_prep(
        self,
        record: colrev.record.PrepRecord,
        preparation_record: colrev.record.PrepRecord,
        item: dict,
        prior_state: colrev.record.RecordState,
    ) -> None:
        if not self.review_manager.verbose_mode:
            self.__print_post_package_prep_info(
                record=record, item=item, prior_state=prior_state
            )

        if self.last_round and not self.polish:
            if record.status_to_prepare():
                for key in list(record.data.keys()):
                    if key not in self.fields_to_keep:
                        record.remove_field(key=key)
                    elif record.data[key] in ["", "NA"]:
                        record.remove_field(key=key)
                record.update_by_record(update_record=preparation_record)
                # Note: update_masterdata_provenance sets to md_needs_manual_preparation
                record.update_masterdata_provenance()

        if self.polish:
            record.set_status(target_state=prior_state)

    # Note : no named arguments for multiprocessing
    def prepare(self, item: dict) -> dict:
        """Prepare a record (based on package_endpoints in the settings)"""

        record: colrev.record.PrepRecord = item["record"]

        if not record.status_to_prepare() and not self.polish:
            return record.get_data()

        if self.review_manager.verbose_mode:
            self.review_manager.logger.info(" prep " + record.data["ID"])

        # preparation_record changes with each endpoint and
        # eventually replaces record (if md_prepared or endpoint.always_apply_changes)
        preparation_record = record.copy_prep_rec()
        prior_state = record.data["colrev_status"]

        for prep_round_package_endpoint in deepcopy(
            item["prep_round_package_endpoints"]
        ):
            try:
                self.__package_prep(
                    prep_round_package_endpoint,
                    record,
                    preparation_record,
                )
            except colrev_exceptions.PreparationBreak:
                break

        self.__post_package_prep(
            record=record,
            preparation_record=preparation_record,
            item=item,
            prior_state=prior_state,
        )

        return record.get_data()

    def __select_record_list_for_reset(self, *, record_list: list[dict]) -> list[dict]:
        record_list = [
            rec
            for rec in record_list
            if str(rec["colrev_status"])
            in [
                str(colrev.record.RecordState.md_prepared),
                str(colrev.record.RecordState.md_needs_manual_preparation),
            ]
        ]

        for rec in [
            rec
            for rec in record_list
            if str(rec["colrev_status"])
            not in [
                str(colrev.record.RecordState.md_prepared),
                str(colrev.record.RecordState.md_needs_manual_preparation),
            ]
        ]:
            msg = (
                f"{rec['ID']}: status must be md_prepared/md_needs_manual_preparation "
                + f'(is {rec["colrev_status"]})'
            )
            self.review_manager.logger.error(msg)
            self.review_manager.report_logger.error(msg)
        return record_list

    def __get_revlist_for_reset(self) -> typing.Iterator[tuple]:
        git_repo = self.review_manager.dataset.get_repo()
        revlist = (
            (
                commit.hexsha,
                commit.message,
                (
                    commit.tree / str(self.review_manager.dataset.RECORDS_FILE_RELATIVE)
                ).data_stream.read(),
            )
            for commit in git_repo.iter_commits(
                paths=str(self.review_manager.dataset.RECORDS_FILE_RELATIVE)
            )
        )
        return revlist

    def __reset(self, *, record_list: list[dict]) -> None:
        record_list = self.__select_record_list_for_reset(record_list=record_list)
        revlist = self.__get_revlist_for_reset()

        record_reset_list = [[record, deepcopy(record)] for record in record_list]

        for commit_id, cmsg, filecontents in list(revlist):
            cmsg_l1 = str(cmsg).split("\n", maxsplit=1)[0]
            if "colrev load" not in cmsg:
                print(f"Skip {str(commit_id)} (non-load commit) - {str(cmsg_l1)}")
                continue
            print(f"Check {str(commit_id)} - {str(cmsg_l1)}")

            prior_records_dict = self.review_manager.dataset.load_records_dict(
                load_str=filecontents.decode("utf-8")
            )
            for prior_record in prior_records_dict.values():
                if str(prior_record["colrev_status"]) != str(
                    colrev.record.RecordState.md_imported
                ):
                    continue
                for record_to_unmerge, record in record_reset_list:
                    if any(
                        o in prior_record["colrev_origin"]
                        for o in record["colrev_origin"]
                    ):
                        self.review_manager.report_logger.info(
                            f'reset({record["ID"]}) to'
                            f"\n{self.review_manager.p_printer.pformat(prior_record)}\n\n"
                        )
                        # Note : we don't want to restore the old ID...
                        current_id = record_to_unmerge["ID"]
                        record_to_unmerge.clear()
                        for key, value in prior_record.items():
                            record_to_unmerge[key] = value
                        record_to_unmerge["ID"] = current_id
                        break
                # Stop if all original records have been found
                if (
                    len(
                        [
                            x["colrev_status"] != "md_imported"
                            for x, y in record_reset_list
                        ]
                    )
                    == 0
                ):
                    break

        for record_to_unmerge, record in record_reset_list:
            record_to_unmerge.update(
                colrev_status=colrev.record.RecordState.md_needs_manual_preparation
            )

    def reset_records(self, *, reset_ids: list) -> None:
        """Reset records based on IDs"""
        # Note: entrypoint for CLI

        records = self.review_manager.dataset.load_records_dict()
        records_to_reset = []
        for reset_id in reset_ids:
            if reset_id in records:
                records_to_reset.append(records[reset_id])
            else:
                print(f"Error: record not found (ID={reset_id})")

        self.__reset(record_list=records_to_reset)

        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()
        self.review_manager.create_commit(
            msg="Reset metadata for manual preparation",
        )

    def set_ids(self) -> None:
        """Set IDs (regenerate). In force-mode, all IDs are regenerated and PDFs are renamed"""
        self.review_manager.logger.info("Set IDs")
        records = self.review_manager.dataset.load_records_dict()
        self.review_manager.dataset.set_ids(records=records, selected_ids=list(records))
        for record_dict in records.values():
            if "file" not in record_dict:
                continue

            if str(Path(record_dict["file"]).name) == f'{record_dict["ID"]}.pdf':
                continue

            old_filename = record_dict["file"]
            new_filename = Path(record_dict["file"]).parent / Path(
                f'{record_dict["ID"]}.pdf'
            )
            try:
                Path(record_dict["file"]).rename(new_filename)
            except FileNotFoundError:
                print(f"rename error: {record_dict['file']}")
                continue
            record_dict["file"] = str(new_filename)
            if "colrev_data_provenance" in record_dict:
                for value in record_dict["colrev_data_provenance"].values():
                    if value["source"] == old_filename:
                        value["source"] = value["source"].replace(
                            old_filename, str(new_filename)
                        )
            if "colrev_masterdata_provenance" in record_dict:
                for value in record_dict["colrev_masterdata_provenance"].values():
                    if value["source"] == old_filename:
                        value["source"] = value["source"].replace(
                            old_filename, str(new_filename)
                        )

            # simple heuristic:
            pdfs_origin_file = Path("data/search/pdfs.bib")
            if pdfs_origin_file.is_file():
                colrev.env.utils.inplace_change(
                    filename=pdfs_origin_file,
                    old_string=old_filename,
                    new_string=str(new_filename),
                )
                self.review_manager.dataset.add_changes(path=pdfs_origin_file)

        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()

        self.review_manager.create_commit(
            msg="Set IDs",
        )

    def reset_ids(self) -> None:
        """Reset the IDs of records"""
        # Note: entrypoint for CLI

        records = self.review_manager.dataset.load_records_dict()

        prior_records_dict = next(
            self.review_manager.dataset.load_records_from_history()
        )
        for record in records.values():
            prior_record_l = [
                x
                for x in prior_records_dict.values()
                if x["colrev_origin"] == record["colrev_origin"]
            ]
            if len(prior_record_l) != 1:
                continue
            prior_record = prior_record_l[0]
            record["ID"] = prior_record["ID"]

        self.review_manager.dataset.save_records_dict(records=records)

    def setup_custom_script(self) -> None:
        """Setup a custom prep script"""

        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/custom_scripts/custom_prep_script.py")
        )
        if filedata:
            with open("custom_prep_script.py", "w", encoding="utf-8") as file:
                file.write(filedata.decode("utf-8"))

        self.review_manager.dataset.add_changes(path=Path("custom_prep_script.py"))

        prep_round = self.review_manager.settings.prep.prep_rounds[-1]
        prep_round.prep_package_endpoints.append({"endpoint": "custom_prep_script"})
        self.review_manager.save_settings()

    def __load_prep_data(self, *, polish: bool = False) -> dict:
        records_headers = self.review_manager.dataset.load_records_dict(
            header_only=True
        )
        record_header_list = list(records_headers.values())

        pad = (
            35
            if (0 == len(record_header_list))
            else min((max(len(x["ID"]) for x in record_header_list) + 2), 35)
        )

        r_states_to_prepare = [
            colrev.record.RecordState.md_imported,
            colrev.record.RecordState.md_needs_manual_preparation,
        ]
        if polish:
            r_states_to_prepare = list(colrev.record.RecordState)

        items = list(
            self.review_manager.dataset.read_next_record(
                conditions=[{"colrev_status": s} for s in r_states_to_prepare]
            )
        )

        prep_data = {
            "nr_tasks": len(items),
            "PAD": pad,
            "items": list(items),
        }

        return prep_data

    def __get_preparation_data(
        self,
        *,
        prep_round: colrev.settings.PrepRound,
        debug_file: Optional[Path] = None,
        debug_ids: str,
        polish: bool = False,
    ) -> list:
        if self.debug_mode:
            prepare_data = self.__load_prep_data_for_debug(
                debug_ids=debug_ids, debug_file=debug_file
            )
            if prepare_data["nr_tasks"] == 0:
                print("ID not found in history.")
        else:
            prepare_data = self.__load_prep_data(polish=polish)

        if self.debug_mode:
            self.review_manager.logger.info(
                "In this round, we set the similarity "
                f"threshold ({self.retrieval_similarity})"
            )
            input("Press Enter to continue")
            self.review_manager.logger.info(
                f"prepare_data: "
                f"{self.review_manager.p_printer.pformat(prepare_data)}"
            )
        self.pad = prepare_data["PAD"]
        items = prepare_data["items"]
        prep_data = []
        nr_items = len(items)
        for item in items:
            prep_data.append(
                {
                    "record": colrev.record.PrepRecord(data=item),
                    "nr_items": nr_items,
                    # Note : we cannot load endpoints here
                    # because pathos/multiprocessing
                    # does not support functions as parameters
                    "prep_round_package_endpoints": prep_round.prep_package_endpoints,
                    "prep_round": prep_round.name,
                }
            )
        return prep_data

    def __retrieve_records_from_history(
        self,
        *,
        original_records: list[dict],
        condition_state: colrev.record.RecordState,
    ) -> list:
        retrieved, prior_records = [], []
        for (
            prior_records_dict
        ) in self.review_manager.dataset.load_records_from_history():
            for prior_record in prior_records_dict.values():
                if prior_record.get("colrev_status", "NA") != condition_state:
                    continue
                for original_record in original_records:
                    if any(
                        o in prior_record["colrev_origin"]
                        for o in original_record["colrev_origin"]
                    ):
                        prior_records.append(prior_record)
                        # only take the latest version (i.e., drop the record)
                        # Note: only append the first one if origins were in
                        # different records (after deduplication)
                        retrieved.append(original_record["ID"])
                original_records = [
                    orec for orec in original_records if orec["ID"] not in retrieved
                ]

        return prior_records

    def __load_prep_data_for_debug(
        self, *, debug_ids: str, debug_file: Optional[Path] = None
    ) -> dict:
        if debug_file:
            with open(debug_file, encoding="utf8") as target_db:
                records_dict = self.review_manager.dataset.load_records_dict(
                    load_str=target_db.read()
                )

            for record_dict in records_dict.values():
                if colrev.record.RecordState.md_imported != record_dict.get(
                    "state", ""
                ):
                    self.review_manager.logger.info(
                        f"Setting colrev_status to md_imported {record_dict['ID']}"
                    )
                    record = colrev.record.Record(data=record_dict)
                    record.set_status(
                        target_state=colrev.record.RecordState.md_imported
                    )
            debug_ids_list = list(records_dict.keys())
            debug_ids = ",".join(debug_ids_list)
            self.review_manager.logger.info("Imported record (retrieved from file)")

        else:
            records = []
            debug_ids_list = debug_ids.split(",")
            original_records = list(
                self.review_manager.dataset.read_next_record(
                    conditions=[{"ID": ID} for ID in debug_ids_list]
                )
            )
            # self.review_manager.logger.info("Current record")
            # self.review_manager.p_printer.pprint(original_records)
            records = self.__retrieve_records_from_history(
                original_records=original_records,
                condition_state=colrev.record.RecordState.md_imported,
            )

        if len(records) == 0:
            prep_data = {"nr_tasks": 0, "PAD": 0, "items": []}
        else:
            prep_data = {
                "nr_tasks": len(debug_ids_list),
                "PAD": len(debug_ids),
                "items": records,
            }
        return prep_data

    def __setup_prep_round(
        self, *, i: int, prep_round: colrev.settings.PrepRound
    ) -> None:
        # pylint: disable=redefined-outer-name,invalid-name
        PREP_COUNTER = Value("i", 0)
        with PREP_COUNTER.get_lock():
            PREP_COUNTER.value = 0  # type: ignore

        self.first_round = bool(i == 0)

        self.last_round = bool(
            i == len(self.review_manager.settings.prep.prep_rounds) - 1
        )

        # Note : we add the endpoint automatically (not as part of the settings.json)
        # because it must always be executed at the end
        if prep_round.name not in ["source_specific_prep", "exclusion"]:
            prep_round.prep_package_endpoints.append(
                {"endpoint": "colrev.update_metadata_status"}
            )

        if self.debug_mode:
            print("\n\n")

        if len(self.review_manager.settings.prep.prep_rounds) > 1:
            self.review_manager.logger.info(f"Prepare ({prep_round.name})")

        self.retrieval_similarity = prep_round.similarity  # type: ignore
        self.review_manager.report_logger.debug(
            f"Set retrieval_similarity={self.retrieval_similarity}"
        )

        required_prep_package_endpoints = list(prep_round.prep_package_endpoints)
        required_prep_package_endpoints.append(
            {"endpoint": "colrev.update_metadata_status"}
        )

        package_manager = self.review_manager.get_package_manager()
        self.prep_package_endpoints: dict[
            str, typing.Any
        ] = package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.prep,
            selected_packages=required_prep_package_endpoints,
            operation=self,
            only_ci_supported=self.review_manager.in_ci_environment(),
        )
        non_available_endpoints = [
            x["endpoint"].lower()
            for x in required_prep_package_endpoints
            if x["endpoint"].lower() not in self.prep_package_endpoints
        ]
        if non_available_endpoints:
            if self.review_manager.in_ci_environment():
                raise colrev_exceptions.ServiceNotAvailableException(
                    dep=f"colrev prep ({','.join(non_available_endpoints)})",
                    detailed_trace="prep not available in ci environment",
                )
            raise colrev_exceptions.ServiceNotAvailableException(
                dep="colrev prep", detailed_trace="prep not available"
            )

        for endpoint_name, endpoint in self.prep_package_endpoints.items():
            check_function = getattr(endpoint, "check_availability", None)
            if callable(check_function):
                self.review_manager.logger.debug(
                    f"Check availability of {endpoint_name}"
                )
                endpoint.check_availability(source_operation=self)  # type: ignore

    def __log_record_change_scores(
        self, *, preparation_data: list, prepared_records: list
    ) -> None:
        for previous_record_item in preparation_data:
            previous_record = previous_record_item["record"]
            prepared_record = [
                r for r in prepared_records if r["ID"] == previous_record.data["ID"]
            ][0]

            change = colrev.record.Record.get_record_change_score(
                record_a=colrev.record.Record(data=prepared_record),
                record_b=previous_record,
            )
            if change > 0.05:
                self.review_manager.report_logger.info(
                    f' {prepared_record["ID"]} ' + f"Change score: {round(change, 2)}"
                )

    def __log_details(self, *, prepared_records: list) -> None:
        nr_recs = len(
            [
                record
                for record in prepared_records
                if "CURATED" in record["colrev_masterdata_provenance"]
            ]
        )

        self.review_manager.logger.info(
            "Overall curated (✔)".ljust(29)
            + f"{colors.GREEN}{nr_recs}{colors.END}".rjust(20, " ")
            + " records"
        )

        nr_recs = len(
            [
                record
                for record in prepared_records
                if record["colrev_status"] == colrev.record.RecordState.md_prepared
            ]
        )

        self.review_manager.logger.info(
            "Overall md_prepared".ljust(29)
            + f"{colors.GREEN}{nr_recs}{colors.END}".rjust(20, " ")
            + " records"
        )

        nr_recs = len(
            [
                record
                for record in prepared_records
                if record["colrev_status"]
                == colrev.record.RecordState.md_needs_manual_preparation
            ]
        )
        if nr_recs > 0:
            self.review_manager.logger.info(
                "To prepare manually".ljust(29)
                + f"{colors.ORANGE}{nr_recs}{colors.END}".rjust(20, " ")
                + " records"
            )

        nr_recs = len(
            [
                record
                for record in prepared_records
                if record["colrev_status"]
                == colrev.record.RecordState.rev_prescreen_excluded
            ]
        )
        if nr_recs > 0:
            self.review_manager.logger.info(
                "Records prescreen-excluded".ljust(29)
                + f"{colors.RED}{nr_recs}{colors.END}".rjust(20, " ")
            )

    def skip_prep(self) -> None:
        """Skip the preparation"""

        records = self.review_manager.dataset.load_records_dict()

        for record_dict in records.values():
            if colrev.record.RecordState.md_imported == record_dict["colrev_status"]:
                record = colrev.record.Record(data=record_dict)
                record.set_status(target_state=colrev.record.RecordState.md_prepared)
        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()
        self.review_manager.create_commit(msg="Skip prep")

    def __initialize_prep(self, *, polish: bool, debug_ids: str, cpu: int) -> None:
        if not polish:
            self.review_manager.logger.info("Prep")
        else:
            self.review_manager.logger.info("Prep (polish mode)")
        self.review_manager.logger.info(
            "Prep completes and corrects record metadata based on APIs and preparation rules."
        )
        self.polish = polish
        if self.polish:
            self.review_manager.logger.info(
                "Polish mode: consider all records but prevent state transitions."
            )
        self.review_manager.logger.info(
            "See https://colrev.readthedocs.io/en/latest/manual/metadata_retrieval/prep.html"
        )

        if self.debug_mode:
            print("\n\n\n")
            self.review_manager.logger.info("Start debug prep\n")
            self.review_manager.logger.info(
                "The debugger will replay the preparation procedures"
                " step-by-step, allow you to identify potential errors, trace them to "
                "their colrev_origin and correct them."
            )
            input("\nPress Enter to continue")
            print("\n\n")

        if debug_ids != "NA":
            self.debug_mode = True

        self.__cpu = cpu

        # Note: for unit testing, we use a simple loop (instead of parallel)
        # to ensure that the IDs of feed records don't change
        unit_testing = "test_prep" == inspect.stack()[1][3]
        if unit_testing or self.debug_mode:
            self.__cpu = 1

    def __prep_packages_ram_heavy(self, prep_round: colrev.settings.PrepRound) -> bool:
        prep_pe_names = [r["endpoint"] for r in prep_round.prep_package_endpoints]
        ram_reavy = "colrev.exclude_languages" in prep_pe_names  # type: ignore
        self.review_manager.logger.info(
            "Info: The language detector requires RAM and may take longer"
        )
        return ram_reavy

    def __get_prep_pool(
        self, *, prep_round: colrev.settings.PrepRound
    ) -> mp.pool.ThreadPool:
        if self.__prep_packages_ram_heavy(prep_round=prep_round):
            pool = Pool(mp.cpu_count() // 2)
        else:
            # Note : if we use too many CPUS,
            # a "too many open files" exception is thrown
            pool = Pool(self.__cpu)
        self.review_manager.logger.info(
            "Info: ✔ = quality-assured by CoLRev community curators"
        )
        return pool

    def __create_prep_commit(
        self,
        *,
        previous_preparation_data: list,
        prepared_records: list,
        prep_round: colrev.settings.PrepRound,
    ) -> None:
        self.__log_record_change_scores(
            preparation_data=previous_preparation_data,
            prepared_records=prepared_records,
        )

        if not self.debug_mode:
            self.review_manager.dataset.save_records_dict(
                records={r["ID"]: r for r in prepared_records}, partial=True
            )

            self.__log_details(prepared_records=prepared_records)

            self.review_manager.create_commit(
                msg=f"Prepare records ({prep_round.name})",
            )
            self.__prep_commit_id = (
                self.review_manager.dataset.get_repo().head.commit.hexsha
            )
            if not self.review_manager.high_level_operation:
                print()
        self.review_manager.reset_report_logger()

        self.__print_stats()

    def __post_prep(self) -> None:
        if not self.review_manager.high_level_operation:
            print()

        self.review_manager.logger.info("To validate the changes, use")

        self.review_manager.logger.info(
            f"{colors.ORANGE}colrev validate {self.__prep_commit_id}{colors.END}"
        )
        if not self.review_manager.high_level_operation:
            print()

        self.review_manager.logger.info(
            f"{colors.GREEN}Completed prep operation{colors.END}"
        )
        if self.review_manager.in_ci_environment():
            print("\n\n")

    def main(
        self,
        *,
        keep_ids: bool = False,
        debug_ids: str = "NA",
        debug_file: Optional[Path] = None,
        cpu: int = 4,
        polish: bool = False,
    ) -> None:
        """Preparation of records (main entrypoint)"""

        self.__initialize_prep(polish=polish, debug_ids=debug_ids, cpu=cpu)

        try:
            for i, prep_round in enumerate(
                self.review_manager.settings.prep.prep_rounds
            ):
                self.__setup_prep_round(i=i, prep_round=prep_round)

                preparation_data = self.__get_preparation_data(
                    prep_round=prep_round,
                    debug_file=debug_file,
                    debug_ids=debug_ids,
                    polish=polish,
                )
                previous_preparation_data = deepcopy(preparation_data)

                if len(preparation_data) == 0:
                    self.review_manager.logger.info("No records to prepare.")
                    print()
                    return

                if self.__cpu == 1:
                    # Note: preparation_data is not turned into a list of records.
                    prepared_records = []
                    for item in preparation_data:
                        record = self.prepare(item)
                        prepared_records.append(record)
                else:
                    pool = self.__get_prep_pool(prep_round=prep_round)
                    prepared_records = pool.map(self.prepare, preparation_data)
                    pool.close()
                    pool.join()

                self.__create_prep_commit(
                    previous_preparation_data=previous_preparation_data,
                    prepared_records=prepared_records,
                    prep_round=prep_round,
                )

        except requests_ConnectionError as exc:
            if "OSError(24, 'Too many open files" in str(exc):
                raise colrev_exceptions.ServiceNotAvailableException(
                    "Too many files opened (OSError, Errno24). "
                    "To use a smaller number of parallel processes, run colrev prep --cpu 1"
                ) from exc
            raise exc

        except OSError as exc:
            if 24 == exc.errno:
                raise colrev_exceptions.ServiceNotAvailableException(
                    "Too many files opened (OSError, Errno24). "
                    "To use a smaller number of parallel processes, run colrev prep --cpu 1"
                ) from exc
            raise exc

        if not keep_ids and not self.debug_mode:
            self.review_manager.logger.info("Set record IDs")
            self.review_manager.dataset.set_ids()
            self.review_manager.create_commit(msg="Set IDs")

        self.__post_prep()


if __name__ == "__main__":
    pass
