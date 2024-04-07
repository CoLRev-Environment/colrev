CEP003 - SearchSources
====================================

+----------------+------------------------------+
| **Author**     | Gerit Wagner                 |
+----------------+------------------------------+
| **Status**     | Draft                        |
+----------------+------------------------------+
| **Created**    | 2023-10-09                   |
+----------------+------------------------------+
| **Discussion** | TODO : link-to-issue         |
+----------------+------------------------------+

Table of contents
------------------------------

- :any:`summary`
- :any:`search_source_data`
- :any:`methods`
- :any:`documentation`
- :any:`tests`
- :any:`maturity`
- :any:`roadmap`

.. _summary:

Abstract
------------------------------

The SearchSources are an integral part of CoLRev.
Knowing the source matters because many aspects are source-specific, including:

- instructions for manual or automated retrieval and available search types
- restrictions and bugs of data sources
- record identifiers for incremental search updates
- field definitions, including the associated mapping to the standard fields and namespaced fields
- metadata preparation
- metadata correction
- correction paths (if any)

SearchSource packages (classes): instances and methods

.. _search_source_data:

SearchSource data
------------------------------

SearchSources metadata in the settings::

      {
        "endpoint": "colrev.crossref",
        "search_type": "API",
        "search_parameters": {
            "query": "microsourcing"
        },
        "comment": "",
        "filename": "data/search/CROSSREF.bib"
    }

The endpoint can be any :doc:`SearchSource package </resources/package_index>`.

The **search_type** can be DB, API, BACKWARD, FORWARD, TOC, OTHER, FILES, or MD. (TBD: duplicate documentation from retrieval/search?)

**TODO/TBD: update based on search-query**

**Search parameters** are stored in the `SearchSource.search_parameters` field and standardized as follows::

    "query": {
            1: "term1",
            2: "term2",
            3: "1 OR 2"
            }
    scope: {
            "start_date": 2000,
            "end_date": 2023,
            "language": ["en"],
            "outlet": {"journal": ["Nature"], "booktitle": ["ICIS"]},
            "issn": ["1234-5678"],
            }

The **comment** is optional.

The **filename** points to the file in which retrieved records are stored (starts with `data/search/`).

- SearchSources are used to keep a trace to the file or API the records originate (using the ``colrev_origin`` field). This makes iterative searches more efficient. When running ``colrev search`` iteratively, the unique IDs are used to determine whether search results (individual records) already exist or whether they are new. New records are added and existing records are updated in the search source and the main records (if the metadata changed). This is useful when forthcoming journal papers are assigned to a specific volume/issue, when papers are retracted, or when metadata changes in a CoLRev curation.

SearchSources data in the raw data file (`filename` field in the metadata)

- Original field names from the source should not be changed (e.g., use `journal-title` instead of CoLRev's standard `journal` field (CEP002))
- After storing results in the file, SearchSources should map the original field names to CoLRev standard fields (CEP002).

Data in the main records.bib

- The `colrev_origin` field is used to link records loaded in the records.bib to the original records in the raw data files.

TODO:

- raw data (+updates)
- origin generation (for data lineage / provenance) - unique_identifiers or incremental IDs
- Query file implicitly +_query.txt or required as search_parameters?
- Standardization of search_parameters / where are queries stored (list format + file)
- Settings should implement a get_query_dict() (similar to get_query())
- check crossref __YEAR_SCOPE_REGEX

.. _methods:

SearchSource methods
-------------------------------

**search add_endpoint**

- Generally for automated searches: run "colrev search -a SOURCE_NAME" to add search and query.
- for DB searches (new search results files), the `heuristics` method identifies the original source (such as Web of Science)

**search** (manual or automated)

- When you run ``colrev search`` (or ``colrev search --udpate``), the metadata will be updated automatically (e.g., when a paper was retracted, or when fields like citation counts or URLs have changed).
- the `run_search` method retrieves results and stores them in a search feed
- Records retrieved in the search are implicitly in the ``md_retrieved`` status.
- print statistics after DB search
- DB searches: validate new file against file in history

**load**

- Transition from md_retrieved to md_imported
- The `load` utilities can read different file formats and fix formatting errors specific to the search source
- Original field names should be mapped in the SearchSource (not the load utility)

.. list-table:: Load utilities
   :widths: 40 60
   :header-rows: 1

   * - Format
     - Utility
   * - BibTeX
     - :doc:`colrev.loader.bib </dev_docs/_autosummary/colrev.loader.bib>`
   * - CSV/XLSX
     - :doc:`colrev.loader.table </dev_docs/_autosummary/colrev.loader.table>`
   * - ENL
     - :doc:`colrev.loader.enl </dev_docs/_autosummary/colrev.loader.enl>`
   * - Markdown (reference section as unstructured text)
     - :doc:`colrev.loader.md </dev_docs/_autosummary/colrev.loader.md>`
   * - NBIB
     - :doc:`colrev.loader.nbib </dev_docs/_autosummary/colrev.loader.nbib>`
   * - RIS
     - :doc:`colrev.loader.ris </dev_docs/_autosummary/colrev.loader.ris>`

**TODO : implement loader for csl/xml/json...**

- The `load` method also checks whether field names were mapped to the standardized field names (in `constants`)

**prep**

- Transition from md_imported to md_prepared/md_needs_manual_preparation/rev_prescreen_excluded
- the `prepare` method applies SearchSource-specific rules. Some SearchSources have unique data quality issues (e.g., incorrect use of fields or record types). Each source can have its unique preparation steps, and restricting the scope of preparation rules allows us to prevent side effects on other records originating from high-quality sources.
- the `get_masterdata` method can be used in the prep operation to link records from the search source to existing records in the dataset

.. _documentation:

SearchTypes
--------------------------

API searches
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Search results are retrieved and stored using functionality provided by `SearchAPIFeed`.
Currently, results are stored in BibTeX format.
The `load` operation must ensure that field names are mapped to standard namespaces.

Rationale:

- Independent of retrieval format (JSON/XML/...)
- Methods available to add and update records

Alternative (currently discussed): Storing raw data from the API (JSON/XML/...)

- Separate implementations would be needed for JSON/XML/...
- Records should be sorted in "oldest first" order to maintain a transparent and readable history
- Storing raw data would make it easier to identify schema changes
- Multiple files would be retrieved for a SearchSource, potentially requiring sub-folders


Documentation
------------------------------

- TODO : documentation standards

.. _tests:

Tests
------------------------------

- Standardized test data

.. _maturity:

Maturity
------------------------------

- Experimental/mature: parameters must be validated (before adding source and before running search), tests, docs implemented, unique_ids should be tested/recommended

.. _roadmap:

Development roadmap
----------------------------

- SearchSource-specific translation of search queries
- API search-query supercharging
- Retrieval of PDFs
- Coverage reports
- Options for load (e.g., selection or full metadata)
