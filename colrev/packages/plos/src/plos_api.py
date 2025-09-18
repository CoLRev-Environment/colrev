#! /usr/bin/env python
"""Plos API"""
import contextlib
import datetime
import typing
from datetime import timedelta
from importlib.metadata import version
from pathlib import Path
from time import sleep

import requests
import requests_cache
from rapidfuzz import fuzz

import colrev.env.environment_manager
import colrev.exceptions as colrev_exceptions
import colrev.record.record
import colrev.record.record_prep
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import Filepaths
from colrev.packages.plos.src import plos_record_transformer

# pylint: disable=too-many-arguments
# pylint: disable=too-few-public-methods


LIMIT = 100  # Number max of request
MAXOFFSET = 1000

# Creates a session with cache
SESSION = requests_cache.CachedSession(
    str(Filepaths.LOCAL_ENVIRONMENT_DIR / Path("plos_cache.sqlite")),
    backend="sqlite",
    expire_after=timedelta(days=30),
)


class PlosAPIError(Exception):
    """Plos API Error"""


class MaxOffsetError(PlosAPIError):
    """Max Offset Error"""


class HTTPRequest:
    "HTTP Resquest"

    def __init__(self, *, timeout: int) -> None:
        # https://api.plos.org/solr/faq/
        # 10 request per minute (60s)
        self.rate_limits = {"x-rate-limit-limit": 10, "x-rate-limit-interval": 60}
        self.timeout = timeout

    def _update_rate_limits(self, headers: dict) -> None:

        with contextlib.suppress(ValueError):
            self.rate_limits["x-rate-limit-limit"] = int(
                headers.get("x-rate-limit-limit", 10)
            )

        with contextlib.suppress(ValueError):
            # The :-1 is used to erase the "s" from "60s"
            interval_value = int(headers.get("x-rate-limit-interval", "60s")[:-1])

        interval_scope = headers.get("x-rate-limit-interval", "60s")[-1]

        if interval_scope == "m":
            interval_value = interval_value * 60

        if interval_scope == "h":
            interval_value = interval_value * 60 * 60

        self.rate_limits["x-rate-limit-interval"] = interval_value

    def _get_throttling_time(self) -> float:
        return (
            self.rate_limits["x-rate-limit-interval"]
            / self.rate_limits["x-rate-limit-limit"]
        )

    def retrieve(
        self,
        endpoint: str,
        headers: dict,
        data: typing.Optional[dict] = None,
        only_headers: bool = False,
        skip_throttle: bool = False,
    ) -> requests.Response:
        """Retrieve data from a given endpoint."""
        if only_headers is True:
            return requests.head(endpoint, timeout=2)

        result = SESSION.get(endpoint, params=data, timeout=10, headers=headers)

        if not skip_throttle:
            self._update_rate_limits(result.headers)
            sleep(self._get_throttling_time())

        return result


class Endpoint:
    "Endpoint"

    CURSOR_AS_ITER_METHOD = False

    def __init__(
        self,
        request_url: str,
        *,
        email: str = "",
        plos_plus_token: str = "",
    ) -> None:

        self.retrieve = HTTPRequest(timeout=60).retrieve

        # List of http headers
        self.headers = {
            "user-agent": f"colrev/{version('colrev')} "
            + f"(https://github.com/CoLRev-Environment/colrev; mailto:{email})"
        }

        self.plos_plus_token = plos_plus_token
        if plos_plus_token:
            self.headers["Plos-Plus-API-Token"] = self.plos_plus_token
        self.request_url = request_url
        self.request_params: typing.Dict[str, str] = {}
        self.timeout = 60

    @property
    def _rate_limits(self) -> dict:
        request_url = str(self.request_url)

        result = self.retrieve(
            request_url, only_headers=True, headers=self.headers, skip_throttle=True
        )

        return {
            "x-rate-limit-limit": result.headers.get("x-rate-limit-limit", "undefined"),
            "x-rate-limit-interval": result.headers.get(
                "x-rate-limit-interval", "undefined"
            ),
        }

    def _escaped_pagging(self) -> dict:
        # Deletes params of pagination
        escape_pagging = ["offset", "rows"]
        request_params = dict(self.request_params)

        for item in escape_pagging:
            with contextlib.suppress(KeyError):
                del request_params[item]

        return request_params

    @property
    def version(self) -> str:
        "API version"

        request_params = dict(self.request_params)
        request_url = str(self.request_url)

        result = self.retrieve(
            request_url, data=request_params, headers=self.headers
        ).json

        return result["message-version"]

    def get_nr(self) -> int:
        """Retrieve the total number of records resulting from a query."""
        request_params = dict(self.request_params)
        request_url = str(self.request_url)
        request_params["rows"] = "0"

        try:
            result = self.retrieve(
                request_url, data=request_params, headers=self.headers
            ).json()

        except requests.exceptions.RequestException as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                f"PLOS ({Colors.ORANGE}not available{Colors.END})"  # Same situation in API
            ) from exc

        return int(result["response"]["numFound"])

    @property
    def url(self) -> str:
        """Retrieve the url that will be used as a HTTP request."""

        request_params = self._escaped_pagging()
        sorted_request_params = sorted(request_params.items())

        req = requests.Request(
            "get", self.request_url, params=sorted_request_params
        ).prepare()

        return req.url

    def __iter__(self) -> typing.Iterator[dict]:
        request_url = str(self.request_url)
        if request_url.startswith("https://api.plos.org/search?q=doi:10"):
            result = self.retrieve(request_url, headers=self.headers)

            if result.status_code == 404:
                return

            result = result.json()
            yield result["response"]["docs"]

            return

        if self.CURSOR_AS_ITER_METHOD is True:
            request_params = dict(self.request_params)
            request_params["cursor"] = "*"
            request_params["rows"] = str(LIMIT)
            while True:

                result = self.retrieve(
                    request_url, data=request_params, headers=self.headers
                )

                if result.status_code == 404:
                    return

                result = result.json()

                if len(result["response"]["docs"]) == 0:
                    return

                yield from result["response"]["docs"]

                request_params["cursor"] = result["response"]["next-cursor"]

        else:
            request_params = dict(self.request_params)
            request_params["start"] = "0"
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
                if len(result["response"]["docs"]) == 0:
                    return

                yield from result["response"]["docs"]

                request_params["start"] = str(int(request_params["start"]) + LIMIT)

                if int(request_params["start"]) >= MAXOFFSET:
                    msg = "Offset exceded the max offset of %d"
                    raise MaxOffsetError(msg, MAXOFFSET)


class PlosAPI:
    "PLOS Api"

    ISSN_REGEX = r"^\d{4}-?\d{3}[\dxX]$"
    YEAR_SCOPE_REGEX = r"^\d{4}-\d{4}$"

    # https://github.com/Plos/
    _api_url = "https://api.plos.org/"

    last_updated: str = ""

    _availability_exception_message = f"PLOS ({Colors.ORANGE} not avilable{Colors.END})"

    def __init__(
        self,
        *,
        url: str,
        rerun: bool = False,
    ):
        self.url = url

        _, self.email = (
            colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git()
        )
        self.rerun = rerun

    def get_url(self) -> str:
        "Get the url from the Plos API"

        url = self.url
        if not self.rerun and self.last_updated:
            # Changes the last updated date

            # see https://api.plos.org/solr/search-fields/
            # Publication_date format:
            #   [2009-12-07T00:00:00Z TO 2013-02-20T23:59:59Z]

            last_updated = self.last_updated.split(" ", maxsplit=1)[0]
            last_updated = last_updated.split("+")[0] + "Z"
            now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            date_filter = f"fq=publication_date:[{last_updated} TO {now}]"
            url = f"{url}&{date_filter}"

        return url

    def get_len_total(self) -> int:
        "Get the total number of records from Plos based on the parameters"

        endpoint = Endpoint(self.url, email=self.email)

        return endpoint.get_nr()

    def get_len(self) -> int:
        """Get the number of records from Crossref based on the parameters"""

        endpoint = Endpoint(self.get_url(), email=self.email)
        return endpoint.get_nr()

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

    def get_records(self) -> typing.Iterator[colrev.record.record.Record]:
        "Get records from PLOS based on the parameters"
        url = self.get_url()

        endpoint = Endpoint(url, email=self.email)
        try:
            for item in endpoint:
                try:
                    yield plos_record_transformer.json_to_record(item=item)
                except colrev_exceptions.RecordNotParsableException:
                    continue
        except requests.exceptions.RequestException as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                self._availability_exception_message
            ) from exc

    def query_doi(self, *, doi: str) -> colrev.record.record_prep.PrepRecord:
        "Get records from PLOS based on a id query"

        try:
            endpoint = Endpoint(
                self._api_url
                + "search?q=id:"
                + doi
                + "&fl=id,abstract,author_display,title_display,"
                + "journal,publication_date,volume,issue",
                email=self.email,
            )
            plos_query_return = next(iter(endpoint))
            if plos_query_return is None:
                raise colrev_exceptions.RecordNotFoundInPrepSourceException(
                    msg="Record not found in plos (based on id)"
                )

            retrieved_record = plos_record_transformer.json_to_record(
                item=plos_query_return
            )

            return retrieved_record

        except (requests.exceptions.RequestException, StopIteration) as exc:
            raise colrev_exceptions.RecordNotFoundInPrepSourceException(
                msg="Record not found in PLOS (based on doi)"
            ) from exc
