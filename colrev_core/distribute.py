#! /usr/bin/env python
import logging
import shutil
from pathlib import Path

import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from local_paper_index import index

from colrev_core import grobid_client
from colrev_core.process import Process
from colrev_core.process import ProcessType

report_logger = logging.getLogger("colrev_core_report")
logger = logging.getLogger("colrev_core")


class Distribute(Process):
    def __init__(self):
        super().__init__(ProcessType.explore)

    def main(self, path_str: str, target: Path) -> None:

        # TODO: path_str or repo (possibly with conditions)
        # - if no options are given, take the current path/repo
        # optional: target-repo-path
        # path_str: could also be a url
        # option: chdir (to target repo)?
        # file: copy or move?

        path = Path.cwd() / Path(path_str)
        if path.is_file():
            if path.suffix == ".pdf":
                grobid_client.start_grobid()
                record = index.index_pdf(path)

                target_pdf_path = target / "pdfs" / path.name
                target_pdf_path.parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"Copy PDF to {target_pdf_path}")
                shutil.copyfile(path, target_pdf_path)

                logger.info(f"append {record} to search/local_import.bib")
                target_bib_file = target / "search/local_import.bib"
                logger.info(f"target_bib_file: {target_bib_file}")
                if target_bib_file.is_file():
                    with open(target_bib_file) as target_bib:
                        import_db = BibTexParser(
                            customization=convert_to_unicode,
                            ignore_nonstandard_types=False,
                            common_strings=True,
                        ).parse_file(target_bib, partial=True)
                else:
                    import_db = BibDatabase()

                writer = self.REVIEW_MANAGER.REVIEW_DATASET.get_bibtex_writer()

                if 0 != len(import_db.entries):
                    ID = int(index.get_last_ID(target_bib_file))
                    ID += 1
                else:
                    ID = 1

                record["ID"] = f"{ID}".rjust(10, "0")
                record.update(file=str(target_pdf_path))
                import_db.entries.append(record)

                bibtex_str = bibtexparser.dumps(import_db, writer)
                with open(target_bib_file, "w") as f:
                    f.write(bibtex_str)

        return


if __name__ == "__main__":
    pass
