#! /usr/bin/env python
"""IEEE Xplore API"""
import json
import math
import urllib.parse
import urllib.request

import colrev.record.record
from colrev.constants import Fields

# pylint: disable=invalid-name
# pylint: disable=too-many-public-methods
# pylint: disable=colrev-missed-constant-usage


class XPLORE:
    """XPLORE API class"""

    # pylint: disable=too-many-instance-attributes
    # API ENDPOINT (all non-Open Access)
    ENDPOINT = "http://ieeexploreapi.ieee.org/api/v1/search/articles"

    # Open Access Document ENDPOINT
    OPEN_ACCESS_ENDPOINT = "http://ieeexploreapi.ieee.org/api/v1/search/document/"

    # pylint: disable=colrev-missed-constant-usage
    API_FIELDS = [
        "abstract",
        "author_url",
        "accessType",
        "article_number",
        "author_order",
        "author_terms",
        "affiliation",
        "citing_paper_count",
        "conference_dates",
        "conference_location",
        "content_type",
        "doi",
        "publisher",
        "pubtype",
        "d-year",
        "end_page",
        "facet",
        "full_name",
        "html_url",
        "ieee_terms",
        "isbn",
        "issn",
        "issue",
        "pdf_url",
        "publication_year",
        "publication_title",
        "standard_number",
        "standard_status",
        "start_page",
        "title",
        "totalfound",
        "totalsearched",
        "volume",
    ]

    FIELD_MAPPING = {
        "citing_paper_count": "citations",
        "publication_year": Fields.YEAR,
        "html_url": Fields.URL,
        "pdf_url": Fields.FULLTEXT,
        "issue": Fields.NUMBER,
    }

    # array of permitted search fields for _search_field() method
    ALLOWED_SEARCH_FIELDS = [
        "abstract",
        "affiliation",
        "article_number",
        "article_title",
        "author",
        "boolean_text",
        "content_type",
        "d-au",
        "d-pubtype",
        "d-publisher",
        "d-year",
        "doi",
        "end_year",
        "facet",
        "index_terms",
        "isbn",
        "issn",
        "is_number",
        "meta_data",
        "open_access",
        "publication_number",
        "publication_title",
        "publication_year",
        "publisher",
        "querytext",
        "start_year",
        "thesaurus_terms",
    ]

    def __init__(self, *, parameters: dict, api_key: str) -> None:
        # API key
        self.apiKey = api_key

        # flag that some search criteria has been provided
        self.queryProvided = False

        # flag for Open Access, which changes ENDPOINT in use and limits results to just Open Access
        self.usingOpenAccess = False

        # flag that article number has been provided, which overrides all other search criteria
        self.usingArticleNumber = False

        # flag that a boolean method is in use
        self.usingBoolean = False

        # flag that a facet is in use
        self.usingFacet = False

        # flag that a facet has been applied, in the event that multiple facets are passed
        self.facetApplied = False

        # default of 25 results returned
        self.resultSetMax = 25

        # maximum of 200 results returned
        self.resultSetMaxCap = 200

        # records returned default to position 1 in result set
        self.startRecord = 1

        # default sort order is ascending; could also be 'desc' for descending
        self.sortOrder = "asc"

        # field name that is being used for sorting
        self.sortField = "article_title"

        # dictionary of all search parameters in use and their values
        self.parameters: dict = {}

        # dictionary of all filters in use and their values
        self.filters: dict = {}

        parameter_methods = {}
        parameter_methods["query"] = self.queryText
        parameter_methods["parameter"] = self.queryText

        for key, value in parameters.items():
            if key in parameter_methods:
                method = parameter_methods[key]
                method(value)
            else:
                self._search_field(key, value)

    def startingResult(self, start: int) -> None:
        """Set the start position in the results
        string start   Start position in the returned data"""

        self.startRecord = math.ceil(start) if (start > 0) else 1

    def maximumResults(self, maximum: int) -> None:
        """Set the maximum number of results
        string maximum   Max number of results to return"""
        self.resultSetMax = math.ceil(maximum) if (maximum > 0) else 25
        self.resultSetMax = min(self.resultSetMax, self.resultSetMaxCap)

    def resultsFilter(self, filterParam: str, value: str) -> None:
        """Set a filter on results
        string filterParam   Field used for filtering
        string value    Text to filter on"""

        filterParam = filterParam.strip().lower()
        value = value.strip()

        if len(value) > 0:
            self.filters[filterParam] = value
            self.queryProvided = True

            # Standards do not have article titles, so switch to sorting by article number
            if filterParam == "content_type" and value == "Standards":
                self.resultsSorting("publication_year", "asc")

    def resultsSorting(self, field: str, order: str) -> None:
        """Setting sort order for results
        string field   Data field used for sorting
        string order   Sort order for results (ascending or descending)"""
        field = field.strip().lower()
        order = order.strip()
        self.sortField = field
        self.sortOrder = order

    def queryText(self, value: str) -> None:
        """Text to query across metadata fields, abstract and document text"""
        self._add_parameter("querytext", value)

    def articleNumber(self, value: str) -> None:
        """Article number to query"""
        self._add_parameter("article_number", value)

    def _search_field(self, field: str, value: str) -> None:
        """Shortcut method for assigning search parameters and values
        string field   Field used for searching
        string value   Text to query"""

        field = field.strip().lower()
        if field in self.ALLOWED_SEARCH_FIELDS:
            self._add_parameter(field, value)
        else:
            print("Searches against field " + field + " are not supported")

    def facetText(self, value: str) -> None:
        """Facet text to query"""
        self._add_parameter("facet", value)

    def _add_parameter(self, parameter: str, value: str) -> None:
        """Add parameter"""
        value = value.strip()

        if len(value) > 0:
            self.parameters[parameter] = value

            # viable query criteria provided
            self.queryProvided = True

            # set flags based on parameter
            if parameter == "article_number":
                self.usingArticleNumber = True

            if parameter == "boolean_text":
                self.usingBoolean = True

            if parameter in ["facet", "d-au", "d-year", "d-pubtype", "d-publisher"]:
                self.usingFacet = True

    def openAccess(self, article: str) -> None:
        """Open Access document"""
        self.usingOpenAccess = True
        self.queryProvided = True
        self.articleNumber(article)

    def _build_open_access_query(self) -> str:
        """Creates the URL for the Open Access Document API call
        return string: full URL for querying the API"""

        url = self.OPEN_ACCESS_ENDPOINT
        url += str(self.parameters["article_number"]) + "/fulltext"
        url += "?apikey=" + str(self.apiKey)
        url += "&format=json"

        return url

    def _build_query(self) -> str:
        """Creates the URL for the non-Open Access Document API call
        return string: full URL for querying the API"""

        url = self.ENDPOINT
        url += "?apikey=" + str(self.apiKey)
        url += "&format=json"
        url += "&max_records=" + str(self.resultSetMax)
        url += "&start_record=" + str(self.startRecord)
        url += "&sort_order=" + str(self.sortOrder)
        url += "&sort_field=" + str(self.sortField)

        # add in search criteria
        # article number query takes priority over all others
        if self.usingArticleNumber:
            url += "&article_number=" + str(self.parameters["article_number"])

        # boolean query
        elif self.usingBoolean:
            url += (
                "&querytext=("
                + urllib.parse.quote(self.parameters["boolean_text"])
                + ")"
            )

        else:
            for key, value in self.parameters.items():
                if self.usingFacet and self.facetApplied is False:
                    url += "&querytext=" + urllib.parse.quote(value) + "&facet=" + key
                    self.facetApplied = True

                else:
                    url += "&" + key + "=" + urllib.parse.quote(value)

        # add in filters
        for key, value in self.filters.items():
            url += "&" + key + "=" + str(value)

        return url

    def _query_api(self, url: str) -> str:
        """Creates the URL for the API call
        string url  Full URL to pass to API
        return string: Results from API"""
        with urllib.request.urlopen(url) as con:
            content = con.read()
        return content

    def _update_special_case_fields(self, *, record_dict: dict, article: dict) -> None:
        if "start_page" in article:
            record_dict[Fields.PAGES] = article.pop("start_page")
            if "end_page" in article:
                record_dict[Fields.PAGES] += "--" + article.pop("end_page")

        if "authors" in article and "authors" in article["authors"]:
            author_list = []
            for author in article["authors"]["authors"]:
                author_list.append(author["full_name"])
            record_dict[Fields.AUTHOR] = (
                colrev.record.record_prep.PrepRecord.format_author_field(
                    " and ".join(author_list)
                )
            )

        if (
            "index_terms" in article
            and "author_terms" in article["index_terms"]
            and "terms" in article["index_terms"]["author_terms"]
        ):
            record_dict[Fields.KEYWORDS] = ", ".join(
                article["index_terms"]["author_terms"]["terms"]
            )

    def _create_record_dict(self, article: dict) -> dict:
        record_dict = {Fields.ID: article["article_number"]}
        # self.review_manager.p_printer.pprint(article)

        if article["content_type"] == "Conferences":
            record_dict[Fields.ENTRYTYPE] = "inproceedings"
            if "publication_title" in article:
                record_dict[Fields.BOOKTITLE] = article.pop("publication_title")
        else:
            record_dict[Fields.ENTRYTYPE] = "article"
            if "publication_title" in article:
                record_dict[Fields.JOURNAL] = article.pop("publication_title")

        for field in self.API_FIELDS:
            if article.get(field) is None:
                continue
            record_dict[field] = str(article.get(field))

        for api_field, rec_field in self.FIELD_MAPPING.items():
            if api_field not in record_dict:
                continue
            record_dict[rec_field] = record_dict.pop(api_field)

        self._update_special_case_fields(record_dict=record_dict, article=article)

        return record_dict

    def get_records(self) -> list:
        """Calls the API to receive the records"""

        if self.usingOpenAccess is True:
            url = self._build_open_access_query()

        else:
            url = self._build_query()

        if self.queryProvided is False:
            print("No search criteria provided")

        data = self._query_api(url)
        formattedData = json.loads(data)
        if "articles" not in formattedData:
            return []
        articles = formattedData["articles"]
        records = []
        for article in articles:
            record_dict = self._create_record_dict(article)
            record = colrev.record.record.Record(record_dict)
            records.append(record)
        return records
