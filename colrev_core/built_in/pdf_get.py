#! /usr/bin/env python
import json
import os
from pathlib import Path

import requests
import zope.interface
from dacite import from_dict
from pdfminer.high_level import extract_text
from pdfminer.pdftypes import PDFException

import colrev_core.exceptions as colrev_exceptions
import colrev_core.process
import colrev_core.record


@zope.interface.implementer(colrev_core.process.PDFRetrievalEndpoint)
class UnpaywallEndpoint:
    def __init__(self, *, PDF_GET, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    def __unpaywall(
        self, *, REVIEW_MANAGER, doi: str, retry: int = 0, pdfonly: bool = True
    ) -> str:

        url = "https://api.unpaywall.org/v2/{doi}"

        try:
            r = requests.get(url, params={"email": REVIEW_MANAGER.EMAIL})

            if r.status_code == 500 and retry < 3:
                return self.__unpaywall(
                    REVIEW_MANAGER=REVIEW_MANAGER, doi=doi, retry=retry + 1
                )

            if r.status_code in [404, 500]:
                return "NA"

            best_loc = None
            best_loc = r.json()["best_oa_location"]

            assert r.json()["is_oa"]
            assert best_loc is not None
            assert not (pdfonly and best_loc["url_for_pdf"] is None)

        except (
            json.decoder.JSONDecodeError,
            KeyError,
            requests.exceptions.RequestException,
            AssertionError,
        ):
            return "NA"

        return best_loc["url_for_pdf"]

    def __is_pdf(self, *, path_to_file: str) -> bool:
        try:
            extract_text(path_to_file)
            return True
        except PDFException:
            return False

    def get_pdf(self, PDF_RETRIEVAL, RECORD):

        if "doi" not in RECORD.data:
            return RECORD

        pdf_filepath = PDF_RETRIEVAL.REVIEW_MANAGER.paths[
            "PDF_DIRECTORY_RELATIVE"
        ] / Path(f"{RECORD.data['ID']}.pdf")
        url = self.__unpaywall(
            REVIEW_MANAGER=PDF_RETRIEVAL.REVIEW_MANAGER, doi=RECORD.data["doi"]
        )
        if "NA" != url:
            if "Invalid/unknown DOI" not in url:
                res = requests.get(
                    url,
                    headers={
                        "User-Agent": "Chrome/51.0.2704.103",
                        "referer": "https://www.doi.org",
                    },
                )
                if 200 == res.status_code:
                    with open(pdf_filepath, "wb") as f:
                        f.write(res.content)
                    if self.__is_pdf(path_to_file=pdf_filepath):
                        PDF_RETRIEVAL.REVIEW_MANAGER.report_logger.info(
                            "Retrieved pdf (unpaywall):" f" {pdf_filepath.name}"
                        )
                        PDF_RETRIEVAL.REVIEW_MANAGER.logger.info(
                            "Retrieved pdf (unpaywall):" f" {pdf_filepath.name}"
                        )
                        RECORD.data.update(file=str(pdf_filepath))
                        RECORD.data.update(
                            colrev_status=colrev_core.record.RecordState.rev_prescreen_included
                        )
                    else:
                        os.remove(pdf_filepath)
                else:
                    PDF_RETRIEVAL.REVIEW_MANAGER.logger.info(
                        "Unpaywall retrieval error " f"{res.status_code}/{url}"
                    )

        return RECORD


@zope.interface.implementer(colrev_core.process.PDFRetrievalEndpoint)
class LocalIndexEndpoint:
    def __init__(self, *, PDF_GET, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    def get_pdf(self, PDF_RETRIEVAL, RECORD):

        LocalIndex = PDF_RETRIEVAL.REVIEW_MANAGER.get_environment_service(
            service_identifier="LocalIndex"
        )

        LOCAL_INDEX = LocalIndex()
        try:
            retrieved_record = LOCAL_INDEX.retrieve(
                record=RECORD.data, include_file=True
            )
            # print(Record(retrieved_record))
        except colrev_exceptions.RecordNotInIndexException:
            return RECORD

        if "file" in retrieved_record:
            RECORD.data["file"] = retrieved_record["file"]
            PDF_RETRIEVAL.REVIEW_MANAGER.REVIEW_DATASET.import_file(record=RECORD.data)

        return RECORD


@zope.interface.implementer(colrev_core.process.PDFRetrievalEndpoint)
class WebsiteScreenshotEndpoint:
    def __init__(self, *, PDF_GET, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    def get_pdf(self, PDF_RETRIEVAL, RECORD):

        ScreenshotService = PDF_RETRIEVAL.REVIEW_MANAGER.get_environment_service(
            service_identifier="ScreenshotService"
        )

        if "online" == RECORD.data["ENTRYTYPE"]:
            SCREENSHOT_SERVICE = ScreenshotService()
            SCREENSHOT_SERVICE.start_screenshot_service()

            pdf_filepath = PDF_RETRIEVAL.REVIEW_MANAGER.paths[
                "PDF_DIRECTORY_RELATIVE"
            ] / Path(f"{RECORD.data['ID']}.pdf")
            RECORD = SCREENSHOT_SERVICE.add_screenshot(
                RECORD=RECORD, pdf_filepath=pdf_filepath
            )

            if "file" in RECORD.data:
                PDF_RETRIEVAL.REVIEW_MANAGER.REVIEW_DATASET.import_file(
                    record=RECORD.data
                )

        return RECORD
