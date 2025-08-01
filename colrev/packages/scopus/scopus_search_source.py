import requests
from colrev.env.package_manager import BaseSearchSource
from colrev.record import Record
from colrev.search import SearchFeed


class ScopusSearchSource(BaseSearchSource):
    """SearchSource for retrieving records from Scopus API"""

    settings_class = None
    source_identifier = "colrev.scopus"

    def __init__(self, *, operation):
        super().__init__(operation=operation)
        self.api_key = self.review_manager.get_api_key(service="scopus")
        self.base_url = "https://api.elsevier.com/content/search/scopus"

    def search(self, query: str) -> None:
        """Conduct a search using the Scopus API"""
        headers = {"X-ELS-APIKey": self.api_key}
        params = {
            "query": query,
            "count": 5,
        }

        print(f"Querying Scopus for: {query}")
        response = requests.get(self.base_url, headers=headers, params=params)

        if response.status_code != 200:
            raise Exception(f"Scopus API error: {response.status_code}")

        data = response.json()
        entries = data.get("search-results", {}).get("entry", [])

        search_feed = SearchFeed(source_identifier=self.source_identifier)

        for entry in entries:
            doi = entry.get("prism:doi", "no-doi")
            title = entry.get("dc:title", "No title available")
            year = entry.get("prism:coverDate", "")[:4]

            record_dict = {
                "ID": doi,
                "title": title,
                "doi": doi,
                "year": year,
                "source": "Scopus"
            }

            record = Record(data=record_dict)

            if not search_feed.record_exists(record):
                search_feed.add_record(record)

        search_feed.save_feed()
