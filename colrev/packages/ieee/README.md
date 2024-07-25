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

## Links

- [IEEEXplore](https://ieeexplore.ieee.org/)
