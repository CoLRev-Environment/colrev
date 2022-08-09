#! /usr/bin/env python
import zope.interface
from dacite import from_dict
from dacite.exceptions import MissingValueError

import colrev_core.process


@zope.interface.implementer(colrev_core.process.PDFRetrievalManualEndpoint)
class CoLRevCLIPDFRetrievalManual:
    def __init__(self, *, PDF_RETRIEVAL_MAN, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    def get_man_pdf(self, PDF_RETRIEVAL_MAN, records):

        import colrev_core.pdf_get
        import colrev_core.review_manager
        import colrev_core.record

        def get_pdf_from_google(RECORD) -> dict:
            import urllib.parse

            # import webbrowser

            title = RECORD.data.get("title", "no title")
            title = urllib.parse.quote_plus(title)
            url = f"https://www.google.com/search?q={title}+filetype%3Apdf"
            # webbrowser.open_new_tab(url)
            print(url)
            return RECORD

        def pdf_get_man_record_cli(*, PDF_RETRIEVAL_MAN, RECORD) -> None:
            import colrev_core.record

            PDF_RETRIEVAL_MAN.REVIEW_MANAGER.logger.debug(
                f"called pdf_get_man_cli for {RECORD}"
            )

            # to print only the essential information
            print(colrev_core.record.PrescreenRecord(data=RECORD.get_data()))

            if (
                colrev_core.record.RecordState.pdf_needs_manual_retrieval
                != RECORD.data["colrev_status"]
            ):
                return

            retrieval_scripts = {
                "get_pdf_from_google": get_pdf_from_google,
                # 'get_pdf_from_researchgate': get_pdf_from_researchgate,
            }

            filepath = (
                PDF_RETRIEVAL_MAN.REVIEW_MANAGER.paths["PDF_DIRECTORY"]
                / f"{RECORD.data['ID']}.pdf"
            )

            for script_name, retrieval_script in retrieval_scripts.items():
                PDF_RETRIEVAL_MAN.REVIEW_MANAGER.logger.debug(
                    f'{script_name}({RECORD.data["ID"]}) called'
                )
                RECORD = retrieval_script(RECORD)

                if "y" == input("Retrieved (y/n)?"):
                    if not filepath.is_file():
                        print(f'File does not exist: {RECORD.data["ID"]}.pdf')
                    else:
                        filepath = (
                            PDF_RETRIEVAL_MAN.REVIEW_MANAGER.paths[
                                "PDF_DIRECTORY_RELATIVE"
                            ]
                            / f"{RECORD.data['ID']}.pdf"
                        )
                        RECORD.pdf_get_man(
                            REVIEW_MANAGER=PDF_RETRIEVAL_MAN.REVIEW_MANAGER,
                            filepath=filepath,
                        )
                        break

            if not filepath.is_file():
                if "n" == input("Is the PDF available (y/n)?"):
                    RECORD.pdf_get_man(
                        REVIEW_MANAGER=PDF_RETRIEVAL_MAN.REVIEW_MANAGER, filepath=None
                    )

        try:
            REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
        except MissingValueError as e:
            print(f"Error in settings.json: {e}")
            print("To solve this, use\n  colrev settings --upgrade")
            return

        saved_args = locals()
        REVIEW_MANAGER.logger.info("Retrieve PDFs manually")
        PDF_RETRIEVAL = colrev_core.pdf_get.PDF_Retrieval(REVIEW_MANAGER=REVIEW_MANAGER)
        PDF_DIRECTORY = PDF_RETRIEVAL_MAN.REVIEW_MANAGER.paths["PDF_DIRECTORY"]

        records = PDF_RETRIEVAL_MAN.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        records = PDF_RETRIEVAL.check_existing_unlinked_pdfs(records=records)

        for record in records.values():
            RECORD = colrev_core.record.Record(data=record)
            record = PDF_RETRIEVAL.link_pdf(RECORD).get_data()

        PDF_RETRIEVAL_MAN.export_retrieval_table(records=records)
        pdf_get_man_data = PDF_RETRIEVAL_MAN.get_data()

        print(
            "\nInstructions\n\n      "
            "Get the pdfs, rename them (ID.pdf) and store them in the pdfs directory.\n"
        )
        input("Enter to start.")

        for i, item in enumerate(pdf_get_man_data["items"]):
            stat = str(i + 1) + "/" + str(pdf_get_man_data["nr_tasks"])

            record = records[item["ID"]]
            RECORD = colrev_core.record.Record(data=record)

            print(stat)

            pdf_get_man_record_cli(PDF_RETRIEVAL_MAN=PDF_RETRIEVAL_MAN, RECORD=RECORD)

        if PDF_RETRIEVAL_MAN.REVIEW_MANAGER.REVIEW_DATASET.has_changes():
            if "y" == input("Create commit (y/n)?"):
                PDF_RETRIEVAL_MAN.REVIEW_MANAGER.create_commit(
                    msg="Retrieve PDFs manually",
                    manual_author=True,
                    saved_args=saved_args,
                )
        else:
            REVIEW_MANAGER.logger.info(
                "Retrieve PDFs manually and copy the files to "
                f"the {PDF_DIRECTORY}. Afterwards, use "
                "colrev_core pdf-get-man"
            )

        return records
