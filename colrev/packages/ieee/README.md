## Summary

## search

### DB search

csv export is preferred because the other formats (bib/ris) do not export the url (which includes the accession number). The accession number is important for search updates.

### API search

ℹ️ Restriction: API searches do not support complex queries (yet)

Download search results and store in `data/search/` directory.

Data from the IEEE database can be retrieved with the URL from the [https://www.ieee.org/](https://ieeexploreapi.ieee.org/api/v1/search/articles?parameter&apikey=). Add the URL as follows:

```
colrev search --add colrev.ieee -p "https://ieeexploreapi.ieee.org/api/v1/search/articles?parameter=microsourcing"
```

All configured metadata fields, the abstract and the document text are queried.

It is not necessary to pass an API key as a parameter here. In order to keep the key secret, you will be prompted to enter it through user input if it is not already stored in the settings. The api key can be requested via the [IEEE Xplore API Portal](https://developer.ieee.org/member/register).

Specific parameters can also be searched for, such as issn, isbn, doi, article_number, author, publication_year. For each of these, append "parameter=value" to the URL.

```
colrev search --add colrev.ieee -p "https://ieeexploreapi.ieee.org/api/v1/search/articles?issn=1063-6919"
```

Multiple parameters can be concatenated using the "&" symbol.

```
colrev search --add colrev.ieee -p "https://ieeexploreapi.ieee.org/api/v1/search/articles?publication_year=2019&abstract=microsourcing"
```

If your search query includes Boolean operators, add "queryText=query" to the URL.

```
colrev search --add colrev.ieee -p "https://ieeexploreapi.ieee.org/api/v1/search/articles?booleanText=(rfid%20AND%20%22internet%20of%20things%22)"
```

Format of the search-history file (DB search):

```json
{
    "search_string": "microsourcing",
    "platform": "colrev.ieee",
    "search_results_path": "data/search/ieee.bib",
    "search_type": "DB",
    "version": "0.1.0"
}
```

Format of the search-history file (API search):

```json
{
    "search_string": "",
    "platform": "colrev.ieee",
    "search_results_path": "data/search/ieee_api.bib",
    "search_type": "API",
    "search_parameters": {
        "query": "microsourcing",
    },
    "version": "0.1.0"
}
```

## Links

- [IEEEXplore](https://ieeexplore.ieee.org/)
