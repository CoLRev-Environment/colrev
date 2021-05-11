# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0).

## [Unreleased]

### Added

- `initialize` to set up the data directory (including a readme and the search_details)

### Changed

- Refactored code, including `analysis/utils.py/load_references_bib(modification_check, initialize)` and `analysis/utils.py/git_modification_check(filename)`

### Fixed


### [0.1.0] -2021-05-08

### Added

- First version of the pipeline, including `status`, `reformat_bibliography`, `trace_entry`, `trace_hash_id`, `combine_individual_search_results`, `cleanse_records`, `screen_sheet`, `screen_1`, `acquire_pdfs`, `screen_2`, `data_sheet` and `data_pages`
- Environment setup including `Dockerfile` and `Makefiles`
