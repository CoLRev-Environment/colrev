#! /usr/bin/env python
"""Retrieval of PDFs from the unpaywall API"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import requests
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from pdfminer.high_level import extract_text
from pdfminer.pdftypes import PDFException

import colrev.env.package_manager
import colrev.record

# pylint: disable=duplicate-code

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.pdf_get

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PDFGetPackageEndpointInterface)
@dataclass
class Unpaywall(JsonSchemaMixin):
    """Get PDFs from unpaywall.org"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = False

    def __init__(
        self,
        *,
        pdf_get_operation: colrev.ops.pdf_get.PDFGet,
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

        _, self.email = pdf_get_operation.review_manager.get_committer()

    def __unpaywall(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        doi: str,
        retry: int = 0,
        pdfonly: bool = True,
    ) -> str:
        url = f"https://api.unpaywall.org/v2/{doi}"

        try:
            ret = requests.get(url, params={"email": self.email}, timeout=30)
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
        except (PDFException, TypeError):
            return False

    def get_pdf(
        self, pdf_get_operation: colrev.ops.pdf_get.PDFGet, record: colrev.record.Record
    ) -> colrev.record.Record:
        """Get PDFs from unpaywall"""

        if "doi" not in record.data:
            return record

        pdf_filepath = pdf_get_operation.get_target_filepath(record=record)

        url = self.__unpaywall(
            review_manager=pdf_get_operation.review_manager, doi=record.data["doi"]
        )
        if url == "NA":
            return record
        if "Invalid/unknown DOI" in url:
            return record

        try:
            res = requests.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"
                },
                stream=True,
                timeout=30,
            )

            if 200 == res.status_code:
                pdf_filepath.parents[0].mkdir(exist_ok=True, parents=True)
                with open(pdf_filepath, "wb") as file:
                    file.write(res.content)
                if self.__is_pdf(path_to_file=pdf_filepath):
                    pdf_get_operation.review_manager.report_logger.debug(
                        "Retrieved pdf (unpaywall):" f" {pdf_filepath.name}"
                    )
                    source = (
                        f"https://api.unpaywall.org/v2/{record.data['doi']}"
                        + f"?email={self.email}"
                    )
                    record.update_field(
                        key="file", value=str(pdf_filepath), source=source
                    )
                    pdf_get_operation.import_file(record=record)

                else:
                    os.remove(pdf_filepath)
            else:
                if "fulltext" not in record.data:
                    record.data["fulltext"] = url
                if pdf_get_operation.review_manager.verbose_mode:
                    pdf_get_operation.review_manager.logger.info(
                        "Unpaywall retrieval error " f"{res.status_code} - {url}"
                    )
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ):
            pass

        return record


if __name__ == "__main__":
    pass
