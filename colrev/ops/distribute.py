#! /usr/bin/env python
"""Distribte records or PDFs to local CoLRev repositories."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import colrev.env.tei_parser
import colrev.process.operation
import colrev.settings
from colrev.constants import Fields
from colrev.constants import OperationsType
from colrev.constants import SearchType
from colrev.writer.write_utils import write_file


class Distribute(colrev.process.operation.Operation):
    """Distribute records to other local CoLRev projects"""

    type = OperationsType.check

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        # pylint: disable=duplicate-code
        super().__init__(
            review_manager=review_manager,
            operations_type=self.type,
            notify_state_transition_operation=False,
        )
        self.review_manager = review_manager

    def get_environment_registry(self) -> list:
        """Get the environment registry (excluding curated_metadata)"""
        environment_manager = self.review_manager.get_environment_manager()
        return [
            x
            for x in environment_manager.local_repos()
            if "curated_metadata/" not in x["repo_source_path"]
        ]

    def get_next_id(self, *, bib_file: Path) -> int:
        """Get the next ID (incrementing counter)"""
        ids = []
        if bib_file.is_file():
            with open(bib_file, encoding="utf8") as file:
                line = file.readline()
                while line:
                    if "@" in line[:3]:
                        current_id = line[line.find("{") + 1 : line.rfind(",")]
                        ids.append(current_id)
                    line = file.readline()
        max_id = max([int(cid) for cid in ids if cid.isdigit()] + [0]) + 1
        return max_id

    @colrev.process.operation.Operation.decorate()
    def main(self, *, path: Path, target: Path) -> None:
        """Distribute records to other CoLRev repositories (main entrypoint)"""

        # if no options are given, take the current path/repo
        # optional: target-repo-path
        # path_str: could also be a url
        # option: chdir (to target repo)?
        # file: copy or move?

        os.chdir(target)
        path = Path.cwd() / Path(path)

        if path.is_file():
            if path.suffix == ".bib":
                # gh_issue https://github.com/CoLRev-Environment/colrev/issues/69
                # append records (check duplicates/duplicate IDs)
                # if path already exists
                # should the following really rename the file?
                # or just get the updated filepath?

                shutil.move(
                    str(path), str(target / Path("data/search/local_import.bib"))
                )
                input(path)

            if path.suffix == ".pdf":

                tei = colrev.env.tei_parser.TEIParser(
                    pdf_path=path,
                )
                record = tei.get_metadata()

                target_pdf_path = target / "pdfs" / path.name
                target_pdf_path.parent.mkdir(parents=True, exist_ok=True)
                self.review_manager.logger.info(f"Copy PDF to {target_pdf_path}")
                shutil.copyfile(path, target_pdf_path)

                self.review_manager.logger.info(
                    f"append {self.review_manager.p_printer.pformat(record)} "
                    "to data/search/local_import.bib"
                )
                target_bib_file = target / Path("data/search/local_import.bib")
                self.review_manager.logger.info(f"target_bib_file: {target_bib_file}")
                if target_bib_file.is_file():

                    import_records_dict = colrev.loader.load_utils.load(
                        filename=target_bib_file,
                        logger=self.review_manager.logger,
                    )
                    import_records = list(import_records_dict.values())

                else:
                    import_records = []

                    new_source = colrev.settings.SearchSource(
                        endpoint="colrev.unknown_source",
                        filename=Path("search") / target_bib_file.name,
                        search_type=SearchType.OTHER,
                        search_parameters={},
                        comment="",
                    )

                    self.review_manager.settings.sources.append(new_source)
                    self.review_manager.save_settings()

                if 0 == len(import_records):
                    return

                record_id = int(self.get_next_id(bib_file=target_bib_file))
                record[Fields.ID] = f"{record_id}".rjust(10, "0")
                record.update(file=str(target_pdf_path))
                import_records.append(record)

                import_records_dict = {r[Fields.ID]: r for r in import_records}

                write_file(records_dict=import_records_dict, filename=target_bib_file)

                self.review_manager.dataset.add_changes(target_bib_file)
