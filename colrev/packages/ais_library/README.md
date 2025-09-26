## Summary

## search

**Limitation**: The AIS eLibrary currently limits search results an 3.000 records (for DB and API searches).

### DB search

Run a search on [aisel.aisnet.org](https://aisel.aisnet.org/).

Download the search results (advanced search, format:Bibliography Export, click Search) and store them in the `data/search/` directory.

```
colrev search --add colrev.ais_library
```

### API search

Copy the search link and add an API search (replacing the link):

```
colrev search --add colrev.ais_library -p "https://aisel.aisnet.org/do/search/?q=microsourcing&start=0&context=509156&facet="
```

Note: Complex queries can be entered in the basic search field. Example:

```
title:microsourcing AND ( digital OR online)
```

Format of the search-history file (DB search):

```json
{
    "search_string": "title:microsourcing",
    "platform": "colrev.ais_library",
    "search_results_path": "data/search/ais_library.bib",
    "search_type": "DB",
    "version": "0.1.0"
}
```

Format of the search-history file (API search):

```json
{
    "search_string": "",
    "platform": "colrev.ais_library",
    "search_results_path": "data/search/ais_library_api.bib",
    "search_type": "API",
    "search_parameters": {
        "query": "microsourcing",
    },
    "version": "0.1.0"
}
```

## Links

[AIS eLibrary](https://aisel.aisnet.org/)
