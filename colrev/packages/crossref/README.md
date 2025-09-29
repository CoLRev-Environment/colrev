## Summary

[Crossref](https://www.crossref.org/) is a SearchSource that contains metadata deposited by publishers. It is cross-disciplinary and has a size of over 125,000,000 records.

## search

### API search

ℹ️ Restriction: API searches do not support complex queries (yet)

It is possible to copy the url from the [search.crossref.org](https://search.crossref.org/?q=microsourcing&from_ui=yes) UI and add it as follows:

```
colrev search --add colrev.crossref -p "query=microsourcing"
colrev search --add colrev.crossref -p "https://search.crossref.org/?q=+microsourcing&from_ui=yes"
```

<!--
TODO:
colrev search --add colrev.crossref -p "query=microsourcing;years=2000-2010"
-->

Format of the search-history file:

```json
{
    "search_string": "",
    "platform": "colrev.crossref",
    "search_results_path": "data/search/crossref.bib",
    "search_type": "API",
    "search_parameters": {
        "url": "https://api.crossref.org/works?query.bibliographic=microsourcing",
    },
    "version": "0.1.0"
}
```

### TOC search

Whole journals can be added based on their issn:
```
colrev search --add colrev.crossref -p "issn=2162-9730"
```

Format of the search-history file:

```json
{
    "search_string": "",
    "platform": "colrev.crossref",
    "search_results_path": "data/search/CROSSREF.bib",
    "search_type": "TOC",
    "search_parameters": {
        "url": "https://api.crossref.org/journals/0276-7783/works",
    },
    "version": "0.1.0"
}
```

## prep

Crossref generally offers high-quality meta data, making it an effective source to link and update existing records.

## Debugging

To test the metadata provided for a particular `DOI` use:
```
https://api.crossref.org/works/DOI
```

## Links

- [Crossref](https://www.crossref.org/)
- [License](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-metadata-license-information/)
- [Crossref types](https://api.crossref.org/types)
- [Issue: AND Operators not yet supported](https://github.com/fabiobatalha/crossrefapi/issues/20)
