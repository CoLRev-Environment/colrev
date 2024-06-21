#! /usr/bin/env python
"""CoLRev push operation: Push project and record corrections."""
from __future__ import annotations

import json
from pathlib import Path

import colrev.process.operation
from colrev.constants import Colors
from colrev.constants import EndpointType
from colrev.constants import Fields
from colrev.constants import OperationsType


class Push(colrev.process.operation.Operation):
    """Push the project and record corrections"""

    type = OperationsType.check

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=self.type,
        )

    @colrev.process.operation.Operation.decorate()
    def main(
        self,
        *,
        records_only: bool = False,
        project_only: bool = False,
        all_records: bool = False,
    ) -> None:
        """Push a CoLRev project and records (main entrypoint)"""

        if project_only:
            self._push_project()

        if records_only:
            self._push_record_corrections(all_records)

    def _push_project(self) -> None:
        git_repo = self.review_manager.dataset.get_repo()
        origin = git_repo.remotes.origin
        self.review_manager.logger.info(f"Push changes to {git_repo.remotes.origin}")
        origin.push()

    def _get_change_sets(self) -> dict:
        self.review_manager.logger.info("Collect corrections")

        search_source_mappings = {
            x.get_origin_prefix(): x.endpoint
            for x in self.review_manager.settings.sources
        }

        # group by target-repo to bundle changes in a commit
        change_sets = {}  # type: ignore
        corrections_path = self.review_manager.paths.corrections
        for correction_path in corrections_path.glob("*.json"):
            with open(correction_path, encoding="utf8") as json_file:
                output = json.load(json_file)

            record = output["original_record"]
            for source_origin in record[Fields.ORIGIN]:
                # note : simple heuristic / should be based on the SearchSources
                # (objects - whether they offer correction functionality)
                source_prefix = source_origin[: source_origin.find("/")]
                search_source = search_source_mappings[
                    source_origin[: source_origin.find("/")]
                ]

                if search_source in ["colrev.unknown_source"]:
                    continue

                output[Fields.FILE] = correction_path
                if source_prefix not in change_sets:
                    change_sets[source_prefix] = []

                change_sets[source_prefix].append(output)

        return change_sets

    def _push_record_corrections(self, all_records: bool) -> None:
        """Push corrections of records"""

        change_sets = self._get_change_sets()
        package_manager = self.review_manager.get_package_manager()

        for source_prefix, change_itemsets in change_sets.items():
            source_l = [
                s
                for s in self.review_manager.settings.sources
                if source_prefix == s.get_origin_prefix()
            ]
            if not source_l:
                continue

            source = source_l[0]

            search_source_class = package_manager.get_package_endpoint_class(
                package_type=EndpointType.search_source,
                package_identifier=source.endpoint,
            )
            endpoint = search_source_class(
                source_operation=self, settings=source.get_dict()
            )

            correct_function = getattr(endpoint, "apply_correction", None)
            if callable(correct_function):
                self.review_manager.logger.info(
                    f"{Colors.GREEN}Push record corrections to {source_prefix}{Colors.END}"
                )
                endpoint.apply_correction(change_itemsets=change_itemsets)  # type: ignore

            elif all_records:
                # Else: use the share_corrections functionality:
                self.review_manager.logger.info(
                    f"{Colors.GREEN}Push record corrections to {source_prefix}{Colors.END}"
                )
                self.review_manager.logger.debug(
                    f"No correction function in {source.endpoint}"
                )
                self._share_correction(source=source, change_list=change_itemsets)

    def _share_correction(
        self, *, source: colrev.settings.SearchSource, change_list: list
    ) -> None:
        prepared_change_list = []
        for change in change_list:
            prepared_change_list.append(
                {
                    "record": change["original_record"],
                    "changes": change["changes"],
                }
            )

        corrections = self.review_manager.p_printer.pformat(prepared_change_list)

        text = (
            "Dear Sir or Madam,\n\nwe have noticed potential corrections and "
            + "would like to share them with you.\nThe potentical changes are:\n\n"
            + f"{corrections}\n\nBest regards\n\n"
        )

        if source.endpoint == "colrev.dblp":
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
                if Path(change_item[Fields.FILE]).is_file():
                    Path(change_item[Fields.FILE]).unlink()
