#! /usr/bin/env python
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import requests
import zope.interface
from dacite import from_dict
from pdfminer.high_level import extract_text
from pdfminer.pdftypes import PDFException

import colrev.exceptions as colrev_exceptions
import colrev.process
import colrev.record

if TYPE_CHECKING:
    import colrev.review_manager.ReviewManager
    import colrev.pdf_get.PDFGet


@zope.interface.implementer(colrev.process.PDFGetEndpoint)
class UnpaywallEndpoint:
    def __init__(
        self,
        *,
        pdf_get_operation: colrev.pdf_get.PDFGet,  # pylint: disable=unused-argument
        settings,
    ):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def __unpaywall(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        doi: str,
        retry: int = 0,
        pdfonly: bool = True,
    ) -> str:

        url = "https://api.unpaywall.org/v2/{doi}"

        try:
            ret = requests.get(url, params={"email": review_manager.email})

            if ret.status_code == 500 and retry < 3:
                return self.__unpaywall(
                    review_manager=review_manager, doi=doi, retry=retry + 1
                )

            if ret.status_code in [404, 500]:
                return "NA"

            best_loc = None
            best_loc = ret.json()["best_oa_location"]

            assert ret.json()["is_oa"]
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

    def __is_pdf(self, *, path_to_file: Path) -> bool:
        try:
            extract_text(str(path_to_file))
            return True
        except PDFException:
            return False

    def get_pdf(
        self, pdf_get_operation: colrev.pdf_get.PDFGet, record: colrev.record.Record
    ) -> colrev.record.Record:

        if "doi" not in record.data:
            return record

        pdf_filepath = pdf_get_operation.review_manager.PDF_DIRECTORY_RELATIVE / Path(
            f"{record.data['ID']}.pdf"
        )
        url = self.__unpaywall(
            review_manager=pdf_get_operation.review_manager, doi=record.data["doi"]
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
                    with open(pdf_filepath, "wb") as file:
                        file.write(res.content)
                    if self.__is_pdf(path_to_file=pdf_filepath):
                        pdf_get_operation.review_manager.report_logger.info(
                            "Retrieved pdf (unpaywall):" f" {pdf_filepath.name}"
                        )
                        pdf_get_operation.review_manager.logger.info(
                            "Retrieved pdf (unpaywall):" f" {pdf_filepath.name}"
                        )
                        record.data.update(file=str(pdf_filepath))
                        record.data.update(
                            colrev_status=colrev.record.RecordState.rev_prescreen_included
                        )
                    else:
                        os.remove(pdf_filepath)
                else:
                    pdf_get_operation.review_manager.logger.info(
                        "Unpaywall retrieval error " f"{res.status_code}/{url}"
                    )

        return record


@zope.interface.implementer(colrev.process.PDFGetEndpoint)
class LocalIndexEndpoint:
    def __init__(
        self,
        *,
        pdf_get_operation: colrev.pdf_get.PDFGet,  # pylint: disable=unused-argument
        settings,
    ):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def get_pdf(
        self, pdf_get_operation: colrev.pdf_get.PDFGet, record: colrev.record.Record
    ) -> colrev.record.Record:

        local_index = pdf_get_operation.review_manager.get_local_index()

        try:
            retrieved_record = local_index.retrieve(
                record_dict=record.data, include_file=True
            )
            # print(Record(retrieved_record))
        except colrev_exceptions.RecordNotInIndexException:
            return record

        if "file" in retrieved_record:
            record.data["file"] = retrieved_record["file"]
            pdf_get_operation.review_manager.dataset.import_file(record=record.data)

        return record


@zope.interface.implementer(colrev.process.PDFGetEndpoint)
class WebsiteScreenshotEndpoint:
    def __init__(
        self,
        *,
        pdf_get_operation: colrev.pdf_get.PDFGet,  # pylint: disable=unused-argument
        settings,
    ):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def get_pdf(
        self, pdf_get_operation: colrev.pdf_get.PDFGet, record: colrev.record.Record
    ) -> colrev.record.Record:

        screenshot_service = pdf_get_operation.review_manager.get_screenshot_service()

        if "online" == record.data["ENTRYTYPE"]:
            screenshot_service.start_screenshot_service()

            pdf_filepath = (
                pdf_get_operation.review_manager.PDF_DIRECTORY_RELATIVE
                / Path(f"{record.data['ID']}.pdf")
            )
            record = screenshot_service.add_screenshot(
                record=record, pdf_filepath=pdf_filepath
            )

            if "file" in record.data:
                pdf_get_operation.review_manager.dataset.import_file(record=record.data)

        return record


if __name__ == "__main__":
    pass
