#! /usr/bin/env python
from __future__ import annotations

import logging
import multiprocessing as mp
import pkgutil
import time
import typing
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING

import git
import timeout_decorator
from pathos.multiprocessing import ProcessPool

import colrev.built_in.database_connectors as db_connectors
import colrev.built_in.prep as built_in_prep
import colrev.cli_colors as colors
import colrev.process
import colrev.record
import colrev.settings

if TYPE_CHECKING:
    import colrev.review_manager.ReviewManager

logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("requests_cache").setLevel(logging.ERROR)


class Prep(colrev.process.Process):

    timeout = 10
    max_retries_on_error = 3

    retrieval_similarity: float

    first_round: bool
    last_round: bool

    pad: int

    prep_scripts: dict[str, typing.Any]

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
        "colrev_id",
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

    built_in_scripts: dict[str, dict[str, typing.Any]] = {
        "load_fixes": {
            "endpoint": built_in_prep.LoadFixesPrep,
        },
        "exclude_non_latin_alphabets": {
            "endpoint": built_in_prep.ExcludeNonLatinAlphabetsPrep,
        },
        "exclude_languages": {
            "endpoint": built_in_prep.ExcludeLanguagesPrep,
        },
        "exclude_collections": {
            "endpoint": built_in_prep.ExcludeCollectionsPrep,
        },
        "remove_urls_with_500_errors": {
            "endpoint": built_in_prep.RemoveError500URLsPrep,
        },
        "remove_broken_IDs": {
            "endpoint": built_in_prep.RemoveBrokenIDPrep,
        },
        "global_ids_consistency_check": {
            "endpoint": built_in_prep.GlobalIDConsistencyPrep,
        },
        "prep_curated": {
            "endpoint": built_in_prep.CuratedPrep,
        },
        "format": {
            "endpoint": built_in_prep.FormatPrep,
        },
        "resolve_crossrefs": {
            "endpoint": built_in_prep.BibTexCrossrefResolutionPrep,
        },
        "get_doi_from_sem_scholar": {
            "endpoint": built_in_prep.SemanticScholarPrep,
        },
        "get_doi_from_urls": {"endpoint": built_in_prep.DOIFromURLsPrep},
        "get_masterdata_from_doi": {
            "endpoint": built_in_prep.DOIMetadataPrep,
        },
        "get_masterdata_from_crossref": {
            "endpoint": built_in_prep.CrossrefMetadataPrep,
        },
        "get_masterdata_from_dblp": {
            "endpoint": built_in_prep.DBLPMetadataPrep,
        },
        "get_masterdata_from_open_library": {
            "endpoint": built_in_prep.OpenLibraryMetadataPrep,
        },
        "get_masterdata_from_citeas": {
            "endpoint": built_in_prep.CiteAsPrep,
        },
        "get_year_from_vol_iss_jour_crossref": {
            "endpoint": built_in_prep.CrossrefYearVolIssPrep,
        },
        "get_record_from_local_index": {
            "endpoint": built_in_prep.LocalIndexPrep,
        },
        "remove_nicknames": {
            "endpoint": built_in_prep.RemoveNicknamesPrep,
        },
        "format_minor": {
            "endpoint": built_in_prep.FormatMinorPrep,
        },
        "drop_fields": {
            "endpoint": built_in_prep.DropFieldsPrep,
        },
        "remove_redundant_fields": {
            "endpoint": built_in_prep.RemoveRedundantFieldPrep,
        },
        "correct_recordtype": {
            "endpoint": built_in_prep.CorrectRecordTypePrep,
        },
        "update_metadata_status": {
            "endpoint": built_in_prep.UpdateMetadataStatusPrep,
        },
    }

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
        debug: str = "NA",
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            process_type=colrev.process.ProcessType.prep,
            notify_state_transition_operation=notify_state_transition_operation,
            debug=(debug != "NA"),
        )
        self.notify_state_transition_operation = notify_state_transition_operation

        self.fields_to_keep += self.review_manager.settings.prep.fields_to_keep

        self.cpus: int = self.cpus * 4
        self.pad = 0

    def check_dbs_availability(self) -> None:

        # TODO : check_status as a default method for the PreparationInterface
        # and iterate over it?

        self.review_manager.logger.info("Check availability of connectors...")
        db_connectors.CrossrefConnector.check_status(prep_operation=self)
        self.review_manager.logger.info("CrossrefConnector available")
        db_connectors.DBLPConnector.check_status(prep_operation=self)
        self.review_manager.logger.info("DBLPConnector available")
        db_connectors.OpenLibraryConnector.check_status(prep_operation=self)
        self.review_manager.logger.info("OpenLibraryConnector available")

        print()

    def __print_diffs_for_debug(
        self,
        *,
        prior: colrev.record.PrepRecord,
        preparation_record: colrev.record.PrepRecord,
        prep_script: colrev.process.PrepEndpoint,
    ) -> None:
        diffs = prior.get_diff(other_record=preparation_record)
        if diffs:
            change_report = (
                f"{prep_script}"
                f'({preparation_record.data["ID"]})'
                f" changed:\n{self.review_manager.p_printer.pformat(diffs)}\n"
            )
            if self.review_manager.debug_mode:
                self.review_manager.logger.info(change_report)
                self.review_manager.logger.info(
                    "To correct errors in the script,"
                    " open an issue at "
                    "https://github.com/geritwagner/colrev/issues"
                )
                self.review_manager.logger.info(
                    "To correct potential errors at source,"
                    f" {prep_script.source_correction_hint}"
                )
                input("Press Enter to continue")
                print("\n")
        else:
            self.review_manager.logger.debug(f"{prep_script.prepare} changed: -")
            if self.review_manager.debug_mode:
                print("\n")
                time.sleep(0.3)

    # Note : no named arguments for multiprocessing
    def prepare(self, item: dict) -> dict:

        record: colrev.record.PrepRecord = item["record"]

        if not record.status_to_prepare():
            return record.get_data()

        self.review_manager.logger.info(" prep " + record.data["ID"])

        # preparation_record changes with each script and
        # eventually replaces record (if md_prepared or endpoint.always_apply_changes)
        preparation_record = record.copy_prep_rec()

        # unprepared_record will not change (for diffs)
        unprepared_record = record.copy_prep_rec()

        for prep_round_script in deepcopy(item["prep_round_scripts"]):

            try:
                prep_script = self.prep_scripts[prep_round_script["endpoint"]]

                if self.review_manager.debug_mode:
                    self.review_manager.logger.info(
                        f"{prep_script.settings.name}(...) called"
                    )

                prior = preparation_record.copy_prep_rec()

                preparation_record = prep_script.prepare(self, preparation_record)

                self.__print_diffs_for_debug(
                    prior=prior,
                    preparation_record=preparation_record,
                    prep_script=prep_script,
                )

                if prep_script.always_apply_changes:
                    record.update_by_record(update_record=preparation_record)

                if preparation_record.preparation_save_condition():
                    record.update_by_record(update_record=preparation_record)
                    record.update_masterdata_provenance(
                        unprepared_record=unprepared_record,
                        review_manager=self.review_manager,
                    )

                if preparation_record.preparation_break_condition():
                    record.update_by_record(update_record=preparation_record)
                    break
            except timeout_decorator.timeout_decorator.TimeoutError:
                self.review_manager.logger.error(
                    f"{colors.RED}{prep_script.settings.name}(...) timed out{colors.END}"
                )

        if self.last_round:
            if record.status_to_prepare():
                record.update_by_record(update_record=preparation_record)
                # Note: update_masterdata_provenance sets to md_needs_manual_preparation
                record.update_masterdata_provenance(
                    unprepared_record=unprepared_record,
                    review_manager=self.review_manager,
                )

        return record.get_data()

    def reset(self, *, record_list: list[dict]) -> None:

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

        record_reset_list = [[record, deepcopy(record)] for record in record_list]

        git_repo = git.Repo(str(self.review_manager.path))
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
                        for o in record["colrev_origin"].split(";")
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

        # TODO : double-check! resetting the prep does not necessarily mean
        # that wrong records were merged...
        # TODO : if any record_to_unmerge['status'] != RecordState.md_imported:
        # retrieve the original record from the search/source file
        for record_to_unmerge, record in record_reset_list:
            record_to_unmerge.update(
                colrev_status=colrev.record.RecordState.md_needs_manual_preparation
            )

    def reset_records(self, *, reset_ids: list) -> None:
        # Note: entrypoint for CLI

        records = self.review_manager.dataset.load_records_dict()
        records_to_reset = []
        for reset_id in reset_ids:
            if reset_id in records:
                records_to_reset.append(records[reset_id])
            else:
                print(f"Error: record not found (ID={reset_id})")

        self.reset(record_list=records_to_reset)

        saved_args = {"reset_records": ",".join(reset_ids)}
        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()
        self.review_manager.create_commit(
            msg="Reset metadata for manual preparation",
            script_call="colrev prep",
            saved_args=saved_args,
        )

    def reset_ids(self) -> None:
        # Note: entrypoint for CLI

        records = self.review_manager.dataset.load_records_dict()

        git_repo = self.review_manager.dataset.get_repo()
        records_file_relative = self.review_manager.dataset.RECORDS_FILE_RELATIVE
        revlist = (
            ((commit.tree / str(records_file_relative)).data_stream.read())
            for commit in git_repo.iter_commits(paths=str(records_file_relative))
        )
        filecontents = next(revlist)  # noqa
        prior_records_dict = self.review_manager.dataset.load_records_dict(
            load_str=filecontents.decode("utf-8")
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

        filedata = pkgutil.get_data(__name__, "template/custom_prep_script.py")
        if filedata:
            with open("custom_prep_script.py", "w", encoding="utf-8") as file:
                file.write(filedata.decode("utf-8"))

        self.review_manager.dataset.add_changes(path=Path("custom_prep_script.py"))

        prep_round = self.review_manager.settings.prep.prep_rounds[-1]
        prep_round.scripts.append({"endpoint": "custom_prep_script"})
        self.review_manager.save_settings()

    def main(
        self,
        *,
        keep_ids: bool = False,
        debug_ids: str = "NA",
        debug_file: str = "NA",
    ) -> None:
        """Preparation of records"""

        saved_args = locals()

        self.check_dbs_availability()

        if self.review_manager.debug_mode:
            print("\n\n\n")
            self.review_manager.logger.info("Start debug prep\n")
            self.review_manager.logger.info(
                "The script will replay the preparation procedures"
                " step-by-step, allow you to identify potential errors, trace them to "
                "their colrev_origin and correct them."
            )
            input("\nPress Enter to continue")
            print("\n\n")

        if not keep_ids:
            del saved_args["keep_ids"]

        def load_prep_data():

            record_state_list = self.review_manager.dataset.get_record_state_list()
            nr_tasks = len(
                [
                    x
                    for x in record_state_list
                    if str(colrev.record.RecordState.md_imported) == x["colrev_status"]
                ]
            )

            if 0 == len(record_state_list):
                pad = 35
            else:
                pad = min((max(len(x["ID"]) for x in record_state_list) + 2), 35)

            r_states_to_prepare = [
                colrev.record.RecordState.md_imported,
                colrev.record.RecordState.md_prepared,
                colrev.record.RecordState.md_needs_manual_preparation,
            ]
            items = self.review_manager.dataset.read_next_record(
                conditions=[{"colrev_status": s} for s in r_states_to_prepare]
            )

            prior_ids = [
                x["ID"]
                for x in record_state_list
                if str(colrev.record.RecordState.md_imported) == x["colrev_status"]
            ]

            prep_data = {
                "nr_tasks": nr_tasks,
                "PAD": pad,
                "items": list(items),
                "prior_ids": prior_ids,
            }
            self.review_manager.logger.debug(
                self.review_manager.p_printer.pformat(prep_data)
            )
            return prep_data

        def get_preparation_data(*, prep_round: colrev.settings.PrepRound) -> list:
            if self.review_manager.debug_mode:
                prepare_data = load_prep_data_for_debug(
                    debug_ids=debug_ids, debug_file=debug_file
                )
                if prepare_data["nr_tasks"] == 0:
                    print("ID not found in history.")
            else:
                prepare_data = load_prep_data()

            if self.review_manager.debug_mode:
                self.review_manager.logger.info(
                    "In this round, we set the similarity "
                    f"threshold ({self.retrieval_similarity})"
                )
                input("Press Enter to continue")
                print("\n\n")
                self.review_manager.logger.info(
                    f"prepare_data: "
                    f"{self.review_manager.p_printer.pformat(prepare_data)}"
                )
            self.pad = prepare_data["PAD"]
            items = prepare_data["items"]
            prep_data = []
            for item in items:
                prep_data.append(
                    {
                        "record": colrev.record.PrepRecord(data=item),
                        # Note : we cannot load scripts here
                        # because pathos/multiprocessing
                        # does not support functions as parameters
                        "prep_round_scripts": prep_round.scripts,
                        "prep_round": prep_round.name,
                    }
                )
            return prep_data

        def load_prep_data_for_debug(*, debug_ids: str, debug_file: str = "NA") -> dict:

            self.review_manager.logger.info("Data passed to the scripts")
            if debug_file is None:
                debug_file = "NA"
            if "NA" != debug_file:
                with open(debug_file, encoding="utf8") as target_db:
                    records_dict = self.review_manager.dataset.load_records_dict(
                        load_str=target_db.read()
                    )

                for record in records_dict.values():
                    if colrev.record.RecordState.md_imported != record.get("state", ""):
                        self.review_manager.logger.info(
                            f"Setting colrev_status to md_imported {record['ID']}"
                        )
                        record["colrev_status"] = colrev.record.RecordState.md_imported
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
                records = self.review_manager.dataset.retrieve_records_from_history(
                    original_records=original_records,
                    condition_state=colrev.record.RecordState.md_imported,
                )
                self.review_manager.logger.info(
                    "Imported record (retrieved from history)"
                )

            if len(records) == 0:
                prep_data = {"nr_tasks": 0, "PAD": 0, "items": [], "prior_ids": []}
            else:
                print(colrev.record.PrepRecord(data=records[0]))
                input("Press Enter to continue")
                print("\n\n")
                prep_data = {
                    "nr_tasks": len(debug_ids_list),
                    "PAD": len(debug_ids),
                    "items": records,
                    "prior_ids": [debug_ids_list],
                }
            return prep_data

        def setup_prep_round(*, i, prep_round) -> None:

            if i == 0:
                self.first_round = True

            else:
                self.first_round = False

            if i == len(self.review_manager.settings.prep.prep_rounds) - 1:
                self.last_round = True
            else:
                self.last_round = False

            # Note : we add the script automatically (not as part of the settings.json)
            # because it must always be executed at the end
            if prep_round.name not in ["load_fixes", "exclusion"]:
                prep_round.scripts.append({"endpoint": "update_metadata_status"})

            self.review_manager.logger.info(f"Prepare ({prep_round.name})")

            self.retrieval_similarity = prep_round.similarity  # type: ignore
            saved_args["similarity"] = self.retrieval_similarity
            self.review_manager.report_logger.debug(
                f"Set retrieval_similarity={self.retrieval_similarity}"
            )

            required_prep_scripts = list(prep_round.scripts)

            required_prep_scripts.append({"endpoint": "update_metadata_status"})

            adapter_manager = self.review_manager.get_adapter_manager()
            self.prep_scripts = adapter_manager.load_scripts(
                process=self,
                scripts=required_prep_scripts,
            )

        def log_details(*, prepared_records: list) -> None:
            nr_recs = len(
                [
                    record
                    for record in prepared_records
                    if record["colrev_status"] == colrev.record.RecordState.md_prepared
                ]
            )

            self.review_manager.logger.info(
                "Records prepared:".ljust(35) + f"{colors.GREEN}{nr_recs}{colors.END}"
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
                self.review_manager.report_logger.info(
                    f"Statistics: {nr_recs} records not prepared"
                )
                self.review_manager.logger.info(
                    "Records to prepare manually:".ljust(35)
                    + f"{colors.ORANGE}{nr_recs}{colors.END}"
                )
            else:
                self.review_manager.logger.info(
                    "Records to prepare manually:".ljust(35) + f"{nr_recs}"
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
                self.review_manager.report_logger.info(
                    f"Statistics: {nr_recs} records (prescreen) excluded "
                    "(non-latin alphabet)"
                )
                self.review_manager.logger.info(
                    "Records prescreen-excluded:".ljust(35)
                    + f"{colors.GREEN}{nr_recs}{colors.END}"
                )

        if "NA" != debug_ids:
            self.review_manager.debug_mode = True

        for i, prep_round in enumerate(self.review_manager.settings.prep.prep_rounds):

            setup_prep_round(i=i, prep_round=prep_round)

            preparation_data = get_preparation_data(prep_round=prep_round)

            if len(preparation_data) == 0:
                print("No records to prepare.")
                return

            if self.review_manager.debug_mode:
                # Note: preparation_data is not turned into a list of records.
                prepared_records = []
                for item in preparation_data:
                    record = self.prepare(item)
                    prepared_records.append(record)
            else:
                # Note : p_map shows the progress (tqdm) but it is inefficient
                # https://github.com/swansonk14/p_tqdm/issues/34
                # from p_tqdm import p_map
                # preparation_data = p_map(self.prepare, preparation_data)

                script_names = [r["endpoint"] for r in prep_round.scripts]
                if "exclude_languages" in script_names:  # type: ignore
                    self.review_manager.logger.info(
                        f"{colors.ORANGE}The language detector may take "
                        f"longer and require RAM{colors.END}"
                    )
                    pool = ProcessPool(nodes=mp.cpu_count() // 2)
                else:
                    pool = ProcessPool(nodes=self.cpus)
                prepared_records = pool.map(self.prepare, preparation_data)

                pool.close()
                pool.join()
                pool.clear()

            if not self.review_manager.debug_mode:
                # prepared_records = [x.get_data() for x in prepared_records]
                self.review_manager.dataset.save_record_list_by_id(
                    record_list=prepared_records
                )

                log_details(prepared_records=prepared_records)

                self.review_manager.create_commit(
                    msg=f"Prepare records ({prep_round.name})",
                    script_call="colrev prep",
                    saved_args=saved_args,
                )
                self.review_manager.reset_log()
                print()

        if not keep_ids and not self.review_manager.debug_mode:
            self.review_manager.dataset.set_ids()
            self.review_manager.create_commit(
                msg="Set IDs", script_call="colrev prep", saved_args=saved_args
            )


if __name__ == "__main__":
    pass
