# SearchSource: AIS electronic Library

Note: This document is currently under development. It will contain the following elements.

- description
- coverage (disciplines, types of work)
- supported (details): search updates, get_masterdata, run_search, load_fixes, prep

[AIS eLibrary](https://aisel.aisnet.org/)

## Add the search source

Run a search on [aisel.aisnet.org](https://aisel.aisnet.org/).

Option 1: download the search results (advanced search, format:Bibliography Export, click Search) and store them in the `data/search/` directory.

Option 2: copy the search link and add an API search (replacing the link):

```
colrev search -a colrev.ais_library:"https://aisel.aisnet.org/do/search/?q=microsourcing&start=0&context=509156&facet="
```

## Links
