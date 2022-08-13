#! /usr/bin/env python
import json
from pathlib import Path

import git

import colrev_core.exceptions as colrev_exceptions
import colrev_core.process
import colrev_core.record
import colrev_core.review_manager


class Push(colrev_core.process.Process):
    def __init__(self, *, REVIEW_MANAGER):
        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            process_type=colrev_core.process.ProcessType.explore,
        )

    def main(self, *, records_only: bool = False, project_only: bool = False) -> None:

        if project_only:
            self.push_project()

        if records_only:
            self.push_record_corrections()

    def push_project(self) -> None:
        git_repo = self.REVIEW_MANAGER.REVIEW_DATASET.get_repo()
        origin = git_repo.remotes.origin
        self.REVIEW_MANAGER.logger.info(f"Push changes to {git_repo.remotes.origin}")
        origin.push()

    def push_record_corrections(self) -> None:

        self.REVIEW_MANAGER.logger.info("Collect corrections for curated repositories")

        # group by target-repo to bundle changes in a commit
        change_sets = {}  # type: ignore
        for correction in self.REVIEW_MANAGER.paths["CORRECTIONS_PATH"].glob("*.json"):
            with open(correction, encoding="utf8") as json_file:
                output = json.load(json_file)
            output["file"] = correction
            source_url = output["source_url"]

            if len(change_sets) == 0:
                change_sets[source_url] = [output]
                continue
            if source_url in [p for p, c in change_sets.items()]:
                change_sets[source_url].append(output)
            else:
                change_sets[source_url] = [output]

        for source_url, change_itemset in change_sets.items():
            if not Path(source_url).is_dir:
                print(f"Path {source_url} is not a dir. Skipping...")
                continue
            print()
            if "metadata_source=" in source_url:
                self.REVIEW_MANAGER.logger.info(f"Share corrections with {source_url}")
            else:
                self.REVIEW_MANAGER.logger.info(f"Apply corrections to {source_url}")
            # print(change_itemset)
            for item in change_itemset:
                print()
                print(item["original_curated_record"]["colrev_id"])
                for change_item in item["changes"]:
                    if "change" == change_item[0]:
                        edit_type, field, values = change_item
                        if "colrev_id" == field:
                            continue
                        prefix = f"{edit_type} {field}"
                        print(
                            f"{prefix}"
                            + " " * max(len(prefix), 30 - len(prefix))
                            + f": {values[0]}"
                        )
                        print(" " * max(len(prefix), 30) + f"  {values[1]}")
                    elif "add" == change_item[0]:
                        edit_type, field, values = change_item
                        prefix = f"{edit_type} {values[0][0]}"
                        print(
                            prefix
                            + " " * max(len(prefix), 30 - len(prefix))
                            + f": {values[0][1]}"
                        )
                    else:
                        self.REVIEW_MANAGER.pp.pprint(change_item)

            response = ""
            while True:
                response = input("\nConfirm changes? (y/n)")
                if response in ["y", "n"]:
                    break

            if "y" == response:
                if "metadata_source=" in source_url:
                    self.__share_correction(
                        source_url=source_url, change_list=change_itemset
                    )
                else:
                    self.__apply_correction(
                        source_url=source_url, change_list=change_itemset
                    )

                print(
                    "\nThank you for supporting other researchers "
                    "by sharing your corrections ❤\n"
                )

    def __share_correction(self, *, source_url, change_list) -> None:

        prepared_change_list = []
        for change in change_list:
            prepared_change_list.append(
                {
                    "record": change["original_curated_record"],
                    "changes": change["changes"],
                }
            )

        corrections = self.REVIEW_MANAGER.pp.pformat(prepared_change_list)

        text = (
            "Dear Sir or Madam,\n\nwe have noticed potential corrections and "
            + "would like to share them with you.\nThe potentical changes are:\n\n"
            + f"{corrections}\n\nBest regards\n\n"
        )

        if "metadata_source=DBLP" == source_url:
            file_path = Path("dblp-corrections-mail.txt")
            dblp_header = (
                "Send to: dblp@dagstuhl.de\n\n"
                + "Subject: Potential correction to DBLP metadata\n\n"
            )

            text = dblp_header + text
            file_path.write_text(text, encoding="utf-8")

            print(f"\nPlease send the e-mail (prepared in the file {file_path})")
            input("Press Enter to confirm")

            for change_item in change_list:
                if Path(change_item["file"]).is_file():
                    Path(change_item["file"]).unlink()

    def __apply_correction(self, *, source_url, change_list) -> None:

        # TBD: other modes of accepting changes?
        # e.g., only-metadata, no-changes, all(including optional fields)
        check_REVIEW_MANAGER = colrev_core.review_manager.ReviewManager(
            path_str=source_url
        )
        CHECK_PROCESS = colrev_core.process.CheckProcess(
            REVIEW_MANAGER=check_REVIEW_MANAGER
        )
        REVIEW_DATASET = CHECK_PROCESS.REVIEW_MANAGER.REVIEW_DATASET
        git_repo = REVIEW_DATASET.get_repo()

        if git_repo.is_dirty():
            print(
                f"Repo not clean ({source_url}): "
                "commit or stash before updating records"
            )
            return

        if REVIEW_DATASET.behind_remote():
            o = git_repo.remotes.origin
            o.pull()
            if not REVIEW_DATASET.behind_remote():
                self.REVIEW_MANAGER.logger.info("Pulled changes")
            else:
                self.REVIEW_MANAGER.logger.error(
                    "Repo behind remote. Pull first to avoid conflicts.\n"
                    f"colrev env --update {CHECK_PROCESS.REVIEW_MANAGER.path}"
                )
                return

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
            "dblp_key",
            "url",
        ]

        records = REVIEW_DATASET.load_records_dict()
        pull_request_msgs = []
        for change_item in change_list:
            original_curated_record = change_item["original_curated_record"]

            found = False
            try:
                record = REVIEW_DATASET.retrieve_by_colrev_id(
                    original_curated_record, records.values()
                )
                found = True
            except colrev_exceptions.RecordNotInRepoException:
                print(f"record not found: {original_curated_record['colrev_id']}")

                matching_doi_rec_l = [
                    r
                    for r in records.values()
                    if original_curated_record.get("doi", "NDOI") == r.get("doi", "NA")
                ]
                if len(matching_doi_rec_l) == 1:
                    record = matching_doi_rec_l[0]
                    found = True

                matching_url_rec_l = [
                    r
                    for r in records.values()
                    if original_curated_record.get("url", "NURL") == r.get("url", "NA")
                ]
                if len(matching_url_rec_l) == 1:
                    record = matching_url_rec_l[0]
                    found = True

            if not found:
                print(f'Record not found: {original_curated_record["ID"]}')
                continue

            record_branch_name = record["ID"]
            counter = 1
            new_record_branch_name = record_branch_name
            while new_record_branch_name in [ref.name for ref in git_repo.references]:
                new_record_branch_name = f"{record_branch_name}_{counter}"
                counter += 1

            record_branch_name = new_record_branch_name
            git_repo.git.branch(record_branch_name)

            remote = git_repo.remote()
            prev_branch_name = git_repo.active_branch.name
            for head in git_repo.heads:
                if head.name == record_branch_name:
                    head.checkout()

            rec_for_reset = record.copy()

            for (edit_type, key, change) in list(change_item["changes"]):
                # Note : by retricting changes to essential_md_keys,
                # we also prevent changes in
                # "colrev_status", "colrev_origin", "file"

                # Note: the most important thing is to update the metadata.

                if edit_type == "change":
                    if key not in essential_md_keys:
                        continue
                    record[key] = change[1]
                if edit_type == "add":
                    key = change[0][0]
                    value = change[0][1]
                    if key not in essential_md_keys:
                        continue
                    record[key] = value
                # TODO : deal with remove/merge

            RECORD = colrev_core.record.Record(data=record)
            RECORD.add_colrev_ids(records=[record])
            cids = RECORD.get_data()["colrev_id"]
            record["colrev_id"] = cids

            REVIEW_DATASET.save_records_dict(records=records)
            REVIEW_DATASET.add_record_changes()
            CHECK_PROCESS.REVIEW_MANAGER.create_commit(
                msg=f"Update {record['ID']}", script_call="colrev push"
            )

            git_repo.remotes.origin.push(
                refspec=f"{record_branch_name}:{record_branch_name}"
            )
            self.REVIEW_MANAGER.logger.info("Pushed corrections")

            for head in git_repo.heads:
                if head.name == prev_branch_name:
                    head.checkout()

            g = git.Git(source_url)
            g.execute(["git", "branch", "-D", record_branch_name])

            self.REVIEW_MANAGER.logger.info("Removed local corrections branch")

            if "github.com" in remote.url:
                pull_request_msgs.append(
                    "\nTo create a pull request for your changes go "
                    f"to {str(remote.url).rstrip('.git')}/compare/{record_branch_name}"
                )

            # reset the record - each branch should have changes for one record
            # Note : modify dict (do not replace it) - otherwise changes will not be
            # part of the records.
            for k, v in rec_for_reset.items():
                record[k] = v
            keys_added = [k for k in record.keys() if k not in rec_for_reset.keys()]
            for key in keys_added:
                del record[key]

            if Path(change_item["file"]).is_file():
                Path(change_item["file"]).unlink()

        for pull_request_msg in pull_request_msgs:
            print(pull_request_msg)
        # https://github.com/geritwagner/information_systems_papers/compare/update?expand=1
        # TODO : handle cases where update branch already exists
        return


if __name__ == "__main__":
    pass
