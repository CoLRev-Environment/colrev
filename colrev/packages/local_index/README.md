## Summary

This package creates an sqlite database based on local CoLRev packages, providing meta-data and PDFs to other local packages.

To create or update the index, run

```
colrev env -i
```

## search

### API search

```
colrev search --add colrev.local_index -p "title LIKE '%dark side%'"
```

## pdf-get

Retrieves PDF documents from other local CoLRev repositories, given that they are registered, and that the index is updated.

<!-- ## Links -->
