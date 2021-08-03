# Literature review template

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)


Conducting high-quality literature reviews is a key challenge for generations.
Researchers must be prepared to develop high-quality, rigorous, and insightful reviews while coping with staggering growth and diversity of research output.
This project aims at facilitating review projects based on a robust, scalable, and traceable pipeline.
The most innovative part of our pipeline pertains to the use of *hash_ids* to trace papers from the moment they are returned from an academic literature database.
This makes the process reproducible and the iterative search process much more efficient.
More broadly, our aspiration is to automate repetitive and laborious tasks in which machines perform better than researchers, saving time for the more demanding and creative tasks of a literature review.
For this purpose, this project is designed as a strategic platform to validate and integrate further extensions.


Features

- Collaborative, robust, and tool-supported end-to-end `search > screen > data` pipeline designed for reproducibility, iterativeness, and quality.
Designed for local and distributed use.

- A novel approach, based on *hash_ids*, ensures traceability from the search results extracted from an academic database to the citation in the final paper.
This also makes iterative updates extremely efficient because duplicates only have to be considered once [more](TODO).

- The pipeline includes powerful Python scripts that can handle quality problems in the bibliographic metadata and the PDFs (based on powerful APIs like crossref and the DOI lookup service and excellent open source projects like grobid, tesseract, pdfminersix).

- **Planned**: There are two modes of operation: the default mode, which offers a user interface, and a command-line interface (CLI), which offers access to the Python scripts.
Making the same pipeline accessible through both modes is aimed at enabling collaboration between experts in the research domain and experts in research technology.
Extensions will be developed and tested in the CLI mode before implementation for the default mode.

- Applicability to different types of reviews, including systematic reviews, theory development reviews, scoping reviews and many more.
For meta-analyses, software like RevMan or R-meta-analysis packages are more appropriate.

- Zero-configuration, low installation effort, and cross-platform compatibility ensured by Docker environment.

- Extensibility (explain how it can be accomplished, how it is facilitated (e.g., stable but extensible data structures, robust workflow with checks, python in Docker))

- Tested workflow (10 literature reviews and analyses (systematic, theory development, scoping) individual or collaborative)

- The pipeline is tested in the management disciplines (information systems) in which iterative searches are pertinent.

# Principles of the `search > screen > data` pipeline

- **End-to-end traceability (NEW)**. The chain of evidence is maintained by identifying papers by their *citation_key* throughout the pipeline and by mapping it to *hash_ids* representing individual (possibly duplicated) search results.
Never change the *citation_key* once it has been used in the screen or data extraction and never change the *hash_id* manually.

    <details>
      <summary>Details</summary>

      When combining individual search results, the original entries receive a *hash_id* (a sha256 hash of the main bibliographical fields):

      ```
      # data/search/2020-09-23-WebOfScience.bib (individual search results)

      @Article{ISI:01579827937592,
        	title = {Analyzing the past to prepare for the future},
        	authors = {Webster, Jane and Watson, Richard T.},
        	journal = {MIS Quarterly},
        	year = {2002},
        	volume = {26},
        	issue = {2},
        	pages = {xiii-xxiii}
      }
      ```

      ```
      # Calculating the hash_id

      hash_id = sha256(robust_concatenation(author, year, title, journal, booktitle, volume, issue, pages))
      # Note: robust_concatenation replaces new lines, double-spaces, leading and trailing spaces, and converts all strings to lower case
              = sha256("webster, jand and watson, richard t.analyzing the past to pepare for the future...")
      hash_id = 7a70b0926019ba962519ed63a9aaae890541d2a5acdc22604a213ba48b9f3cd2
      ```

      ```
      # data/references.bib (combined search results with hash_ids linking to the individual search results)

      @Article{Webster2002,
        	title = {Analyzing the past to prepare for the future:
        		Writing a literature review},
        	authors = {Webster, Jane and Watson, Richard T.},
        	journal = {MIS Quarterly},
        	year = {2002},
        	volume = {26},
        	issue = {2},
        	pages = {xiii-xxiii},
        	hash_id = {7a70b0926019ba962519ed63a9aaae890541d2a5acdc22604a213ba48b9f3cd2,...}
      }

      ```

      When all papers (their BibTeX entries, as identified by a *citation_key*) are mapped to their individual search results through *hash_ids*, resolving data quality problems (matching duplicates, updating fields, etc.) in the BibTex entries (`data/references.bib`) does not break the chain of evidence.



      At the end of the search process, each entry (containing one or many *hash_ids*) is assigned a unique *citation_key*.
      At this stage, the *citation_key* can be modified.
      It is recommended to use a semantic *citation_key*, such as "Webster2002" (instead of cryptic strings or random numbers).
      Once a *citation_key* progresses to the screening and data extraction steps, it should not be changed (this would break the chain of evidence).

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

    </details>

- **Consistent structure of files and data** and **incremental propagation of changes**.
Papers are propagated from the individual search outputs (`data/search/YYYY-MM-DD-search_id.bib`) to the `data/references.bib` to the `data/screen.csv` to the `data/data.csv`.
Do not change directories, filenames, or file structures unless suggested in the following.
To reset the analyses, each of these files can be deleted.

    <details>
      <summary>Details</summary>

      When updating data at any stage in the pipeline and rerunning the scripts,
       - existing records in the subsequent files will not be changed
       - additional records will be processed and added to the subsequent file
       - if records have been removed, scripts will create a warning but not remove them from the subsequent file (to avoid accidental losses of data)

    </details>

- The pipeline relies on the **principle of transparent and minimal history changes** in git.

    <details>
      <summary>Details</summary>

      - Transparent means that plain text files must be used (i.e., BibTeX and CSV); proprietary file formats (in particular Excel files) should be avoided.
      - Minimal means that the version history should reflect changes in content and should not be obscured by meaningless changes in format (e.g., ordering of records, fields, or changes in handling of fields).
      This is particularly critical since there is no inherent order in BibTeX or CSV files storing the data of the literature review.
      Applications may easily introduce changes that make it hard to identify the content that has changed in a commit.
      - In the pipeline, this challenge is addressed by enforcing reasonable formatting and ordering defaults in the BibTex and CSV files.

    </details>

# Components

The scripts work together with the [pipeline-validation-hooks](https://github.com/geritwagner/pipeline-validation-hooks).
It is recommended to run `pre-commit run -a` regularly to analyze the status of the pipeline and to ensure consistency.

Modes:

- 🤓∞💻 : Interactive human and computational processing
- 💻→🤓 : Sequential computational processing and human verification
- 💻    : Purely computational processing

| Step: component (mode)           | Description and scripts                                                                   | Status      |
| :------------------------------- | :---------------------------------------------------------------------------------------- | :---------- |
| Management: starter 🤓∞💻        | Sets up the repository.                                                                   | CLI only    |
|                                  | make initialize                                                                           |             |
| Management: formatter 💻         | Formats the bibliography to ensure a clean git history.                                   | CLI only    |
|                                  | make format_bibliography                                                                  |             |
| Management: validator 💻         | Validates the state of the pipeline, ensuring traceability and consistency.               | CLI only    |
|                                  | The corresponding scripts are registered as pre-commit hooks for the git repository and   |             |
|                                  | executed automatically before new git versions are created.                               |             |
|                                  | make validate                                                                             |             |
| Management: tracer 💻            | Traces entries (by citation_keys) or hash_ids back to their origin or                     | CLI only    |
|                                  | search results (BibTeX) to their coding.                                                  |             |
|                                  | make trace_search_result  \| trace_entry \| trace_hash_id                                 |             |
| Management: resolver 🤓∞💻       | Resolves disagreements in parallel independent screening/coding (merge conflicts).        | Planned     |
|                                  | make resolve                                                                              |             |
| Search: importer 💻              | Imports search results, generates a _hash_id_ for each entry, and                         | CLI only    |
|                                  | creates a combined `references.bib` file.                                                 |             |
|                                  | make combine_individual_search_results                                                    |             |
| Search: cleanser 💻→🤓           | Cleanses the `references.bib` file using meta-data provided by Crossref and Doi.org.      | CLI only    |
|                                  | make cleanse_records                                                                      |             |
| Search: backward_searcher 💻→🤓  | Extracts references from PDFs and includes them as search results.                        | CLI only    |
|                                  | make backward_search                                                                      |             |
| Search: merger 💻→🤓/🤓∞💻       | Merges duplicates based on identical _hash_ids_ and based on a threshold and manual input.| CLI only    |
|                                  | make merge_duplicates                                                                     |             |
| Screen: screener 🤓∞💻           | Creates screening sheets, guides users through the pre-screen and the full-text screen.   | CLI only    |
|                                  | make screen_sheet \| screen_1 \| screen_2                                                 |             |
| Screen: pdf_collector 💻→🤓      | Collects PDFs (e.g., using the unpaywall API), renames them (to _citation_key.pdf_),      | Development |
|                                  | validates their content and completes pre-processing steps (e.g., OCR based on ocrmypdf). |             |
|                                  | make acquire_pdfs \| validate_pdfs                                                        |             |
| Data extraction: extractor 🤓∞💻 | Creates the data extraction sheets (structured spreadsheet or weakly structured sheets)   | CLI only    |
|                                  | and guides users through the data extraction/coding process.                              |             |
|                                  | make data_sheet \| data_pages                                                             |             |
| Data extraction: statistician 💻 | Creates summary statistics (e.g., PRISMA diagrams, cross-tabulating of journals/years).   | Planned     |
|                                  | make generate_statistics                                                                  |             |

# Installation

The pipeline operates inside a Docker container which connects to services offered by other Docker containers (e.g., Grobid).
Instructions for  [installing](https://docs.docker.com/install/linux/docker-ce/ubuntu/)  and [configuring](https://docs.docker.com/install/linux/linux-postinstall/) [Docker](https://www.docker.com/) and [Docker-compose](https://docs.docker.com/compose/install/) are available online.


- **Default mode (web interface)/Not yet available**: to start the default mode, execute the following:

```
docker-compose up
# Note: when the default mode is implemented, the app should be available through the browser (information should be provided here).
```

- **CLI mode**: to start the command-line mode, execute the following:

```
docker-compose up
docker-compose run --rm review_template_python3 /bin/bash
```

To install crowd-sourced resources, include them as submodules as follows:

```
git submodule add https://github.com/geritwagner/crowd_resource_information_systems
```

Further instructions are available in the [analysis/readme.md](analysis/readme.md).


# Development status, release, and changes

Note: The status of the pipeline is developmental.
None of the scripts has been tested extensively.
See the [changelog](changelog.md).

# Contributing

- Bug reports or feedback? Please use the [issue tracker](https://github.com/geritwagner/review-template/issues) and let us know.

- You are welcome to contribute code and features. To get your work included, fork the repository, implement your changes, and create a [pull request](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests).

# License

TBD. MIT/Apache2.0?
