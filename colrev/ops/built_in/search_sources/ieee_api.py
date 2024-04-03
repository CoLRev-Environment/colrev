#! /usr/bin/env python
"""SDK for IEEE Xplore API"""
import json
import math
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# pylint: disable=invalid-name
# pylint: disable=too-many-public-methods


class XPLORE:
    """XPLORE SDK"""

    # pylint: disable=too-many-instance-attributes
    # API endpoint (all non-Open Access)
    endPoint = "http://ieeexploreapi.ieee.org/api/v1/search/articles"

    # Open Access Document endpoint
    openAccessEndPoint = "http://ieeexploreapi.ieee.org/api/v1/search/document/"

    def __init__(self, apiKey: str) -> None:
        # API key
        self.apiKey = apiKey

        # flag that some search criteria has been provided
        self.queryProvided = False

        # flag for Open Access, which changes endpoint in use and limits results to just Open Access
        self.usingOpenAccess = False

        # flag that article number has been provided, which overrides all other search criteria
        self.usingArticleNumber = False

        # flag that a boolean method is in use
        self.usingBoolean = False

        # flag that a facet is in use
        self.usingFacet = False

        # flag that a facet has been applied, in the event that multiple facets are passed
        self.facetApplied = False

        # data type for results; default is json (other option is xml)
        self.outputType = "json"

        # data format for results; default is raw (returned string); other option is object
        self.outputDataFormat = "raw"

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

        # array of permitted search fields for searchField() method
        self.allowedSearchFields = [
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

        # dictionary of all search parameters in use and their values
        self.parameters: dict = {}

        # dictionary of all filters in use and their values
        self.filters: dict = {}

    # ensuring == can be used reliably
    def __eq__(self, other: object) -> bool:
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return False

    # ensuring != can be used reliably
    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def dataType(self, outputType: str) -> None:
        """set the data type for the API output
        string outputType   Format for the returned result (JSON, XML)"""

        outputType = outputType.strip().lower()
        self.outputType = outputType

    def dataFormat(self, outputDataFormat: str) -> None:
        """set the data format for the API output
        string outputDataFormat   Data structure for the returned result (raw string or object)
        """

        outputDataFormat = outputDataFormat.strip().lower()
        self.outputDataFormat = outputDataFormat

    def startingResult(self, start: int) -> None:
        """Set the start position in the results
        string start   Start position in the returned data"""

        self.startRecord = math.ceil(start) if (start > 0) else 1

    def maximumResults(self, maximum: int) -> None:
        """set the maximum number of results
        string maximum   Max number of results to return"""
        self.resultSetMax = math.ceil(maximum) if (maximum > 0) else 25
        self.resultSetMax = min(self.resultSetMax, self.resultSetMaxCap)

    def resultsFilter(self, filterParam: str, value: str) -> None:
        """setting a filter on results
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

    def searchField(self, field: str, value: str) -> None:
        """Shortcut method for assigning search parameters and values
        string field   Field used for searching
        string value   Text to query"""

        field = field.strip().lower()
        if field in self.allowedSearchFields:
            self.addParameter(field, value)
        else:
            print("Searches against field " + field + " are not supported")

    def abstractText(self, value: str) -> None:
        """Abstract text to query"""
        self.addParameter("abstract", value)

    def affiliationText(self, value: str) -> None:
        """Affiliation text to query"""
        self.addParameter("affiliation", value)

    def articleNumber(self, value: str) -> None:
        """Article number to query"""
        self.addParameter("article_number", value)

    def articleTitle(self, value: str) -> None:
        """Article title to query"""
        self.addParameter("article_title", value)

    def authorText(self, value: str) -> None:
        """Author to query"""
        self.addParameter("author", value)

    def authorFacetText(self, value: str) -> None:
        """Author Facet text to query"""
        self.addParameter("d-au", value)

    def booleanText(self, value: str) -> None:
        """Value(s) to use in the boolean query"""
        self.addParameter("boolean_text", value)

    def contentTypeFacetText(self, value: str) -> None:
        """Content Type Facet text to query"""
        self.addParameter("d-pubtype", value)

    def doi(self, value: str) -> None:
        """DOI (Digital Object Identifier) to query"""
        self.addParameter("doi", value)

    def facetText(self, value: str) -> None:
        """Facet text to query"""
        self.addParameter("facet", value)

    def indexTerms(self, value: str) -> None:
        """Author Keywords, IEEE Terms, and Mesh Terms to query"""
        self.addParameter("index_terms", value)

    def isbn(self, value: str) -> None:
        """ISBN (International Standard Book Number) to query"""
        self.addParameter("isbn", value)

    def issn(self, value: str) -> None:
        """ISSN (International Standard Serial number) to query"""
        self.addParameter("issn", value)

    def issueNumber(self, value: str) -> None:
        """Issue number to query"""
        self.addParameter("is_number", value)

    def metaDataText(self, value: str) -> None:
        """Text to query across metadata fields and the abstract"""
        self.addParameter("meta_data", value)

    def publicationFacetText(self, value: str) -> None:
        """Publication Facet text to query"""
        self.addParameter("d-year", value)

    def publisherFacetText(self, value: str) -> None:
        """Publisher Facet text to query"""
        self.addParameter("d-publisher", value)

    def publicationTitle(self, value: str) -> None:
        """Publication title to query"""
        self.addParameter("publication_title", value)

    def publicationYear(self, value: str) -> None:
        """Publication year to query"""
        self.addParameter("publication_year", value)

    def queryText(self, value: str) -> None:
        """Text to query across metadata fields, abstract and document text"""
        self.addParameter("querytext", value)

    def thesaurusTerms(self, value: str) -> None:
        """Thesaurus terms (IEEE Terms) to query"""
        self.addParameter("thesaurus_terms", value)

    def addParameter(self, parameter: str, value: str) -> None:
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

    def callAPI(self) -> dict:
        """Calls the API
        string debugMode  If this mode is on (True) then output query and not data
        return either raw result string, XML or JSON object, or array"""

        if self.usingOpenAccess is True:
            ret = self.buildOpenAccessQuery()

        else:
            ret = self.buildQuery()

        if self.queryProvided is False:
            print("No search criteria provided")

        data = self.queryAPI(ret)
        formattedData = self.formatData(data)
        return formattedData

    def buildOpenAccessQuery(self) -> str:
        """Creates the URL for the Open Access Document API call
        return string: full URL for querying the API"""
        url = self.openAccessEndPoint
        url += str(self.parameters["article_number"]) + "/fulltext"
        url += "?apikey=" + str(self.apiKey)
        url += "&format=" + str(self.outputType)

        return url

    def buildQuery(self) -> str:
        """Creates the URL for the non-Open Access Document API call
        return string: full URL for querying the API"""
        url = self.endPoint

        url += "?apikey=" + str(self.apiKey)
        url += "&format=" + str(self.outputType)
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

    def queryAPI(self, url: str) -> str:
        """Creates the URL for the API call
        string url  Full URL to pass to API
        return string: Results from API"""
        with urllib.request.urlopen(url) as con:
            content = con.read()
        return content

    def formatData(self, data: str):  # type: ignore
        """Formats the data returned by the API
        string data    Result string from API"""

        if self.outputDataFormat == "raw":
            return data

        if self.outputDataFormat == "object":
            if self.outputType == "xml":
                obj = ET.ElementTree(ET.fromstring(data))
                return obj

            obj = json.loads(data)
            return obj

        return data
