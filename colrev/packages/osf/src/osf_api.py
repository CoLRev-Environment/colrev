# osf_api.py
import json

import requests


class OSFApiQuery:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.osf.io/v2/nodes"
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
        self.params = {}
        self.outputType = "json"
        self.outputDataFormat = "bib"
        self.startRecord = 1
        self.page = 1

    def dataType(self, data_type: str):
        outputtype = data_type.strip().lower()
        self.outputType = outputtype

    def dataFormat(self, data_format: str):
        outputDataFormat = data_format.strip().lower()
        self.outputDataFormat = outputDataFormat

    def id(self, value: str):
        self.params["id"] = value

    def type(self, value: str):
        self.params["type"] = value

    def title(self, value: str):
        self.params["title"] = value

    def year(self, value: str):
        self.params["year"] = value

    def description(self, value: str):
        self.params["description"] = value

    def tags(self, value: str):
        self.params["tags"] = value

    def date_created(self, value: str):
        self.params["date_created"] = value

    def callAPI(self):
        ret = self.buildQuery()
        data = self.queryAPI(ret)
        formattedData = json.loads(data)
        return formattedData

    def buildQuery(self) -> str:
        """Creates the URL for querying the API with support for nested filter parameters."""

        # Initialize the URL with the base endpoint
        url = f"{self.base_url}/?filter["

        # Add in filters with the correct formatting
        for key, value in self.params.items():
            url += key + "]=" + str(value)

        url += f"&page={self.page}"

        return url

    def queryAPI(self, url: str) -> str:
        """Creates the URL for the API call
        string url  Full URL to pass to API
        return string: Results from API"""

        response = requests.get(url, headers=self.headers)
        return response.text
