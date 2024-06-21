# osf_api.py

import requests
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

class OSFApiQuery:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.osf.io/v2/nodes"
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
        self.params = {}
        self.queryProvided = False
        self.outputType = "json"
        self.usingTitle = False
        self.usingDescription = False
        self.usingTags = False
        self.queryProvided = False
        


    def dataType(self, data_type: str):
        outputtype = data_type.strip().lower()
        self.outputType = outputtype
        # self.params["type"] = data_type

    def dataFormat(self, data_format: str):
        self.params["format"] = data_format

    def maximumResults(self, max_results: int):
        self.params["page[size]"] = max_results

    def id(self, value: str):
        self.params["filter[id]"] = value

    def type(self, value: str):
        self.params["filter[type]"] = value

    def title(self, value: str):
        self.addParameter("title", value)

    def category(self, value: str):
        self.params["filter[category]"] = value

    def year(self, value: str):
        self.params["filter[year]"] = value

    def ia_url(self, value: str):
        self.params["filter[ia_url]"] = value
    
    def description(self, value: str):
        self.addParameter("description", value)
    
    def tags(self, value:str):
        self.addParameter("tags", value)

    def date_created(self, value:str):
        self.params["filter[date_created]"] = value

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



    def buildQuery(self, filters = None) -> str:
        """Creates the URL for the non-Open Access Document API call
        return string: full URL for querying the API"""
        url = self.base_url

        url += "?apikey=" + str(self.api_key)

        # add in search criteria
        # title
        if self.usingTitle:
            url += "[title]=" + str(self.params["title"])

        # description
        if self.usingDescription:
            url += "[description]=" + str(self.params["desciption"])

        # tags
        if self.usingDescription:
            url += "[description]=" + str(self.params["desciption"])

        # else:
        #     for key, value in self.params.items():
        #         url += "&" + key + "=" + urllib.parse.quote(value)

        return url
    
    
    def queryAPI(self, url: str) -> str:
        """Creates the URL for the API call
        string url  Full URL to pass to API
        return string: Results from API"""
        with urllib.request.urlopen(url) as con:
            content = con.read()
        return content.decode('utf-8')

