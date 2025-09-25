## Summary

## search

### API search

ℹ️ Restriction: API searches do not support complex queries (yet)

```
colrev search --add colrev.open_alex -p "..."
```

Format of the search-history file (metadata search):

```json
{
    "search_string": "",
    "platform": "colrev.open_alex",
    "search_results_path": "data/search/md_open_alex.bib",
    "search_type": "MD",
    "version": "0.1.0"
}
```

## prep

Links meta data from OpenAlex to existing records.

## Debugging

To test the metadata provided for a particular `open_alex_id` use:
```
https://api.openalex.org/works/OPEN_ALEX_ID
```

## Links

- [OpenAlex](https://openalex.org/)
- [License](https://docs.openalex.org/additional-help/faq#how-is-openalex-licensed)
