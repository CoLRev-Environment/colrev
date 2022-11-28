#! /usr/bin/env python
"""SearchSource: Crossref"""
from __future__ import annotations

import json
import re
import sys
import typing
import urllib
from dataclasses import dataclass
from pathlib import Path
from sqlite3 import OperationalError
from typing import TYPE_CHECKING

import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from thefuzz import fuzz

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.search_sources.doi_org as doi_connector
import colrev.ops.built_in.search_sources.utils as connector_utils
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
class CrossrefSearchSource(JsonSchemaMixin):
    """Performs a search using the Crossref API"""

    __issn_regex = r"^\d{4}-?\d{3}[\dxX]$"

    # https://github.com/CrossRef/rest-api-doc
    __api_url = "https://api.crossref.org/works?"

    settings_class = colrev.env.package_manager.DefaultSourceSettings

    source_identifier = "https://api.crossref.org/works/{{doi}}"
    search_type = colrev.settings.SearchType.DB

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict = None
    ) -> None:

        if settings:
            self.settings = from_dict(data_class=self.settings_class, data=settings)

        # pylint: disable=import-outside-toplevel
        from crossref.restful import Etiquette
        from importlib.metadata import version

        self.etiquette = Etiquette(
            "CoLRev",
            version("colrev"),
            "https://github.com/geritwagner/colrev",
            source_operation.review_manager.email,
        )

    def check_status(self, *, prep_operation: colrev.ops.prep.Prep) -> None:
        """Check status (availability) of the Crossref API"""

        try:
            # pylint: disable=duplicate-code
            test_rec = {
                "doi": "10.17705/1cais.04607",
                "author": "Schryen, Guido and Wagner, Gerit and Benlian, Alexander "
                "and Paré, Guy",
                "title": "A Knowledge Development Perspective on Literature Reviews: "
                "Validation of a new Typology in the IS Field",
                "ID": "SchryenEtAl2021",
                "journal": "Communications of the Association for Information Systems",
                "ENTRYTYPE": "article",
            }
            returned_record = self.crossref_query(
                review_manager=prep_operation.review_manager,
                record_input=colrev.record.PrepRecord(data=test_rec),
                jour_vol_iss_list=False,
                timeout=prep_operation.timeout,
            )[0]

            if 0 != len(returned_record.data):
                assert returned_record.data["title"] == test_rec["title"]
                assert returned_record.data["author"] == test_rec["author"]
            else:
                if not prep_operation.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException("CROSSREF")
        except (requests.exceptions.RequestException, IndexError) as exc:
            print(exc)
            if not prep_operation.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException(
                    "CROSSREF"
                ) from exc

    def bibliographic_query(self, **kwargs) -> typing.Iterator[dict]:  # type: ignore
        """Get records from Crossref based on a bibliographic query"""

        # pylint: disable=import-outside-toplevel
        from crossref.restful import Works

        assert all(k in ["bibliographic"] for k in kwargs)

        works = Works(etiquette=self.etiquette)
        # use facets:
        # https://api.crossref.org/swagger-ui/index.html#/Works/get_works

        crossref_query_return = works.query(**kwargs)
        for item in crossref_query_return:
            yield connector_utils.json_to_record(item=item)

    def journal_query(self, *, journal_issn: str) -> typing.Iterator[dict]:
        """Get records of a selected journal from Crossref"""

        # pylint: disable=import-outside-toplevel
        from crossref.restful import Journals

        assert re.match(self.__issn_regex, journal_issn)

        journals = Journals(etiquette=self.etiquette)
        crossref_query_return = journals.works(journal_issn).query()
        for item in crossref_query_return:
            yield connector_utils.json_to_record(item=item)

    def __create_query_url(
        self, *, record: colrev.record.Record, jour_vol_iss_list: bool
    ) -> str:

        if jour_vol_iss_list:
            params = {"rows": "50"}
            container_title = re.sub(r"[\W]+", " ", record.data["journal"])
            params["query.container-title"] = container_title.replace("_", " ")

            query_field = ""
            if "volume" in record.data:
                query_field = record.data["volume"]
            if "number" in record.data:
                query_field = query_field + "+" + record.data["number"]
            params["query"] = query_field

        else:
            params = {"rows": "15"}
            if not isinstance(record.data.get("year", ""), str) or not isinstance(
                record.data.get("title", ""), str
            ):
                print("year or title field not a string")
                print(record.data)
                raise AssertionError

            bibl = (
                record.data["title"].replace("-", "_")
                + " "
                + record.data.get("year", "")
            )
            bibl = re.sub(r"[\W]+", "", bibl.replace(" ", "_"))
            params["query.bibliographic"] = bibl.replace("_", " ")

            container_title = record.get_container_title()
            if "." not in container_title:
                container_title = container_title.replace(" ", "_")
                container_title = re.sub(r"[\W]+", "", container_title)
                params["query.container-title"] = container_title.replace("_", " ")

            author_last_names = [
                x.split(",")[0] for x in record.data.get("author", "").split(" and ")
            ]
            author_string = " ".join(author_last_names)
            author_string = re.sub(r"[\W]+", "", author_string.replace(" ", "_"))
            params["query.author"] = author_string.replace("_", " ")

        url = self.__api_url + urllib.parse.urlencode(params)
        return url

    def __get_similarity(
        self, *, record: colrev.record.Record, retrieved_record_dict: dict
    ) -> float:
        title_similarity = fuzz.partial_ratio(
            retrieved_record_dict["title"].lower(),
            record.data.get("title", "").lower(),
        )
        container_similarity = fuzz.partial_ratio(
            colrev.record.PrepRecord(data=retrieved_record_dict)
            .get_container_title()
            .lower(),
            record.get_container_title().lower(),
        )
        weights = [0.6, 0.4]
        similarities = [title_similarity, container_similarity]

        similarity = sum(similarities[g] * weights[g] for g in range(len(similarities)))
        # logger.debug(f'record: {pp.pformat(record)}')
        # logger.debug(f'similarities: {similarities}')
        # logger.debug(f'similarity: {similarity}')
        # pp.pprint(retrieved_record_dict)
        return similarity

    def crossref_query(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        record_input: colrev.record.Record,
        jour_vol_iss_list: bool = False,
        timeout: int = 10,
    ) -> list:
        """Retrieve records from Crossref based on a query"""

        # pylint: disable=too-many-branches
        # pylint: disable=too-many-statements
        # pylint: disable=too-many-locals

        # Note : only returning a multiple-item list for jour_vol_iss_list

        try:

            record = record_input.copy_prep_rec()

            url = self.__create_query_url(
                record=record, jour_vol_iss_list=jour_vol_iss_list
            )
            headers = {"user-agent": f"{__name__} (mailto:{review_manager.email})"}
            record_list = []
            session = review_manager.get_cached_session()

            # review_manager.logger.debug(url)
            ret = session.request("GET", url, headers=headers, timeout=timeout)
            ret.raise_for_status()
            if ret.status_code != 200:
                # review_manager.logger.debug(
                #     f"crossref_query failed with status {ret.status_code}"
                # )
                return []

            most_similar, most_similar_record = 0.0, {}
            data = json.loads(ret.text)
            for item in data["message"]["items"]:
                if "title" not in item:
                    continue

                retrieved_record_dict = connector_utils.json_to_record(item=item)

                similarity = self.__get_similarity(
                    record=record, retrieved_record_dict=retrieved_record_dict
                )

                retrieved_record = colrev.record.PrepRecord(data=retrieved_record_dict)
                if "retracted" in retrieved_record.data.get("warning", ""):
                    retrieved_record.prescreen_exclude(reason="retracted")
                    retrieved_record.remove_field(key="warning")

                source = (
                    f'https://api.crossref.org/works/{retrieved_record.data["doi"]}'
                )
                retrieved_record.add_provenance_all(source=source)

                record.set_masterdata_complete(source_identifier=source)

                if jour_vol_iss_list:
                    record_list.append(retrieved_record)
                elif most_similar < similarity:
                    most_similar = similarity
                    most_similar_record = retrieved_record.get_data()
        except json.decoder.JSONDecodeError:
            pass
        except requests.exceptions.RequestException:
            return []
        # pylint: disable=duplicate-code
        except OperationalError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            ) from exc

        if not jour_vol_iss_list:
            record_list = [colrev.record.PrepRecord(data=most_similar_record)]

        return record_list

    def get_masterdata_from_crossref(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        timeout: int = 10,
    ) -> colrev.record.Record:
        """Retrieve masterdata from Crossref based on similarity with the record provided"""

        # To test the metadata provided for a particular DOI use:
        # https://api.crossref.org/works/DOI

        # https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
        if len(record.data.get("title", "")) > 35:
            try:

                retrieved_records = self.crossref_query(
                    review_manager=prep_operation.review_manager,
                    record_input=record,
                    jour_vol_iss_list=False,
                    timeout=timeout,
                )
                retrieved_record = retrieved_records.pop()

                retries = 0
                while (
                    not retrieved_record
                    and retries < prep_operation.max_retries_on_error
                ):
                    retries += 1

                    retrieved_records = self.crossref_query(
                        review_manager=prep_operation.review_manager,
                        record_input=record,
                        jour_vol_iss_list=False,
                        timeout=timeout,
                    )
                    retrieved_record = retrieved_records.pop()

                if 0 == len(retrieved_record.data):
                    return record

                similarity = colrev.record.PrepRecord.get_retrieval_similarity(
                    record_original=record, retrieved_record_original=retrieved_record
                )
                if similarity > prep_operation.retrieval_similarity:
                    # prep_operation.review_manager.logger.debug("Found matching record")
                    # prep_operation.review_manager.logger.debug(
                    #     f"crossref similarity: {similarity} "
                    #     f"(>{prep_operation.retrieval_similarity})"
                    # )
                    source = (
                        f"https://api.crossref.org/works/{retrieved_record.data['doi']}"
                    )
                    retrieved_record.add_provenance_all(source=source)
                    record.merge(merging_record=retrieved_record, default_source=source)

                    if "retracted" in record.data.get("warning", ""):
                        record.prescreen_exclude(reason="retracted")
                        record.remove_field(key="warning")
                    else:
                        doi_connector.DOIConnector.get_link_from_doi(
                            review_manager=prep_operation.review_manager,
                            record=record,
                        )
                        record.set_masterdata_complete(source_identifier=source)
                        record.set_status(
                            target_state=colrev.record.RecordState.md_prepared
                        )

                else:
                    prep_operation.review_manager.logger.debug(
                        f"crossref similarity: {similarity} "
                        f"(<{prep_operation.retrieval_similarity})"
                    )

            except requests.exceptions.RequestException:
                pass
            except IndexError:
                pass
            # pylint: disable=duplicate-code
            except KeyboardInterrupt:
                sys.exit()
        return record

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

        if not any(x in source.search_parameters for x in ["query", "scope"]):
            raise colrev_exceptions.InvalidQueryException(
                "Crossref search_parameters requires a query or journal_issn field"
            )

        if "scope" in source.search_parameters:
            if "journal_issn" in source.search_parameters["scope"]:
                issn_field = source.search_parameters["scope"]["journal_issn"]
                if not re.match(
                    "[0-9][0-9][0-9][0-9][-]?[0-9][0-9][0-9][X0-9]", issn_field
                ):
                    raise colrev_exceptions.InvalidQueryException(
                        f"Crossref journal issn ({issn_field}) not matching required format"
                    )
            else:
                raise colrev_exceptions.InvalidQueryException(
                    "Query missing valid parameters"
                )

        elif "query" in source.search_parameters:
            # Note: not yet implemented/supported
            if " AND " in source.search_parameters["query"]:
                raise colrev_exceptions.InvalidQueryException(
                    "AND not supported in CROSSREF query"
                )

        else:
            raise colrev_exceptions.InvalidQueryException(
                "Query missing valid parameters"
            )

        if source.search_type not in [
            colrev.settings.SearchType.DB,
            colrev.settings.SearchType.TOC,
        ]:
            raise colrev_exceptions.InvalidQueryException(
                "Crossref search_type should be in [DB,TOC]"
            )
        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        """Run a search of Crossref"""

        # pylint: disable=too-many-branches

        params = self.settings.search_parameters
        feed_file = self.settings.filename

        available_ids = {}
        max_id = 1
        if not feed_file.is_file():
            records = {}
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:
                records = search_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )

            available_ids = {x["doi"]: x["ID"] for x in records.values() if "doi" in x}
            max_id = (
                max([int(x["ID"]) for x in records.values() if x["ID"].isdigit()] + [1])
                + 1
            )

        def get_crossref_query_return(params: dict) -> typing.Iterator[dict]:

            if "scope" in params:
                if "journal_issn" in params["scope"]:
                    for journal_issn in params["scope"]["journal_issn"].split("|"):
                        yield from self.journal_query(journal_issn=journal_issn)
            else:
                if "query" in params:
                    crossref_query = {"bibliographic": params["query"]}
                    # potential extension : add the container_title:
                    # crossref_query_return = works.query(
                    #     container_title=
                    #       "Journal of the Association for Information Systems"
                    # )
                    yield from self.bibliographic_query(**crossref_query)

        nr_retrieved = 0
        try:
            for record_dict in get_crossref_query_return(params):

                # Note : discard "empty" records
                if "" == record_dict.get("author", "") and "" == record_dict.get(
                    "title", ""
                ):
                    continue

                if record_dict["doi"].upper() in available_ids:
                    record_dict["ID"] = available_ids[record_dict["doi"].upper()]
                else:
                    record_dict["ID"] = str(max_id).rjust(6, "0")

                prep_record = colrev.record.PrepRecord(data=record_dict)
                doi_connector.DOIConnector.get_link_from_doi(
                    record=prep_record,
                    review_manager=search_operation.review_manager,
                )
                record_dict = prep_record.get_data()
                if "colrev_data_provenance" in record_dict:
                    del record_dict["colrev_data_provenance"]

                # TODO : if masterdata_curated repo
                if "cited_by" in record_dict:
                    del record_dict["cited_by"]

                # TODO : propagate changes to records.bib (if any)?
                # TODO : notify on major changes!

                if record_dict["doi"].upper() not in available_ids:
                    search_operation.review_manager.logger.info(
                        " retrieved " + record_dict["doi"]
                    )
                    nr_retrieved += 1
                    max_id += 1

                available_ids[record_dict["doi"]] = record_dict["ID"]
                records[record_dict["ID"]] = record_dict

        except (requests.exceptions.JSONDecodeError, KeyError) as exc:
            # watch github issue:
            # https://github.com/fabiobatalha/crossrefapi/issues/46
            if "504 Gateway Time-out" in str(exc):
                raise colrev_exceptions.ServiceNotAvailableException(
                    "Crossref (check https://status.crossref.org/)"
                )
            raise colrev_exceptions.ServiceNotAvailableException(
                f"Crossref (check https://status.crossref.org/) ({exc})"
            )
        search_operation.save_feed_file(records=records, feed_file=feed_file)
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
        """Source heuristic for Crossref"""

        result = {"confidence": 0.0}

        return result

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for Crossref"""

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for Crossref"""

        return record


if __name__ == "__main__":
    pass
