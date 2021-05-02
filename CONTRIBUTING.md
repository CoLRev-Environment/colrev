
The pipeline implemented in this repository relies on a consistent structure of files and data.
To ensure that the repository complies with this structure and to get information on the current progress of the review, execute
```
make status
```

ouput:
```
Status

 ┌ Search
 |  - total retrieved:    1285
 |  - merged:             1000
 |
 ├ Screen 1
 |  - total:               995
 |  - included:              1
 |  - excluded:              1
 |  - TODO:                993
 |
 ├ Screen 2
 |  - total:               994
 |  - included:              0
 |  - excluded:              0
 |  - TODO:                994
 |
 ┌ Data
 |  - Not yet initiated

```

# Search

1. Execute search
  - Retrieval of search results must be completed manually (e.g., database searches, table-of-content scans, citation searches, lists of papers shared by external researchers)
  - Each of these search processes is assumed to produce a BibTeX file. Other file formats must be converted to BibTeX. For .ris files, this works best with Endnote (import as endnote file, select BibTeX as the output style, mark all and export).
  - Search results are stored as `data/search/YYYY-MM-DD-search_id.bib`.
  - Details on the search are stored in the [search_details.csv](search/search_details.csv).

2. Combine files containing individual search results

```
make combine_individual_search_results
```

- This procedure combines all search results in the [references.bib](data/references.bib)and adds a hash_id to each entry.

3. Cleanse records

```
make cleanse_records
```

- Improves the quality of the records. Please note that this can take some time (depending on the number of records) since it calls the [Crossref API](https://www.crossref.org/education/retrieve-metadata/rest-api/) to retrieve DOIs and the [DOI resolution service](https://www.doi.org/) to retrieve corresponding meta-data. For 1,000 records, this might take approx. 1:30 hours.

4. Complete fields necessary for merging

```
pre_merging_quality_check
```
- Prints all records lacking the title, author, or year field (minimum requirement for duplicate removal).
- Manually add missing fields

5. Identify and merge duplicates


- Manually check and remove duplicates using the hash-id compatible version of JabRef. To maintain the trace from the original search records to the merged record, it is important to add the hash_ids to the merged entry (this is done automatically in the hash-id compatible version of JabRef).

6. Check/update citation_keys

- update citation_keys for records that did not have author or year fields
- compare citation_keys with other local/shared bibliographies to avoid citation_key conflicts (TODO: develop scripts to support this step)

- Please note that after this step, the citation_keys will be propagated to the screen.csv and data.csv, i.e., they should not be changed afterwards.

When updating the search, follow the same procedures as described above. Note that `make search` will only add new records to the references.bib and `cleanse_records` will only be executed for new records.

# Inclusion screen

1. Create screening sheet

```
make screen_sheet
```
- This procedure asks for exclusion criteria and adds the search records to the [screening sheet](data/screen.csv).

2. Complete screen 1

```
make screen_1
```
- This procedure iterates over all records and records inclusion decisions for screen 1 in the [inclusion.csv](data/inclusion.csv).

The following steps apply only to records retained after screen 1 (coded as inclusion_1 == yes).

4. Check bibliographical meta-data of included records

- Manually check the completeness and correctness of bibliographic data
- TBD: how to do that efficiently?? (create keyword=included in the bibfile?)

5. PDF acquisition etc.

TODO
- Acquire PDF for full-text eligibility assessment (store in data/pdfs and link in references.bib)

4. PDF validation

TODO
- Compare paper meta-data with bibtex entry to make sure it is accurate and complete (including pages etc.).

5. Complete screen 2

```
make screen_2
```
- This procedure iterates over all records, prompts the user for each exclusion criterion (if exclusion criteria are available), and records inclusion decisions for screen 2 in the [inclusion.csv](data/inclusion.csv).


When updating the search, follow the same procedures as described above. Note that `make screen_sheet` will add additional search results to the [screening sheet](data/screen.csv). If records in the screening sheet are no longer in the references.bib (possibly because citation_keys have been modified in the references.bib), `make screen_sheet` will print a warning (but still retain the record in the screening sheet).

# Data extraction

1. Create data extraction sheet

```
make data
```
- This procedure adds records of included papers to the [data extraction sheet](data/data.csv).

When updating the data extraction, follow the same procedures as described above. Note that `make data` will add additional included records to the [data sheet](data/data.csv). If records in the data sheet are no longer in the screening sheet, `make data` will print a warning (but still retain the record in the data sheet).

# Synthesis, reporting, and dissemination

TODO
