#! /usr/bin/env python
import json
from pathlib import Path

import git

import colrev.exceptions as colrev_exceptions
import colrev.process
import colrev.record
import colrev.review_manager


class Push(colrev.process.Process):
    def __init__(self, *, review_manager):
        super().__init__(
            review_manager=review_manager,
            process_type=colrev.process.ProcessType.explore,
        )

    def main(self, *, records_only: bool = False, project_only: bool = False) -> None:

        if project_only:
            self.push_project()

        if records_only:
            self.push_record_corrections()

    def push_project(self) -> None:
        git_repo = self.review_manager.dataset.get_repo()
        origin = git_repo.remotes.origin
        self.review_manager.logger.info(f"Push changes to {git_repo.remotes.origin}")
        origin.push()

    def push_record_corrections(self) -> None:

        self.review_manager.logger.info("Collect corrections for curated repositories")

        # group by target-repo to bundle changes in a commit
        change_sets = {}  # type: ignore
        for correction in self.review_manager.paths["CORRECTIONS_PATH"].glob("*.json"):
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
                self.review_manager.logger.info(f"Share corrections with {source_url}")
            else:
                self.review_manager.logger.info(f"Apply corrections to {source_url}")
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
                        self.review_manager.p_printer.pprint(change_item)

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

        corrections = self.review_manager.p_printer.pformat(prepared_change_list)

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
        check_review_manager = colrev.review_manager.ReviewManager(path_str=source_url)
        check_process = colrev.process.CheckProcess(review_manager=check_review_manager)
        git_repo = check_process.review_manager.dataset.get_repo()

        if git_repo.is_dirty():
            print(
                f"Repo not clean ({source_url}): "
                "commit or stash before updating records"
            )
            return

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

        records = check_process.review_manager.dataset.load_records_dict()
        pull_request_msgs = []
        for change_item in change_list:
            original_curated_record = change_item["original_curated_record"]

            found = False
            try:
                record_dict = (
                    check_process.review_manager.dataset.retrieve_by_colrev_id(
                        original_curated_record, records.values()
                    )
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
                    record_dict = matching_doi_rec_l[0]
                    found = True

                matching_url_rec_l = [
                    r
                    for r in records.values()
                    if original_curated_record.get("url", "NURL") == r.get("url", "NA")
                ]
                if len(matching_url_rec_l) == 1:
                    record_dict = matching_url_rec_l[0]
                    found = True

            if not found:
                print(f'Record not found: {original_curated_record["ID"]}')
                continue

            record_branch_name = record_dict["ID"]
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

            rec_for_reset = record_dict.copy()

            for (edit_type, key, change) in list(change_item["changes"]):
                # Note : by retricting changes to essential_md_keys,
                # we also prevent changes in
                # "colrev_status", "colrev_origin", "file"

                # Note: the most important thing is to update the metadata.

                if edit_type == "change":
                    if key not in essential_md_keys:
                        continue
                    record_dict[key] = change[1]
                if edit_type == "add":
                    key = change[0][0]
                    value = change[0][1]
                    if key not in essential_md_keys:
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

            if "github.com" in remote.url:
                pull_request_msgs.append(
                    "\nTo create a pull request for your changes go "
                    f"to {str(remote.url).rstrip('.git')}/compare/{record_branch_name}"
                )

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

        for pull_request_msg in pull_request_msgs:
            print(pull_request_msg)
        # https://github.com/geritwagner/information_systems_papers/compare/update?expand=1
        # TODO : handle cases where update branch already exists
        return


if __name__ == "__main__":
    pass
