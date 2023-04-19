#! /usr/bin/env python
"""Connector to doi.org (API)"""
from __future__ import annotations

import json
from sqlite3 import OperationalError
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.search_sources.utils as connector_utils
import colrev.record


if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.prep

# Note: not (yet) implemented as a full search_source
# (including SearchSourcePackageEndpointInterface, packages_endpoints.json)

# pylint: disable=too-few-public-methods


class DOIConnector:
    """Connector for the DOI.org API"""

    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.oni

    @classmethod
    def retrieve_doi_metadata(
        cls,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        record: colrev.record.PrepRecord,
        timeout: int = 60,
    ) -> colrev.record.Record:
        """Retrieve the metadata from DOI.org based on a record (similarity)"""

        if "doi" not in record.data:
            return record

        try:
            session = review_manager.get_cached_session()

            # for testing:
            # curl -iL -H "accept: application/vnd.citationstyles.csl+json"
            # -H "Content-Type: application/json" http://dx.doi.org/10.1111/joop.12368

            try:
                url = "http://dx.doi.org/" + record.data["doi"]
                # review_manager.logger.debug(url)
                headers = {"accept": "application/vnd.citationstyles.csl+json"}
                ret = session.request("GET", url, headers=headers, timeout=timeout)
                ret.raise_for_status()
                if ret.status_code != 200:
                    review_manager.report_logger.info(
                        f' {record.data["ID"]}'
                        + "metadata for "
                        + f'doi  {record.data["doi"]} not (yet) available'
                    )
                    return record
            except OperationalError as exc:
                raise colrev_exceptions.ServiceNotAvailableException(
                    "sqlite, required for requests CachedSession "
                    "(possibly caused by concurrent operations)"
                ) from exc

            retrieved_json = json.loads(ret.text)
            language_service = colrev.env.language_service.LanguageService()
            retrieved_record_dict = connector_utils.json_to_record(item=retrieved_json)
            language_service.unify_to_iso_639_3_language_codes(record=record)
            retrieved_record = colrev.record.PrepRecord(data=retrieved_record_dict)
            retrieved_record.add_provenance_all(source=url)
            record.merge(merging_record=retrieved_record, default_source=url)
            record.set_masterdata_complete(source=url)
            record.set_status(target_state=colrev.record.RecordState.md_prepared)
            if "retracted" in record.data.get("warning", ""):
                record.prescreen_exclude(reason="retracted")
                record.remove_field(key="warning")

            if "title" in record.data:
                record.format_if_mostly_upper(key="title")

        except (
            requests.exceptions.RequestException,
            colrev_exceptions.InvalidMerge,
        ) as exc:
            print(exc)

        return record

    @classmethod
    def get_link_from_doi(
        cls,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        record: colrev.record.Record,
        timeout: int = 30,
    ) -> None:
        """Get the website link from DOI resolution API"""

        if "doi" not in record.data:
            return

        doi_url = f"https://www.doi.org/{record.data['doi']}"

        def meta_redirect(*, content: bytes) -> str:
            if "<!DOCTYPE HTML PUBLIC" not in str(content):
                raise TypeError
            soup = BeautifulSoup(content, "lxml")
            result = soup.find("meta", attrs={"http-equiv": "REFRESH"})
            if result:
                _, text = result["content"].split(";")
                if "http" in text:
                    url = text[text.lower().find("http") :]
                    url = unquote(url, encoding="utf-8", errors="replace")
                    url = url[: url.find("?")]
                    return str(url)
            return ""

        try:
            url = doi_url

            session = review_manager.get_cached_session()

            requests_headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/39.0.2171.95 Safari/537.36"
            }
            ret = session.request(
                "GET",
                doi_url,
                headers=requests_headers,
                timeout=timeout,
            )
            if 503 == ret.status_code:
                return
            if (
                200 == ret.status_code
                and "doi.org" not in ret.url
                and "linkinghub" not in ret.url
            ):
                url = ret.url
            else:
                # follow the chain of redirects
                while meta_redirect(content=ret.content):
                    url = meta_redirect(content=ret.content)
                    ret = session.request(
                        "GET",
                        url,
                        headers=requests_headers,
                        timeout=timeout,
                    )
            record.update_field(
                key="url",
                value=str(url.rstrip("/")),
                source=doi_url,
                keep_source_if_equal=True,
                append_edit=False,
            )
        except (requests.exceptions.RequestException, TypeError, UnicodeDecodeError):
            pass
        except OperationalError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            ) from exc


if __name__ == "__main__":
    pass
