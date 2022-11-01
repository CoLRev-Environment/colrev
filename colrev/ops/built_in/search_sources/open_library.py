#! /usr/bin/env python
"""Connector to OpenLibrary (API)"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import requests

import colrev.exceptions as colrev_exceptions
import colrev.record


if TYPE_CHECKING:
    import colrev.ops.prep

# Note: not (yet) implemented as a full search_source
# (including SearchSourcePackageEndpointInterface, packages_endpoints.json)


# pylint: disable=too-few-public-methods


class OpenLibraryConnector:
    """Connector for the OpenLibrary API"""

    @classmethod
    def check_status(cls, *, prep_operation: colrev.ops.prep.Prep) -> None:
        """Check the status (availability) of the OpenLibrary API"""

        test_rec = {
            "ENTRYTYPE": "book",
            "isbn": "9781446201435",
            # 'author': 'Ridley, Diana',
            "title": "The Literature Review A Stepbystep Guide For Students",
            "ID": "Ridley2012",
            "year": "2012",
        }
        try:
            url = f"https://openlibrary.org/isbn/{test_rec['isbn']}.json"
            ret = requests.get(
                url,
                headers=prep_operation.requests_headers,
                timeout=prep_operation.timeout,
            )
            if ret.status_code != 200:
                if not prep_operation.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException("OPENLIBRARY")
        except requests.exceptions.RequestException as exc:
            if not prep_operation.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException(
                    "OPENLIBRARY"
                ) from exc

    @classmethod
    def __open_library_json_to_record(
        cls, *, item: dict, url: str
    ) -> colrev.record.PrepRecord:
        retrieved_record: dict = {}

        if "author_name" in item:
            authors_string = " and ".join(
                [
                    colrev.record.PrepRecord.format_author_field(input_string=author)
                    for author in item["author_name"]
                ]
            )
            retrieved_record.update(author=authors_string)
        if "publisher" in item:
            retrieved_record.update(publisher=str(item["publisher"][0]))
        if "title" in item:
            retrieved_record.update(title=str(item["title"]))
        if "publish_year" in item:
            retrieved_record.update(year=str(item["publish_year"][0]))
        if "edition_count" in item:
            retrieved_record.update(edition=str(item["edition_count"]))
        if "seed" in item:
            if "/books/" in item["seed"][0]:
                retrieved_record.update(ENTRYTYPE="book")
        if "publish_place" in item:
            retrieved_record.update(address=str(item["publish_place"][0]))
        if "isbn" in item:
            retrieved_record.update(isbn=str(item["isbn"][0]))

        record = colrev.record.PrepRecord(data=retrieved_record)
        record.add_provenance_all(source=url)
        return record

    @classmethod
    def get_masterdata_from_open_library(
        cls,
        *,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        timeout: int = 10,  # pylint: disable=unused-argument
    ) -> colrev.record.Record:
        """Retrieve masterdata from OpenLibrary based on similarity with the record provided"""

        # pylint: disable=too-many-branches
        try:

            session = prep_operation.review_manager.get_cached_session()

            url = "NA"
            if "isbn" in record.data:
                isbn = record.data["isbn"].replace("-", "").replace(" ", "")
                url = f"https://openlibrary.org/isbn/{isbn}.json"
                ret = session.request(
                    "GET",
                    url,
                    headers=prep_operation.requests_headers,
                    timeout=prep_operation.timeout,
                )
                ret.raise_for_status()
                # prep_operation.review_manager.logger.debug(url)
                if '"error": "notfound"' in ret.text:
                    record.remove_field(key="isbn")

                item = json.loads(ret.text)

            else:
                base_url = "https://openlibrary.org/search.json?"
                url = ""
                if record.data.get("author", "NA").split(",")[0]:
                    url = (
                        base_url
                        + "&author="
                        + record.data.get("author", "NA").split(",")[0]
                    )
                if "inbook" == record.data["ENTRYTYPE"] and "editor" in record.data:
                    if record.data.get("editor", "NA").split(",")[0]:
                        url = (
                            base_url
                            + "&author="
                            + record.data.get("editor", "NA").split(",")[0]
                        )
                if base_url not in url:
                    return record

                title = record.data.get("title", record.data.get("booktitle", "NA"))
                if len(title) < 10:
                    return record
                if ":" in title:
                    title = title[: title.find(":")]  # To catch sub-titles
                url = url + "&title=" + title.replace(" ", "+")
                ret = session.request(
                    "GET",
                    url,
                    headers=prep_operation.requests_headers,
                    timeout=prep_operation.timeout,
                )
                ret.raise_for_status()
                # prep_operation.review_manager.logger.debug(url)

                # if we have an exact match, we don't need to check the similarity
                if '"numFoundExact": true,' not in ret.text:
                    return record

                data = json.loads(ret.text)
                items = data["docs"]
                if not items:
                    return record
                item = items[0]

            retrieved_record = cls.__open_library_json_to_record(item=item, url=url)

            record.merge(merging_record=retrieved_record, default_source=url)

            # if "title" in record.data and "booktitle" in record.data:
            #     record.remove_field(key="booktitle")

        except requests.exceptions.RequestException:
            pass
        except UnicodeEncodeError:
            prep_operation.review_manager.logger.error(
                "UnicodeEncodeError - this needs to be fixed at some time"
            )

        return record


if __name__ == "__main__":
    pass
