
The pipeline implemented in this repository relies on a consistent structure of files and data.
To ensure that the repository complies with this structure and to get information on the current progress of the review, execute
```
make status
```

# Search

- Execute search and save results as `data/search/YYYY-MM-DD-search_id.bib`.
- Convert search results to BibTeX if necessary.
  - For .ris files, this works best with Endnote (import as endnote file, select BibTeX as the output style, mark all and export).
- Provide details on the search in the [search_details.csv](search/search_details.csv).
- Run search.py, which combines all search results and adds a hash_id to each entry
```
make search
```
- Run cleanse_records, which improves the quality of the records. Please note that this can take some time (depending on the number of records) since it calls the [Crossref API](https://www.crossref.org/education/retrieve-metadata/rest-api/) to retrieve DOIs and the [DOI resolution service](doi.org). For 1,000 records, this might take approx. XXXX hours.
```
make cleanse_records
```

- Manually check and remove duplicates using the hash-id compatible version of JabRef. To maintain the trace from the original search records to the merged record, it is important to add the hash_ids to the merged entry (this is done automatically in the hash-id compatible version of JabRef).
- Generate citation keys for the entries in JabRef (do not change existing ones). Please note that these citation_keys will be propagated to the screen.csv and data.csv (and should not be changed afterwards)

# Inclusion screen

- Run screen.py, which adds new search records to the [screening sheet](data/screen.csv):
```
make screen
```

- Record screening decision: [inclusion.csv](data/inclusion.csv), coding Inclusion_1 as 'yes' or 'no'
- In a paper is considered for inclusion (inclusion_1 == yes):
  - Completeness of bibliographic data
  - Acquire PDF for full-text eligibility assessment
- Record screening decision: [inclusion.csv](data/inclusion.csv), coding Inclusion_2 as 'yes' or 'no'

# Data extraction

- Run data.py, which adds records of included papers to the [data extraction sheet](data/data.csv):
```
make data
```

# Synthesis, reporting, and dissemination



TO INTEGRATE:





- todo

# Eligibility assessment based on full-texts

- Record screening decision: [inclusion.csv](inclusion.csv), column Inclusion_2
- If it is excluded:
  - save pdf in the 1-raw-rata/excluded directory
  - create a link in the bibtex entry
- If it is included:
  - save pdf in the data/paper directory
  - create a link in the bibtex entry
  - compare paper meta-data with bibtex entry to make sure it is accurate and complete (including pages etc.). Note: this could be (partially) automated.
  - copy bibtex entry to bibliography (using a crossref link for conference papers, deleting the file-link)
  - Execute backward search for the paper
  - add bibtex entry to the sample (Appendix)

# Data extraction

[data.csv](data.csv), column Extraction


code book...
