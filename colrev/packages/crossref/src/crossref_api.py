#! /usr/bin/env python
"""Crossref API"""
import json
import re
import typing
import urllib
from datetime import timedelta
from importlib.metadata import version
from pathlib import Path
from sqlite3 import OperationalError

import requests
import requests_cache
from crossref.restful import Etiquette
from crossref.restful import Journals
from crossref.restful import Works
from rapidfuzz import fuzz

import colrev.env.environment_manager
import colrev.exceptions as colrev_exceptions
import colrev.record.record_prep
from colrev.constants import Fields
from colrev.constants import Filepaths
from colrev.packages.crossref.src import record_transformer


class CrossrefAPI:
    """Crossref API"""

    ISSN_REGEX = r"^\d{4}-?\d{3}[\dxX]$"
    YEAR_SCOPE_REGEX = r"^\d{4}-\d{4}$"

    # https://github.com/CrossRef/rest-api-doc
    _api_url = "https://api.crossref.org/works?"

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        params: dict,
        rerun: bool = False,
        # timeout: int = 60,
    ):
        self.params = params
        _, self.email = (
            colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git()
        )
        self.etiquette = self.get_etiquette()
        self.rerun = rerun

        self.session = requests_cache.CachedSession(
            str(Filepaths.LOCAL_ENVIRONMENT_DIR / Path("crossref_cache.sqlite")),
            backend="sqlite",
            expire_after=timedelta(days=30),
        )

    def get_etiquette(self) -> Etiquette:
        """Get the etiquette for the crossref api"""
        return Etiquette(
            "CoLRev",
            version("colrev"),
            "https://github.com/CoLRev-Environment/colrev",
            self.email,
        )

    def get_len(self) -> int:
        """Get the number of records from Crossref based on the parameters"""

        if "query" in self.params:
            works = Works(etiquette=self.etiquette)
            return works.query(**{"bibliographic": self.params["query"]}).count()
        if "scope" in self.params:
            journals = Journals(etiquette=self.etiquette)
            return journals.works(self.params["scope"][Fields.ISSN][0]).count()
        return -1

    def _query(self, **kwargs) -> typing.Iterator[dict]:  # type: ignore
        """Get records from Crossref based on a bibliographic query"""

        works = Works(etiquette=self.etiquette)
        # use facets:
        # https://api.crossref.org/swagger-ui/index.html#/Works/get_works

        crossref_query_return = works.query(**kwargs).sort("deposited").order("desc")
        yield from crossref_query_return

    def _query_journal(self) -> typing.Iterator[dict]:
        """Get records of a selected journal from Crossref"""

        journals = Journals(etiquette=self.etiquette)

        scope_filters = {}
        if "scope" in self.params and "years" in self.params["scope"]:
            year_from, year_to = self.params["scope"]["years"].split("-")
            scope_filters["from-pub-date"] = year_from
            scope_filters["until-pub-date"] = year_to

        for issn in self.params["scope"][Fields.ISSN]:
            assert re.match(self.ISSN_REGEX, issn)
            if self.rerun:
                # Note : the "deposited" field is not always provided.
                # only the general query will return all records.
                crossref_query_return = (
                    journals.works(issn).query().filter(**scope_filters)
                )
            else:
                crossref_query_return = (
                    journals.works(issn)
                    .query()
                    .filter(**scope_filters)
                    .sort("deposited")
                    .order("desc")
                )

            yield from crossref_query_return

    def get_records(self) -> typing.Iterator[colrev.record.record.Record]:
        """Get records from Crossref based on the parameters"""

        if "query" in self.params and "mode" not in self.params:
            crossref_query = {"bibliographic": self.params["query"].replace(" ", "+")}
            # potential extension : add the container_title:
            # crossref_query_return = works.query(
            #     container_title=
            #       "Journal of the Association for Information Systems"
            # )
            # yield from self._query(**crossref_query)
            for item in self._query(**crossref_query):
                try:
                    yield record_transformer.json_to_record(item=item)
                except colrev_exceptions.RecordNotParsableException:
                    continue

        elif "scope" in self.params and Fields.ISSN in self.params["scope"]:
            if Fields.ISSN in self.params["scope"]:
                for item in self._query_journal():
                    try:
                        yield record_transformer.json_to_record(item=item)
                    except colrev_exceptions.RecordNotParsableException:
                        continue

            # raise NotImplemented

    def query_doi(self, *, doi: str) -> colrev.record.record_prep.PrepRecord:
        """Get records from Crossref based on a doi query"""

        try:
            works = Works(etiquette=self.etiquette)
            crossref_query_return = works.doi(doi)
            if crossref_query_return is None:
                raise colrev_exceptions.RecordNotFoundInPrepSourceException(
                    msg="Record not found in crossref (based on doi)"
                )

            retrieved_record = record_transformer.json_to_record(
                item=crossref_query_return
            )
            return retrieved_record

        except (requests.exceptions.RequestException,) as exc:
            raise colrev_exceptions.RecordNotFoundInPrepSourceException(
                msg="Record not found in crossref (based on doi)"
            ) from exc

    def _get_similarity(
        self, *, record: colrev.record.record.Record, retrieved_record_dict: dict
    ) -> float:
        title_similarity = fuzz.partial_ratio(
            retrieved_record_dict.get(Fields.TITLE, "NA").lower(),
            record.data.get(Fields.TITLE, "").lower(),
        )
        container_similarity = fuzz.partial_ratio(
            colrev.record.record_prep.PrepRecord(retrieved_record_dict)
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

    def _create_query_url(
        self, *, record: colrev.record.record.Record, jour_vol_iss_list: bool
    ) -> str:
        if jour_vol_iss_list:
            if not all(
                x in record.data for x in [Fields.JOURNAL, Fields.VOLUME, Fields.NUMBER]
            ):
                raise colrev_exceptions.NotEnoughDataToIdentifyException
            params = {"rows": "50"}
            container_title = re.sub(r"[\W]+", " ", record.data[Fields.JOURNAL])
            params["query.container-title"] = container_title.replace("_", " ")

            query_field = ""
            if Fields.VOLUME in record.data:
                query_field = record.data[Fields.VOLUME]
            if Fields.NUMBER in record.data:
                query_field = query_field + "+" + record.data[Fields.NUMBER]
            params["query"] = query_field

        else:
            if Fields.TITLE not in record.data:
                raise colrev_exceptions.NotEnoughDataToIdentifyException()

            params = {"rows": "15"}
            if not isinstance(record.data.get(Fields.YEAR, ""), str) or not isinstance(
                record.data.get(Fields.TITLE, ""), str
            ):
                print("year or title field not a string")
                print(record.data)
                raise AssertionError

            bibl = (
                record.data[Fields.TITLE].replace("-", "_")
                + " "
                + record.data.get(Fields.YEAR, "")
            )
            bibl = re.sub(r"[\W]+", "", bibl.replace(" ", "_"))
            params["query.bibliographic"] = bibl.replace("_", " ")

            container_title = record.get_container_title()
            if "." not in container_title:
                container_title = container_title.replace(" ", "_")
                container_title = re.sub(r"[\W]+", "", container_title)
                params["query.container-title"] = container_title.replace("_", " ")

            author_last_names = [
                x.split(",")[0]
                for x in record.data.get(Fields.AUTHOR, "").split(" and ")
            ]
            author_string = " ".join(author_last_names)
            author_string = re.sub(r"[\W]+", "", author_string.replace(" ", "_"))
            params["query.author"] = author_string.replace("_", " ")

        url = self._api_url + urllib.parse.urlencode(params)
        return url

    def _get_crossref_query_items(
        self,
        *,
        record: colrev.record.record.Record,
        jour_vol_iss_list: bool,
        timeout: int,
    ) -> list:
        # Note : only returning a multiple-item list for jour_vol_iss_list
        try:
            url = self._create_query_url(
                record=record, jour_vol_iss_list=jour_vol_iss_list
            )
            headers = {"user-agent": f"{__name__} (mailto:{self.email})"}

            # review_manager.logger.debug(url)
            ret = self.session.request("GET", url, headers=headers, timeout=timeout)
            ret.raise_for_status()
            if ret.status_code != 200:
                # review_manager.logger.debug(
                #     f"crossref_query failed with status {ret.status_code}"
                # )
                return []

            data = json.loads(ret.text)

        # pylint: disable=duplicate-code
        except OperationalError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            ) from exc
        except (
            colrev_exceptions.NotEnoughDataToIdentifyException,
            json.decoder.JSONDecodeError,
            requests.exceptions.RequestException,
        ):
            return []

        return data["message"].get("items", [])

    def crossref_query(
        self,
        *,
        record_input: colrev.record.record.Record,
        jour_vol_iss_list: bool = False,
        timeout: int = 40,
    ) -> list:
        """Retrieve records from Crossref based on a query"""

        record = record_input.copy_prep_rec()
        record_list, most_similar, most_similar_record = [], 0.0, {}
        for item in self._get_crossref_query_items(
            record=record, jour_vol_iss_list=jour_vol_iss_list, timeout=timeout
        ):
            try:
                retrieved_record = record_transformer.json_to_record(item=item)
                similarity = self._get_similarity(
                    record=record, retrieved_record_dict=retrieved_record.data
                )

                # source = (
                #     f'https://api.crossref.org/works/{retrieved_record.data[Fields.DOI]}'
                # )
                # retrieved_record.add_provenance_all(source=source)

                # record.set_masterdata_complete(source=source)

                if jour_vol_iss_list:
                    record_list.append(retrieved_record)
                elif most_similar < similarity:
                    most_similar = similarity
                    most_similar_record = retrieved_record.get_data()
            except colrev_exceptions.RecordNotParsableException:
                pass

        if not jour_vol_iss_list:
            if most_similar_record:
                record_list = [
                    colrev.record.record_prep.PrepRecord(most_similar_record)
                ]

        return record_list
