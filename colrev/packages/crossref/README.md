# Crossref

| SearchSource                                                             | Scope              | Size          |
|--------------------------------------------------------------------------|--------------------|---------------|
| [Crossref](https://www.crossref.org/) (metadata deposited by publishers) | Cross-disciplinary | > 125,000,000 |

## search

### API search

It is possible to copy the url from the [search.crossref.org](https://search.crossref.org/?q=microsourcing&from_ui=yes) UI and add it as follows:

```
colrev search --add colrev.crossref -p "query=microsourcing"
colrev search --add colrev.crossref -p "https://search.crossref.org/?q=+microsourcing&from_ui=yes"
```

<!--
TODO:
colrev search --add colrev.crossref -p "query=microsourcing;years=2000-2010"
-->

### TOC search

Whole journals can be added based on their issn:
```
colrev search --add colrev.crossref -p "issn=2162-9730"
```

## prep

Crossref linking

Note: This document is currently under development. It will contain the following elements.

- description
- example

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
