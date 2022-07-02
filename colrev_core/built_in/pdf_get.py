#! /usr/bin/env python
import json
import os
from pathlib import Path

import requests
import zope.interface
from pdfminer.high_level import extract_text

from colrev_core.process import PDFRetrievalEndpoint
from colrev_core.record import RecordState


@zope.interface.implementer(PDFRetrievalEndpoint)
class UnpaywallEndpoint:
    @classmethod
    def __unpaywall(
        cls, *, REVIEW_MANAGER, doi: str, retry: int = 0, pdfonly: bool = True
    ) -> str:

        url = "https://api.unpaywall.org/v2/{doi}"

        try:
            r = requests.get(url, params={"email": REVIEW_MANAGER.EMAIL})

            if r.status_code == 404:
                return "NA"

            if r.status_code == 500:
                if retry < 3:
                    return cls.__unpaywall(
                        REVIEW_MANAGER=REVIEW_MANAGER, doi=doi, retry=retry + 1
                    )
                else:
                    return "NA"

            best_loc = None
            best_loc = r.json()["best_oa_location"]
        except json.decoder.JSONDecodeError:
            return "NA"
        except KeyError:
            return "NA"
        except requests.exceptions.RequestException:
            return "NA"

        if not r.json()["is_oa"] or best_loc is None:
            return "NA"

        if best_loc["url_for_pdf"] is None and pdfonly is True:
            return "NA"
        else:
            return best_loc["url_for_pdf"]

    @classmethod
    def __is_pdf(cls, *, path_to_file: str) -> bool:
        try:
            extract_text(path_to_file)
            return True
        except:  # noqa E722
            return False

    @classmethod
    def get_pdf(cls, REVIEW_MANAGER, RECORD):

        if "doi" not in RECORD.data:
            return RECORD

        pdf_filepath = REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"] / Path(
            f"{RECORD.data['ID']}.pdf"
        )
        url = cls.__unpaywall(REVIEW_MANAGER=REVIEW_MANAGER, doi=RECORD.data["doi"])
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
                    if cls.__is_pdf(path_to_file=pdf_filepath):
                        REVIEW_MANAGER.report_logger.info(
                            "Retrieved pdf (unpaywall):" f" {pdf_filepath.name}"
                        )
                        REVIEW_MANAGER.logger.info(
                            "Retrieved pdf (unpaywall):" f" {pdf_filepath.name}"
                        )
                        RECORD.data.update(file=str(pdf_filepath))
                        RECORD.data.update(
                            colrev_status=RecordState.rev_prescreen_included
                        )
                    else:
                        os.remove(pdf_filepath)
                else:
                    REVIEW_MANAGER.logger.info(
                        "Unpaywall retrieval error " f"{res.status_code}/{url}"
                    )

        return RECORD


@zope.interface.implementer(PDFRetrievalEndpoint)
class LocalIndexEndpoint:
    @classmethod
    def get_pdf(cls, REVIEW_MANAGER, RECORD):
        from colrev_core.environment import LocalIndex, RecordNotInIndexException

        LOCAL_INDEX = LocalIndex()
        try:
            retrieved_record = LOCAL_INDEX.retrieve(
                record=RECORD.data, include_file=True
            )
            # print(Record(retrieved_record))
        except RecordNotInIndexException:
            pass
            return RECORD

        if "file" in retrieved_record:
            RECORD.data["file"] = retrieved_record["file"]
            REVIEW_MANAGER.REVIEW_DATASET.import_file(record=RECORD.data)

        return RECORD


@zope.interface.implementer(PDFRetrievalEndpoint)
class WebsiteScreenshotEndpoint:
    @classmethod
    def get_pdf(cls, REVIEW_MANAGER, RECORD):
        from colrev_core.environment import ScreenshotService

        if "online" == RECORD.data["ENTRYTYPE"]:
            SCREENSHOT_SERVICE = ScreenshotService()
            SCREENSHOT_SERVICE.start_screenshot_service()

            pdf_filepath = REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"] / Path(
                f"{RECORD.data['ID']}.pdf"
            )
            RECORD = SCREENSHOT_SERVICE.add_screenshot(
                RECORD=RECORD, pdf_filepath=pdf_filepath
            )

            if "file" in RECORD.data:
                REVIEW_MANAGER.REVIEW_DATASET.import_file(record=RECORD.data)

        return RECORD
