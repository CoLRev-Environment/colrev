# SearchSource: PDF Backward Search

Note: This document is currently under development. It will contain the following elements.

- description
- coverage (disciplines, types of work)
- supported (details): search updates, get_masterdata, run_search, load_fixes, prep

One strategy could be to start with a relatively high threshold for the number of intext citations and to iteratively decrease it, and update the search:
colrev search -a colrev.pdf_backward_search:min_intext_citations=2

Citation data is automatically consolidated with open-citations data to improve data quality.

based on [GROBID](https://github.com/kermitt2/grobid)

## Add the search source

```
colrev search -a colrev.pdf_backward_search:default
colrev search -a colrev.pdf_backward_search:min_intext_citations=2
```

## Links
