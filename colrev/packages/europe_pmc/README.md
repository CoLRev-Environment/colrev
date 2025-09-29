## Summary

Europe PMC is a comprehensive database that includes metadata from PubMed Central (PMC) and provides access to over 40 million records.

## search

### API search

```
colrev search --add colrev.europe_pmc -p "https://europepmc.org/search?query=fitbit%20AND%20gamification%20AND%20RCT%20AND%20diabetes%20mellitus"
```
Format of the search-history file (DB search):

```json
{
    "search_string": "TITLE:\"microsourcing\"",
    "platform": "colrev.europe_pmc",
    "search_results_path": "data/search/europe_pmc.bib",
    "search_type": "DB",
    "version": "0.1.0"
}
```

Format of the search-history file (API search):

```json
{
    "search_string": "",
    "platform": "colrev.europe_pmc",
    "search_results_path": "data/search/europe_pmc_api.bib",
    "search_type": "API",
    "search_parameters": {
        "query": "TITLE:%22microsourcing%22"
    },
    "version": "0.1.0"
}
```

## prep

EuropePMC linking

## Links

- [Europe PMC](https://europepmc.org/)
- License: [may contain copyrighted material, unless stated otherwise](https://europepmc.org/Copyright)
- [Field definitions](https://europepmc.org/docs/EBI_Europe_PMC_Web_Service_Reference.pdf)
