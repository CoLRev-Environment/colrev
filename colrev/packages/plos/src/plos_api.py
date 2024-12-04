#! /usr/bin/env python
"""Plos API"""
import contextlib
import re
import typing
import urllib
from datetime import timedelta
from importlib.metadata import version
from pathlib import Path
from time import sleep
import colrev.record.record_prep

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

LIMIT = 100 #Number max of elements returned
MAXOFFSET = 1000

#Creates a session with cache
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

    def retrieve(
        self, 
        endpoint: str,
        headers: dict,
        data: typing.Optional[dict] = None,
        only_headers: bool = False,
        skip_throttle: bool = False
    ) -> requests.Response:
        """Retrieve data from a given endpoint."""

        if only_headers is True:
            return requests.head(endpoint, timeout=2)

        result = SESSION.get(
            endpoint, params=data, timeout=self.timeout, headers=headers
        )

        if not skip_throttle:
            #In case we want rate limits
            self.update_rate_limits(result.headers) #To implement
            sleep(self._get_throttling_yime()) #To implement

        return result


class Enpoint:
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
        #To do in class HttpRequest

        #List of http headers
        self.headers = {
            "user-agent": f"colrev/{version('colrev')} "
            + f"(https://github.com/CoLRev-Environment/colrev; mailto:{email})"
        }

        self.plos_plus_token = plos_plus_token
        if plos_plus_token:
            self.headers["Plos-Plus-API-Token"] = self.plos_plus_token #???
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
            skip_throttle=True
        )

        return {
            "x-rate-limit-limit": result.headers.get("x-rate-limit-limit", "undefined"),
            "x-rate-limit-interval": result.headers.get(
                "x-rate-limit-interval", "undefined"
            ),

        }

    def _escaped_pagging(self) -> dict:
        #Deletes params of pagination
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
        request_url,
        data = request_params,
        headers=self.headers
       ).json

       return result["message-version"]

    def get_nr(self) -> int:
        """Retrieve the total number of records resulting from a query."""

        request_params = dict(self.request_params)
        request_url = str(self.request_url)
        request_params["rows"] = "0"

        try:
            result = self.retrieve(
                request_url,
                data = request_params,
                headers=self.headers).json
        except requests.exceptions.RequestException as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                f"PLOS ({Colors.ORANGE}check https://*********{Colors.END})" #To do
            ) from exc

        return int(result["message"]["total-results"]) #To do
                                                       #Check how is in PLOS

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

        if request_url.startswith("******"): #To do
            result = self.retrieve(
                request_url, 
                headers=self.headers
            )

            if result.status_code == 404:
                return

            result = result.json()

            yield result["message"]

            return


        if self.CURSOR_AS_ITER_METHOD is True:
            request_params = dict(self.request_params)
            request_params["cursor"] = "*"
            request_params["rows"] = str(LIMIT)
            while True:

                result = self.retrieve(
                    request_url,
                    data=request_params,
                    headers=self.headers
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

                if len(result["message"]["items"]) == 0:
                    return

                yield from result["message"]["items"]

                request_params["offset"] = str(int(request_params["offset"]) + LIMIT)

                if int(request_params["offset"]) >= MAXOFFSET:
                    msg = "Offset exceded the max offset of %d"
                    raise MaxOffsetError(msg, MAXOFFSET)




class PlosAPI:
    "PLOS Api"

    ISSN_REGEX = r"^\d{4}-?\d{3}[\dxX]$"
    YEAR_SCOPE_REGEX = r"^\d{4}-\d{4}$"  

    # https://github.com/Plos/
    _api_url = "https://api.plos.org/"

    last_updated: str = ""

    _availability_exception_message = (
        f"Plos ({Colors.ORANGE}check https://status.plos.org/{Colors.END})"
    )

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

    
    def get_url(self) -> str:
        "Get the url from the Plos API"

        if "url" not in self.params:
            raise ValueError("No url in params")
        
        url = self.params["url"]
        if not self.rerun and self.last_updated:
            #Changes the last updated date

            #see https://api.plos.org/solr/search-fields/
            #Publication_date format:
            #   [2009-12-07T00:00:00Z TO 2013-02-20T23:59:59Z]

            last_updated = self.last_updated.split(" ", maxsplit=1)[0]
            date_filter = f"fq=publication_date:[{last_updated} TO NOW]"
            url = f"{url}?{date_filter}"

        return url

    def get_len_total(self) -> int:
        "Get the total number of records from Plos based on the parameters"

        endpoint = Enpoint(self.params["url"], email=self.email)
        return endpoint.get_nr() #TO DO IN ENDPOINT CLASS
    

    def get_records(self) -> typing.Iterator[colrev.record.record.Record]:
        """Get records fromPlos based on parameters"""

        url = self.get_url()

        endpoint = Enpoint(url, email=self.email)

        
        for item in endpoint:
            print("Hola")