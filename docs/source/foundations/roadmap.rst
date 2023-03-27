
Development status and roadmap
==================================

Currently, CoLRev is recommended for users with technical expertise. We use it for our own projects and the use of Git versioning prevents data losses.
A detailed overview of the project status and the roadmap is provided below. The maturity is rated as follows:

.. list-table::
   :widths: 10 90
   :header-rows: 1

   * - Status
     - Description
   * -  🟢
     - Functionality is fully implemented, including unit and user tests, as well as comprehensive documentation. Reviewed from a technical and methodological perspective. **Recommended for use.**
   * - 🟡
     - Functionality is implemented, partially tested, and documented. **Recommended for users with technical expertise.**
   * - 🔴
     - Functionality may not be fully implemented, tested, or documented. **Recommended for developers, not for general users.**

Status: Core functionality
-----------------------------------------------------------------

**Development status overall**: 🟡/🟢

**Summary statement**: The core functionality related to data management, operations, and environment services are fairly well documented and tested, although work is still in progress.

..
    To activate:
    - Dataset: 🟡
    - Records: 🟡
    - ReviewManager: 🟡
    - Operation load: 🟡
    - Operation prep: 🟡
    - Operation dedupe: 🟡
    - Operation prescreen: 🟡
    - Operation pdfs: 🟡
    - Operation screen: 🟡
    - Operation data: 🟡
    - Other operations: 🟡

Status: Collaboration
-----------------------------------------------------------------

**Development status overall**: 🟡/🟢

**Summary statement**: The collaboration model relies on established git mechanisms. CoLRev partly supports the collaboration by applying formatting and consistency checks. More specific collaboration principles and guidelines are currently developed.

Status: Packages
-----------------------------------------------------------------

**Development status overall**: 🔴/🟡

**Summary statement**: The packages are generally under heavy development. Packages vary in maturity but most are not yet completed and require testing as well as documentation. At the same time, we use most packages regularly and quickly fix bugs.

..
    - We focus on those package that are suggested as part of the default initial setup (a table overview follows)
    - it should become clear whether there are mature packages for each operation (which ones)


The status of each package is provided in the operations subpages (`init <../manual/problem_formulation/init.html>`_, `search <../manual/metadata_retrieval/search.html>`_, `load <../manual/metadata_retrieval/load.html>`_, `prep <../manual/metadata_retrieval/prep.html>`_, `dedupe <../manual/metadata_retrieval/dedupe.html>`_, `prescreen <../manual/metadata_prescreen/prescreen.html>`_, `pdf-get <../manual/pdf_retrieval/pdf_get.html>`_, `pdf-prep <../manual/pdf_retrieval/pdf_prep.html>`_, `screen <../manual/pdf_screen/screen.html>`_, `data <../manual/data/data.html>`_) Instructions on adding new packages and having them reviewed are provided in the `extensions <../manual/extensions.html>`_ section.

..
    -> TODO : link to criteria

Status: Methods
-----------------------------------------------------------------

**Development status overall**: 🔴/🟡

**Summary statement**: The operations are `aligned <../manual/operations.html>`_ with the established methodological steps of the review process and differences between review types and the typical forms of data analysis are considered during project setup. The *encoding of review methodology* is in progress and requires documentation.

..
    TODO : cover differences between review types in setup/validation

Roadmap
-----------------------------------------------------------------

- The goal is to release new versions on a bi-monthly basis.
- Current focus: on the data management and integration with Git.
- Once CoLRev has matured, UIs should make it accessible to a broader user base.

..
    Once CoLRev has matured, UIs should make it accessible to a broader user base. CoLRev is the result of intense prototyping, research and development. We use it for our own projects and believe it is ready to be released - after all, git ensures that your work is never lost.

    Focused on development towards maturity
    Not focused on features

    Design a status page (what's unit/user tested/documented/recommended for testing/users with technical experience/generally)
    Ampel / Test coverage



Releases: Upcoming
-----------------------------------------------------------------

- Extension colrev_cml_assistant
- Templates for review_types
- Synchronous session support
- `Additional SearchSources <https://github.com/CoLRev-Environment/colrev/issues/106>`_

Release: v0.9.0 (expected 06-01)
-----------------------------------------------------------------

- Advanced validation options (e.g., for prescreen)
- R package

Release: v0.8.0 (2023-03-26)
-----------------------------------------------------------------

- Unit tests (coverage 70%)
- User tests and numerous changes
- Documentation and development status
- Data endpoint for bibliography exports
- Github-actions setup for colrev and colrev repositories
- Docker dependency is now optional
- Replace OpenSearch by sqlite
- Update the SearchSource interface

Release: v0.7.0 (2023-01-16)
-----------------------------------------------------------------

- Unit tests
- User tests
- Package management

Release: v0.6.0 (2022-10-12)
-----------------------------------------------------------------

- Architecture refactoring

Release: v0.5.0 (2022-06-28)
-----------------------------------------------------------------

- Data provenance model
- Extensible endpoints (search, prep, prescreen, pdf-get, pdf-prep, screen, data)
- Prescreen scope
- Documentation
- Push/pull (including corrections), sync, validate, service operations

Release: v0.4.0 (2022-04-06)
------------------------------------------------------

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

Release: v0.3.0 (2022-02-06)
------------------------------------------------------

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

Release: v0.2.0 (2021-11-12)
------------------------------------------------------

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

Release: v0.1.0 (2021-05-08)
------------------------------------------------------

- First version of the pipeline, including `status`, `reformat_bibliography`, `trace_entry`, `trace_hash_id`, `combine_individual_search_results`, `cleanse_records`, `screen_sheet`, `screen_1`, `acquire_pdfs`, `screen_2`, `data_sheet` and `data_pages`
- Environment setup including `Dockerfile` and `Makefiles`
