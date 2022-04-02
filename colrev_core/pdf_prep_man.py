#! /usr/bin/env python
from pathlib import Path

import bibtexparser
import imagehash
import pandas as pd
from pdf2image import convert_from_path
from PyPDF2 import PdfFileReader
from PyPDF2 import PdfFileWriter

from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.process import RecordState


class PDFPrepMan(Process):
    def __init__(self, REVIEW_MANAGER, notify_state_transition_process: bool = True):

        super().__init__(
            REVIEW_MANAGER,
            ProcessType.pdf_prep_man,
            notify_state_transition_process=notify_state_transition_process,
        )

    def get_data(self) -> dict:

        record_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
        nr_tasks = len(
            [
                x
                for x in record_state_list
                if str(RecordState.pdf_needs_manual_preparation) == x[1]
            ]
        )
        PAD = min((max(len(x[0]) for x in record_state_list) + 2), 40)

        items = self.REVIEW_MANAGER.REVIEW_DATASET.read_next_record(
            conditions=[{"status": RecordState.pdf_needs_manual_preparation}]
        )
        pdf_prep_man_data = {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}
        self.REVIEW_MANAGER.logger.debug(
            self.REVIEW_MANAGER.pp.pformat(pdf_prep_man_data)
        )
        return pdf_prep_man_data

    def get_pdf_hash(self, path: Path) -> str:
        return str(
            imagehash.average_hash(
                convert_from_path(path, first_page=1, last_page=1)[0],
                hash_size=32,
            )
        )

    def set_data(self, record: dict) -> None:

        record.update(status=RecordState.pdf_prepared)

        if "pdf_prep_hints" in record:
            del record["pdf_prep_hints"]

        record.update(pdf_hash=self.get_pdf_hash(Path(record["file"])))

        self.REVIEW_MANAGER.REVIEW_DATASET.update_record_by_ID(record)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
            str(self.REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"])
        )

        return

    def pdfs_prepared_manually(self) -> bool:
        return self.REVIEW_MANAGER.REVIEW_DATASET.has_changes()

    def pdf_prep_man_stats(self) -> None:
        import pandas as pd

        self.REVIEW_MANAGER.logger.info(
            f"Load {self.REVIEW_MANAGER.paths['MAIN_REFERENCES_RELATIVE']}"
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()

        self.REVIEW_MANAGER.logger.info("Calculate statistics")
        stats: dict = {"ENTRYTYPE": {}}

        prep_man_hints = []
        crosstab = []
        for record in records:

            if RecordState.pdf_needs_manual_preparation != record["status"]:
                continue

            if record["ENTRYTYPE"] in stats["ENTRYTYPE"]:
                stats["ENTRYTYPE"][record["ENTRYTYPE"]] = (
                    stats["ENTRYTYPE"][record["ENTRYTYPE"]] + 1
                )
            else:
                stats["ENTRYTYPE"][record["ENTRYTYPE"]] = 1

            if "pdf_prep_hints" in record:
                hints = record["pdf_prep_hints"].split(";")
                prep_man_hints.append([hint.lstrip() for hint in hints])

                for hint in hints:
                    crosstab.append([record["journal"], hint.lstrip()])

        crosstab_df = pd.DataFrame(crosstab, columns=["journal", "hint"])

        if crosstab_df.empty:
            print("No records to prepare manually.")
        else:
            tabulated = pd.pivot_table(
                crosstab_df[["journal", "hint"]],
                index=["journal"],
                columns=["hint"],
                aggfunc=len,
                fill_value=0,
                margins=True,
            )
            # .sort_index(axis='columns')
            tabulated.sort_values(by=["All"], ascending=False, inplace=True)
            # Transpose because we tend to have more error categories than search files.
            tabulated = tabulated.transpose()
            print(tabulated)
            self.REVIEW_MANAGER.logger.info(
                "Writing data to file: manual_preparation_statistics.csv"
            )
            tabulated.to_csv("manual_pdf_preparation_statistics.csv")

        return

    def extract_needs_pdf_prep_man(self) -> None:
        from bibtexparser.bibdatabase import BibDatabase

        prep_bib_path = self.REVIEW_MANAGER.paths["REPO_DIR"] / Path(
            "prep-references.bib"
        )
        prep_csv_path = self.REVIEW_MANAGER.paths["REPO_DIR"] / Path(
            "prep-references.csv"
        )

        if prep_csv_path.is_file():
            print(f"Please rename file to avoid overwriting changes ({prep_csv_path})")
            return

        if prep_bib_path.is_file():
            print(f"Please rename file to avoid overwriting changes ({prep_bib_path})")
            return

        self.REVIEW_MANAGER.logger.info(
            f"Load {self.REVIEW_MANAGER.paths['MAIN_REFERENCES_RELATIVE']}"
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()

        records = [
            record
            for record in records
            if RecordState.pdf_needs_manual_preparation == record["status"]
        ]

        # Casting to string (in particular the RecordState Enum)
        records = [{k: str(v) for k, v in r.items()} for r in records]

        bib_db = BibDatabase()
        bib_db.entries = records
        bibtex_str = bibtexparser.dumps(bib_db)
        with open(prep_bib_path, "w") as out:
            out.write(bibtex_str)

        bib_db_df = pd.DataFrame.from_records(records)

        col_names = [
            "ID",
            "origin",
            "author",
            "title",
            "year",
            "journal",
            # "booktitle",
            "volume",
            "number",
            "pages",
            "doi",
        ]
        for col_name in col_names:
            if col_name not in bib_db_df:
                bib_db_df[col_name] = "NA"
        bib_db_df = bib_db_df[col_names]

        bib_db_df.to_csv(prep_csv_path, index=False)
        self.REVIEW_MANAGER.logger.info(f"Created {prep_csv_path.name}")

        return

    def apply_pdf_prep_man(self) -> None:

        if Path("prep-references.csv").is_file():
            self.REVIEW_MANAGER.logger.info("Load prep-references.csv")
            bib_db_df = pd.read_csv("prep-references.csv")
            bib_db_changed = bib_db_df.to_dict("records")
        if Path("prep-references.bib").is_file():
            self.REVIEW_MANAGER.logger.info("Load prep-references.bib")

            from bibtexparser.bparser import BibTexParser
            from bibtexparser.customization import convert_to_unicode

            with open("prep-references.bib") as target_db:
                bib_db = BibTexParser(
                    customization=convert_to_unicode,
                    ignore_nonstandard_types=False,
                    common_strings=True,
                ).parse_file(target_db, partial=True)

                bib_db_changed = bib_db.entries

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()
        for record in records:
            # IDs may change - matching based on origins
            changed_record_l = [
                x for x in bib_db_changed if x["origin"] == record["origin"]
            ]
            if len(changed_record_l) == 1:
                changed_record = changed_record_l.pop()
                for k, v in changed_record.items():
                    # if record['ID'] == 'Alter2014':
                    #     print(k, v)
                    if str(v) == "nan":
                        if k in record:
                            del record[k]
                        continue
                    record[k] = v
                    if v == "":
                        del record[k]

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)
        self.REVIEW_MANAGER.format_references()
        self.REVIEW_MANAGER.check_repo()
        return

    def extract_coverpage(self, filepath: Path) -> None:
        from colrev_core.environment import LocalIndex

        cp_path = LocalIndex.local_environment_path / Path(".coverpages")
        cp_path.mkdir(exist_ok=True)

        pdfReader = PdfFileReader(str(filepath), strict=False)
        writer_cp = PdfFileWriter()
        writer_cp.addPage(pdfReader.getPage(0))
        writer = PdfFileWriter()
        for i in range(1, pdfReader.getNumPages()):
            writer.addPage(pdfReader.getPage(i))
        with open(filepath, "wb") as outfile:
            writer.write(outfile)
        with open(cp_path / filepath.name, "wb") as outfile:
            writer_cp.write(outfile)
        return


if __name__ == "__main__":
    pass
