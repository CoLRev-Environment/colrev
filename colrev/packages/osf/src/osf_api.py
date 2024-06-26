# osf_api.py
import math
import requests
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlencode

class OSFApiQuery:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.osf.io/v2/nodes"
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
        self.params = {}
        self.filters = {}
        self.queryProvided = False
        self.outputType = "json"
        self.outputDataFormat = "bib"
        self.usingTitle = False
        self.usingDescription = False
        self.usingTags = False
        self.queryProvided = False
        self.resultSetMax = 25
        self.startRecord = 1
        self.page = 45


    def dataType(self, data_type: str):
        outputtype = data_type.strip().lower()
        self.outputType = outputtype
        # self.params["type"] = data_type

    def dataFormat(self, data_format: str):
        outputDataFormat = data_format.strip().lower()
        self.outputDataFormat = outputDataFormat

    def maximumResults(self, max_results: int):
        self.resultSetMax = math.ceil(max_results) if (max_results > 0) else 25
        self.resultSetMax = min(self.resultSetMax, 200)

    def id(self, value: str):
        self.params['id'] = value

    def type(self, value: str):
        self.params['type'] = value

    def title(self, value: str):
        self.params['title'] = value

    def category(self, value: str):
        self.params['category'] = value

    def year(self, value: str):
        self.params['year'] = value

    def ia_url(self, value: str):
        self.params['ia_url'] = value
    
    def description(self, value: str):
        self.params['description'] = value
    
    def tags(self, value:str):
        self.params['tags'] = value

    def date_created(self, value:str):
        self.params['date_created'] = value

    def set_parameter(self, key, value):
        self.params[f'filter[{key}]'] = value

    def addParameter(self, parameter: str, value: str) -> None:
        """Add parameter"""
        value = value.strip()

        if len(value) > 0:
            self.params[parameter] = value

            # viable query criteria provided
            self.queryProvided = True

            # set flags based on parameter
            if parameter == "title":
                self.usingTitle = True

            if parameter == "description":
                self.usingDescription = True

            if parameter == "tags":
                self.usingTags = True


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
 
        url += f"&apikey={self.api_key}"

        url += f"&page={self.page}"
        # input(url)
        return url

    def queryAPI(self, url: str) -> str:
        """Creates the URL for the API call
        string url  Full URL to pass to API
        return string: Results from API"""
        with urllib.request.urlopen(url) as con:
            content = con.read()
        return content.decode("utf-8")
