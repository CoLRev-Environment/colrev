
Roadmap
==================================

**Development status**: Currently recommend for users with technical experience. Once CoLRev has matured, UIs should make it accessible to a broader user base. CoLRev is the result of intense prototyping, research and development. We use it for our own projects and believe it is ready to be released - after all, git ensures that your work is never lost.

The goal is to release new versions on a bi-monthly basis.

Upcoming
--------------------------------------

- Extension colrev_cml_assistant
- Extension backward_search
- Templates for review_types
- Synchronous session support
- `Additional SearchSources <https://github.com/geritwagner/colrev/issues/106>`_

2023-04-01: v0.8.0 (expected)
--------------------------------------

- User tests
- Unit tests (extension and efficiency)
- Documentation (methods)
- Advanced validation options (e.g., for prescreen)
- Data endpoint for bibliography exports
- R package

2023-01-16: v0.7.0
--------------------------------------

- Unit tests
- User tests
- Package management

2022-10-12: v0.6.0
--------------------------------------

- Architecture refactoring

2022-06-28: v0.5.0
--------------------------------------

- Data provenance model
- Extensible endpoints (search, prep, prescreen, pdf-get, pdf-prep, screen, data)
- Prescreen scope
- Documentation
- Push/pull (including corrections), sync, validate, service operations

2022-04-06: v0.4.0
---------------------------

- Extract functionality: ReviewDataset, Process
- Developed LocalIndex, EnvironmentManager, OpenSearch
- Curation model, including Resource installation and a "correction path"
- Search operation (reintegrating paper_feed and local_paper_index)
- Prep exclusion based on languages
- Object-oriented refactoring of the whole codebase
- Use Zotero translators (instead of bibutils) for imports
- Duplicate identification (add FP safeguards based on LocalIndex, add a procedure for small samples)
- Consistent PDF path handling
- Structured data extraction based on csv

2022-02-06: v0.3.0
---------------------------

- Introduced ReviewManager and integrated hooks/checks
- Fetch metadata from Open Library
- Required fields for misc
- Information on needs_manual_preparation (man_prep_hints)
- Activated mypy hooks
- Introduced custom load scripts
- Documentation
- LocalIndex: hash-table implementation for indexing and retrieval

- Dedupe: based on active learning (dedupe-io)
- Improved batches
- Pass records instead of BibDatabase
- PDF prep and longer pdf hashes

2021-11-12: v0.2.0
---------------------------

- Status model (rev_status, md_status, pdf_status)
- Implemented cli interface
- Import formats (bib, ris, endn, pdf, text list of references)
- Docker services for import, ocr, building the paper etc.
- Metadata repositories for record preparation (crossref, dblp, semantic scholar)
- PDF preparation (OCR, metadata validation)
- Commit message reporting
- Check and validation of iteration completeness
- Support for building papers based on pandoc
- Integrated review process status (including prescreen, screen inclusion vs exclusion) in the references.bib
- Renamed scripts and cli entrypoints
- Refactored code
- Tracing from hash_id to origin links
- Extended and refactored pre-commit hooks

2021-05-08: v0.1.0
---------------------------

- First version of the pipeline, including `status`, `reformat_bibliography`, `trace_entry`, `trace_hash_id`, `combine_individual_search_results`, `cleanse_records`, `screen_sheet`, `screen_1`, `acquire_pdfs`, `screen_2`, `data_sheet` and `data_pages`
- Environment setup including `Dockerfile` and `Makefiles`
