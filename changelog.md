# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0).

## [Unreleased]

### Added

- `initialize` to set up the data directory (including a `readme.md` and the `search_details.csv`)
- `merge_duplicates` with automated (threshold-based) and semi-automated identification of duplicates
- `sample_profile` to generate a csv of the sample and to cross-tabulate journals vs years

### Changed

- Changed environment to Docker-compose and revised Makefiles to call scripts within Docker containers
- Refactored code, including `analysis/utils.py/load_references_bib(modification_check, initialize)` and `analysis/utils.py/git_modification_check(filename)`
- Improve treatment of diacritics and accents when generating citation_keys in `analysis/cleanse_records.py`
- `backward_search` now works with tei-conversion provided by a grobid Docker container

### Removed

- R scripts for sample statistics (the goal is to implement them in Python)

### Fixed

- Bugs in `analysis/combine_individual_search_results.py` and in `analysis/acquire_pdfs.py`
- Catch exceptions and check bad responses in `analysis/acquire_pdfs.py`
- Bug in git modification check for `references.bib` in `analysis/utils.py`

### [0.1.0] -2021-05-08

### Added

- First version of the pipeline, including `status`, `reformat_bibliography`, `trace_entry`, `trace_hash_id`, `combine_individual_search_results`, `cleanse_records`, `screen_sheet`, `screen_1`, `acquire_pdfs`, `screen_2`, `data_sheet` and `data_pages`
- Environment setup including `Dockerfile` and `Makefiles`
