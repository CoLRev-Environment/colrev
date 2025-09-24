## Summary

The table shows the search sources available in the dblp package. The main source is dblp.org, which provides curated metadata for computer science and information technology. The size of the database is over 5,750,000 entries.

## search

### API search

ℹ️ Restriction: API searches do not support complex queries (yet)

Run a search on dblp.org and paste the url in the following command:

```
colrev search --add colrev.dblp -p "https://dblp.org/search?q=microsourcing"
```

Format of the search-history file:

```json
{
    "search_string": "",
    "platform": "colrev.dblp",
    "search_results_path": "data/search/dblp.bib",
    "search_type": "API",
    "search_parameters": {
        "query": "https://dblp.org/search/publ/api?q=microsourcing",
    },
    "version": "0.1.0"
}
```

### TOC search

TODO

Format of the search-history file:

```json
{
    "platform": "colrev.dblp",
    "search_results_path": "data/search/DBLP.bib",
    "search_type": "TOC",
    "search_string": "",
    "search_parameters": {
        "scope": {
            "venue_key": "journals/misq",
            "journal_abbreviated": "MIS Q."
        },
    },
    "version": "0.1.0"
}
```

## prep

linking metadata

## Links

- License: [Open Data Commons ODC-BY 1.0 license](https://dblp.org/db/about/copyright.html)
- [DBLP](https://dblp.org/)
