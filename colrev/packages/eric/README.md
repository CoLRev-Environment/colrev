## Summary

## search

### DB search

Download search results and store in `data/search/` directory.

### API search

ℹ️ Restriction: API searches do not support complex queries (yet)

A search on the ERIC API can be performed as follows:

```
colrev search --add colrev.eric -p "https://api.ies.ed.gov/eric/?search=blockchain"
```
This command searches the core fields title, author, source, subject, and description of the entered search string (here: blockchain). The data is always returned in json format (xml and csv are not yet supported).

A field search can also be used if only a search for a string in a specific field is wanted:

```
colrev search --add colrev.eric -p "https://api.ies.ed.gov/eric/?search=author: Creamer, Don"
```

This command returns all records by author Don Creamer.

If several strings are to be searched for in different fields, the AND operator can be used:

```
colrev search --add colrev.eric -p "https://api.ies.ed.gov/eric/?search=author:Creamer, Don AND title: Alternative"
```
This command returns all records by author Don Creamer that have the string "Alternative" in the title.

In addition, the start parameter the starting record number for the returned results set can be determined and the rows parameter can be used to determine how many records are to be returned (by default start hat the value 0 and rows the value 2000):

```
colrev search --add colrev.eric -p "https://api.ies.ed.gov/eric/?search=blockchain&start=0&rows=5"
```

This command returns 5 records with starting record number 0.

Format of the search-history file (DB search):

```json
{
    "search_string": "descriptor:distance education",
    "platform": "colrev.eric",
    "search_results_path": "data/search/eric.bib",
    "search_type": "DB",
    "version": "0.1.0"
}
```

Format of the search-history file (API search):

```json
{
    "search_string": "",
    "platform": "colrev.eric",
    "search_results_path": "data/search/eric_api.bib",
    "search_type": "API",
    "search_parameters": {
        "query": "fitbit",
    },
    "version": "0.1.0"
}
```

## Links

- [ERIC](https://eric.ed.gov/)
- [ERIC API](https://eric.ed.gov/?api)
