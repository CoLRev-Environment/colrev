#! /usr/bin/env python
"""SearchSource: DBLP"""
from __future__ import annotations

import html
import json
import re
import typing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from sqlite3 import OperationalError
from typing import TYPE_CHECKING

import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.search
import colrev.record
import colrev.ui_cli.cli_colors as colors


if TYPE_CHECKING:
    import colrev.ops.prep

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class DBLPSearchSource(JsonSchemaMixin):
    """SearchSource for DBLP"""

    __api_url = "https://dblp.org/search/publ/api?q="
    __api_url_venues = "https://dblp.org/search/venue/api?q="

    # settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "{{dblp_key}}"
    search_type = colrev.settings.SearchType.DB

    @dataclass
    class DBLPSearchSourceSettings(JsonSchemaMixin):
        """Settings for DBLPSearchSource"""

        # pylint: disable=duplicate-code
        # pylint: disable=too-many-instance-attributes
        endpoint: str
        filename: Path
        search_type: colrev.settings.SearchType
        source_identifier: str
        search_parameters: dict
        load_conversion_package_endpoint: dict
        comment: typing.Optional[str]

        _details = {
            "search_parameters": {
                "tooltip": "Currently supports a scope item "
                "with venue_key and journal_abbreviated fields."
            },
        }

    settings_class = DBLPSearchSourceSettings

    def __init__(
        self,
        *,
        source_operation: colrev.operation.Operation,
        settings: dict = None,
    ) -> None:

        if settings:
            self.settings = from_dict(data_class=self.settings_class, data=settings)

    def check_status(self, *, prep_operation: colrev.ops.prep.Prep) -> None:
        """Check status (availability) of DBLP API"""

        try:
            # pylint: disable=duplicate-code
            test_rec = {
                "ENTRYTYPE": "article",
                "doi": "10.17705/1cais.04607",
                "author": "Schryen, Guido and Wagner, Gerit and Benlian, Alexander "
                "and Paré, Guy",
                "title": "A Knowledge Development Perspective on Literature Reviews: "
                "Validation of a new Typology in the IS Field",
                "ID": "SchryenEtAl2021",
                "journal": "Communications of the Association for Information Systems",
                "volume": "46",
                "year": "2020",
                "colrev_status": colrev.record.RecordState.md_prepared,  # type: ignore
            }

            query = "" + str(test_rec.get("title", "")).replace("-", "_")

            dblp_record = self.retrieve_dblp_records(
                review_manager=prep_operation.review_manager,
                query=query,
            )[0]

            if 0 != len(dblp_record.data):
                assert dblp_record.data["title"] == test_rec["title"]
                assert dblp_record.data["author"] == test_rec["author"]
            else:
                if not prep_operation.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException("DBLP")
        except requests.exceptions.RequestException as exc:
            if not prep_operation.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException("DBLP") from exc

    def __get_dblp_venue(
        self,
        *,
        session: requests.Session,
        review_manager: colrev.review_manager.ReviewManager,
        timeout: int,
        venue_string: str,
        venue_type: str,
    ) -> str:
        # Note : venue_string should be like "behaviourIT"
        # Note : journals that have been renamed seem to return the latest
        # journal name. Example:
        # https://dblp.org/db/journals/jasis/index.html
        venue = venue_string
        url = self.__api_url_venues + venue_string.replace(" ", "+") + "&format=json"
        headers = {"user-agent": f"{__name__} (mailto:{review_manager.email})"}
        try:
            ret = session.request("GET", url, headers=headers, timeout=timeout)
            ret.raise_for_status()
            data = json.loads(ret.text)
            if "hit" not in data["result"]["hits"]:
                return ""
            hits = data["result"]["hits"]["hit"]
            for hit in hits:
                if hit["info"]["type"] != venue_type:
                    continue
                if f"/{venue_string.lower()}/" in hit["info"]["url"].lower():
                    venue = hit["info"]["venue"]
                    break

            venue = re.sub(r" \(.*?\)", "", venue)
        except requests.exceptions.RequestException:
            pass
        return venue

    def __dblp_json_to_dict(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        session: requests.Session,
        item: dict,
        timeout: int,
    ) -> dict:
        # pylint: disable=too-many-branches

        # To test in browser:
        # https://dblp.org/search/publ/api?q=ADD_TITLE&format=json

        retrieved_record = {}
        if "Withdrawn Items" == item["type"]:
            if "journals" == item["key"][:8]:
                item["type"] = "Journal Articles"
            if "conf" == item["key"][:4]:
                item["type"] = "Conference and Workshop Papers"
            retrieved_record["warning"] = "Withdrawn (according to DBLP)"
        if "Journal Articles" == item["type"]:
            retrieved_record["ENTRYTYPE"] = "article"
            lpos = item["key"].find("/") + 1
            rpos = item["key"].rfind("/")
            ven_key = item["key"][lpos:rpos]
            retrieved_record["journal"] = self.__get_dblp_venue(
                session=session,
                review_manager=review_manager,
                timeout=timeout,
                venue_string=ven_key,
                venue_type="Journal",
            )
        if "Conference and Workshop Papers" == item["type"]:
            retrieved_record["ENTRYTYPE"] = "inproceedings"
            lpos = item["key"].find("/") + 1
            rpos = item["key"].rfind("/")
            ven_key = item["key"][lpos:rpos]
            retrieved_record["booktitle"] = self.__get_dblp_venue(
                session=session,
                review_manager=review_manager,
                venue_string=ven_key,
                venue_type="Conference or Workshop",
                timeout=timeout,
            )
        if "title" in item:
            retrieved_record["title"] = item["title"].rstrip(".")
        if "year" in item:
            retrieved_record["year"] = item["year"]
        if "volume" in item:
            retrieved_record["volume"] = item["volume"]
        if "number" in item:
            retrieved_record["number"] = item["number"]
        if "pages" in item:
            retrieved_record["pages"] = item["pages"].replace("-", "--")
        if "authors" in item:
            if "author" in item["authors"]:
                if isinstance(item["authors"]["author"], dict):
                    author_string = item["authors"]["author"]["text"]
                else:
                    authors_nodes = [
                        author
                        for author in item["authors"]["author"]
                        if isinstance(author, dict)
                    ]
                    authors = [x["text"] for x in authors_nodes if "text" in x]
                    author_string = " and ".join(authors)
                author_string = colrev.record.PrepRecord.format_author_field(
                    input_string=author_string
                )
                retrieved_record["author"] = author_string

        if "key" in item:
            retrieved_record["dblp_key"] = "https://dblp.org/rec/" + item["key"]

        if "doi" in item:
            retrieved_record["doi"] = item["doi"].upper()
        if "ee" in item:
            if "https://doi.org" not in item["ee"]:
                retrieved_record["url"] = item["ee"]

        for key, value in retrieved_record.items():
            retrieved_record[key] = (
                html.unescape(value).replace("{", "").replace("}", "")
            )

        return retrieved_record

    def retrieve_dblp_records(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        query: str = None,
        url: str = None,
        timeout: int = 10,
    ) -> list:
        """Retrieve records from DBLP based on a query"""

        try:
            assert query is not None or url is not None
            session = review_manager.get_cached_session()
            items = []

            if query:
                query = re.sub(r"[\W]+", " ", query.replace(" ", "_"))
                url = self.__api_url + query.replace(" ", "+") + "&format=json"

            headers = {"user-agent": f"{__name__}  (mailto:{review_manager.email})"}
            # review_manager.logger.debug(url)
            ret = session.request(
                "GET", url, headers=headers, timeout=timeout  # type: ignore
            )
            ret.raise_for_status()
            if ret.status_code == 500:
                return []

            data = json.loads(ret.text)
            if "hits" not in data["result"]:
                return []
            if "hit" not in data["result"]["hits"]:
                return []
            hits = data["result"]["hits"]["hit"]
            items = [hit["info"] for hit in hits]
            dblp_dicts = [
                self.__dblp_json_to_dict(
                    review_manager=review_manager,
                    session=session,
                    item=item,
                    timeout=timeout,
                )
                for item in items
            ]
            retrieved_records = [
                colrev.record.PrepRecord(data=dblp_dict) for dblp_dict in dblp_dicts
            ]
            for retrieved_record in retrieved_records:
                retrieved_record.add_provenance_all(
                    source=retrieved_record.data["dblp_key"]
                )

        # pylint: disable=duplicate-code
        except OperationalError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            ) from exc

        return retrieved_records

    def __retrieve_and_append_year_batch(
        self,
        *,
        search_operation: colrev.ops.search.Search,
        records_dict: typing.Dict[str, typing.Dict],
        year: int,
    ) -> typing.Dict[str, typing.Dict]:

        search_operation.review_manager.logger.debug(f"Retrieve year {year}")
        __api_url = "https://dblp.org/search/publ/api?q="

        query = (
            self.settings.search_parameters["scope"]["journal_abbreviated"]
            + "+"
            + str(year)
        )
        # query = params['scope']["venue_key"] + "+" + str(year)

        available_ids = [
            x["dblp_key"] for x in records_dict.values() if "dblp_key" in x
        ]
        max_id = (
            max(
                [int(x["ID"]) for x in records_dict.values() if x["ID"].isdigit()] + [1]
            )
            + 1
        )

        nr_retrieved = 0
        batch_size = 250
        while True:
            url = (
                __api_url
                + query.replace(" ", "+")
                + f"&format=json&h={batch_size}&f={nr_retrieved}"
            )
            nr_retrieved += batch_size
            # search_operation.review_manager.logger.debug(url)

            retrieved = False
            for retrieved_record in self.retrieve_dblp_records(
                review_manager=search_operation.review_manager, url=url
            ):
                if "colrev_data_provenance" in retrieved_record.data:
                    del retrieved_record.data["colrev_data_provenance"]
                if "colrev_masterdata_provenance" in retrieved_record.data:
                    del retrieved_record.data["colrev_masterdata_provenance"]

                retrieved = True

                if (
                    f"{self.settings.search_parameters['scope']['venue_key']}/"
                    not in retrieved_record.data["dblp_key"]
                ):
                    continue

                if retrieved_record.data["dblp_key"] not in available_ids:
                    retrieved_record.data["ID"] = str(max_id).rjust(6, "0")
                    if retrieved_record.data.get("ENTRYTYPE", "") not in [
                        "article",
                        "inproceedings",
                    ]:
                        continue
                        # retrieved_record["ENTRYTYPE"] = "misc"
                    if "pages" in retrieved_record.data:
                        del retrieved_record.data["pages"]
                    available_ids.append(retrieved_record.data["dblp_key"])

                    records_dict[retrieved_record.data["ID"]] = retrieved_record.data
                    max_id += 1

            if not retrieved:
                break

        return records_dict

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
        )

        if source.source_identifier != self.source_identifier:
            raise colrev_exceptions.InvalidQueryException(
                f"Invalid source_identifier: {source.source_identifier} "
                f"(should be {self.source_identifier})"
            )

        # maybe : validate/assert that the venue_key is available
        if "scope" not in source.search_parameters:
            raise colrev_exceptions.InvalidQueryException(
                "scope required in search_parameters"
            )
        if "venue_key" not in source.search_parameters["scope"]:
            raise colrev_exceptions.InvalidQueryException(
                "venue_key required in search_parameters/scope"
            )
        if "journal_abbreviated" not in source.search_parameters["scope"]:
            raise colrev_exceptions.InvalidQueryException(
                "journal_abbreviated required in search_parameters/scope"
            )

        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        """Run a search of DBLP"""

        # https://dblp.org/search/publ/api?q=ADD_TITLE&format=json

        search_operation.review_manager.logger.debug(
            f"Retrieve DBLP: {self.settings.search_parameters}"
        )

        records: list = []
        if self.settings.filename.is_file():
            with open(self.settings.filename, encoding="utf8") as bibtex_file:
                feed_rd = search_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )
                records = list(feed_rd.values())

        nr_retrieved = 0

        try:

            # Note : journal_abbreviated is the abbreviated venue_key

            start = 1980
            if len(records) > 100 and not search_operation.review_manager.force_mode:
                start = datetime.now().year - 2
            records_dict = {r["ID"]: r for r in records}
            for year in range(start, datetime.now().year):
                len_before = len(records_dict)
                records_dict = self.__retrieve_and_append_year_batch(
                    search_operation=search_operation,
                    records_dict=records_dict,
                    year=year,
                )
                nr_added = len(records_dict) - len_before
                nr_retrieved += nr_added

                search_operation.save_feed_file(
                    records=records_dict, feed_file=self.settings.filename
                )

        except UnicodeEncodeError:
            print("UnicodeEncodeError - this needs to be fixed at some time")
        except (
            requests.exceptions.ReadTimeout,
            requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError,
        ):
            pass

        if nr_retrieved > 0:
            search_operation.review_manager.logger.info(
                f"{colors.GREEN}Retrieved {nr_retrieved} records{colors.END}"
            )
        else:
            search_operation.review_manager.logger.info(
                f"{colors.GREEN}No additional records retrieved{colors.END}"
            )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for DBLP"""

        result = {"confidence": 0.0}
        # Simple heuristic:
        if "bibsource = {dblp computer scienc" in data:
            result["confidence"] = 1.0
            return result
        return result

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for DBLP"""

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for DBLP"""

        return record


if __name__ == "__main__":
    pass
