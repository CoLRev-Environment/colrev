# SearchSource: PDF Backward Search

Note: This document is currently under development. It will contain the following elements.

- description
- coverage (disciplines, types of work)
- supported (details): run_search (including updates), load,  prep (including get_masterdata)

One strategy could be to start with a relatively high threshold for the number of intext citations and to iteratively decrease it, and update the search:
colrev search -a colrev.pdf_backward_search:min_intext_citations=2

Citation data is automatically consolidated with open-citations data to improve data quality.

based on [GROBID](https://github.com/kermitt2/grobid)

## Add the search source

```
colrev search -a colrev.pdf_backward_search:default
colrev search -a colrev.pdf_backward_search:min_intext_citations=2
```

## Conducting a selective backward search

A selective backward search for a single paper and selected references can be conducted by running
```
colrev search -bws record_id
```
References can be selected interactively for import.

## Links
