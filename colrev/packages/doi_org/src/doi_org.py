#! /usr/bin/env python
"""Connector to doi.org (API)"""
from __future__ import annotations

import json
import re
from sqlite3 import OperationalError
from urllib.parse import unquote

import requests

import colrev.exceptions as colrev_exceptions
import colrev.package_manager.package_manager
import colrev.record.record
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import RecordState
from colrev.constants import SearchSourceHeuristicStatus
from colrev.packages.crossref.src import record_transformer

# Note: not (yet) implemented as a full search_source
# (including SearchSourceInterface, packages_endpoints.json)

# pylint: disable=too-few-public-methods


class DOIConnector:
    """Connector for the DOI.org API"""

    heuristic_status = SearchSourceHeuristicStatus.oni

    @classmethod
    def retrieve_doi_metadata(
        cls,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        record: colrev.record.record_prep.PrepRecord,
        timeout: int = 60,
    ) -> colrev.record.record.Record:
        """Retrieve the metadata from DOI.org based on a record (similarity)"""

        if Fields.DOI not in record.data:
            return record

        try:
            session = review_manager.get_cached_session()

            # for testing:
            # curl -iL -H "accept: application/vnd.citationstyles.csl+json"
            # -H "Content-Type: application/json" http://dx.doi.org/10.1111/joop.12368

            try:
                url = "http://dx.doi.org/" + record.data[Fields.DOI]
                # review_manager.logger.debug(url)
                headers = {"accept": "application/vnd.citationstyles.csl+json"}
                ret = session.request("GET", url, headers=headers, timeout=timeout)
                ret.raise_for_status()
                if ret.status_code != 200:
                    review_manager.report_logger.info(
                        f" {record.data[Fields.ID]}"
                        + "metadata for "
                        + f"doi  {record.data[Fields.DOI]} not (yet) available"
                    )
                    return record
            except OperationalError as exc:
                raise colrev_exceptions.ServiceNotAvailableException(
                    "sqlite, required for requests CachedSession "
                    "(possibly caused by concurrent operations)"
                ) from exc

            retrieved_json = json.loads(ret.text)
            language_service = colrev.env.language_service.LanguageService()
            language_service.unify_to_iso_639_3_language_codes(record=record)
            retrieved_record = record_transformer.json_to_record(item=retrieved_json)
            retrieved_record.add_provenance_all(source=url)
            record.merge(retrieved_record, default_source=url)
            record.set_masterdata_complete(
                source=url,
                masterdata_repository=review_manager.settings.is_curated_repo(),
            )
            record.set_status(RecordState.md_prepared)
            if FieldValues.RETRACTED in record.data.get("warning", ""):
                record.prescreen_exclude(reason=FieldValues.RETRACTED)
                record.remove_field(key="warning")

            if Fields.TITLE in record.data:
                record.format_if_mostly_upper(Fields.TITLE, case="sentence")

        except (requests.exceptions.RequestException,) as exc:
            print(exc)

        return record

    @classmethod
    def get_link_from_doi(
        cls,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        record: colrev.record.record.Record,
        timeout: int = 30,
    ) -> None:
        """Get the website link from DOI resolution API"""

        if Fields.DOI not in record.data:
            return

        doi_url = f"https://www.doi.org/{record.data['doi']}"

        def meta_redirect(*, content: bytes) -> str:
            content_str = content.decode("utf-8", errors="replace")

            # Ensure the content is of the expected type (contains the DOCTYPE)
            if "<!DOCTYPE HTML PUBLIC" not in content_str:
                raise TypeError

            # Regex to match the meta tag with http-equiv="REFRESH"
            meta_refresh_pattern = re.search(
                r'<meta\s+http-equiv=["\']REFRESH["\']\s+" + \
                r"content=["\']\d+;\s*url=["\']([^"\']+)["\']',
                content_str,
                re.IGNORECASE,
            )

            if meta_refresh_pattern:
                url = meta_refresh_pattern.group(1)

                # First, try to find any https URL directly in the content
                https_url_match = re.search(r'https?://[^\s"\']+', url)
                if https_url_match:
                    full_url = unquote(
                        https_url_match.group(0), encoding="utf-8", errors="replace"
                    )
                    full_url = full_url[: full_url.find("?")]
                    return str(full_url)

                # If no https URL is found, fall back to checking for a 'Redirect=' parameter
                redirect_url_match = re.search(r"Redirect=([^&]+)", url)
                if redirect_url_match:
                    # Decode and extract the full URL from the Redirect parameter
                    full_url = unquote(
                        redirect_url_match.group(1), encoding="utf-8", errors="replace"
                    )
                    full_url = full_url[: full_url.find("?")]
                    return str(full_url)

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
                key=Fields.URL,
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
