# SearchSource: Crossref

<!--
Note: This document is currently under development. It will contain the following elements.

- description
- coverage (disciplines, types of work)
- supported (details): run_search (including updates), load,  prep (including get_masterdata)
-->

[Crossref](https://www.crossref.org/)

[License](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-metadata-license-information/)

## Add the search source

It is possible to copy the url from the [search.crossref.org](https://search.crossref.org/?q=microsourcing&from_ui=yes) UI and add it as follows:

```
colrev search -a colrev.crossref:"https://search.crossref.org/?q=+microsourcing&from_ui=yes"
```

Whole journals can be added based on their issn:
```
colrev search -a colrev.crossref:"issn=1234-5678"
```

To test the metadata provided for a particular `open_alex_id` use:
```
https://api.crossref.org/works/DOI
```

## Links
