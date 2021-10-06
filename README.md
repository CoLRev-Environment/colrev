# Literature review template

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

- Git-based (collaborative) literature reviews
- Easy to learn and use: one command (review_template status) shows an overview and contextual instructions (based on the current dataset, collaboration approach, ...)
- Respects methodological and typological pluralism through configurable templates for
  - informal literature reviews (e.g., for a related work section) or
  - standalone review papers requiring extraction and analysis of structured data (e.g., critical reviews, descriptive reviews, meta-analysis, qualitative systematic reviews, realist reviews)
  - standalone review papers requiring interpretive analyses and syntheses of (semi) structured data (e.g., narrative reviews, scoping reviews, theoretical reviews, umbrella reviews)
- Right amount of automation (completion of fields, cleansing, merging) supporting you to achieve accurate results while saving time [link: what's automated/what's not]
- Collaboration protocols
- Changes of other researchers, scripts, and crowds can be visualized and validated
- Verifiable traceability (always know where each record is and how it got there)
- Cross-platform and tested (Windows, Linux, MacOs)
- Aimed at preventing errors (erroneous merging of records, analysis of wrong PDFs, or non-machine-readable PDFs)
- Designed with 10+ years of experience conducting and publishing literature reviews, methods and commentary papers, teaching PhD level courses on literature reviews.


# Installation and usage

Requirements: [git](https://git-scm.com/downloads), [a git gui](https://git-scm.com/downloads), [Docker](https://www.docker.com/), [Python 3](https://www.python.org/), and [pip](https://pypi.org/project/pip/).

```
# Installation (currently, while not yet available via pip)
git clone https://github.com/geritwagner/review_template
cd review_template
pip3 install --user -e .
# Goal:
# pip install review_template

# Navigate to project directory (cd ...)
review_template status
# the status command will recommend the next processing steps and commands based on the state of the project
```

To install crowd-sourced resources, include them as submodules as follows:

```
git submodule add https://github.com/geritwagner/crowd_resource_information_systems
```

Further instructions are available in the documentation (add-link-here).


# Features

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

# Development status, release, and changes

Note: The status of the pipeline is developmental.
None of the scripts has been tested extensively.
See the [changelog](CHANGELOG.md).

# Contributing

- See [contributing guidelines](CONTRIBUTING.rst).

- Bug reports or feedback? Please use the [issue tracker](https://github.com/geritwagner/review_template/issues) and let us know.

- You are welcome to contribute code and features. To get your work included, fork the repository, implement your changes, and create a [pull request](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests).

# License

MIT License.
