#! /usr/bin/env python
"""Retrieval of PDFs from the unpaywall API"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from pdfminer.high_level import extract_text
from pdfminer.pdftypes import PDFException

import colrev.env.package_manager
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.pdf_get

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PDFGetPackageInterface)
@dataclass
class Unpaywall(JsonSchemaMixin):
    """Get PDFs from unpaywall.org"""

    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(
        self,
        *,
        pdf_get_operation: colrev.ops.pdf_get.PDFGet,  # pylint: disable=unused-argument
        settings,
    ):
        self.settings = from_dict(data_class=self.settings_class, data=settings)

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
        self, pdf_get_operation: colrev.ops.pdf_get.PDFGet, record: colrev.record.Record
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


if __name__ == "__main__":
    pass
