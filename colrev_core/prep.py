#! /usr/bin/env python
import logging
import multiprocessing as mp
import time
import typing
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import dictdiffer
import git
import requests_cache
from pathos.multiprocessing import ProcessPool

from colrev_core.environment import AdapterManager
from colrev_core.environment import EnvironmentManager
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import PrepRecord
from colrev_core.record import RecordState

logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("requests_cache").setLevel(logging.ERROR)


class Preparation(Process):

    PAD = 0
    TIMEOUT = 10
    MAX_RETRIES_ON_ERROR = 3

    requests_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"
    }

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

    # session = requests_cache.CachedSession("requests_cache")
    cache_path = EnvironmentManager.colrev_path / Path("prep_requests_cache")
    session = requests_cache.CachedSession(
        str(cache_path), backend="sqlite", expire_after=timedelta(days=30)
    )

    from colrev_core.built_in import prep as built_in_prep

    built_in_scripts: typing.Dict[str, typing.Dict[str, typing.Any]] = {
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
            "endpoint": built_in_prep.CrossrefResolutionPrep,
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
            "endpoint": built_in_prep.FormatMinorPRep,
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
        REVIEW_MANAGER,
        force=False,
        similarity: float = 0.9,
        notify_state_transition_process: bool = True,
        debug: str = "NA",
    ):
        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            type=ProcessType.prep,
            notify_state_transition_process=notify_state_transition_process,
            debug=(debug != "NA"),
        )
        self.notify_state_transition_process = notify_state_transition_process

        self.RETRIEVAL_SIMILARITY = similarity

        self.fields_to_keep += self.REVIEW_MANAGER.settings.prep.fields_to_keep

        # if similarity == 0.0:  # if it has not been set use default
        # saved_args["RETRIEVAL_SIMILARITY"] = self.RETRIEVAL_SIMILARITY
        # RETRIEVAL_SIMILARITY = self.RETRIEVAL_SIMILARITY
        # saved_args["RETRIEVAL_SIMILARITY"] = similarity

        self.CPUS = self.CPUS * 1

        required_prep_scripts = [
            s["endpoint"]
            for r in REVIEW_MANAGER.settings.prep.prep_rounds
            for s in r.scripts
        ]
        required_prep_scripts.append("update_metadata_status")

        self.prep_scripts: typing.Dict[
            str, typing.Dict[str, typing.Any]
        ] = AdapterManager.load_scripts(
            PROCESS=self,
            scripts=required_prep_scripts,
        )

    def check_DBs_availability(self) -> None:
        from colrev_core.built_in import database_connectors as database_connectors

        # TODO : check_status as a default method for the PreparationInterface
        # and iterate over it?

        self.REVIEW_MANAGER.logger.info("Check availability of connectors...")
        database_connectors.CrossrefConnector.check_status(PREPARATION=self)
        self.REVIEW_MANAGER.logger.info("CrossrefConnector available")
        database_connectors.DBLPConnector.check_status(PREPARATION=self)
        self.REVIEW_MANAGER.logger.info("DBLPConnector available")
        database_connectors.OpenLibraryConnector.check_status(PREPARATION=self)
        self.REVIEW_MANAGER.logger.info("OpenLibraryConnector available")

        print()
        return

    # TODO : integrate the following ?
    # e.g.,
    # class SemanticScholarPrep(SemanticScholarConnector)
    # with SemanticScholarConnector implementing the methods to retrieve the metadata
    # Generally: design a connector class that may implement

    # Note : no named arguments for multiprocessing
    def prepare(self, item: dict) -> dict:

        RECORD = item["record"]

        # TODO : if we exclude the RecordState.md_prepared
        # from all of the following prep-scripts, we are missing out
        # on potential improvements...
        # if RecordState.md_imported != record["colrev_status"]:
        if RECORD.data["colrev_status"] not in [
            RecordState.md_imported,
            # RecordState.md_prepared, # avoid changing prepared records
            RecordState.md_needs_manual_preparation,
        ]:
            return RECORD

        self.REVIEW_MANAGER.logger.info("Prepare " + RECORD.data["ID"])

        #  preparation_record will change and eventually replace record (if successful)
        preparation_record = deepcopy(RECORD.get_data())

        # UNPREPARED_RECORD will not change (for diffs)
        UNPREPARED_RECORD = PrepRecord(data=deepcopy(RECORD.get_data()))

        # Note: we require (almost) perfect matches for the scripts.
        # Cases with higher dissimilarity will be handled in the prep_man.py
        # Note : the record should always be the first element of the list.
        # Note : we need to rerun all preparation scripts because records are not stored
        # if not prepared successfully.

        # TODO : extract the following in a function
        SF_REC = PrepRecord(data=deepcopy(RECORD.get_data()))
        SF_REC.drop_fields(self)

        preparation_details = []
        preparation_details.append(
            f'prepare({RECORD.data["ID"]})' + f" called with: \n{SF_REC}\n\n"
        )

        for settings_prep_script in item["prep_round_scripts"]:

            # Note : we have to select scripts here because pathos/multiprocessing
            # does not support functions as parameters
            prep_script = self.prep_scripts[settings_prep_script["endpoint"]]

            # startTime = datetime.now()

            prior = deepcopy(preparation_record)

            if self.REVIEW_MANAGER.DEBUG_MODE:
                self.REVIEW_MANAGER.logger.info(f"{prep_script}(...) called")

            PREPARATION_RECORD = PrepRecord(data=preparation_record)
            PREPARATION_RECORD = prep_script["endpoint"].prepare(
                self, PREPARATION_RECORD
            )
            preparation_record = PREPARATION_RECORD.get_data()

            diffs = list(dictdiffer.diff(prior, preparation_record))
            if diffs:
                # print(PREPARATION_RECORD)
                change_report = (
                    f"{prep_script}"
                    f'({preparation_record["ID"]})'
                    f" changed:\n{self.REVIEW_MANAGER.pp.pformat(diffs)}\n"
                )
                preparation_details.append(change_report)
                if self.REVIEW_MANAGER.DEBUG_MODE:
                    self.REVIEW_MANAGER.logger.info(change_report)
                    self.REVIEW_MANAGER.logger.info(
                        "To correct errors in the script,"
                        " open an issue at "
                        "https://github.com/geritwagner/colrev_core/issues"
                    )
                    self.REVIEW_MANAGER.logger.info(
                        "To correct potential errors at source,"
                        f" {prep_script['endpoint'].source_correction_hint}"
                    )
                    input("Press Enter to continue")
                    print("\n")
            else:
                self.REVIEW_MANAGER.logger.debug(f"{prep_script} changed: -")
                if self.REVIEW_MANAGER.DEBUG_MODE:
                    print("\n")
                    time.sleep(0.3)

            # TODO : the endpoints may have a boolean flag indicating whether
            # the changes should be applied always or only when there is a
            # change in record status
            if "load_fixes" == settings_prep_script["endpoint"]:
                RECORD.data = deepcopy(preparation_record)

            if preparation_record["colrev_status"] in [
                RecordState.rev_prescreen_excluded,
                RecordState.md_prepared,
            ] or "disagreement with " in preparation_record.get(
                "colrev_masterdata_provenance", ""
            ):
                RECORD.data = deepcopy(preparation_record)
                RECORD.update_masterdata_provenance(
                    UNPREPARED_RECORD=UNPREPARED_RECORD,
                    REVIEW_MANAGER=self.REVIEW_MANAGER,
                )
                break

            # diff = (datetime.now() - startTime).total_seconds()
            # with open("stats.csv", "a", encoding="utf8") as f:
            #     f.write(f'{prep_script};{record["ID"]};{diff};\n')

        # TODO : deal with "crossmark" in preparation_record

        if self.LAST_ROUND:
            if RECORD.data["colrev_status"] in [
                RecordState.md_needs_manual_preparation,
                RecordState.md_imported,
            ]:
                RECORD.data = deepcopy(preparation_record)
                RECORD.update_masterdata_provenance(
                    UNPREPARED_RECORD=UNPREPARED_RECORD,
                    REVIEW_MANAGER=self.REVIEW_MANAGER,
                )
        else:
            if self.REVIEW_MANAGER.DEBUG_MODE:
                if (
                    RecordState.md_needs_manual_preparation
                    == preparation_record["colrev_status"]
                ):
                    self.REVIEW_MANAGER.logger.debug(
                        "Resetting values (instead of saving them)."
                    )
                    # for the readability of diffs,
                    # we change records only once (in the last round)

        # TBD: rely on colrev prep --debug ID (instead of printing everyting?)
        # for preparation_detail in preparation_details:
        #     self.REVIEW_MANAGER.report_logger.info(preparation_detail)
        return RECORD

    def __log_details(self, *, preparation_batch: list) -> None:

        nr_recs = len(
            [
                record
                for record in preparation_batch
                if record["colrev_status"] == RecordState.md_needs_manual_preparation
            ]
        )
        if nr_recs > 0:
            self.REVIEW_MANAGER.report_logger.info(
                f"Statistics: {nr_recs} records not prepared"
            )

        nr_recs = len(
            [
                record
                for record in preparation_batch
                if record["colrev_status"] == RecordState.rev_prescreen_excluded
            ]
        )
        if nr_recs > 0:
            self.REVIEW_MANAGER.report_logger.info(
                f"Statistics: {nr_recs} records (prescreen) excluded "
                "(non-latin alphabet)"
            )

        return

    def reset(self, *, record_list: typing.List[dict]):
        from colrev_core.prep_man import PrepMan

        record_list = [
            r
            for r in record_list
            if str(r["colrev_status"])
            in [
                str(RecordState.md_prepared),
                str(RecordState.md_needs_manual_preparation),
            ]
        ]

        for r in [
            r
            for r in record_list
            if str(r["colrev_status"])
            not in [
                str(RecordState.md_prepared),
                str(RecordState.md_needs_manual_preparation),
            ]
        ]:
            msg = (
                f"{r['ID']}: status must be md_prepared/md_needs_manual_preparation "
                + f'(is {r["colrev_status"]})'
            )
            self.REVIEW_MANAGER.logger.error(msg)
            self.REVIEW_MANAGER.report_logger.error(msg)

        record_reset_list = [[record, deepcopy(record)] for record in record_list]

        MAIN_REFERENCES_RELATIVE = self.REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]
        git_repo = git.Repo(str(self.REVIEW_MANAGER.paths["REPO_DIR"]))
        revlist = (
            (
                commit.hexsha,
                commit.message,
                (commit.tree / str(MAIN_REFERENCES_RELATIVE)).data_stream.read(),
            )
            for commit in git_repo.iter_commits(paths=str(MAIN_REFERENCES_RELATIVE))
        )

        for commit_id, cmsg, filecontents in list(revlist):
            cmsg_l1 = str(cmsg).split("\n")[0]
            if "colrev load" not in cmsg:
                print(f"Skip {str(commit_id)} (non-load commit) - {str(cmsg_l1)}")
                continue
            print(f"Check {str(commit_id)} - {str(cmsg_l1)}")

            prior_records_dict = self.REVIEW_MANAGER.REVIEW_DATASET.load_records(
                load_str=filecontents.decode("utf-8")
            )
            for prior_record in prior_records_dict.values():
                if str(prior_record["colrev_status"]) != str(RecordState.md_imported):
                    continue
                for record_to_unmerge, record in record_reset_list:

                    if any(
                        o in prior_record["colrev_origin"]
                        for o in record["colrev_origin"].split(";")
                    ):
                        self.REVIEW_MANAGER.report_logger.info(
                            f'reset({record["ID"]}) to'
                            f"\n{self.REVIEW_MANAGER.pp.pformat(prior_record)}\n\n"
                        )
                        # Note : we don't want to restore the old ID...
                        current_id = record_to_unmerge["ID"]
                        record_to_unmerge.clear()
                        for k, v in prior_record.items():
                            record_to_unmerge[k] = v
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

        PREP_MAN = PrepMan(REVIEW_MANAGER=self.REVIEW_MANAGER)
        # TODO : double-check! resetting the prep does not necessarily mean
        # that wrong records were merged...
        # TODO : if any record_to_unmerge['status'] != RecordState.md_imported:
        # retrieve the original record from the search/source file
        for record_to_unmerge, record in record_reset_list:
            PREP_MAN.append_to_non_dupe_db(
                record_to_unmerge_original=record_to_unmerge, record_original=record
            )
            record_to_unmerge.update(
                colrev_status=RecordState.md_needs_manual_preparation
            )

        return

    def reset_records(self, *, reset_ids: list) -> None:
        # Note: entrypoint for CLI

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        records_to_reset = []
        for reset_id in reset_ids:
            if reset_id in records:
                records_to_reset.append(records[reset_id])
            else:
                print(f"Error: record not found (ID={reset_id})")

        self.reset(record_list=records_to_reset)

        saved_args = {"reset_records": ",".join(reset_ids)}
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        # self.REVIEW_MANAGER.format_references()
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        self.REVIEW_MANAGER.create_commit(
            msg="Reset metadata for manual preparation",
            script_call="colrev prep",
            saved_args=saved_args,
        )
        return

    def reset_ids(self) -> None:
        # Note: entrypoint for CLI

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        git_repo = self.REVIEW_MANAGER.REVIEW_DATASET.get_repo()
        MAIN_REFERENCES_RELATIVE = self.REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]
        revlist = (
            ((commit.tree / str(MAIN_REFERENCES_RELATIVE)).data_stream.read())
            for commit in git_repo.iter_commits(paths=str(MAIN_REFERENCES_RELATIVE))
        )
        filecontents = next(revlist)  # noqa
        prior_records_dict = self.REVIEW_MANAGER.REVIEW_DATASET.load_records(
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

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)

        return

    def set_ids(
        self,
    ) -> None:
        # Note: entrypoint for CLI

        self.REVIEW_MANAGER.REVIEW_DATASET.set_IDs()
        self.REVIEW_MANAGER.create_commit(msg="Set IDs")

        return

    def print_doi_metadata(self, *, doi: str) -> None:
        """CLI entrypoint"""

        from colrev_core.built_in import database_connectors

        DOI_METADATA = database_connectors.DOIMetadataPrep()

        DUMMY_R = PrepRecord(data={"doi": doi})
        RECORD = DOI_METADATA.prepare(self, DUMMY_R)
        print(RECORD)

        if "url" in RECORD.data:
            print("Metadata retrieved from website:")

            URL_CONNECTOR = database_connectors.URLConnector()
            RECORD = URL_CONNECTOR.retrieve_md_from_url(RECORD=RECORD, PREPARATION=self)
            print(RECORD)

        return

    def setup_custom_script(self) -> None:
        import pkgutil

        filedata = pkgutil.get_data(__name__, "template/custom_prep_script.py")
        if filedata:
            with open("custom_prep_script.py", "w") as file:
                file.write(filedata.decode("utf-8"))

        self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(path="custom_prep_script.py")

        prep_round = self.REVIEW_MANAGER.settings.prep.prep_rounds[-1]
        prep_round.scripts.append("custom_prep_script")
        self.REVIEW_MANAGER.save_settings()

        return

    def main(
        self,
        *,
        keep_ids: bool = False,
        debug_ids: str = "NA",
        debug_file: str = "NA",
    ) -> None:
        """Preparation of records"""
        from colrev_core.settings import PrepRound

        saved_args = locals()

        self.check_DBs_availability()

        if self.REVIEW_MANAGER.DEBUG_MODE:
            print("\n\n\n")
            self.REVIEW_MANAGER.logger.info("Start debug prep\n")
            self.REVIEW_MANAGER.logger.info(
                "The script will replay the preparation procedures"
                " step-by-step, allow you to identify potential errors, trace them to "
                "their colrev_origin and correct them."
            )
            input("\nPress Enter to continue")
            print("\n\n")

        if not keep_ids:
            del saved_args["keep_ids"]

        def load_prep_data():
            from colrev_core.record import RecordState

            record_state_list = (
                self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
            )
            nr_tasks = len(
                [
                    x
                    for x in record_state_list
                    if str(RecordState.md_imported) == x["colrev_status"]
                ]
            )

            PAD = min((max(len(x["ID"]) for x in record_state_list) + 2), 35)

            items = self.REVIEW_MANAGER.REVIEW_DATASET.read_next_record(
                conditions=[
                    {"colrev_status": RecordState.md_imported},
                    {"colrev_status": RecordState.md_prepared},
                    {"colrev_status": RecordState.md_needs_manual_preparation},
                ],
            )

            prior_ids = [
                x["ID"]
                for x in record_state_list
                if str(RecordState.md_imported) == x["colrev_status"]
            ]

            prep_data = {
                "nr_tasks": nr_tasks,
                "PAD": PAD,
                "items": list(items),
                "prior_ids": prior_ids,
            }
            self.REVIEW_MANAGER.logger.debug(self.REVIEW_MANAGER.pp.pformat(prep_data))
            return prep_data

        def get_preparation_batch(*, prep_round: PrepRound):
            if self.REVIEW_MANAGER.DEBUG_MODE:
                prepare_data = load_prep_data_for_debug(
                    debug_ids=debug_ids, debug_file=debug_file
                )
                if prepare_data["nr_tasks"] == 0:
                    print("ID not found in history.")
            else:
                prepare_data = load_prep_data()

            if self.REVIEW_MANAGER.DEBUG_MODE:
                self.REVIEW_MANAGER.logger.info(
                    "In this round, we set the similarity "
                    f"threshold ({self.RETRIEVAL_SIMILARITY})"
                )
                input("Press Enter to continue")
                print("\n\n")
                self.REVIEW_MANAGER.logger.info(
                    f"prepare_data: " f"{self.REVIEW_MANAGER.pp.pformat(prepare_data)}"
                )
            self.PAD = prepare_data["PAD"]
            items = prepare_data["items"]
            batch = []
            for item in items:
                batch.append(
                    {
                        "record": PrepRecord(data=item),
                        "prep_round_scripts": prep_round.scripts,
                        "prep_round": prep_round.name,
                    }
                )
            return batch

        def load_prep_data_for_debug(
            *, debug_ids: str, debug_file: str = "NA"
        ) -> typing.Dict:

            self.REVIEW_MANAGER.logger.info("Data passed to the scripts")
            if debug_file is None:
                debug_file = "NA"
            if "NA" != debug_file:
                with open(debug_file, encoding="utf8") as target_db:
                    records_dict = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                        load_str=target_db.read()
                    )

                for record in records_dict.values():
                    if RecordState.md_imported != record.get("state", ""):
                        self.REVIEW_MANAGER.logger.info(
                            f"Setting colrev_status to md_imported {record['ID']}"
                        )
                        record["colrev_status"] = RecordState.md_imported
                debug_ids_list = list(records_dict.keys())
                debug_ids = ",".join(debug_ids_list)
                self.REVIEW_MANAGER.logger.info("Imported record (retrieved from file)")

            else:
                records = []
                debug_ids_list = debug_ids.split(",")
                REVIEW_DATASET = self.REVIEW_MANAGER.REVIEW_DATASET
                original_records = list(
                    REVIEW_DATASET.read_next_record(
                        conditions=[{"ID": ID} for ID in debug_ids_list]
                    )
                )
                # self.REVIEW_MANAGER.logger.info("Current record")
                # self.REVIEW_MANAGER.pp.pprint(original_records)
                records = REVIEW_DATASET.retrieve_records_from_history(
                    original_records=original_records,
                    condition_state=RecordState.md_imported,
                )
                self.REVIEW_MANAGER.logger.info(
                    "Imported record (retrieved from history)"
                )

            if len(records) == 0:
                prep_data = {"nr_tasks": 0, "PAD": 0, "items": [], "prior_ids": []}
            else:
                print(PrepRecord(data=records[0]))
                input("Press Enter to continue")
                print("\n\n")
                prep_data = {
                    "nr_tasks": len(debug_ids_list),
                    "PAD": len(debug_ids),
                    "items": records,
                    "prior_ids": [debug_ids_list],
                }
            return prep_data

        def setup_prep_round(*, i, prep_round):

            if i == 0:
                self.FIRST_ROUND = True

            else:
                self.FIRST_ROUND = False

            if i == len(self.REVIEW_MANAGER.settings.prep.prep_rounds) - 1:
                self.LAST_ROUND = True
            else:
                self.LAST_ROUND = False

            # Note : we add the script automatically (not as part of the settings.json)
            # because it must always be executed at the end
            if prep_round.name not in ["load_fixes", "exclusion"]:
                prep_round.scripts.append({"endpoint": "update_metadata_status"})

            # Note : can set selected prep scripts/rounds in the settings...
            # if self.FIRST_ROUND and not self.REVIEW_MANAGER.DEBUG_MODE:
            #     if prepare_data["nr_tasks"] < 20:
            #         self.REVIEW_MANAGER.logger.info(
            #             "Less than 20 records: prepare in one batch."
            #         )
            #         modes = [m for m in modes if "low_confidence" == m["name"]]
            # use one mode/run to avoid multiple commits

            self.REVIEW_MANAGER.logger.info(f"Prepare ({prep_round.name})")
            if self.FIRST_ROUND:
                self.session.remove_expired_responses()  # Note : this takes long...

            self.RETRIEVAL_SIMILARITY = prep_round.similarity  # type: ignore
            saved_args["similarity"] = self.RETRIEVAL_SIMILARITY
            self.REVIEW_MANAGER.report_logger.debug(
                f"Set RETRIEVAL_SIMILARITY={self.RETRIEVAL_SIMILARITY}"
            )
            return

        if "NA" != debug_ids:
            self.REVIEW_MANAGER.DEBUG_MODE = True

        for i, prep_round in enumerate(self.REVIEW_MANAGER.settings.prep.prep_rounds):

            setup_prep_round(i=i, prep_round=prep_round)

            preparation_batch = get_preparation_batch(prep_round=prep_round)
            if len(preparation_batch) == 0:
                return

            if self.REVIEW_MANAGER.DEBUG_MODE:
                # Note: preparation_batch is not turned into a list of records.
                preparation_batch_items = preparation_batch
                preparation_batch = []
                for item in preparation_batch_items:
                    r = self.prepare(item)
                    preparation_batch.append(r)
            else:
                # Note : p_map shows the progress (tqdm) but it is inefficient
                # https://github.com/swansonk14/p_tqdm/issues/34
                # from p_tqdm import p_map
                # preparation_batch = p_map(self.prepare, preparation_batch)

                if "exclude_languages" in prep_round.scripts:  # type: ignore
                    pool = ProcessPool(nodes=mp.cpu_count() // 2)
                else:
                    pool = ProcessPool(nodes=self.CPUS)
                preparation_batch = pool.map(self.prepare, preparation_batch)

                pool.close()
                pool.join()
                pool.clear()

            if not self.REVIEW_MANAGER.DEBUG_MODE:
                preparation_batch = [x.get_data() for x in preparation_batch]
                self.REVIEW_MANAGER.REVIEW_DATASET.save_record_list_by_ID(
                    record_list=preparation_batch
                )

                self.__log_details(preparation_batch=preparation_batch)

                # Multiprocessing mixes logs of different records.
                # For better readability:
                preparation_batch_IDs = [x["ID"] for x in preparation_batch]
                self.REVIEW_MANAGER.reorder_log(IDs=preparation_batch_IDs)

                # Note: for formatting...
                # records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
                # self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
                # self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

                self.REVIEW_MANAGER.create_commit(
                    msg=f"Prepare records ({prep_round.name})",
                    script_call="colrev prep",
                    saved_args=saved_args,
                )
                self.REVIEW_MANAGER.reset_log()
                print()

        if not keep_ids and not self.REVIEW_MANAGER.DEBUG_MODE:
            self.REVIEW_MANAGER.REVIEW_DATASET.set_IDs()
            self.REVIEW_MANAGER.create_commit(
                msg="Set IDs", script_call="colrev prep", saved_args=saved_args
            )

        return


class ServiceNotAvailableException(Exception):
    def __init__(self, msg: str):
        self.message = msg
        super().__init__(f"Service not available: {self.message}")


if __name__ == "__main__":
    pass
