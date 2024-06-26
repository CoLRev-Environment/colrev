# osf_api.py
import requests


class OSFApiQuery:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.osf.io/v2"
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
        self.params = {}

    def dataType(self, data_type: str):
        self.params["format"] = data_type

    def dataFormat(self, data_format: str):
        self.params["format"] = data_format

    def maximumResults(self, max_results: int):
        self.params["page[size]"] = max_results

    def id(self, value: str):
        self.params["filter[id]"] = value

    def type(self, value: str):
        self.params["filter[type]"] = value

    def title(self, value: str):
        self.params["filter[title]"] = value

    def category(self, value: str):
        self.params["filter[category]"] = value

    def year(self, value: str):
        self.params["filter[year]"] = value

    def ia_url(self, value: str):
        self.params["filter[ia_url]"] = value

    def description(self, value: str):
        self.params["filter[description]"] = value

    def tags(self, value: str):
        self.params["filter[tags]"] = value

    def date_created(self, value: str):
        self.params["filter[date_created]"] = value

    def callAPI(self):
        response = requests.get(self.base_url, headers=self.headers, params=self.params)
        response.raise_for_status()
        return response.json()
