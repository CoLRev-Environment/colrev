#! /usr/bin/env python
"""SearchSource: Crossref"""
import typing
from pathlib import Path

import requests
import zope.interface
from dacite import from_dict

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.database_connectors
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.SearchSourcePackageInterface)
class CrossrefSourceSearchSource:
    """Performs a search using the Crossref API"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "{{doi}}"

    source_identifier_search = "https://api.crossref.org/works/{{doi}}"
    search_mode = "all"

    def __init__(self, *, source_operation, settings: dict) -> None:
        if not any(
            x in settings["search_parameters"]["scope"]
            for x in ["query", "journal_issn"]
        ):
            raise colrev_exceptions.InvalidQueryException(
                "Crossref search_parameters/scope requires a query or journal_issn field"
            )

        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        params = self.settings.search_parameters
        feed_file = self.settings.filename
        # pylint: disable=import-outside-toplevel
        from colrev.ops.built_in.database_connectors import (
            CrossrefConnector,
            DOIConnector,
        )

        # Note: not yet implemented/supported
        if " AND " in params.get("selection_clause", ""):
            raise colrev_exceptions.InvalidQueryException(
                "AND not supported in CROSSREF query selection_clause"
            )
        # Either one or the other is possible:
        if not bool("selection_clause" in params) ^ bool(
            "journal_issn" in params.get("scope", {})
        ):
            raise colrev_exceptions.InvalidQueryException(
                "combined selection_clause and journal_issn (scope) "
                "not supported in CROSSREF query"
            )

        available_ids = []
        max_id = 1
        if not feed_file.is_file():
            records = {}
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:
                records = search_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )

            available_ids = [x["doi"] for x in records.values() if "doi" in x]
            max_id = (
                max([int(x["ID"]) for x in records.values() if x["ID"].isdigit()] + [1])
                + 1
            )
        crossref_connector = CrossrefConnector(
            review_manager=search_operation.review_manager
        )

        def get_crossref_query_return(params) -> typing.Iterator[dict]:
            if "selection_clause" in params:
                crossref_query = {"bibliographic": params["selection_clause"]}
                # TODO : add the container_title:
                # crossref_query_return = works.query(
                #     container_title=
                #       "Journal of the Association for Information Systems"
                # )
                yield from crossref_connector.get_bibliographic_query_return(
                    **crossref_query
                )

            if "journal_issn" in params.get("scope", {}):

                for journal_issn in params["scope"]["journal_issn"].split("|"):
                    yield from crossref_connector.get_journal_query_return(
                        journal_issn=journal_issn
                    )

        try:
            for record_dict in get_crossref_query_return(params):
                if record_dict["doi"].upper() not in available_ids:

                    # Note : discard "empty" records
                    if "" == record_dict.get("author", "") and "" == record_dict.get(
                        "title", ""
                    ):
                        continue

                    search_operation.review_manager.logger.info(
                        " retrieved " + record_dict["doi"]
                    )
                    record_dict["ID"] = str(max_id).rjust(6, "0")

                    prep_record = colrev.record.PrepRecord(data=record_dict)
                    DOIConnector.get_link_from_doi(
                        record=prep_record,
                        review_manager=search_operation.review_manager,
                    )
                    record_dict = prep_record.get_data()

                    available_ids.append(record_dict["doi"])
                    records[record_dict["ID"]] = record_dict
                    max_id += 1
        except (requests.exceptions.JSONDecodeError, KeyError) as exc:
            # TODO : watch issue
            # https://github.com/fabiobatalha/crossrefapi/issues/46
            if "504 Gateway Time-out" in str(exc):
                raise colrev_exceptions.ServiceNotAvailableException(
                    "Crossref (check https://status.crossref.org/)"
                )
            raise colrev_exceptions.ServiceNotAvailableException(
                f"Crossref (check https://status.crossref.org/) ({exc})"
            )
        search_operation.save_feed_file(records=records, feed_file=feed_file)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        # TODO
        result = {"confidence": 0, "source_identifier": cls.source_identifier}

        return result

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        return record


if __name__ == "__main__":
    pass
