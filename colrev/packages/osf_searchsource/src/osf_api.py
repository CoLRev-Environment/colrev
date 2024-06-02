# osf_api.py

import requests

class OSFApiQuery:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.osf.io/v2"
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
        self.params = {}

    def id(self, value: str):
        self.params["filter[id]"] = value

    def type(self, value: str):
        self.params["filter[type]"] = value

    def author(self, value: str):
        self.params["filter[author]"] = value

    def doi(self, value: str):
        self.params["filter[doi]"] = value

    def publisher(self, value: str):
        self.params["filter[publisher]"] = value

    def title(self, value: str):
        self.params["filter[title]"] = value

    def links(self, value: str):
        self.params["filter[links]"] = value

    def callAPI(self):
        response = requests.get(self.base_url, headers=self.headers, params=self.params)
        response.raise_for_status()
        return response.json()
