## Summary

## search

### DB search

Run a search on [aisel.aisnet.org](https://aisel.aisnet.org/).

Download the search results (advanced search, format:Bibliography Export, click Search) and store them in the `data/search/` directory.

```
colrev search --add colrev.ais_library
```

### API search

Copy the search link and add an API search (replacing the link):

```
colrev search --add colrev.ais_library -p "https://aisel.aisnet.org/do/search/?q=microsourcing&start=0&context=509156&facet="
```

Note: Complex queries can be entered in the basic search field. Example:

```
title:microsourcing AND ( digital OR online)
```

## Links

[AIS eLibrary](https://aisel.aisnet.org/)
