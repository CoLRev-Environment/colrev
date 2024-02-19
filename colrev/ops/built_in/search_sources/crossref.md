# Crossref

## search

### API search

It is possible to copy the url from the [search.crossref.org](https://search.crossref.org/?q=microsourcing&from_ui=yes) UI and add it as follows:

```
colrev search -a colrev.crossref -p "query=microsourcing;years=2000-2010"
colrev search -a colrev.crossref -p "https://search.crossref.org/?q=+microsourcing&from_ui=yes"
```

### TOC search

Whole journals can be added based on their issn:
```
colrev search -a colrev.crossref -p "issn=1234-5678"
```

## prep

Crossref linking

Note: This document is currently under development. It will contain the following elements.

- description
- example

## Links

- [Crossref](https://www.crossref.org/)
- [License](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-metadata-license-information/)
- [Crossref types](https://api.crossref.org/types)
- [Issue: AND Operators not yet supported](https://github.com/fabiobatalha/crossrefapi/issues/20)

To test the metadata provided for a particular `DOI` use:
```
https://api.crossref.org/works/DOI
```
