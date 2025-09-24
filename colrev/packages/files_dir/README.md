## Summary

## search

### FILES  search

```
colrev search --add colrev.files_dir
```

- PDF metadata extracted based on PDF hashes and the local_index (clone curations and run `colrev env --index`).
- PDF metadata extracted based on [GROBID](https://github.com/kermitt2/grobid)


For metadata curations, i.e., repositories containing all PDFs organized in directories for volumes/issues, it is possible to set the `scope` parameter in the `settings.json`, ensuring that the journal name, entrytype, and volume/issue is set automatically.

```json
{
    "platform": "colrev.files_dir",
    "search_results_path": "data/search/pdfs.bib",
    "search_type": "FILES",
    "search_string": "",
    "search_parameters": {
        "scope": {
            "subdir_pattern": "volume_number",
            "type": "journal",
            "journal": "MIS Quarterly",
            "path": "data/pdfs"
        },
    },
    "version": "0.1.0"
}
```

<!-- ## Links -->
