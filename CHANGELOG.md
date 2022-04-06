# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0).

## [Unreleased]

### Added

### Changed

### Removed

### Fixed

### [0.4.0] - 2022-04-06

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

### [0.3.0] - 2022-02-05

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

### [0.2.0] - 2021-09-12

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

### [0.1.0] - 2021-05-08

### Added

- First version of the pipeline, including `status`, `reformat_bibliography`, `trace_entry`, `trace_hash_id`, `combine_individual_search_results`, `cleanse_records`, `screen_sheet`, `screen_1`, `acquire_pdfs`, `screen_2`, `data_sheet` and `data_pages`
- Environment setup including `Dockerfile` and `Makefiles`
