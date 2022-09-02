#! /usr/bin/env python
from __future__ import annotations

import typing
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from PyPDF2 import PdfFileReader
from PyPDF2 import PdfFileWriter

import colrev.built_in.pdf_prep_man as built_in_pdf_prep_man
import colrev.process
import colrev.record

if TYPE_CHECKING:
    import colrev.review_manager.ReviewManager


class PDFPrepMan(colrev.process.Process):

    built_in_scripts: dict[str, dict[str, typing.Any]] = {
        "colrev_cli_pdf_prep_man": {
            "endpoint": built_in_pdf_prep_man.CoLRevCLIPDFManPrep,
        }
    }

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
    ) -> None:

        super().__init__(
            review_manager=review_manager,
            process_type=colrev.process.ProcessType.pdf_prep_man,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.verbose = True

        adapter_manager = self.review_manager.get_adapter_manager()
        self.pdf_prep_man_scripts: dict[str, typing.Any] = adapter_manager.load_scripts(
            process=self,
            scripts=review_manager.settings.pdf_prep.man_pdf_prep_scripts,
        )

    def get_data(self) -> dict:

        record_state_list = self.review_manager.dataset.get_record_state_list()
        nr_tasks = len(
            [
                x
                for x in record_state_list
                if str(colrev.record.RecordState.pdf_needs_manual_preparation)
                == x["colrev_status"]
            ]
        )
        pad = min((max(len(x["ID"]) for x in record_state_list) + 2), 40)

        items = self.review_manager.dataset.read_next_record(
            conditions=[
                {
                    "colrev_status": colrev.record.RecordState.pdf_needs_manual_preparation
                }
            ]
        )
        pdf_prep_man_data = {"nr_tasks": nr_tasks, "PAD": pad, "items": items}
        self.review_manager.logger.debug(
            self.review_manager.p_printer.pformat(pdf_prep_man_data)
        )
        return pdf_prep_man_data

    def pdfs_prepared_manually(self) -> bool:
        return self.review_manager.dataset.has_changes()

    def pdf_prep_man_stats(self) -> None:
        # pylint: disable=duplicate-code

        self.review_manager.logger.info(
            f"Load {self.review_manager.dataset.RECORDS_FILE_RELATIVE}"
        )
        records = self.review_manager.dataset.load_records_dict()

        self.review_manager.logger.info("Calculate statistics")
        stats: dict = {"ENTRYTYPE": {}}

        prep_man_hints = []
        crosstab = []
        for record_dict in records.values():

            if (
                colrev.record.RecordState.pdf_needs_manual_preparation
                != record_dict["colrev_status"]
            ):
                continue

            if record_dict["ENTRYTYPE"] in stats["ENTRYTYPE"]:
                stats["ENTRYTYPE"][record_dict["ENTRYTYPE"]] = (
                    stats["ENTRYTYPE"][record_dict["ENTRYTYPE"]] + 1
                )
            else:
                stats["ENTRYTYPE"][record_dict["ENTRYTYPE"]] = 1

            record = colrev.record.Record(data=record_dict)
            prov_d = record.data["colrev_data_provenance"]

            if "file" in prov_d:
                if prov_d["file"]["note"] != "":
                    for hint in prov_d["file"]["note"].split(","):
                        prep_man_hints.append(hint.lstrip())

            for hint in prep_man_hints:
                crosstab.append([record_dict["journal"], hint.lstrip()])

        crosstab_df = pd.DataFrame(crosstab, columns=["journal", "hint"])

        if crosstab_df.empty:
            print("No records to prepare manually.")
        else:
            # pylint: disable=duplicate-code
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
            self.review_manager.logger.info(
                "Writing data to file: manual_preparation_statistics.csv"
            )
            tabulated.to_csv("manual_pdf_preparation_statistics.csv")

    def extract_needs_pdf_prep_man(self) -> None:

        prep_bib_path = self.review_manager.path / Path("prep-records.bib")
        prep_csv_path = self.review_manager.path / Path("prep-records.csv")

        if prep_csv_path.is_file():
            print(f"Please rename file to avoid overwriting changes ({prep_csv_path})")
            return

        if prep_bib_path.is_file():
            print(f"Please rename file to avoid overwriting changes ({prep_bib_path})")
            return

        self.review_manager.logger.info(
            f"Load {self.review_manager.dataset.RECORDS_FILE_RELATIVE}"
        )
        records = self.review_manager.dataset.load_records_dict()

        records = {
            record["ID"]: record
            for record in records.values()
            if colrev.record.RecordState.pdf_needs_manual_preparation
            == record["colrev_status"]
        }
        self.review_manager.dataset.save_records_dict_to_file(
            records=records, save_path=prep_bib_path
        )

        bib_db_df = pd.DataFrame.from_records(list(records.values()))

        # pylint: disable=duplicate-code
        col_names = [
            "ID",
            "colrev_origin",
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
        self.review_manager.logger.info(f"Created {prep_csv_path.name}")

    def apply_pdf_prep_man(self) -> None:

        if Path("prep-records.csv").is_file():
            self.review_manager.logger.info("Load prep-records.csv")
            bib_db_df = pd.read_csv("prep-records.csv")
            records_changed = bib_db_df.to_dict("records")

        if Path("prep-records.bib").is_file():
            self.review_manager.logger.info("Load prep-records.bib")

            with open("prep-records.bib", encoding="utf8") as target_db:
                records_changed_dict = self.review_manager.dataset.load_records_dict(
                    load_str=target_db.read()
                )
                records_changed = records_changed_dict.values()

        records = self.review_manager.dataset.load_records_dict()
        for record in records.values():
            # IDs may change - matching based on origins
            changed_record_l = [
                x
                for x in records_changed
                if x["colrev_origin"] == record["colrev_origin"]
            ]
            if len(changed_record_l) == 1:
                changed_record = changed_record_l.pop()
                for key, value in changed_record.items():
                    # if record['ID'] == 'Alter2014':
                    #     print(key, value)
                    if str(value) == "nan":
                        if key in record:
                            del record[key]
                        continue
                    record[key] = value
                    if value == "":
                        del record[key]

        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.check_repo()

    def extract_coverpage(self, *, filepath: Path) -> None:

        local_index = self.review_manager.get_local_index()
        cp_path = local_index.local_environment_path / Path(".coverpages")
        cp_path.mkdir(exist_ok=True)

        pdf_reader = PdfFileReader(str(filepath), strict=False)
        writer_cp = PdfFileWriter()
        writer_cp.addPage(pdf_reader.getPage(0))
        writer = PdfFileWriter()
        for i in range(1, pdf_reader.getNumPages()):
            writer.addPage(pdf_reader.getPage(i))
        with open(filepath, "wb") as outfile:
            writer.write(outfile)
        with open(cp_path / filepath.name, "wb") as outfile:
            writer_cp.write(outfile)

    def main(self) -> None:

        records = self.review_manager.dataset.load_records_dict()

        for (
            pdf_prep_man_script
        ) in self.review_manager.settings.pdf_prep.man_pdf_prep_scripts:

            if pdf_prep_man_script["endpoint"] not in self.pdf_prep_man_scripts:
                if self.verbose:
                    print(f"Error: endpoint not available: {pdf_prep_man_script}")
                continue

            endpoint_script = self.pdf_prep_man_scripts[pdf_prep_man_script["endpoint"]]

            endpoint = endpoint_script["endpoint"]
            records = endpoint.prep_man_pdf(self, records)


if __name__ == "__main__":
    pass
