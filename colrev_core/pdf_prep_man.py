#! /usr/bin/env python
import typing
from pathlib import Path

import pandas as pd
from PyPDF2 import PdfFileReader
from PyPDF2 import PdfFileWriter

import colrev_core.built_in.pdf_prep_man as built_in_pdf_prep_man
import colrev_core.process
import colrev_core.record


class PDFPrepMan(colrev_core.process.Process):

    built_in_scripts: typing.Dict[str, typing.Dict[str, typing.Any]] = {
        "colrev_cli_pdf_prep_man": {
            "endpoint": built_in_pdf_prep_man.CoLRevCLIPDFManPrep,
        }
    }

    def __init__(self, *, REVIEW_MANAGER, notify_state_transition_process: bool = True):

        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            process_type=colrev_core.process.ProcessType.pdf_prep_man,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.verbose = True

        AdapterManager = self.REVIEW_MANAGER.get_environment_service(
            service_identifier="AdapterManager"
        )
        self.pdf_prep_man_scripts: typing.Dict[
            str, typing.Any
        ] = AdapterManager.load_scripts(
            PROCESS=self,
            scripts=REVIEW_MANAGER.settings.pdf_prep.man_pdf_prep_scripts,
        )

    def get_data(self) -> dict:

        record_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
        nr_tasks = len(
            [
                x
                for x in record_state_list
                if str(colrev_core.record.RecordState.pdf_needs_manual_preparation)
                == x["colrev_status"]
            ]
        )
        PAD = min((max(len(x["ID"]) for x in record_state_list) + 2), 40)

        items = self.REVIEW_MANAGER.REVIEW_DATASET.read_next_record(
            conditions=[
                {
                    "colrev_status": colrev_core.record.RecordState.pdf_needs_manual_preparation
                }
            ]
        )
        pdf_prep_man_data = {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}
        self.REVIEW_MANAGER.logger.debug(
            self.REVIEW_MANAGER.pp.pformat(pdf_prep_man_data)
        )
        return pdf_prep_man_data

    def pdfs_prepared_manually(self) -> bool:
        return self.REVIEW_MANAGER.REVIEW_DATASET.has_changes()

    def pdf_prep_man_stats(self) -> None:
        # pylint: disable=duplicate-code

        self.REVIEW_MANAGER.logger.info(
            f"Load {self.REVIEW_MANAGER.paths['RECORDS_FILE_RELATIVE']}"
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        self.REVIEW_MANAGER.logger.info("Calculate statistics")
        stats: dict = {"ENTRYTYPE": {}}

        prep_man_hints = []
        crosstab = []
        for record in records.values():

            if (
                colrev_core.record.RecordState.pdf_needs_manual_preparation
                != record["colrev_status"]
            ):
                continue

            if record["ENTRYTYPE"] in stats["ENTRYTYPE"]:
                stats["ENTRYTYPE"][record["ENTRYTYPE"]] = (
                    stats["ENTRYTYPE"][record["ENTRYTYPE"]] + 1
                )
            else:
                stats["ENTRYTYPE"][record["ENTRYTYPE"]] = 1

            RECORD = colrev_core.record.Record(data=record)
            prov_d = RECORD.data["colrev_data_provenance"]

            if "file" in prov_d:
                if prov_d["file"]["note"] != "":
                    for hint in prov_d["file"]["note"].split(","):
                        prep_man_hints.append(hint.lstrip())

            for hint in prep_man_hints:
                crosstab.append([record["journal"], hint.lstrip()])

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
            self.REVIEW_MANAGER.logger.info(
                "Writing data to file: manual_preparation_statistics.csv"
            )
            tabulated.to_csv("manual_pdf_preparation_statistics.csv")

    def extract_needs_pdf_prep_man(self) -> None:

        prep_bib_path = self.REVIEW_MANAGER.paths["REPO_DIR"] / Path("prep-records.bib")
        prep_csv_path = self.REVIEW_MANAGER.paths["REPO_DIR"] / Path("prep-records.csv")

        if prep_csv_path.is_file():
            print(f"Please rename file to avoid overwriting changes ({prep_csv_path})")
            return

        if prep_bib_path.is_file():
            print(f"Please rename file to avoid overwriting changes ({prep_bib_path})")
            return

        self.REVIEW_MANAGER.logger.info(
            f"Load {self.REVIEW_MANAGER.paths['RECORDS_FILE_RELATIVE']}"
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        records = {
            record["ID"]: record
            for record in records.values()
            if colrev_core.record.RecordState.pdf_needs_manual_preparation
            == record["colrev_status"]
        }
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict_to_file(
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
        self.REVIEW_MANAGER.logger.info(f"Created {prep_csv_path.name}")

    def apply_pdf_prep_man(self) -> None:

        if Path("prep-records.csv").is_file():
            self.REVIEW_MANAGER.logger.info("Load prep-records.csv")
            bib_db_df = pd.read_csv("prep-records.csv")
            records_changed = bib_db_df.to_dict("records")

        if Path("prep-records.bib").is_file():
            self.REVIEW_MANAGER.logger.info("Load prep-records.bib")

            with open("prep-records.bib", encoding="utf8") as target_db:
                records_changed_dict = (
                    self.REVIEW_MANAGER.REVIEW_DATASEt.load_records_dict(
                        load_str=target_db.read()
                    )
                )
                records_changed = records_changed_dict.values()

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        for record in records.values():
            # IDs may change - matching based on origins
            changed_record_l = [
                x
                for x in records_changed
                if x["colrev_origin"] == record["colrev_origin"]
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

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        self.REVIEW_MANAGER.check_repo()

    def extract_coverpage(self, *, filepath: Path) -> None:

        LocalIndex = self.REVIEW_MANAGER.get_environment_service(
            service_identifier="LocalIndex"
        )
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

    def main(self) -> None:

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        for (
            PDF_PREP_MAN_SCRIPT
        ) in self.REVIEW_MANAGER.settings.pdf_prep.man_pdf_prep_scripts:

            if PDF_PREP_MAN_SCRIPT["endpoint"] not in self.pdf_prep_man_scripts:
                if self.verbose:
                    print(f"Error: endpoint not available: {PDF_PREP_MAN_SCRIPT}")
                continue

            endpoint = self.pdf_prep_man_scripts[PDF_PREP_MAN_SCRIPT["endpoint"]]

            ENDPOINT = endpoint["endpoint"]
            records = ENDPOINT.prep_man_pdf(self, records)


if __name__ == "__main__":
    pass
