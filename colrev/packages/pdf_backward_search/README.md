## Summary

## search

### BACKWARD_SEARCH

One strategy could be to start with a relatively high threshold for the number of intext citations and to iteratively decrease it, and update the search:
colrev search --add colrev.pdf_backward_search:min_intext_citations=2

Citation data is automatically consolidated with open-citations data to improve data quality.

based on [GROBID](https://github.com/kermitt2/grobid)

```
colrev search --add colrev.pdf_backward_search
colrev search --add colrev.pdf_backward_search -p min_intext_citations=2
```

**Conducting selective backward searches**

A selective backward search for a single paper and selected references can be conducted by running
```
colrev search -bws record_id
```
References can be selected interactively for import.

<!-- ## Links -->
