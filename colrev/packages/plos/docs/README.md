## Summary

PLOS is a SearchSource providing open access metadata for articles published in PLOS journals. It focuses on life sciences and health but includes articles in other disciplines. Its database contains metadata for thousands of articles across multiple PLOS journals.

## Installation

```bash
colrev install colrev.plos
```

## Usage

### API search
To make an API search, first introduce the next command:

```
colrev search -a colrev.plos
```
On the menu displayed, select the option API:

```
2024-12-20 16:22:31 [INFO] Add search package: colrev.plos
[?] Select SearchType::
 > API
   TOC
```

Finally introduce a keyword to search:
```
Add colrev.plos as an API SearchSource

Enter the keywords:
```


### Load

```
colrev load
```

## Debugging

In order to test the metada provided for a specific `DOI` it can be used the following link:

```
https://api.plos.org/search?q=DOI:
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Links

- [PLOS API](https://api.plos.org)
- [Sorl Search Fileds and Article types](https://api.plos.org/solr/search-fields/)
