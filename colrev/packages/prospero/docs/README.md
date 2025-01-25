## Summary

[PROSPERO](https://www.crd.york.ac.uk/prospero/#searchadvanced) is an international database of prospectively registered systematic reviews in health and social care, welfare, public health, education, crime, justice, and international development, where there is a health related outcome.

### Installation

```bash
colrev install colrev.prospero
```

### search

Download the search results and store them in the data/search/ directory.
```
colrev search --add colrev.prospero
```
The search is done using keywords that can be entered into the console.

### load
It is possible to save the records after search. All records that were found during the search will be saved to a data/records.bib file. Load function will add the records to the file or update existing one.

```
colrev load
```
## Links

- [PROSPERO](https://www.crd.york.ac.uk/prospero/)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
