#! /usr/bin/env python
"""Distribte records or PDFs to local CoLRev repositories."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import colrev.operation
import colrev.settings

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.review_manager


class Distribute(colrev.operation.Operation):
    """Distribute records to other local CoLRev projects"""

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        # pylint: disable=duplicate-code
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.check,
            notify_state_transition_operation=False,
        )
        self.review_manager = review_manager

    def get_environment_registry(self) -> list:
        """Get the environment registry (excluding curated_metadata)"""
        environment_manager = self.review_manager.get_environment_manager()
        environment_registry = environment_manager.load_environment_registry()
        return [
            x
            for x in environment_registry
            if "curated_metadata/" not in x["repo_source_path"]
        ]

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

                path.rename(target / Path("data/search/local_import.bib"))
                input(path)

            if path.suffix == ".pdf":
                grobid_service = self.review_manager.get_grobid_service()

                grobid_service.start()

                tei = self.review_manager.get_tei(
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
                    with open(target_bib_file, encoding="utf8") as target_bib:
                        import_records_dict = (
                            self.review_manager.dataset.load_records_dict(
                                load_str=target_bib.read()
                            )
                        )
                        import_records = list(import_records_dict.values())
                else:
                    import_records = []

                    new_source = colrev.settings.SearchSource(
                        endpoint="colrev.unknown_source",
                        filename=Path("search") / target_bib_file.name,
                        search_type=colrev.settings.SearchType.OTHER,
                        search_parameters={},
                        load_conversion_package_endpoint={},
                        comment="",
                    )

                    self.review_manager.settings.sources.append(new_source)
                    self.review_manager.save_settings()

                if 0 != len(import_records):
                    record_id = int(
                        self.review_manager.dataset.get_next_id(
                            bib_file=target_bib_file
                        )
                    )

                record["ID"] = f"{record_id}".rjust(10, "0")
                record.update(file=str(target_pdf_path))
                import_records.append(record)

                import_records_dict = {r["ID"]: r for r in import_records}
                self.review_manager.dataset.save_records_dict_to_file(
                    records=import_records_dict, save_path=target_bib_file
                )

                self.review_manager.dataset.add_changes(path=target_bib_file)


if __name__ == "__main__":
    pass
