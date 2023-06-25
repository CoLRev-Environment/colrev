import math
import urllib
import urllib2
import xml.etree.ElementTree as ET
import json

class XPLORE:
 
    # API endpoint (all non-Open Access)
    endPoint = "http://ieeexploreapi.ieee.org/api/v1/search/articles"

    # Open Access Document endpoint
    openAccessEndPoint = "http://ieeexploreapi.ieee.org/api/v1/search/document/"    

    def __init__(self, apiKey):

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
        self.outputType = 'json'

        # data format for results; default is raw (returned string); other option is object
        self.outputDataFormat = 'raw'

        # default of 25 results returned
        self.resultSetMax = 25

        # maximum of 200 results returned
        self.resultSetMaxCap = 200

        # records returned default to position 1 in result set
        self.startRecord = 1

        # default sort order is ascending; could also be 'desc' for descending
        self.sortOrder = 'asc'

        # field name that is being used for sorting
        self.sortField = 'article_title'

        # array of permitted search fields for searchField() method
        self.allowedSearchFields = ['abstract', 'affiliation', 'article_number', 'article_title', 'author', 'boolean_text', 'content_type', 'd-au', 'd-pubtype', 'd-publisher', 'd-year', 'doi', 'end_year', 'facet', 'index_terms', 'isbn', 'issn', 'is_number', 'meta_data', 'open_access', 'publication_number', 'publication_title', 'publication_year', 'publisher', 'querytext', 'start_year', 'thesaurus_terms']

        # dictionary of all search parameters in use and their values
        self.parameters = {}

        # dictionary of all filters in use and their values
        self.filters = {}


    # ensuring == can be used reliably
    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False


    # ensuring != can be used reliably
    def __ne__(self, other):
        return not self.__eq__(other)


    # set the data type for the API output
    # string outputType   Format for the returned result (JSON, XML)
    # return void
    def dataType(self, outputType):

        outputType = outputType.strip().lower()
        self.outputType = outputType


    # set the data format for the API output
    # string outputDataFormat   Data structure for the returned result (raw string or object)
    # return void
    def dataFormat(self, outputDataFormat):

        outputDataFormat = outputDataFormat.strip().lower()
        self.outputDataFormat = outputDataFormat


    # set the start position in the
    # string start   Start position in the returned data
    # return void
    def startingResult(self, start):

        self.startRecord = math.ceil(start) if (start > 0) else 1


    # set the maximum number of results
    # string maximum   Max number of results to return
    # return void
    def maximumResults(self, maximum):

        self.resultSetMax = math.ceil(maximum) if (maximum > 0) else 25
        if self.resultSetMax > self.resultSetMaxCap:
            self.resultSetMax = self.resultSetMaxCap


    # setting a filter on results
    # string filterParam   Field used for filtering
    # string value    Text to filter on
    # return void
    def resultsFilter(self, filterParam, value):

        filterParam = filterParam.strip().lower()
        value = value.strip()

        if len(value) > 0:
            self.filters[filterParam] = value
            self.queryProvided = True

            # Standards do not have article titles, so switch to sorting by article number
            if (filterParam == 'content_type' and value == 'Standards'):
                self.resultsSorting('publication_year', 'asc')


    # setting sort order for results
    # string field   Data field used for sorting
    # string order   Sort order for results (ascending or descending)
    # return void
    def resultsSorting(self, field, order):

        field = field.strip().lower()
        order = order.strip()
        self.sortField = field
        self.sortOrder = order


    # shortcut method for assigning search parameters and values
    # string field   Field used for searching
    # string value   Text to query
    # return void
    def searchField(self, field, value):

        field = field.strip().lower()
        if field in self.allowedSearchFields:
            self.addParameter(field, value)
        else:
            print "Searches against field " + field + " are not supported"


    # string value   Abstract text to query
    # return void
    def abstractText(self, value):

        self.addParameter('abstract', value)


    # string value   Affiliation text to query
    # return void
    def affiliationText(self, value):

        self.addParameter('affiliation', value)


    # string value   Article number to query
    # return void
    def articleNumber(self, value):

        self.addParameter('article_number', value)


    # string value   Article title to query
    # return void
    def articleTitle(self, value):

        self.addParameter('article_title', value)


    # string value   Author to query
    # return void
    def authorText(self, value):

        self.addParameter('author', value)


    # string value   Author Facet text to query
    # return void
    def authorFacetText(self, value):

        self.addParameter('d-au', value)


    # string value   Value(s) to use in the boolean query
    # return void
    def booleanText(self, value):

        self.addParameter('boolean_text', value)


    # string value   Content Type Facet text to query
    # return void
    def contentTypeFacetText(self, value):

        self.addParameter('d-pubtype', value)


    # string value   DOI (Digital Object Identifier) to query
    # return void
    def doi(self, value):

        self.addParameter('doi', value)


    # string value   Facet text to query
    # return void
    def facetText(self, value):

        self.addParameter('facet', value)


    # string value   Author Keywords, IEEE Terms, and Mesh Terms to query
    # return void
    def indexTerms(self, value):

        self.addParameter('index_terms', value)


    # string value   ISBN (International Standard Book Number) to query
    # return void
    def isbn(self, value):

        self.addParameter('isbn', value)


    # string value   ISSN (International Standard Serial number) to query
    # return void
    def issn(self, value):

        self.addParameter('issn', value)


    # string value   Issue number to query
    # return void
    def issueNumber(self, value):

        self.addParameter('is_number', value)


    # string value   Text to query across metadata fields and the abstract
    # return void
    def metaDataText(self, value):

        self.addParameter('meta_data', value)


    # string value   Publication Facet text to query
    # return void
    def publicationFacetText(self, value):

        self.addParameter('d-year', value)


    # string value   Publisher Facet text to query
    # return void
    def publisherFacetText(self, value):

        self.addParameter('d-publisher', value)


    # string value   Publication title to query
    # return void
    def publicationTitle(self, value):

        self.addParameter('publication_title', value)


    # string or number value   Publication year to query
    # return void
    def publicationYear(self, value):

        self.addParameter('publication_year', value)


    # string value   Text to query across metadata fields, abstract and document text
    # return void
    def queryText(self, value):

        self.addParameter('querytext', value)


    # string value   Thesaurus terms (IEEE Terms) to query
    # return void
    def thesaurusTerms(self, value):

        self.addParameter('thesaurus_terms', value)


    # add query parameter
    # string parameter   Data field to query
    # string value       Text to use in query
    # return void
    def addParameter(self, parameter, value):
      
        value = value.strip()

        if (len(value) > 0):

            self.parameters[parameter]= value
        
            # viable query criteria provided
            self.queryProvided = True

            # set flags based on parameter
            if (parameter == 'article_number'):

                self.usingArticleNumber = True

            if (parameter == 'boolean_text'):

                self.usingBoolean = True

            if (parameter == 'facet' or parameter == 'd-au' or parameter == 'd-year' or parameter == 'd-pubtype' or parameter == 'd-publisher'):

                self.usingFacet = True

    
    # Open Access document
    # string article   Article number to query
    # return void
    def openAccess(self, article):
      
        self.usingOpenAccess = True
        self.queryProvided = True
        self.articleNumber(article)


    # calls the API
    # string debugMode  If this mode is on (True) then output query and not data
    # return either raw result string, XML or JSON object, or array
    def callAPI(self, debugModeOff=True):
        
        if self.usingOpenAccess is True:

            str = self.buildOpenAccessQuery()         

        else:

            str = self.buildQuery()

        if debugModeOff is False:
        
            return str
        
        else:
        
            if self.queryProvided is False:
                print "No search criteria provided"
        
            data = self.queryAPI(str)
            formattedData = self.formatData(data)
            return formattedData


    # creates the URL for the Open Access Document API call
    # return string: full URL for querying the API
    def buildOpenAccessQuery(self):

        url = self.openAccessEndPoint;
        url += str(self.parameters['article_number']) + '/fulltext'
        url += '?apikey=' + str(self.apiKey)
        url += '&format=' + str(self.outputType)

        return url


    # creates the URL for the non-Open Access Document API call
    # return string: full URL for querying the API
    def buildQuery(self):

        url = self.endPoint;

        url += '?apikey=' + str(self.apiKey)
        url += '&format=' + str(self.outputType)
        url += '&max_records=' + str(self.resultSetMax)
        url += '&start_record=' + str(self.startRecord)
        url += '&sort_order=' + str(self.sortOrder)
        url += '&sort_field=' + str(self.sortField)

        # add in search criteria
        # article number query takes priority over all others
        if (self.usingArticleNumber):

            url += '&article_number=' + str(self.parameters['article_number'])

        # boolean query
        elif (self.usingBoolean):

             url += '&querytext=(' + urllib.quote_plus(self.parameters['boolean_text']) + ')'

        else:

            for key in self.parameters:

                if (self.usingFacet and self.facetApplied is False):

                    url += '&querytext=' + urllib.quote_plus(self.parameters[key]) + '&facet=' + key
                    self.facetApplied = True

                else:

                    url += '&' + key + '=' + urllib.quote_plus(self.parameters[key])


        # add in filters
        for key in self.filters:

            url += '&' + key + '=' + str(self.filters[key])
 
        return url


    # creates the URL for the API call
    # string url  Full URL to pass to API
    # return string: Results from API
    def queryAPI(self, url):

        content = urllib2.urlopen(url).read()
        return content


    # formats the data returned by the API
    # string data    Result string from API
    def formatData(self, data):

        if self.outputDataFormat == 'raw':
            return data

        elif self.outputDataFormat == 'object':
            
            if self.outputType == 'xml':
                obj = ET.ElementTree(ET.fromstring(data))
                return obj

            else:
                obj = json.loads(data) 
                return obj

        else:
            return data
