#! /usr/bin/env python
import shutil
from pathlib import Path

import colrev_core.process
import colrev_core.settings


class Distribute(colrev_core.process.Process):
    def __init__(self, *, REVIEW_MANAGER):
        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            process_type=colrev_core.process.ProcessType.explore,
            notify_state_transition_process=False,
        )

    def main(self, *, path_str: str, target: Path) -> None:

        # if no options are given, take the current path/repo
        # optional: target-repo-path
        # path_str: could also be a url
        # option: chdir (to target repo)?
        # file: copy or move?

        path = Path.cwd() / Path(path_str)
        if path.is_file():
            if path.suffix == ".pdf":

                GrobidService = self.REVIEW_MANAGER.get_environment_service(
                    service_identifier="GrobidService"
                )
                GROBID_SERVICE = GrobidService()

                GROBID_SERVICE.start()

                TEIParser = self.REVIEW_MANAGER.get_environment_service(
                    service_identifier="TEIParser"
                )

                TEI_INSTANCE = TEIParser(
                    self.REVIEW_MANAGER,
                    path,
                )
                record = TEI_INSTANCE.get_metadata()

                target_pdf_path = target / "pdfs" / path.name
                target_pdf_path.parent.mkdir(parents=True, exist_ok=True)
                self.REVIEW_MANAGER.logger.info(f"Copy PDF to {target_pdf_path}")
                shutil.copyfile(path, target_pdf_path)

                self.REVIEW_MANAGER.logger.info(
                    f"append {self.REVIEW_MANAGER.pp.pformat(record)} "
                    "to search/local_import.bib"
                )
                target_bib_file = target / "search/local_import.bib"
                self.REVIEW_MANAGER.logger.info(f"target_bib_file: {target_bib_file}")
                if target_bib_file.is_file():
                    with open(target_bib_file, encoding="utf8") as target_bib:
                        import_records_dict = (
                            self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                                load_str=target_bib.read()
                            )
                        )
                        import_records = import_records_dict.values()
                else:
                    import_records = []

                    NEW_SOURCE = colrev_core.settings.SearchSource(
                        filename=Path("search") / target_bib_file.name,
                        search_type=colrev_core.settings.SearchType.OTHER,
                        source_name="locally_distributed_references",
                        source_identifier="",
                        search_parameters="",
                        search_script={},
                        conversion_script={},
                        source_prep_scripts=[{}],
                        comment="",
                    )

                    SOURCES = self.REVIEW_MANAGER.settings.sources
                    SOURCES.append(NEW_SOURCE)
                    self.REVIEW_MANAGER.save_settings()

                if 0 != len(import_records):
                    ID = int(
                        self.REVIEW_MANAGER.REVIEW_DATASET.get_next_ID(target_bib_file)
                    )

                record["ID"] = f"{ID}".rjust(10, "0")
                record.update(file=str(target_pdf_path))
                import_records.append(record)

                import_records_dict = {r["ID"]: r for r in import_records}
                self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict_to_file(
                    import_records_dict, save_path=target_bib_file
                )

                self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
                    path=str(target_bib_file)
                )


if __name__ == "__main__":
    pass
