# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0).

<!--
## Unreleased

### Added

### Changed

### Removed

### Fixed
-->

## 0.12.3 - 2024-06-15

- Extend documentation (package development, package summaries, asciinema demo)
- Bugfixes and codebase improvements (e.g., package management and discovery, closing sqlite connections)
- Reduce dependencies (e.g., levenshtein, PyPDF2, pdfminer, daff, psutil)
- Refactor colrev.bibliography_export (add writers)
- Extend tests: cover MacOS and Python 3.12
- Remove unnecessary options (e.g., init --local_pdf_collection)
- Add and test support for GitHub codespaces

## 0.12.2 - 2024-04-29

- Update CoLRev packages (including interfaces, development docs etc.)
- Refactoring (local-index)
- Implement json-loader
- Make ui_web (dash, blinker) optional to prevent errors in WSL
- Bugfixes

## 0.12.1 - 2024-04-17

- Refactor and test (dataset, records, provenance, local_index)
- Extract package_manager into a separate internal package
- Use bib-dedupe for matching (instead of simple similarities)
- Update docs

## 0.12.0 - 2024-04-04

### Added

- Add linter `colrev_records_variable_naming_convention`
- Test coverage increased from 71% to 80%

### Changed

- Split `records`, `dataset`, created `records` package.
- Extracted `process` as a separate package.
- Implemented loaders as a separate package, created a standard interface. SearchSources now create the specific mapping of IDs, entrytypes and fields.
- Moved field standardization from `load` to SearchSources.
- Extended use of constants
- SearchSourceInterface: renamed `run_search` to `search`, prefer `prep_link_md` over `get_masterdata`
- Renamed and refactored `GeneralOriginFeed` to `SearchAPIFeed`
- Pass record objects instead of dicts (in `local_index` in particular)
- Replaced unnecessary keyword arguments by positional arguments
- Moved `zotero_translation_service` to `bibliography_export` package
- Consolidated code for reference parsing in `tei_parser`
- Upgraded Grobid to 0.8.0

### Removed

- Removed dead code
- Dropped `INCONSISTENT_WITH_DOI_METADATA`
- `transitions` dependency

### Fixed

- Do not require review_manager for `colrev env -i`
- Fixed `status_stats`, including special cases.
- Repository registration: resolve() and absolute() path

## 0.11.0 - 2024-02-17

### Added

- Separate PDF quality model ([#268](https://github.com/CoLRev-Environment/colrev/pull/268))
- `download_from_website` pdf-get package
- Separate loader utilities for nbib, ris, bib
- SearchSources: SemanticScholar ([#288](https://github.com/CoLRev-Environment/colrev/pull/288)), Arxiv ([#203](https://github.com/CoLRev-Environment/colrev/pull/203))
- Constants module for Fields, ENTRYTYPES, etc.
- CEP003 for SearchSources
- New default dedupe package based on [bib-dedupe](https://github.com/CoLRev-Environment/bib-dedupe)
- Colrev pandas for Jupyter notebooks
- GitHub actions: pip-install test, make documentation

### Changed

- Integrated `colrev.resolve_crossrefs` into `load_utils_bib.py`
- Defect codes can be ignored based on the `IGNORE:` prefix ([#269](https://github.com/CoLRev-Environment/colrev/pull/269))
- Documentation for setup (VM, MacOS, WSL)
- Revised interfaces for SearchSources
- Integrated: pdf_dir + video_dir > files_dir
- poetry extras
- Backward search: export of parameters and expected sample sizes
- Replace thefuzz witz rapidfuzz

### Removed

- Package based on dedupe-io, including incompatible dependencies
- Crossref resolution package (integrated in bib-loader)

## 0.10.4 - 2023-10-15

### Fixed

- Removed unstable test case

## 0.10.3 - 2023-10-25

### Changed

- GitHub actions for CoLRev updates now install with Poetry because the fixed dependencies are more stable compared to pip installation

## 0.10.2 - 2023-10-15

### Fixed

- paper_md: export BibTeX file and replace keys containing `.` to prevent pandoc error

## 0.10.1 - 2023-10-06

### Changed

- SearchTypes: API, TOC, MD are added, PDFS is replaced by FILES.
- SearchTypes are explained in the docs.
- Package documentation is imported to docs.
- colrev.pdfs_dir and colrev.video_dir are integrated into colrev.files_dir.

## 0.10. - 2023-10-02

### Added

- SearchSources: SYNERGY datasets, OpenAlex, ERIC, IEEEXplore, ArXiv
- JournalRankings: index, prep, and prescreen
- CoLRev shell via cli-repl (`colrev shell`)
- prep operation: pause and resume
- Dashboard overview of the sample and project status
- Extended tests, updated documentation (especially for extension development)
- GitHub workflows to update dependencies (poetry update)
- Ruff linter

### Changed

- Load: ris/csv/... files are loaded directly (without creating intermediate BibTeX file)
- Introduced namespaced fields (e.g., `colrev.pubmed.pubmedid` instead of `pubmedid`)
- Extracted quality checks to separate Quality Model
- Docs: instructions for development setup
- Code quality improvements (codacy)

### Removed

- colrev-asreview: extracted to separate package
- watchdog-based service

## 0.9.3 - 2023-10-01

### Changed

- Introduced namespaced fields (e.g., `colrev.pubmed.pubmedid` instead of `pubmedid`).

## 0.9.2 - 2023-07-24

### Changed

- Updated colrev-asreview dependency (PyPI instead of GitHub)

## 0.9.1 - 2023-07-23

### Changed

- Integrated `load` into `SearchSource`. Removed `load_conversion` endpoint: `settings.json`, `packages`, `interface` etc.

## 0.9.0 - 2023-06-01

### Added

- The `quality_model` was created to check for quality defects
- The `auto_upgrade` flag allows users to enable/disable automated upgrades
- All-contributors bot to acknowledge contributions to CoLRev
- Implemented OpenLibrary as a SearchSource
- Pylint check for direct assignment of colrev_status
- Test battery for built-in SearchSources (heuristics, load, prep)
- Backward-search comparison with OpenCitations data

### Changed

- Refactored `language_service`
- Refactored the tests (`conftest.py` now provides the `base_repo_review_manager` fixture)
- Changed pdf-hash (pdf to image) from poppler to mupdf for cross-platform compatibility (`cpid1` -> `cpid2`)
- Local settings changed from yaml to json
- Quality defects (colrev_masterdata_provenance notes) change
- The `colrev.global_ids_consistency_check` prep-endpoint is removed (integrated into the quality model)
- Individual quality checks can be disabled through the `prep/defects_to_ignore` settings
- Update the Github action workflows in CoLRev repositories

### Removed

- `timeout-decorator` dependency (for better compatibility with MacOS)
- Docker image `pdf-hash-service` (replaced by mupdf)
- Redundant fields for the backward search are removed (`cited_by_file` and `cited_by_id`)

### Fixed

- Documentation: typos and inconsistencies
- Codacy issues and refactored complex files [1](https://app.codacy.com/gh/CoLRev-Environment/colrev/dashboard)
- Windows paths in `iter_commit` (git history)

## 0.8.4 - 2023-05-19

### Changed

- Implemented new quality model
- Quality defects (colrev_masterdata_provenance notes) change
- The `colrev.global_ids_consistency_check` prep-endpoint is removed (integrated into the quality model)
- Individual quality checks can be disabled through the `prep/defects_to_ignore` settings

### Removed

- Redundant fields for the backward search are removed (`cited_by_file` and `cited_by_id`)

## 0.8.3 - 2023-04-22

### Changed

- CoLRev pdf IDs are now based on the mupdf library

## 0.8.2 - 2023-04-05

### Fixed

- Fix InvalidGitRepositoryError (raised upon status in empty directories)

## 0.8.1 - 2023-04-04

### Changed

- Update the Github action workflows in CoLRev repositories
- Add auto-upgrade flag to settings

## 0.8.0 - 2023-03-26

### Added

- Unit tests: increased test coverage to 70%, added Github actions matrix tests across OS and Python versions
- Completed OpenSSF Best Practices checks ([1](https://bestpractices.coreinfrastructure.org/de/projects/7148))
- Added forward and backward searches based on [OpenCitations](https://opencitations.net/)
- Moved documentation to [readthedocs](https://colrev.readthedocs.io/en/latest/) and revised documentation
- Added dependabot and pre-commit.ci: automated code and secrity checks
- Added support for Github actions, distinguishing packages that are supported in ci-environments (``ci_supported`` flag)
- Added Pubmed API searches and metadata preparation support
- Option to initialize and run CoLRev repositories without requiring Docker
- Overview video presented at ESMARConf2023 [1](https://www.youtube.com/watch?v=fuLpu8X1Mr0)
- CITATION.cff and Zenodo
- API-searches for the AIS eLibrary

### Changed

- Numerous modifications based on the [user tests](https://github.com/CoLRev-Environment/colrev/issues/41)
- Replaced OpenSearch with sqlite
- SearchSource interface: ``run_search`` and ``add_package`` are now mandatory
- Documentation review, including detailed information on development status
- Consistent setup of Github actions (test, publish to PyPI)
- Built-in packages renamed from ``colrev_built_in`` to ``colrev``
- Data package ``manuscript``renamed to ``paper_md``
- Simplified upgrade operation and activated upgrades per default
- Extracted and refactored language-service

### Fixed

- Several bugfixes

### 0.7.1 - 2023-03-25

### Changed

- Changed package prefix from ``colrev_built_in`` to ``colrev``

### 0.7.0 - 2023-01-16

### Added

- Add retrieve and pdfs as high-level operations
- Metadata preparation can add records to separate origin feeds
- Initial package manager functionality (registering packages and displaying them in the docs)
- Search: update of records and propagation of changes
- Several SearchSources (including SearchSource query validation)
- Revisions of CLI (verbose mode, user feedback)
- Colrev merge (reconciliation coding when merging git branches)
- dedupe --merge/--unmerge
- Integrated colrev pre-commit hooks
- PRISMA diagram (data endpoint)
- Obsidian (data endpoint)
- Preparation: not-in-toc exception/warning
- Setup of pytests

### Changed

- Curated records are now explicitly identified through curation_IDs
- Revise colrev validate (commits, users, properties)
- Detailed advisor (using get_advice() for data endpoints)
- Performance improvements and simplification of status (cli)
- Moved correction functionality to SearchSources (refactored correction path)
- Preparation: simplified preparation rounds (default settings)
- Retrieve TEIs through local_index (if available) instead of recreating it
- Replace pathos by Threadpool
- Revise the documentation
- Revise and extend exceptions

### Removed

- Remove persistent colrev-ids
- Remove realtime review
- Dependencies ansiwrap and p-tqdm

### Fixed

- **kwargs calls in ReviewManager
- Indexing of non-curated records
- Address special cases in dedupe (active learning)

### 0.6.0 - 2022-10-12

### Added

- Web-based editor for project settings
- Comprehensive architecture refactoring
- Conformance with pylint, mypy, flake8
- Introduced packages
- Updated file and directory structure
- Documentation of modules, classes, and methods
- Github-pages as a data package_endpoint

### Changed

- Renamed from colrev_core to colrev (integrated cli)
- Switch to poetry for dependency management
- Renamed scripts to package_endpoints
- PDF-hash generation based on Docker to avoid platform dependency issues
- Switch to Jinja templates (instead of concatenating multiple strings)

### Fixed

- Concurrent request session handling
- StatusStats calculations

### 0.5.0 - 2022-06-28

### Added

- Push/pull (including corrections), sync, validate, service operations
- Data provenance model (colrev_data_provenance, colrev_masterdata_provenance)
- Extensible endpoints (search, prep, prescreen, pdf-get, pdf-prep, screen, data)
- Prescreen scope

### Changed

- Improvements: prep, dedupe operations
- Performance improvements (e.g., status, bibtexparser > pybtex)
- Extended Record class (e.g., merge and fuse_best_fields)
- LocalIndex: Elasticsearch to Opensearch
- Dedupe: testing and parameter optimization (option to prevent same-source merges)
- Settings.json and validation
- Updated documentation
- Testing and refactoring (e.g., for Windows, prefer keyword arguments in functions, python package type information)


### 0.4.0 - 2022-04-06

### Added

- Extract functionality: ReviewDataset, Process
- Developed LocalIndex, EnvironmentManager, OpenSearch
- Curation model, including Resource installation and a "correction path"
- Search operation (reintegrating paper_feed and local_paper_index)
- Prep exclusion based on languages

### Changed

- Object-oriented refactoring of the whole codebase
- Use Zotero translators (instead of bibutils) for imports
- Duplicate identification (add FP safeguards based on LocalIndex, add a procedure for small samples)
- Consistent PDF path handling
- Structured data extraction based on csv

### Fixed

- Loggers
- Performance issues in prep and status

### 0.3.0 - 2022-02-05

### Added

- Introduced ReviewManager and integrated hooks/checks
- Fetch metadata from Open Library
- Required fields for misc
- Information on needs_manual_preparation (man_prep_hints)
- Activated mypy hooks
- Introduced custom load scripts
- Documentation
- LocalIndex: hash-table implementation for indexing and retrieval

### Changed

- Dedupe: based on active learning (dedupe-io)
- Improved batches
- Pass records instead of BibDatabase
- PDF prep and longer pdf hashes

### Removed

- CLI: now in separate colrev repository

### Fixed

- Initializing repositories
- Backward search adds two entries to search_details
- Logging (reinitialize after batches/commits)

### 0.2.0 - 2021-09-12

### Added

- Status model (rev_status, md_status, pdf_status)
- Implemented cli interface
- Import formats (bib, ris, endn, pdf, text list of references)
- Docker services for import, ocr, building the paper etc.
- Metadata repositories for record preparation (crossref, dblp, semantic scholar)
- PDF preparation (OCR, metadata validation)
- Commit message reporting
- Check and validation of iteration completeness
- Support for building papers based on pandoc

### Changed

- Integrated review process status (including prescreen, screen inclusion vs exclusion) in the references.bib
- Renamed scripts and cli entrypoints
- Refactored code
- Tracing from hash_id to origin links
- Extended and refactored pre-commit hooks

### Removed

- R scripts for sample statistics (the goal is to implement them in Python)
- hash_id function, trace_entry, trace_hash_id

### Fixed

- Bugs in `analysis/combine_individual_search_results.py` and in `analysis/acquire_pdfs.py`
- Catch exceptions and check bad responses in `analysis/acquire_pdfs.py`
- Bug in git modification check for `references.bib` in `analysis/utils.py`
- Exception in `anaylsis/screen_2.py` (IndexError)
- Global constant conflict with `analysis/entry_hash_function.py` (nameparser.config/CONSTANTS)

### 0.1.0 - 2021-05-08

### Added

- First version of the pipeline, including `status`, `reformat_bibliography`, `trace_entry`, `trace_hash_id`, `combine_individual_search_results`, `cleanse_records`, `screen_sheet`, `screen_1`, `acquire_pdfs`, `screen_2`, `data_sheet` and `data_pages`
- Environment setup including `Dockerfile` and `Makefiles`
