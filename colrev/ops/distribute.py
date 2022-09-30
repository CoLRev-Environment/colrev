#! /usr/bin/env python
"""Distribte records or PDFs to local CoLRev repositories."""
from __future__ import annotations

import os
import shutil
import typing
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from yaml import safe_load

import colrev.operation
import colrev.settings

if TYPE_CHECKING:
    import colrev.review_manager


class Distribute(colrev.operation.Operation):
    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.check,
            notify_state_transition_operation=False,
        )

    def get_local_registry(self) -> list:
        local_registry_path = Path.home().joinpath("colrev/registry.yaml")
        local_registry: typing.List[str] = []
        if not os.path.exists(local_registry_path):
            print("no local repositories registered")
            return local_registry

        with open(local_registry_path, encoding="utf-8") as file:
            local_registry_df = pd.json_normalize(safe_load(file))
            local_registry_dict = local_registry_df.to_dict("records")
            local_registry = [
                x["repo_source_path"]
                for x in local_registry_dict
                if "curated_metadata/" not in x["repo_source_path"]
            ]
        return local_registry

    def main(self, *, path: Path, target: Path) -> None:

        # if no options are given, take the current path/repo
        # optional: target-repo-path
        # path_str: could also be a url
        # option: chdir (to target repo)?
        # file: copy or move?

        os.chdir(target)
        path = Path.cwd() / Path(path)

        if path.is_file():

            if path.suffix == ".bib":
                # TODO : append records (check duplicates/duplicate IDs)
                # if path already exists
                path.rename(target / Path("data/search/local_import.bib"))
                input(path)

            if path.suffix == ".pdf":

                # Note : this is actually correct: camel case for classes...
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
                        endpoint="colrev_built_in.unknown_source",
                        filename=Path("search") / target_bib_file.name,
                        search_type=colrev.settings.SearchType.OTHER,
                        source_identifier="",
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
