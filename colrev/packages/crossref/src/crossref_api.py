#! /usr/bin/env python
"""Crossref API"""
import contextlib
import re
import typing
import urllib
from datetime import timedelta
from importlib.metadata import version
from pathlib import Path
from time import sleep

import requests
import requests_cache
from rapidfuzz import fuzz

import colrev.env.environment_manager
import colrev.exceptions as colrev_exceptions
import colrev.record.record_prep
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import Filepaths
from colrev.packages.crossref.src import record_transformer

LIMIT = 1000
MAXOFFSET = 10000

SESSION = requests_cache.CachedSession(
    str(Filepaths.LOCAL_ENVIRONMENT_DIR / Path("crossref_cache.sqlite")),
    backend="sqlite",
    expire_after=timedelta(days=30),
)


class CrossrefAPIError(Exception):
    """Crossref API Error"""


class MaxOffsetError(CrossrefAPIError):
    """Max Offset Error"""


# pylint: disable=too-few-public-methods
class HTTPRequest:
    """HTTP Request"""

    def __init__(self, *, timeout: int) -> None:
        self.rate_limits = {"x-rate-limit-limit": 50, "x-rate-limit-interval": 1}
        self.timeout = timeout

    def _update_rate_limits(self, headers: dict) -> None:

        with contextlib.suppress(ValueError):
            self.rate_limits["x-rate-limit-limit"] = int(
                headers.get("x-rate-limit-limit", 50)
            )

        with contextlib.suppress(ValueError):
            interval_value = int(headers.get("x-rate-limit-interval", "1s")[:-1])

        interval_scope = headers.get("x-rate-limit-interval", "1s")[-1]

        if interval_scope == "m":
            interval_value = interval_value * 60

        if interval_scope == "h":
            interval_value = interval_value * 60 * 60

        self.rate_limits["x-rate-limit-interval"] = interval_value

    def _get_throttling_time(self) -> float:
        """"""
        return (
            self.rate_limits["x-rate-limit-interval"]
            / self.rate_limits["x-rate-limit-limit"]
        )

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    def retrieve(
        self,
        endpoint: str,
        headers: dict,
        data: typing.Optional[dict] = None,
        only_headers: bool = False,
        skip_throttle: bool = False,
        cache: bool = True,
    ) -> requests.Response:
        """Retrieve data from a given endpoint."""

        if only_headers is True:
            return requests.head(endpoint, timeout=2)

        if cache:
            result = SESSION.get(
                endpoint, params=data, timeout=self.timeout, headers=headers
            )
        else:
            result = requests.get(
                endpoint, params=data, timeout=self.timeout, headers=headers
            )

        if not skip_throttle:
            self._update_rate_limits(result.headers)
            sleep(self._get_throttling_time())

        return result


class Endpoint:
    """Endpoint"""

    cursor_as_iter_method = False

    def __init__(
        self,
        request_url: str,
        *,
        email: str = "",
        crossref_plus_token: str = "",
    ) -> None:

        self.retrieve = HTTPRequest(timeout=60).retrieve

        self.headers = {
            "user-agent": f"colrev/{version('colrev')} "
            + f"(https://github.com/CoLRev-Environment/colrev; mailto:{email})"
        }
        self.crossref_plus_token = crossref_plus_token
        if crossref_plus_token:
            self.headers["Crossref-Plus-API-Token"] = self.crossref_plus_token
        self.request_url = request_url
        self.request_params: typing.Dict[str, str] = {}
        self.timeout = 60

    @property
    def _rate_limits(self) -> dict:
        request_url = str(self.request_url)

        result = self.retrieve(
            request_url,
            only_headers=True,
            headers=self.headers,
            skip_throttle=True,
        )

        return {
            "x-rate-limit-limit": result.headers.get("x-rate-limit-limit", "undefined"),
            "x-rate-limit-interval": result.headers.get(
                "x-rate-limit-interval", "undefined"
            ),
        }

    def _escaped_pagging(self) -> dict:
        escape_pagging = ["offset", "rows"]
        request_params = dict(self.request_params)

        for item in escape_pagging:
            with contextlib.suppress(KeyError):
                del request_params[item]

        return request_params

    @property
    def version(self) -> str:
        """API version."""

        request_params = dict(self.request_params)
        request_url = str(self.request_url)

        result = self.retrieve(
            request_url,
            data=request_params,
            headers=self.headers,
        ).json()

        return result["message-version"]

    def get_nr(self) -> int:
        """Retrieve the total number of records resulting from a query."""
        request_params = dict(self.request_params)
        request_url = str(self.request_url)
        request_params["rows"] = "0"

        try:
            result = self.retrieve(
                request_url,
                data=request_params,
                headers=self.headers,
            ).json()
        except requests.exceptions.RequestException as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                f"Crossref ({Colors.ORANGE}check https://status.crossref.org/{Colors.END})"
            ) from exc

        return int(result["message"].get("total-results", 0))

    def get_dois(self) -> typing.List[str]:
        """Retrieve the dois resulting from a query."""
        request_params = dict(self.request_params)
        request_url = str(self.request_url)

        try:
            result = self.retrieve(
                request_url,
                data=request_params,
                headers=self.headers,
            ).json()
        except requests.exceptions.RequestException as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                f"Crossref ({Colors.ORANGE}check https://status.crossref.org/{Colors.END})"
            ) from exc

        return [item["DOI"] for item in result["message"]["items"]]

    @property
    def url(self) -> str:
        """Retrieve the url that will be used as a HTTP request."""

        request_params = self._escaped_pagging()
        sorted_request_params = sorted(request_params.items())

        req = requests.Request(
            "get", self.request_url, params=sorted_request_params
        ).prepare()

        return req.url

    # pylint: disable=too-many-branches
    # pylint: disable=too-many-return-statements
    def __iter__(self) -> typing.Iterator[dict]:

        request_url = str(self.request_url)

        if request_url.startswith("https://api.crossref.org/works/"):
            result = self.retrieve(
                request_url,
                headers=self.headers,
            )

            if result.status_code == 404:
                return

            result = result.json()

            yield result["message"]

            return

        if self.cursor_as_iter_method is True:
            request_params = dict(self.request_params)
            request_params["cursor"] = "*"
            request_params["rows"] = str(LIMIT)
            while True:

                result = self.retrieve(
                    request_url,
                    data=request_params,
                    headers=self.headers,
                    cache=False,
                )

                if result.status_code == 404:
                    return

                result = result.json()

                if len(result["message"]["items"]) == 0:
                    return

                yield from result["message"]["items"]

                request_params["cursor"] = result["message"]["next-cursor"]

        else:
            request_params = dict(self.request_params)
            request_params["offset"] = "0"
            request_params["rows"] = str(LIMIT)
            while True:
                result = self.retrieve(
                    request_url,
                    data=request_params,
                    headers=self.headers,
                )

                if result.status_code == 404:
                    return

                result = result.json()

                if (
                    "message" not in result
                    or "items" not in result["message"]
                    or len(result["message"]["items"]) == 0
                ):
                    return

                yield from result["message"]["items"]

                request_params["offset"] = str(int(request_params["offset"]) + LIMIT)

                if int(request_params["offset"]) >= MAXOFFSET:
                    msg = "Offset exceded the max offset of %d"
                    raise MaxOffsetError(msg, MAXOFFSET)


class CrossrefAPI:
    """Crossref API"""

    ISSN_REGEX = r"^\d{4}-?\d{3}[\dxX]$"
    YEAR_SCOPE_REGEX = r"^\d{4}-\d{4}$"

    # https://github.com/CrossRef/rest-api-doc
    _api_url = "https://api.crossref.org/"

    last_updated: str = ""

    _availability_exception_message = (
        f"Crossref ({Colors.ORANGE}check https://status.crossref.org/{Colors.END})"
    )

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        params: dict,
        rerun: bool = False,
    ):
        self.params = params

        _, self.email = (
            colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git()
        )
        self.rerun = rerun

    def check_availability(self, raise_service_not_available: bool = True) -> None:
        """Check the availability of the API"""

        try:
            # pylint: disable=duplicate-code
            test_rec = {
                Fields.DOI: "10.17705/1cais.04607",
                Fields.AUTHOR: "Schryen, Guido and Wagner, Gerit and Benlian, Alexander "
                "and Paré, Guy",
                Fields.TITLE: "A Knowledge Development Perspective on Literature Reviews: "
                "Validation of a new Typology in the IS Field",
                Fields.ID: "SchryenEtAl2021",
                Fields.JOURNAL: "Communications of the Association for Information Systems",
                Fields.ENTRYTYPE: "article",
            }

            returned_record = self.crossref_query(
                record_input=colrev.record.record_prep.PrepRecord(test_rec),
                jour_vol_iss_list=False,
            )[0]

            if 0 != len(returned_record.data):
                assert returned_record.data[Fields.TITLE] == test_rec[Fields.TITLE]
                assert returned_record.data[Fields.AUTHOR] == test_rec[Fields.AUTHOR]
            else:
                if raise_service_not_available:
                    raise colrev_exceptions.ServiceNotAvailableException(
                        self._availability_exception_message
                    )
        except (requests.exceptions.RequestException, IndexError) as exc:
            print(exc)
            if raise_service_not_available:
                raise colrev_exceptions.ServiceNotAvailableException(
                    self._availability_exception_message
                ) from exc

    def get_url(self) -> str:
        """Get the url for the Crossref API"""

        if "url" not in self.params:
            raise ValueError("No url in params")

        url = self.params["url"]
        if not self.rerun and self.last_updated:
            # see https://api.staging.crossref.org/swagger-ui/
            # index.html#/Journals/get_journals__issn__works
            # "Notes on incremental metadata updates"

            last_updated = self.last_updated.split("T", maxsplit=1)[0]
            url = url + f"?filter=from-index-date:{last_updated}"

        return url

    def get_len_total(self) -> int:
        """Get the total number of records from Crossref based on the parameters"""

        endpoint = Endpoint(self.params["url"], email=self.email)
        return endpoint.get_nr()

    def get_number_of_records(self) -> int:
        """Get the number of records from Crossref based on the parameters"""

        endpoint = Endpoint(self.get_url(), email=self.email)
        return endpoint.get_nr()

    def get_records(self) -> typing.Iterator[colrev.record.record.Record]:
        """Get records from Crossref based on the parameters"""

        url = self.get_url()

        endpoint = Endpoint(url, email=self.email)
        if self.get_number_of_records() > 10000:
            endpoint.cursor_as_iter_method = True

        try:
            for item in endpoint:
                try:
                    yield record_transformer.json_to_record(item=item)
                except colrev_exceptions.RecordNotParsableException:
                    continue
        except requests.exceptions.RequestException as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                self._availability_exception_message
            ) from exc

    def query_doi(self, *, doi: str) -> colrev.record.record_prep.PrepRecord:
        """Get records from Crossref based on a doi query"""

        try:
            endpoint = Endpoint(self._api_url + "works/" + doi, email=self.email)

            crossref_query_return = next(iter(endpoint))

            if crossref_query_return is None:
                raise colrev_exceptions.RecordNotFoundInPrepSourceException(
                    msg="Record not found in crossref (based on doi)"
                )

            retrieved_record = record_transformer.json_to_record(
                item=crossref_query_return
            )
            return retrieved_record

        except (requests.exceptions.RequestException, StopIteration) as exc:
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
        return similarity

    def _create_query_url(
        self, *, record: colrev.record.record.Record, jour_vol_iss_list: bool
    ) -> str:
        if jour_vol_iss_list:
            if not all(
                x in record.data for x in [Fields.JOURNAL, Fields.VOLUME, Fields.NUMBER]
            ):
                raise colrev_exceptions.NotEnoughDataToIdentifyException
            params = {}
            container_title = re.sub(r"[\W]+", " ", record.data[Fields.JOURNAL])
            params["query.container-title"] = container_title.replace("_", " ")

            query_field = ""
            if Fields.VOLUME in record.data:
                query_field = record.data[Fields.VOLUME]
            if Fields.NUMBER in record.data:
                query_field = query_field + "+" + record.data[Fields.NUMBER]
            params["query"] = query_field
            # params["rows"]  = "50"

        else:
            if Fields.TITLE not in record.data:
                raise colrev_exceptions.NotEnoughDataToIdentifyException()

            params = {}
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
            params["query.bibliographic"] = bibl.replace("_", " ").rstrip("+")

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
            # params["rows"] = "15"

        url = self._api_url + "works?" + urllib.parse.urlencode(params)
        return url

    def crossref_query(
        self,
        *,
        record_input: colrev.record.record.Record,
        jour_vol_iss_list: bool = False,
    ) -> list:
        """Retrieve records from Crossref based on a query"""

        record = record_input.copy_prep_rec()
        record_list, most_similar, most_similar_record = [], 0.0, {}

        url = self._create_query_url(record=record, jour_vol_iss_list=jour_vol_iss_list)

        endpoint = Endpoint(url, email=self.email)
        if jour_vol_iss_list:
            endpoint.request_params["rows"] = "50"
        else:
            endpoint.request_params["rows"] = "15"

        counter = 0
        while True:
            try:
                item = next(iter(endpoint), None)
            except requests.exceptions.RequestException as exc:
                raise colrev_exceptions.ServiceNotAvailableException(
                    f"Crossref ({Colors.ORANGE}check https://status.crossref.org/{Colors.END})"
                ) from exc
            if item is None:
                break
            try:
                retrieved_record = record_transformer.json_to_record(item=item)
                similarity = self._get_similarity(
                    record=record, retrieved_record_dict=retrieved_record.data
                )

                if jour_vol_iss_list:
                    record_list.append(retrieved_record)
                elif most_similar < similarity:
                    most_similar = similarity
                    most_similar_record = retrieved_record.get_data()
            except colrev_exceptions.RecordNotParsableException:
                pass
            counter += 1
            if jour_vol_iss_list and counter > 200:
                break
            if not jour_vol_iss_list and counter > 5:
                break

        if not jour_vol_iss_list:
            if most_similar_record:
                record_list = [
                    colrev.record.record_prep.PrepRecord(most_similar_record)
                ]

        return record_list
