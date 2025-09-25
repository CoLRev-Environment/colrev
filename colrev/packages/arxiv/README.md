## Summary

## Add the search source

### API

ℹ️ Restriction: API searches do not support complex queries (yet)

```
colrev search --add colrev.arxiv -p "https://arxiv.org/search/?query=fitbit&searchtype=all&abstracts=show&order=-announced_date_first&size=50"
```

Format of the search-history file:

```json
{
    "search_string": "",
    "platform": "colrev.arxiv",
    "search_results_path": "data/search/arxiv.bib",
    "search_type": "API",
    "search_parameters": {
        "query": "microsourcing"
    },
    "version": "0.1.0"
}
```

## Links

- [arXiv](https://arxiv.org/)
