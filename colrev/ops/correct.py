#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import git
from dictdiffer import diff

import colrev.exceptions as colrev_exceptions


if TYPE_CHECKING:
    import colrev.review_manager


class Corrections:

    # pylint: disable=duplicate-code
    essential_md_keys = [
        "title",
        "author",
        "journal",
        "year",
        "booktitle",
        "number",
        "volume",
        "issue",
        "author",
        "doi",
        "colrev_origin",  # Note : for merges
    ]

    keys_to_ignore = [
        "screening_criteria",
        "colrev_status",
        "source_url",
        "metadata_source_repository_paths",
        "ID",
        "grobid-version",
        "colrev_pdf_id",
        "file",
        "colrev_origin",
        "colrev_data_provenance",
        "sem_scholar_id",
    ]

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
    ) -> None:

        self.review_manager = review_manager
        self.local_index = self.review_manager.get_local_index()
        self.resources = self.review_manager.get_resources()

    def __curated_record_corrected(
        self, *, prior_cr: dict, curated_record: dict
    ) -> bool:
        return not all(
            prior_cr.get(k, "NA") == curated_record.get(k, "NA")
            for k in self.essential_md_keys
        )

    def __get_original_curated_record_from_index(self, *, prior_cr: dict) -> dict:

        # retrieve record from index to identify origin repositories
        try:
            original_curated_record = self.local_index.retrieve(record_dict=prior_cr)

            # Note : this is a simple heuristic:
            curation_path = self.resources.curations_path / Path(
                original_curated_record["colrev_masterdata_provenance"]["source"].split(
                    "/"
                )[-1]
            )
            if not curation_path.is_dir():
                prov_inf = original_curated_record["colrev_masterdata_provenance"][
                    "source"
                ]
                print(
                    "Source path of indexed record not available "
                    f'({original_curated_record["ID"]} - '
                    f"{prov_inf})"
                )
                return {}
        except (colrev_exceptions.RecordNotInIndexException, KeyError):
            original_curated_record = prior_cr.copy()
        return original_curated_record

    def __create_change_item(
        self,
        *,
        original_curated_record: dict,
        corrected_curated_record: dict,
    ) -> None:

        original_curated_record["colrev_id"] = colrev.record.Record(
            data=original_curated_record
        ).create_colrev_id()

        # Cast to string for persistence
        original_curated_record = {
            k: str(v) for k, v in original_curated_record.items()
        }
        corrected_curated_record = {
            k: str(v) for k, v in corrected_curated_record.items()
        }

        # Note : removing the fields is a temporary fix
        # because the subsetting of change_items does not seem to
        # work properly
        keys_to_drop = ["pages", "colrev_status"]
        for k in keys_to_drop:
            original_curated_record.pop(k, None)
            corrected_curated_record.pop(k, None)

        # if "dblp_key" in corrected_curated_record:
        #     del corrected_curated_record["dblp_key"]

        # TODO : export only essential changes?
        changes = diff(original_curated_record, corrected_curated_record)
        change_items = list(changes)

        selected_change_items = []
        for change_item in change_items:
            change_type, key, val = change_item
            if "add" == change_type:
                for add_item in val:
                    add_item_key, add_item_val = add_item
                    if add_item_key not in self.keys_to_ignore:
                        selected_change_items.append(
                            ("add", "", [(add_item_key, add_item_val)])
                        )
            elif "change" == change_type:
                if key not in self.keys_to_ignore:
                    selected_change_items.append(change_item)

        change_items = selected_change_items

        if len(change_items) == 0:
            return

        if len(corrected_curated_record.get("colrev_origin", "").split(";")) > len(
            original_curated_record.get("colrev_origin", "").split(";")
        ):
            if (
                "dblp_key" in corrected_curated_record
                and "dblp_key" in original_curated_record
            ):
                if (
                    corrected_curated_record["dblp_key"]
                    != original_curated_record["dblp_key"]
                ):
                    change_items = {  # type: ignore
                        "merge": [
                            corrected_curated_record["dblp_key"],
                            original_curated_record["dblp_key"],
                        ]
                    }
            # else:
            #     change_items = {
            #         "merge": [
            #             corrected_curated_record["ID"],
            #             original_curated_record["ID"],
            #         ]
            #     }

        # TODO : cover non-masterdata corrections
        if "colrev_masterdata_provenance" not in original_curated_record:
            return

        dict_to_save = {
            "source_url": original_curated_record["colrev_masterdata_provenance"],
            "original_curated_record": original_curated_record,
            "changes": change_items,
        }
        filepath = self.review_manager.corrections_path / Path(
            f"{corrected_curated_record['ID']}.json"
        )
        filepath.parent.mkdir(exist_ok=True)

        with open(filepath, "w", encoding="utf8") as corrections_file:
            json.dump(dict_to_save, corrections_file, indent=4)

        # TODO : combine merge-record corrections

    def check_corrections_of_curated_records(self) -> None:

        dataset = self.review_manager.dataset

        if not dataset.records_file.is_file():
            return

        record_curated_current = dataset.get_records_curated_currentl()
        record_curated_prior = dataset.get_records_curated_prior_from_history()

        # TODO : The following code should be much simpler...
        for curated_record in record_curated_current:

            # TODO : use origin-indexed dict (discarding changes during merges)

            # identify curated records for which essential metadata is changed
            record_curated_prior = [
                x
                for x in record_curated_prior
                if any(
                    y in curated_record["colrev_origin"].split(";")
                    for y in x["colrev_origin"].split(";")
                )
            ]

            if len(record_curated_prior) == 0:
                self.review_manager.logger.debug("No prior records found")
                continue

            for prior_cr in record_curated_prior:

                if self.__curated_record_corrected(
                    prior_cr=prior_cr, curated_record=curated_record
                ):

                    corrected_curated_record = curated_record.copy()

                    original_curated_record = (
                        self.__get_original_curated_record_from_index(prior_cr=prior_cr)
                    )
                    if not original_curated_record:
                        continue

                    self.__create_change_item(
                        original_curated_record=original_curated_record,
                        corrected_curated_record=corrected_curated_record,
                    )

    def __apply_corrections_precondition(
        self, *, check_process, source_url: str
    ) -> bool:
        git_repo = check_process.review_manager.dataset.get_repo()

        if git_repo.is_dirty():
            # TODO : raise exception
            print(
                f"Repo not clean ({source_url}): "
                "commit or stash before updating records"
            )
            return False

        if check_process.review_manager.dataset.behind_remote():
            origin = git_repo.remotes.origin
            origin.pull()
            if not check_process.review_manager.dataset.behind_remote():
                self.review_manager.logger.info("Pulled changes")
            else:
                self.review_manager.logger.error(
                    "Repo behind remote. Pull first to avoid conflicts.\n"
                    f"colrev env --update {check_process.review_manager.path}"
                )
                return False

        return True

    def __retrieve_record_for_correction(
        self, *, check_process, records, change_item
    ) -> dict:
        original_curated_record = change_item["original_curated_record"]

        try:
            record_dict = check_process.review_manager.dataset.retrieve_by_colrev_id(
                indexed_record_dict=original_curated_record,
                records=list(records.values()),
            )
            return record_dict
        except colrev_exceptions.RecordNotInRepoException:
            print(f"record not found: {original_curated_record['colrev_id']}")

            matching_doi_rec_l = [
                r
                for r in records.values()
                if original_curated_record.get("doi", "NDOI") == r.get("doi", "NA")
            ]
            if len(matching_doi_rec_l) == 1:
                record_dict = matching_doi_rec_l[0]
                return record_dict

            matching_url_rec_l = [
                r
                for r in records.values()
                if original_curated_record.get("url", "NURL") == r.get("url", "NA")
            ]
            if len(matching_url_rec_l) == 1:
                record_dict = matching_url_rec_l[0]
                return record_dict

        print(f'Record not found: {original_curated_record["ID"]}')
        return {}

    def __create_correction_branch(
        self, *, git_repo: git.Repo, record_dict: dict
    ) -> str:
        record_branch_name = record_dict["ID"]
        counter = 1
        new_record_branch_name = record_branch_name
        while new_record_branch_name in [ref.name for ref in git_repo.references]:
            new_record_branch_name = f"{record_branch_name}_{counter}"
            counter += 1

        record_branch_name = new_record_branch_name
        git_repo.git.branch(record_branch_name)
        return record_branch_name

    def __apply_record_correction(
        self, *, check_process, records, record_dict: dict, change_item: dict
    ) -> None:

        for (edit_type, key, change) in list(change_item["changes"]):
            # Note : by retricting changes to self.essential_md_keys,
            # we also prevent changes in
            # "colrev_status", "colrev_origin", "file"

            # Note: the most important thing is to update the metadata.

            if edit_type == "change":
                if key not in self.essential_md_keys:
                    continue
                record_dict[key] = change[1]
            if edit_type == "add":
                key = change[0][0]
                value = change[0][1]
                if key not in self.essential_md_keys:
                    continue
                record_dict[key] = value
            # TODO : deal with remove/merge

        record = colrev.record.Record(data=record_dict)
        record.add_colrev_ids(records=[record_dict])
        cids = record.get_data()["colrev_id"]
        record_dict["colrev_id"] = cids

        check_process.review_manager.dataset.save_records_dict(records=records)
        check_process.review_manager.dataset.add_record_changes()
        check_process.review_manager.create_commit(
            msg=f"Update {record_dict['ID']}", script_call="colrev push"
        )

    def __push_corrections_and_reset_branch(
        self,
        *,
        git_repo: git.Repo,
        record_branch_name: str,
        prev_branch_name: str,
        source_url: str,
    ) -> None:

        git_repo.remotes.origin.push(
            refspec=f"{record_branch_name}:{record_branch_name}"
        )
        self.review_manager.logger.info("Pushed corrections")

        for head in git_repo.heads:
            if head.name == prev_branch_name:
                head.checkout()

        git_repo = git.Git(source_url)
        git_repo.execute(["git", "branch", "-D", record_branch_name])

        self.review_manager.logger.info("Removed local corrections branch")

    def __reset_record_after_correction(
        self, *, record_dict: dict, rec_for_reset: dict, change_item: dict
    ) -> None:
        # reset the record - each branch should have changes for one record
        # Note : modify dict (do not replace it) - otherwise changes will not be
        # part of the records.
        for key, value in rec_for_reset.items():
            record_dict[key] = value
        keys_added = [
            key for key in record_dict.keys() if key not in rec_for_reset.keys()
        ]
        for key in keys_added:
            del record_dict[key]

        if Path(change_item["file"]).is_file():
            Path(change_item["file"]).unlink()

    def __apply_change_item_correction(
        self, *, check_process, source_url: str, change_list: list
    ) -> None:

        git_repo = check_process.review_manager.dataset.get_repo()
        records = check_process.review_manager.dataset.load_records_dict()

        pull_request_msgs = []
        for change_item in change_list:

            record_dict = self.__retrieve_record_for_correction(
                check_process=check_process, records=records, change_item=change_item
            )
            if not record_dict:
                continue

            record_branch_name = self.__create_correction_branch(
                git_repo=git_repo, record_dict=record_dict
            )
            prev_branch_name = git_repo.active_branch.name

            remote = git_repo.remote()
            for head in git_repo.heads:
                if head.name == record_branch_name:
                    head.checkout()

            rec_for_reset = record_dict.copy()

            self.__apply_record_correction(
                check_process=check_process,
                records=records,
                record_dict=record_dict,
                change_item=change_item,
            )

            self.__push_corrections_and_reset_branch(
                git_repo=git_repo,
                record_branch_name=record_branch_name,
                prev_branch_name=prev_branch_name,
                source_url=source_url,
            )

            self.__reset_record_after_correction(
                record_dict=record_dict,
                rec_for_reset=rec_for_reset,
                change_item=change_item,
            )

            if "github.com" in remote.url:
                pull_request_msgs.append(
                    "\nTo create a pull request for your changes go "
                    f"to {str(remote.url).rstrip('.git')}/compare/{record_branch_name}"
                )

        for pull_request_msg in pull_request_msgs:
            print(pull_request_msg)
        # https://github.com/geritwagner/information_systems_papers/compare/update?expand=1
        # TODO : handle cases where update branch already exists

    def apply_correction(self, *, source_url: str, change_list: list) -> None:

        # TBD: other modes of accepting changes?
        # e.g., only-metadata, no-changes, all(including optional fields)
        check_review_manager = self.review_manager.get_review_manager(
            path_str=source_url
        )
        check_process = colrev.process.CheckProcess(review_manager=check_review_manager)

        if not self.__apply_corrections_precondition(
            check_process=check_process, source_url=source_url
        ):
            return

        # pylint: disable=duplicate-code
        self.essential_md_keys = [
            "title",
            "author",
            "journal",
            "year",
            "booktitle",
            "number",
            "volume",
            "issue",
            "author",
            "doi",
            "dblp_key",
            "url",
        ]

        self.__apply_change_item_correction(
            check_process=check_process, source_url=source_url, change_list=change_list
        )


if __name__ == "__main__":
    pass
