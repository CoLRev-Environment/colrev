#! /usr/bin/env python
import itertools
import json
import string
from pathlib import Path

from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.review_manager import ReviewManager


class Push(Process):
    def __init__(self, REVIEW_MANAGER):
        super().__init__(REVIEW_MANAGER, ProcessType.explore)

    def main(self, records_only: bool = False, project_only: bool = False) -> None:

        # self.REVIEW_MANAGER.REVIEW_DATASET.check_corrections_of_curated_records()
        # input("done")

        if project_only:
            self.push_project()

        if records_only:
            input("TODO: check/pull curated repos before!")
            self.push_record_corrections()

        return

    def push_project(self) -> None:
        git_repo = self.REVIEW_MANAGER.REVIEW_DATASET.get_repo()
        origin = git_repo.remotes.origin
        self.REVIEW_MANAGER.logger.info(f"Pull changes from {git_repo.remotes.origin}")
        origin.push()
        return

    def push_record_corrections(self) -> None:

        self.REVIEW_MANAGER.logger.info("Collect corrections for curated repositories")

        # group by target-repo to bundle changes in a commit
        change_sets = {}  # type: ignore
        for correction in self.REVIEW_MANAGER.paths["CORRECTIONS_PATH"].glob("*.json"):
            with open(correction) as json_file:
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
                        type, field, values = change_item
                        prefix = f"{type} {field}"
                        print(f"{prefix}: {values[0]}")
                        print(" " * len(prefix) + f"  {values[1]}")
                    else:
                        self.REVIEW_MANAGER.pp.pprint(change_item)
            if "y" == input("\nConfirm changes? (y/n)"):
                if "metadata_source=" in source_url:
                    self.__share_correction(source_url, change_itemset)
                else:
                    self.__apply_correction(source_url, change_itemset)

                print(
                    "\nThank you for supporting other researchers "
                    "by sharing your corrections ❤\n"
                )
        return

    def __share_correction(self, source_url, change_list) -> None:

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
            file_path.write_text(text)

            print(f"\nPlease send the e-mail (prepared in the file {file_path})")
            input("Press Enter to confirm")

            for change_item in change_list:
                if Path(change_item["file"]).is_file():
                    Path(change_item["file"]).unlink()

        return

    def __apply_correction(self, source_url, change_list) -> None:
        from colrev_core.process import CheckProcess
        from bibtexparser.bibdatabase import BibDatabase
        from bibtexparser.bparser import BibTexParser
        from bibtexparser.customization import convert_to_unicode
        import bibtexparser
        from colrev_core.review_dataset import RecordNotInRepoException
        import git

        # TBD: other modes of accepting changes?
        # e.g., only-metadata, no-changes, all(including optional fields)
        check_REVIEW_MANAGER = ReviewManager(path_str=source_url)
        CHECK_PROCESS = CheckProcess(check_REVIEW_MANAGER)
        REVIEW_DATASET = CHECK_PROCESS.REVIEW_MANAGER.REVIEW_DATASET
        git_repo = REVIEW_DATASET.get_repo()
        if REVIEW_DATASET.behind_remote():
            self.REVIEW_MANAGER.logger.error(
                "Repo behind remote. Pull first to avoid conflicts.\n"
                f"colrev env --update {CHECK_PROCESS.REVIEW_MANAGER.path}"
            )
            return

        if git_repo.is_dirty():
            print(
                f"Repo not clean ({source_url}): "
                "commit or stash before updating records"
            )
            return

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
            except RecordNotInRepoException:
                pass
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

            corrections_bib_path = CHECK_PROCESS.REVIEW_MANAGER.paths[
                "SEARCHDIR"
            ] / Path("corrections.bib")
            if corrections_bib_path.is_file():
                with open(corrections_bib_path) as target_db:
                    corrections_bib = BibTexParser(
                        customization=convert_to_unicode,
                        ignore_nonstandard_types=False,
                        common_strings=True,
                    ).parse_file(target_db, partial=True)
            else:
                corrections_bib = BibDatabase()
                new_record = {
                    "filename": str(corrections_bib_path.name),
                    "search_type": "OTHER",
                    "source_name": "corrections",
                    "source_url": str(corrections_bib_path.name),
                    "search_parameters": "",
                    "comment": "",
                }

                sources = REVIEW_DATASET.load_sources()
                sources.append(new_record)
                REVIEW_DATASET.save_sources(sources)

            # append original record to search/corrections.bib
            # add ID as an origin to record
            rec_for_reset = record.copy()
            prior_rec = record.copy()

            order = 0
            letters = list(string.ascii_lowercase)
            temp_ID = prior_rec["ID"]
            next_unique_ID = temp_ID
            other_ids = [x["ID"] for x in corrections_bib.entries]
            appends: list = []
            while next_unique_ID in other_ids:
                if len(appends) == 0:
                    order += 1
                    appends = [p for p in itertools.product(letters, repeat=order)]
                next_unique_ID = temp_ID + "".join(list(appends.pop(0)))
            prior_rec["ID"] = next_unique_ID

            if "status" in prior_rec:
                del prior_rec["status"]
            if "origin" in prior_rec:
                del prior_rec["origin"]
            if "metadata_source" in prior_rec:
                del prior_rec["metadata_source"]
            if "doi" in prior_rec:
                del prior_rec["doi"]
            if "colrev_id" in prior_rec:
                del prior_rec["colrev_id"]
            if "colrev_pdf_id" in prior_rec:
                del prior_rec["colrev_pdf_id"]
            if "grobid-version" in prior_rec:
                del prior_rec["grobid-version"]
            if "file" in prior_rec:
                del prior_rec["file"]
            corrections_bib.entries.append(prior_rec)
            record["origin"] = (
                record["origin"] + f";{corrections_bib_path.name}/{prior_rec['ID']}"
            )

            for (type, key, change) in list(change_item["changes"]):
                if key in ["status", "origin", "metadata_source", "file"]:
                    continue

                # Note: the most important thing is to update the metadata.
                # we can create a copy/duplicate representation (/search) later
                if key not in essential_md_keys:
                    continue
                # TODO : deal with add/remove
                if type != "change":
                    continue

                record[key] = change[1]

            corrections_bib.entries = sorted(
                corrections_bib.entries, key=lambda d: d["ID"]
            )

            bibtex_str = bibtexparser.dumps(
                corrections_bib,
                writer=self.REVIEW_MANAGER.REVIEW_DATASET.get_bibtex_writer(),
            )

            with open(corrections_bib_path, "w") as out:
                out.write(bibtex_str)

            crb_path = str(
                CHECK_PROCESS.REVIEW_MANAGER.paths["SEARCHDIR_RELATIVE"]
                / Path("corrections.bib")
            )
            REVIEW_DATASET.add_changes(crb_path)
            REVIEW_DATASET.add_changes(
                str(CHECK_PROCESS.REVIEW_MANAGER.paths["SOURCES_RELATIVE"])
            )
            REVIEW_DATASET.save_records_dict(records)
            REVIEW_DATASET.add_record_changes()
            CHECK_PROCESS.REVIEW_MANAGER.create_commit(f"Update {record['ID']}")

            git_repo.remotes.origin.push(
                refspec=f"{record_branch_name}:{record_branch_name}"
            )

            for head in git_repo.heads:
                if head.name == prev_branch_name:
                    head.checkout()

            g = git.Git(source_url)
            g.execute(["git", "branch", "-D", record_branch_name])

            if "github.com" in remote.url:
                pull_request_msgs.append(
                    "\nTo create a pull request for your changes go "
                    f"to {str(remote.url).rstrip('.git')}/compare/{record_branch_name}"
                )

            # reset the record - each branch should have changes for one record
            for k, v in rec_for_reset.items():
                record[k] = v

            if Path(change_item["file"]).is_file():
                Path(change_item["file"]).unlink()

        for pull_request_msg in pull_request_msgs:
            print(pull_request_msg)
        # https://github.com/geritwagner/information_systems_papers/compare/update?expand=1
        # TODO : handle cases where update branch already exists
        return


if __name__ == "__main__":
    pass
