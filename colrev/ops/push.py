#! /usr/bin/env python
from __future__ import annotations

import json
from pathlib import Path

import colrev.ops.correct
import colrev.process
import colrev.record


class Push(colrev.process.Process):
    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
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

    def __get_change_sets(self) -> dict:
        self.review_manager.logger.info("Collect corrections for curated repositories")

        # group by target-repo to bundle changes in a commit
        change_sets = {}  # type: ignore
        for correction in self.review_manager.corrections_path.glob("*.json"):
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

        return change_sets

    def push_record_corrections(self) -> None:
        # pylint: disable=too-many-branches

        change_sets = self.__get_change_sets()

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
                    corrections_operation = colrev.ops.correct.Corrections(
                        review_manager=self.review_manager
                    )
                    corrections_operation.apply_correction(
                        source_url=source_url, change_list=change_itemset
                    )

                print(
                    "\nThank you for supporting other researchers "
                    "by sharing your corrections ❤\n"
                )

    def __share_correction(self, *, source_url: str, change_list: list) -> None:

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


if __name__ == "__main__":
    pass
