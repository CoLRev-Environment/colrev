# Instructions

Instructions for setting up the environment and applications for the pipeline are available in the [setup](SETUP.md).

Principles of the review pipeline

- The pipeline propagates search results from the individual search outputs (`data/search/YYYY-MM-DD-search_id.bib`) to the `data/references.bib` to the `data/screen.csv` to the `data/data.csv`.
To reset the analyses, each of these files can be deleted.
- The pipeline relies on the principle of *incremental propagation of changes*. When updating data at any stage in the pipeline and rerunning the scripts,  
  - existing records in the subsequent files will not be changed
  - additional records will be processed and added to the subsequent file
  - if records have been removed, scripts will create a warning but not remove them from the subsequent file (to avoid accidental losses of data)
- The pipeline relies on a consistent structure of files and data. Do not change directories, filenames, or file structures unless suggested in the following.
- The pipeline relies on the **principle of transparent and minimal history changes** in git.

  - Transparent means that plain text files must be used (i.e., BibTeX and CSV); proprietary file formats (in particular Excel files) should be avoided.
  - Minimal means that the version history should reflect changes in content and should not be obscured by meaningless changes in format (e.g., ordering of records, fields, or changes in handling of fields).
  This is particularly critical since there is no inherent order in BibTeX or CSV files storing the data of the literature review.
  Applications may easily introduce changes that make it hard to identify the content that has changed in a commit.
  - In the pipeline, this challenge is addressed by enforcing reasonable formatting and ordering defaults in the BibTex and CSV files.
  - When editing files with external applications or manually, a general recommendation is to save the file after a few changes and check the changes via `git status`.
  If it shows few changes, continue editing the files and check the `git status` before creating a commit.
  If git identifies changes in the whole file, check whether the formatting can be adjusted in the application (e.g., setting quoting defaults in LibreOffice or sort order in Jabref).
  It is always possible to `git restore ...` the file and start over.

To ensure that the repository complies with this structure and to get information on the current progress of the review, execute
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

The following overview explains each step of the review pipeline, providing information on the steps that are executed manually and the steps that are augmented or automated by scripts.

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

- This procedure combines all search results in the [references.bib](data/references.bib), adds a hash_id to each entry.

3. Cleanse records (script)

```
make cleanse_records
```

- Improves the quality for all records not yet included in the `data/search/bib_details.csv`.
Please note that this can take some time (depending on the number of records) since it calls the [Crossref API](https://www.crossref.org/education/retrieve-metadata/rest-api/) to retrieve DOIs and the [DOI resolution service](https://www.doi.org/) to retrieve corresponding meta-data.
For 1,000 records, this might take approx. 1:30 hours.

4. Complete fields necessary for merging (manual task, supported by a script)

```
make pre_merging_quality_check
```
- Estimates the degree of incompleteness (missing fields per record) and probability of duplication and saves results in `data/references_pre_screen_quality_check.csv`.
- Check the first entries (sorted in descending order of completeness and probability of duplication) and manually add missing fields to the `data/references.bib`.

5. Identify and merge duplicates (manual task, supported by a script)

```
make merge_duplicates
```

- TODO: This script identifies and merges duplicates when confidence is very high.
- Check and remove duplicates using the hash-id compatible version of JabRef. When using JabRef, make sure to call the `find duplicates` function multiple times since it only completes two-way merges.
- When editing `references.bib` manually, and to maintain the trace from the original search records to the merged record, it is important to add the hash_ids to the merged entry (this is done automatically in the hash-id compatible version of JabRef).

6. Check/update citation_keys (manual task)

- update citation_keys for records that did not have author or year fields
- compare citation_keys with other local/shared bibliographies to avoid citation_key conflicts (TODO: develop scripts to support this step)

- Please note that after this step, the citation_keys will be propagated to the screen.csv and data.csv, i.e., they should not be changed afterwards.

When updating the search, follow the same procedures as described above. Note that `make search` will only add new records to the references.bib and `cleanse_records` will only be executed for new records.

## Inclusion screen

1. Create screening sheet (script)

```
make screen_sheet
```
- This procedure asks for exclusion criteria and adds the search records to the [screening sheet](data/screen.csv).

2. Complete screen 1 (manual task, supported by a script)

```
make screen_1
```
- This procedure iterates over all records and records inclusion decisions for screen 1 in the [inclusion.csv](data/inclusion.csv).

The following steps apply only to records retained after screen 1 (coded as inclusion_1 == yes).

4. Check bibliographical meta-data of included records (manual task)

- Manually check the completeness and correctness of bibliographic data
- TBD: how to do that efficiently?? (create keyword=included in the bibfile?)

5. PDF acquisition etc. (manual task)

TODO: include the script
- Acquire PDF for full-text eligibility assessment (store in data/pdfs and link in references.bib)

6. PDF validation (manual task)

TODO: include the script
- Compare paper meta-data with bibtex entry to make sure it is accurate and complete (including pages etc.).

7. Complete screen 2 (manual task, supported by a script)

```
make screen_2
```
- This procedure iterates over all records, prompts the user for each exclusion criterion (if exclusion criteria are available), and records inclusion decisions for screen 2 in the [inclusion.csv](data/inclusion.csv).


When updating the search, follow the same procedures as described above. Note that `make screen_sheet` will add additional search results to the [screening sheet](data/screen.csv). If records in the screening sheet are no longer in the references.bib (possibly because citation_keys have been modified in the references.bib), `make screen_sheet` will print a warning (but still retain the record in the screening sheet).

## Data extraction

1. Generate sample profile (script)

TODO: scripts in analysis/R
descriptive statistics of paper meta-data


2. Create data extraction sheet (script)

```
make data
```
- This procedure adds records of included papers to the [data extraction sheet](data/data.csv).

3. Complete data extraction (manual task)

TODO: include description of the step

When updating the data extraction, follow the same procedures as described above. Note that `make data` will add additional included records to the [data sheet](data/data.csv). If records in the data sheet are no longer in the screening sheet, `make data` will print a warning (but still retain the record in the data sheet).

## Synthesis, reporting, and dissemination

TODO
