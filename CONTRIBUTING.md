
The pipeline implemented in this repository relies on a consistent structure of files and data.
To ensure that the repository complies with this structure and to get information on the current progress of the review, execute
```
make status
```

# Search

- Execute search
  - Save results as `data/search/YYYY-MM-DD-search_id.bib`.
  - Convert search results to BibTeX if necessary. For .ris files, this works best with Endnote (import as endnote file, select BibTeX as the output style, mark all and export).
- Provide details on the search in the [search_details.csv](search/search_details.csv).
- Run search.py, which combines all search results and adds a hash_id to each entry
```
make search
```
- Run cleanse_records, which improves the quality of the records. Please note that this can take some time (depending on the number of records) since it calls the [Crossref API](https://www.crossref.org/education/retrieve-metadata/rest-api/) to retrieve DOIs and the [DOI resolution service](doi.org). For 1,000 records, this might take approx. 1:30 hours.
```
make cleanse_records
```

- Manually check and remove duplicates using the hash-id compatible version of JabRef. To maintain the trace from the original search records to the merged record, it is important to add the hash_ids to the merged entry (this is done automatically in the hash-id compatible version of JabRef).
- Generate citation keys for the entries in JabRef (do not change existing ones). Please note that these citation_keys will be propagated to the screen.csv and data.csv (and should not be changed afterwards)

When updating the search, follow the same procedures as described above. Note that `make search` will only add new records to the references.bib and `cleanse_records` will only be executed for new records.

# Inclusion screen

- Run screen.py, which adds the search records to the [screening sheet](data/screen.csv):
```
make screen
```

- Record screening decision: [inclusion.csv](data/inclusion.csv), coding Inclusion_1 as 'yes' or 'no'
- In a paper is considered for inclusion (inclusion_1 == yes):
  - Completeness of bibliographic data
  - Acquire PDF for full-text eligibility assessment (store in data/pdfs and link in references.bib)
  - Compare paper meta-data with bibtex entry to make sure it is accurate and complete (including pages etc.).
- Record screening decision: [inclusion.csv](data/inclusion.csv)
  - Coding Inclusion_2 as 'yes' or 'no'
  - Coding exclusion criteria

When updating the search, follow the same procedures as described above. Note that `make screen` will add additional search results to the [screening sheet](data/screen.csv). If records in the screening sheet are no longer in the references.bib (possibly because citation_keys have been modified in the references.bib), `make screen` will print a warning (but still retain the record in the screening sheet).

# Data extraction

- Run data.py, which adds records of included papers to the [data extraction sheet](data/data.csv):
```
make data
```

When updating the data extraction, follow the same procedures as described above. Note that `make data` will add additional included records to the [data sheet](data/data.csv). If records in the data sheet are no longer in the screening sheet, `make data` will print a warning (but still retain the record in the data sheet).

# Synthesis, reporting, and dissemination

TODO
