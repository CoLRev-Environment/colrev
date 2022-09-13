#! /usr/bin/env python
import typing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests
import zope.interface
from dacite import from_dict

import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.database_connectors
import colrev.ops.search
import colrev.process
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class DBLPSearchSource:
    # settings_class = colrev.process.DefaultSourceSettings
    source_identifier = "{{biburl}}"

    source_identifier_search = "{{dblp_key}}"
    search_mode = "all"

    @dataclass
    class DBLPSearchSourceSettings:
        # pylint: disable=duplicate-code
        name: str
        filename: Path
        search_type: colrev.settings.SearchType
        source_name: str
        source_identifier: str
        search_parameters: dict
        load_conversion_script: dict
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
        source_operation,
        settings: dict,
    ) -> None:
        # maybe : validate/assert that the venue_key is available
        if "scope" not in settings["search_parameters"]:
            raise colrev_exceptions.InvalidQueryException(
                "scope required in search_parameters"
            )
        if "venue_key" not in settings["search_parameters"]["scope"]:
            raise colrev_exceptions.InvalidQueryException(
                "venue_key required in search_parameters/scope"
            )
        if "journal_abbreviated" not in settings["search_parameters"]["scope"]:
            raise colrev_exceptions.InvalidQueryException(
                "journal_abbreviated required in search_parameters/scope"
            )
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        params = self.settings.search_parameters
        feed_file = self.settings.filename

        # https://dblp.org/search/publ/api?q=ADD_TITLE&format=json

        search_operation.review_manager.logger.info(f"Retrieve DBLP: {params}")

        available_ids = []
        max_id = 1
        if not feed_file.is_file():
            records: list = []
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:
                feed_rd = search_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )
                records = list(feed_rd.values())

            available_ids = [x["dblp_key"] for x in records if "dblp_key" in x]
            max_id = max([int(x["ID"]) for x in records if x["ID"].isdigit()] + [1]) + 1

        try:
            api_url = "https://dblp.org/search/publ/api?q="

            # Note : journal_abbreviated is the abbreviated venue_key
            # TODO : tbd how the abbreviated venue_key can be retrieved
            # https://dblp.org/rec/journals/jais/KordzadehW17.html?view=bibtex

            start = 1980
            if len(records) > 100 and not search_operation.review_manager.force_mode:
                start = datetime.now().year - 2
            records_dict = {r["ID"]: r for r in records}
            for year in range(start, datetime.now().year):
                search_operation.review_manager.logger.info(f"Retrieving year {year}")
                query = params["scope"]["journal_abbreviated"] + "+" + str(year)
                # query = params['scope']["venue_key"] + "+" + str(year)
                nr_retrieved = 0
                batch_size = 250
                dblp_connector = colrev.ops.built_in.database_connectors.DBLPConnector
                while True:
                    url = (
                        api_url
                        + query.replace(" ", "+")
                        + f"&format=json&h={batch_size}&f={nr_retrieved}"
                    )
                    nr_retrieved += batch_size
                    search_operation.review_manager.logger.debug(url)

                    retrieved = False
                    for retrieved_record in dblp_connector.retrieve_dblp_records(
                        review_manager=search_operation.review_manager, url=url
                    ):
                        if "colrev_data_provenance" in retrieved_record.data:
                            del retrieved_record.data["colrev_data_provenance"]
                        if "colrev_masterdata_provenance" in retrieved_record.data:
                            del retrieved_record.data["colrev_masterdata_provenance"]

                        retrieved = True

                        if (
                            f"{params['scope']['venue_key']}/"
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

                            records = [
                                {
                                    k: v.replace("\n", "").replace("\r", "")
                                    for k, v in r.items()
                                }
                                for r in records
                            ]
                            records.append(retrieved_record.data)
                            max_id += 1

                    if not retrieved:
                        break

                    if len(records) == 0:
                        continue

                    records_dict = {r["ID"]: r for r in records}
                search_operation.save_feed_file(
                    records=records_dict, feed_file=feed_file
                )

        except UnicodeEncodeError:
            print("UnicodeEncodeError - this needs to be fixed at some time")
        except (
            requests.exceptions.ReadTimeout,
            requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError,
        ):
            pass

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0, "source_identifier": cls.source_identifier}
        # Simple heuristic:
        if "bibsource = {dblp computer scienc" in data:
            result["confidence"] = 1.0
            return result
        return result

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:
        # TODO (if any)
        return record


if __name__ == "__main__":
    pass
