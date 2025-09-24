## Summary

PubMed is a free search engine that provides access to a vast collection of biomedical literature. It allows users to search for articles, abstracts, and citations from various sources, including scientific journals and research papers. PubMed is widely used by researchers, healthcare professionals, and students to find relevant information in the field of medicine and life sciences.

## search

### API search

ℹ️ Restriction: API searches do not support complex queries (yet)

To add a pubmed API search, enter the query in the [Pubmed web interface](https://pubmed.ncbi.nlm.nih.gov/), run the search, copy the url and run:

```
colrev search --add colrev.pubmed -p "https://pubmed.ncbi.nlm.nih.gov/?term=fitbit"
```

Format of the search-history file:

```json
{
  "search_string": "",
  "platform": "colrev.pubmed",
  "search_results_path": "data/search/pubmed.bib",
  "search_type": "API",
  "search_parameters": {
    "url": "https://pubmed.ncbi.nlm.nih.gov/?term=fitbit",
  },
  "version": "0.1.0"
}
```

## prep

PubMed linking

## Links

- [Data field descriptions](https://www.nlm.nih.gov/bsd/mms/medlineelements.html)
- [Pubmed](https://pubmed.ncbi.nlm.nih.gov/)
