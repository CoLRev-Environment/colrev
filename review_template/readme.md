# Setup

The pipeline is implemented in a Docker-compose environment, ensuring cross-platform compatibility.

The analyses are mostly implemented in Python.
Git and make are available in the Docker container.

To open the cli-mode, run

```
make cli
```

# Pipeline management

The following overview explains each step of the review pipeline, providing information on the steps that are executed manually and the steps that are augmented or automated by scripts.

```
make initialize
```

- This procedure sets up the repository in the data directory.

To get information on the current progress of the review and to check whether the repository complies with the structure, execute

```
make status
```

TODO: currently only provides status information (validation and checks need to be implemented)

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

## Protocol

The review protocol is developed manually.

- Develop a review protocol and store it in the [readme](readme.md).
- State the goals and research questions
- Select an appropriate type of review (descriptive, narrative, scoping, critical, theoretical, qualitative systematic, meta-analysis, umbrella), considering the goal and the current state of research on the topic
- Methodological
  - Set the scope for the search
  - ...
- Team, ...
- Schedule, ...

TODO: include useful references

## Search

The search combines automated and manual steps as follows:

1. Execute search (manual task)
  - Retrieval of search results must be completed manually (e.g., database searches, table-of-content scans, citation searches, lists of papers shared by external researchers)
  - Each of these search processes is assumed to produce a BibTeX file. Other file formats must be converted to BibTeX. For .ris files, this works best with Endnote (import as endnote file, select BibTeX as the output style, mark all and export).
  - Search results are stored as `data/search/YYYY-MM-DD-search_id.bib`.
  - Details on the search are stored in the [search_details.csv](search/search_details.csv).

2. Combine files containing individual search results (script)

```
make combine_individual_search_results
```

- This procedure creates a hash_id for each entry and adds all entries with a unique hash_id to the [references.bib](references.bib).
This means that duplicate entries with an identical hash_id (based on titles, authors, journal, ...) are merged automatically (which is particularly important when running `make combine_individual_search_results` in incremental mode).

3. Cleanse records (script)

```
make cleanse_records
```

- Improves the quality of entries stored in `references.bib`.
If an entry has been cleansed, its hash_id is stored in the `search/bib_details.csv` to avoid re-cleansing (and potentially overriding manual edits).
Please note that this can take some time (depending on the number of records) since it calls the [Crossref API](https://www.crossref.org/education/retrieve-metadata/rest-api/) to retrieve DOIs and the [DOI resolution service](https://www.doi.org/) to retrieve corresponding meta-data.
For 1,000 records, this might take approx. 1:30 hours.


4. Identify and process duplicates (partly automated, partly manual task)

```
make process_duplicates
```

- Creates a similarity matrix for all entries
- Process potential duplicate entries based on a threshold first (e.g., similarity = 0.99)
- Iterates over the remaining candidates (e.g., 0.8 < similarity < 0.99) and asks the user to classify as duplicate/non-duplicate
- When merging entries, it checks whether either of the *citation_keys* has been propagated. If the *citation_keys* of both entries have been propagated, it prints a warning and does not merge the entry. Otherwise, non-propagated *citation_keys* are removed when entries are merged.
- Creates commits after the automated and manual processing of duplicates
- It is recommended to check both commits for potential errors.


5. Check/update citation_keys (manual task)

- update citation_keys for records that did not have author or year fields
- compare citation_keys with other local/shared bibliographies to avoid citation_key conflicts (TODO: develop scripts to support this step)

- Please note that after this step, the citation_keys will be propagated to the screen.csv and data.csv, i.e., they should not be changed afterwards.

When updating the search, follow the same procedures as described above. Note that `make search` will only add new records to the references.bib and `cleanse_records` will only be executed for new records.


6. Backward search: after completing the first iteration of the search (requires first pipeline iteration to be completed

- i.e., screen.csv/inclusion_2 must have included papers and PDF available.

```
make backward_search

```
- The procedure transforms all PDFs linked to included papers (inclusion_2 = yes) to tei files, extracts the reference sections and transforms them to BibTeX files.

## Inclusion screen

1. Create screening sheet (script)

```
make screen_sheet
```
- This procedure asks for exclusion criteria and adds the search records to the [screening sheet](screen.csv).

2. Complete screen 1 (manual task, supported by a script)

```
make screen_1
```
- This procedure iterates over all records and records inclusion decisions for screen 1 in the [screening sheet](screen.csv).

The following steps apply only to records retained after screen 1 (coded as inclusion_1 == yes).

4. Check bibliographical meta-data of included records (manual task)

- Manually check the completeness and correctness of bibliographic data
- TBD: how to do that efficiently?? (create keyword=included in the bibfile?)

5. PDF acquisition etc. (manual task)

```
make acquire_pdfs
```

- TODO: The script acquires PDFs for the full-text eligibility assessment in screen 2.
- It queries the unpaywall api.
- If there are unliked files in the `pdfs` directory, it links them
- It creates a csv file (`missing_pdf_files.csv`) listing all PDFs that need to be retrieved manually.

- Manual PDF acquisition: acquire PDF and rename PDFs as `citation_key.pdf`, move to `dat/pdfs` directory. Rerun the `acquire_pdfs` script to link the pdfs into the `references.bib`.

- Check whether PDFs can be opened from Jabref. This might require you to set the Library > Library properties > General file directory to the `pdfs` directory, which is stored in the `references.bib` as follows:

```
@Comment{jabref-meta: fileDirectory-username-username-computer:/home/username/path-to-/review_template;}
```

- PDF file links should take the form `file = {:pdfs/citation_key.pdf:PDF}`


6. PDF validation (manual task)

TODO: include the script
- Compare paper meta-data with bibtex entry to make sure it is accurate and complete (including pages etc.).

7. Complete screen 2 (manual task, supported by a script)

```
make screen_2
```
- This procedure iterates over all records, prompts the user for each exclusion criterion (if exclusion criteria are available), and records inclusion decisions for screen 2 in the [screen.csv](screen.csv).


When updating the search, follow the same procedures as described above. Note that `make screen_sheet` will add additional search results to the [screening sheet](screen.csv). If records in the screening sheet are no longer in the references.bib (possibly because citation_keys have been modified in the references.bib), `make screen_sheet` will print a warning (but still retain the record in the screening sheet).

## Data extraction

1. Generate sample profile (script)

TODO: scripts in analysis/R
descriptive statistics of paper meta-data


2. Create data extraction sheet (script)

```
make data
```
- This procedure adds records of included papers to the [data extraction sheet](data.csv).

3. Complete data extraction (manual task)

TODO: include description of the step

When updating the data extraction, follow the same procedures as described above. Note that `make data` will add additional included records to the [data sheet](data.csv). If records in the data sheet are no longer in the screening sheet, `make data` will print a warning (but still retain the record in the data sheet).

## Synthesis, reporting, and dissemination

The [paper](paper.md) is written in markdown following the contributing guidelines in the [paper-template](https://github.com/geritwagner/paper-template/blob/main/CONTRIBUTING.md).


# Compatibility of complementary software

- JabRef (hash-id compatible)

This is a modified version of JabRef that preserves hash-ids when merging records.

```
git clone --depth=10 https://github.com/geritwagner/jabref.git
cd jabref
./gradlew assemble
./gradlew run

```

Based on [JabRef instructions](https://devdocs.jabref.org/getting-into-the-code/guidelines-for-setting-up-a-local-workspace).

- LibreOffice to modify csv files manually:

Set the following default parameters for CSV files (or manually select them everytime when opening/importing and saving a csv file through the "edit filter settings" dialogue) via Tools > Options > LibreOffice > advanced > Open Expert Configuration:

- CSVExport/TextSeparator: "
- CSVExport/FieldSeparator: ,
- CSVExport/QuoteAllTextCells: true
- CSVImport/QuotedFieldAsText: true
