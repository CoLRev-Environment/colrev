#! /usr/bin/env python
import shutil
from pathlib import Path

import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

from colrev_core import grobid_client
from colrev_core.process import Process
from colrev_core.process import ProcessType


class Distribute(Process):
    def __init__(self, REVIEW_MANAGER):
        super().__init__(
            REVIEW_MANAGER,
            type=ProcessType.explore,
            notify_state_transition_process=False,
        )

    def get_last_ID(self, bib_file: Path) -> str:
        current_ID = "1"
        if bib_file.is_file():
            with open(bib_file) as f:
                line = f.readline()
                while line:
                    if "@" in line[:3]:
                        current_ID = line[line.find("{") + 1 : line.rfind(",")]
                    line = f.readline()
        return current_ID

    def main(self, path_str: str, target: Path) -> None:
        from colrev_core.tei import TEI

        # if no options are given, take the current path/repo
        # optional: target-repo-path
        # path_str: could also be a url
        # option: chdir (to target repo)?
        # file: copy or move?

        path = Path.cwd() / Path(path_str)
        if path.is_file():
            if path.suffix == ".pdf":
                grobid_client.start_grobid()
                TEI_INSTANCE = TEI(
                    self.REVIEW_MANAGER,
                    path,
                    notify_state_transition_process=False,
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
                    with open(target_bib_file) as target_bib:
                        import_db = BibTexParser(
                            customization=convert_to_unicode,
                            ignore_nonstandard_types=False,
                            common_strings=True,
                        ).parse_file(target_bib, partial=True)
                else:
                    import_db = BibDatabase()
                    new_record = {
                        "filename": str(target_bib_file.name),
                        "search_type": "OTHER",
                        "source_name": "Local import",
                        "source_url": str(target_bib_file.name),
                        "search_parameters": "",
                        "comment": "",
                    }

                    sources = self.REVIEW_MANAGER.REVIEW_DATASET.load_sources()
                    sources.append(new_record)
                    self.REVIEW_MANAGER.REVIEW_DATASET.save_sources(sources)

                writer = self.REVIEW_MANAGER.REVIEW_DATASET.get_bibtex_writer()

                if 0 != len(import_db.entries):
                    ID = int(self.get_last_ID(target_bib_file))
                    ID += 1
                else:
                    ID = 1

                record["ID"] = f"{ID}".rjust(10, "0")
                record.update(file=str(target_pdf_path))
                import_db.entries.append(record)

                bibtex_str = bibtexparser.dumps(import_db, writer)
                with open(target_bib_file, "w") as f:
                    f.write(bibtex_str)
                self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(str(target_bib_file))

        return


if __name__ == "__main__":
    pass
