# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0).

## [Unreleased]

### Added

- `initialize` to set up the data directory (including a `readme.md` and the `search_details.csv`)
- `merge_duplicates` with automated (threshold-based) and semi-automated identification of duplicates
- `sample_profile` to generate a csv of the sample and to cross-tabulate journals vs years
- Use of submodules for crowd-sourced data
- Checks whether the hash_id function is up-to-date with the commit-id in the `.pre-commit-config.yaml`
- `analysis/fix_errors.py` to fix missing hash_ids and to rename propagated citation_keys
- `analysis/renew_hash_id_function.py` to keep track of hash functions and commit ids of pipeline_validation_hooks in `analysis/hash_function_pipeline_commit_id.csv`
- `analysis/trace_search_result.py` to trace search records (in BibTeX format)

### Changed

- Changed environment to Docker-compose and revised Makefiles to call scripts within Docker containers
- Refactored code, including `analysis/utils.py/load_references_bib(modification_check, initialize)` and `analysis/utils.py/git_modification_check(filename)`
- Improve treatment of diacritics and accents when generating citation_keys in `analysis/cleanse_records.py`
- `backward_search` now works with tei-conversion provided by a grobid Docker container
- Update `utils.py/save_bib()` and pre-commit hook/formatter
- Updated `analysis/cleanse_records.py` based on derek73/python-nameparser
- Updated `analysis/combine_individual_search_results.py`, `analysis/merge_duplicates.py`
- Update hash_id function
- Updated path handling (`analysis/config.py`)
- Renaed `analysis/combine_individual_search_results.py` to `analysis/importer.py`

### Removed

- R scripts for sample statistics (the goal is to implement them in Python)

### Fixed

- Bugs in `analysis/combine_individual_search_results.py` and in `analysis/acquire_pdfs.py`
- Catch exceptions and check bad responses in `analysis/acquire_pdfs.py`
- Bug in git modification check for `references.bib` in `analysis/utils.py`
- Exception in `anaylsis/screen_2.py` (IndexError)
- Global constant conflict with `analysis/entry_hash_function.py` (nameparser.config/CONSTANTS)

### [0.1.0] -2021-05-08

### Added

- First version of the pipeline, including `status`, `reformat_bibliography`, `trace_entry`, `trace_hash_id`, `combine_individual_search_results`, `cleanse_records`, `screen_sheet`, `screen_1`, `acquire_pdfs`, `screen_2`, `data_sheet` and `data_pages`
- Environment setup including `Dockerfile` and `Makefiles`
