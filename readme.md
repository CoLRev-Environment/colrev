# Literature review template

Note: The status of the pipeline is developmental.
None of the scripts has been tested extensively.
Status of the main scripts:

| Script                                | Status                   |
| :------------------------------------ | :----------------------- |
| make initialize                       | Implemented              |
| make status                           | Implemented              |
| make reformat_bibliography            | Implemented              |
| make trace_entry                      | Implemented              |
| make trace_hash_id                    | Implemented              |
| make cleanse_records                  | Implemented              |
| make screen_sheet                     | Implemented              |
| make screen_1                         | Implemented              |
| make acquire_pdfs                     | Implemented              |
| make screen_2                         | Implemented              |
| make data_sheet                       | Implemented              |
| make data_pages                       | Implemented              |
| make backward_search                  | Implemented              |
| make extract_manual_pre_merging_edits | Experimental/development |
| make merge_duplicates                 | Experimental/development |
| make pre_merging_quality_check        | Experimental/development |
| make validate_pdfs                    | Experimental/development |


Instructions for setting up the environment and applications for the pipeline are available in the [setup](SETUP.md).

All commands must be executed inside the Docker container.
For example:
```
# for Linux
docker run -ti --volume ${PWD}:/opt/workdir --user `id -u`:`id -g` review_template_python3 /bin/bash
# for Windows
docker run -ti --volume $(pwd):/opt/workdir --user `id -u`:`id -g` review_template_python3 /bin/bash
make status
```

Principles of the review pipeline

- The pipeline propagates search results from the individual search outputs (`data/search/YYYY-MM-DD-search_id.bib`) to the `data/references.bib` to the `data/screen.csv` to the `data/data.csv`.
To reset the analyses, each of these files can be deleted.
- The pipeline maintains the **chain of evidence** by identifying individual search results by their *hash_id*.
At the end of the search process, each entry (containing one or many *hash_ids*) is assigned a unique *citation_key*.
At this stage, the *citation_key* can be modified.
It is recommended to use a semantic *citation_key*, such as "Webster2002" (instead of cryptic strings or random numbers).
Once a *citation_key* progresses to the screening and data extraction steps, it should not be changed (this would break the chain of evidence).

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
  It is always possible to run `make reformat_bibliography`, or to `git restore ...` the file and start over.

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

Traceability is ensured through unique `hash_id` (in the search phase and the `references.bib`) and unique `citation_key` fields.
Note that one `citation_key`, representing a unique record, can be associated with multiple `hash_ids` the record has been returned multiple times in the search.
Once `citation_key` fields are set at the end of the search step (iteration), they should not be changed to ensure traceability through the following steps.

Forward traceability is ensured through the `trace_entry` procedure

```
make trace_entry

Example input:
@book{Author2010, author = {Author, Name}, title = {Paper on Tracing},  series = {Proceedings}, year = {2017}, }"

```

Backward traceability is ensured through the `trace_hash_id` procedure

```
make trace_hash_id
```

- This procedure traces a hash_id to the original entry in the `data/search/YYYY-MM-DD-search_id.bib` file.

The following overview explains each step of the review pipeline, providing information on the steps that are executed manually and the steps that are augmented or automated by scripts.

```
make initialize
```

- This procedure sets up the repository in the data directory.


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

- This procedure creates a hash_id for each entry and adds all entries with a unique hash_id to the [references.bib](data/references.bib).
This means that duplicate entries with an identical hash_id (based on titles, authors, journal, ...) are merged automatically (which is particularly important when running `make combine_individual_search_results` in incremental mode).

3. Cleanse records (script)

```
make cleanse_records
```

- Improves the quality of entries stored in `data/references.bib`.
If an entry has been cleansed, its hash_id is stored in the `data/search/bib_details.csv` to avoid re-cleansing (and potentially overriding manual edits).
Please note that this can take some time (depending on the number of records) since it calls the [Crossref API](https://www.crossref.org/education/retrieve-metadata/rest-api/) to retrieve DOIs and the [DOI resolution service](https://www.doi.org/) to retrieve corresponding meta-data.
For 1,000 records, this might take approx. 1:30 hours.

4. Complete fields necessary for merging (manual task, supported by a script)

```
make pre_merging_quality_check
```
- Estimates the degree of incompleteness (missing fields per record) and probability of duplication and saves results in `data/references_pre_screen_quality_check.csv`.
- Check the first entries (sorted in descending order of completeness and probability of duplication) and manually add missing fields to the `data/references.bib`.

5. Identify and merge duplicates (manual task, supported by JabRef)

- Check and remove duplicates using the hash-id compatible version of JabRef. When using JabRef, make sure to call the `find duplicates` function multiple times since it only completes two-way merges.
- IMPORTANT: sort entries according to title and authors and manually check for duplicates (JabRef does not always identify all duplicates).
For merging, select both entries and press `ctrl+M`.
- After merging duplicates in JabRef, it might be necessary to run `make reformat` to improve the readability of the history (for better readability in gitk, increase lines of context).
- When editing `references.bib` manually, and to maintain the trace from the original search records to the merged record, it is important to add the hash_ids to the merged entry (this is done automatically in the hash-id compatible version of JabRef).

TODO: `make merge_duplicates` is work-in-progress. The script identifies and merges duplicates when confidence is very high.

6. Check/update citation_keys (manual task)

- update citation_keys for records that did not have author or year fields
- compare citation_keys with other local/shared bibliographies to avoid citation_key conflicts (TODO: develop scripts to support this step)

- Please note that after this step, the citation_keys will be propagated to the screen.csv and data.csv, i.e., they should not be changed afterwards.

When updating the search, follow the same procedures as described above. Note that `make search` will only add new records to the references.bib and `cleanse_records` will only be executed for new records.


7. Backward search: after completing the first iteration of the search (requires first pipeline iteration to be completed

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

```
make acquire_pdfs
```

- TODO: The script acquires PDFs for the full-text eligibility assessment in screen 2.
- It queries the unpaywall api.
- If there are unliked files in the `data/pdfs` directory, it links them
- It creates a csv file (`data/missing_pdf_files.csv`) listing all PDFs that need to be retrieved manually.

- Manual PDF acquisition: acquire PDF and rename PDFs as `citation_key.pdf`, move to `dat/pdfs` directory. Rerun the `acquire_pdfs` script to link the pdfs into the `references.bib`.

- Check whether PDFs can be opened from Jabref. This might require you to set the Library > Library properties > General file directory to the `data/pdfs` directory, which is stored in the `references.bib` as follows:

```
@Comment{jabref-meta: fileDirectory-username-username-computer:/home/username/path-to-/review-template;}
```

- PDF file links should take the form `file = {:data/pdfs/citation_key.pdf:PDF}`


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

The [paper](paper.md) is written in markdown following the contributing guidelines in the [paper-template](https://github.com/geritwagner/paper-template/blob/main/CONTRIBUTING.md).
