CEP003 - SearchSources
====================================

+----------------+--------------------------------------------------------------------+
| **Author**     | Gerit Wagner                                                       |
+----------------+--------------------------------------------------------------------+
| **Status**     | Draft                                                              |
+----------------+--------------------------------------------------------------------+
| **Created**    | 2023-10-09                                                         |
+----------------+--------------------------------------------------------------------+
| **Discussion** | `issue <https://github.com/CoLRev-Environment/colrev/issues/425>`_ |
+----------------+--------------------------------------------------------------------+

Table of contents
------------------------------

- :any:`summary`
- :any:`search_source_data`
- :any:`methods`
- :any:`documentation`
- :any:`roadmap`
- :any:`references`

.. _summary:

Abstract
------------------------------

SearchSource packages are an essential part of CoLRev.
A SearchSource package is a CoLRev package implementing the `SearchSourcePackageBaseClass <../../dev_docs/packages/package_base_classes.html#colrev.package_manager.package_base_classes.SearchSourcePackageBaseClass>`_, e.g., for data sources like Web of Science, Scopus, or Crossref.
Distinguishing SearchSources matters because many aspects are source-specific, including:

- Available :doc:`search types <../../manual/metadata_retrieval/search>` (API, DB, BACKWARD, FORWARD, TOC, OTHER, FILES, MD)
- Syntax of search queries (e.g., API and DB searches), or instructions for manual retrieval (e.g., DB searches)
- Field definitions of records, including the associated mapping to the standard or namespaced fields (see :doc:`CEP002 <cep002_data_schema>`)
- Unique record identifiers, which are needed for incremental search updates
- Restrictions, bugs, and potential fixes (see Li and Rainer, 2022)
- Paths to have metadata corrected (if any)

SearchSource packages must comply with the `SearchSourcePackageBaseClass <../../dev_docs/packages/package_base_classes.html#colrev.package_manager.package_base_classes.SearchSourcePackageBaseClass>`_ for class and method definitions.

.. _search_source_data:

Settings
------------------------------

SearchSource metadata are stored in the settings.json as follows::

  {
    ...
    "sources": [
        {
            "endpoint": "colrev.crossref",
            "search_type": "API",
            "search_parameters": {
                "query": "microsourcing"
            },
            "comment": "",
            "filename": "data/search/CROSSREF.bib"
        },
        ...
    ],
    ...
  }

- The **endpoint** can be the name of any :doc:`SearchSource package <../../manual/packages>`.
- The **search_type** can be DB, API, BACKWARD, FORWARD, TOC, OTHER, FILES, or MD (as explained in the :doc:`search documentation <../../manual/metadata_retrieval/search>`)
- The **comment** is optional.
- The **filename** points to the file in which retrieved records are stored. It starts with `data/search/`.

Data
------------------------

Data of SearchSources includes records retrieved from an academic database (as an export file), an API, or other sources. Data are stored in the raw data file (`filename` field in the metadata).

For API searches:

- Original field names from the source should not be changed (e.g., use `journal-title` instead of CoLRev's standard `journal` field (:doc:`CEP002 <cep002_data_schema>`))
- After storing results in the file, SearchSources should map the original field names to CoLRev standard fields (:doc:`CEP002 <cep002_data_schema>`).

Records are copied to the main records.bib by the ``load`` method (called by the ``load`` operation).

- The `colrev_origin` field is used to link records loaded in the records.bib to the original records in the raw data files. This field is used to keep a trace to the file or API from which the records originate. This makes iterative searches more efficient. When running ``colrev search`` iteratively, the unique IDs are used to determine whether search results (individual records) already exist or whether they are new. New records are added, and existing records are updated in the search source and the main records (if the metadata changed). This is useful when forthcoming journal papers are assigned to a specific volume/issue, when papers are retracted, or when metadata changes in a CoLRev curation.

.. _methods:

Methods
-------------------------------

..
  TODO: state expected behavior

**heuristic**

- Only for DB searches: the method identifies the original source (such as Web of Science) when new search results files are added.

**search add_endpoint**

- Typically called for automated searches when running "colrev search -a SOURCE_NAME" to add search and query.

**search**

- Records retrieved in the search are implicitly in the ``md_retrieved`` status (when they are not yet added to the main records file).
- API searches:

  - The ``search`` method retrieves results and stores them in a search feed
  - Upon running ``colrev search``, the metadata should be updated automatically (e.g., when a paper was retracted, or when fields like citation counts or URLs have changed).

- Statistics should be printed at the end

**load**

- Records transition from ``md_retrieved`` to ``md_imported`` when they are imported into the main records file (this is done by the ``load`` operation)
- The ``load`` method can apply SearchSource-specific rules. Some SearchSources have unique data quality issues (e.g., incorrect use of fields or record types).
- The ``load`` utilities can read different file formats and fix formatting errors specific to the search source
- Original field names should be mapped in the SearchSource (not the load utility)
- The ``load`` operation checks whether field names were mapped to the standardized field names (in `constants`)

..
  Each source can have its unique preparation steps, and restricting the scope of preparation rules allows us to prevent side effects on other records originating from high-quality sources.

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
   * - JSON
     - :doc:`colrev.loader.json </dev_docs/_autosummary/colrev.loader.json>`
   * - CSL
     - TODO
   * - XML
     - TODO


**prep**

- Records transition from ``md_imported`` to ``md_prepared``, ``md_needs_manual_preparation``, or ``rev_prescreen_excluded``.
- For API searches, source-specific preparation should primarily be handled in the load step.

..
  - the `get_masterdata` method can be used in the prep operation to link records from the search source to existing records in the dataset

.. _documentation:

Standards
------------------------------

API Searches

- Search parameters are stored in the standard JSON-format (Haddaway)
- Queries are validated (upon entry and execution) based on the search-query package
- Before running an API search, users are informed about rate limits, and presented with an indication of the number of results and an estimated runtime
- Users are warned when the API/DB has an overall limit of results
- Number of records retrieved are compared with number of records available in the API/DB

See pubmed-api!

Specifics for SearchTypes
-------------------------------

API searches
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Search results are retrieved and stored using functionality provided by `SearchAPIFeed`.
Results are stored in BibTeX format.
The ``load`` operation must ensure that field names are mapped to standard namespaces.

.. dropdown:: Rationale

  - Independent of retrieval format (JSON/XML/...)
  - Methods available to add and update records

  Alternative (currently discussed): Storing raw data from the API (JSON/XML/...)

  - Separate implementations would be needed for JSON/XML/...
  - Records should be sorted in "oldest first" order to maintain a transparent and readable history
  - Storing raw data would make it easier to identify schema changes
  - Multiple files would be retrieved for a SearchSource, potentially requiring sub-folders

.. _roadmap:

Development roadmap
----------------------------

- Specifics for DB: standard cli-ui interaction and principles for updates (validating the new file against the file in history)
- Documentation standards
- Evolution of database schema and query syntax
- Standardize test data
- Clarify maturity levels: Experimental/mature: parameters must be validated (before adding source and before running search), tests, docs implemented, unique_ids should be tested/recommended
- Integrate search-query package
- Update settings based on the following:

**Search parameters** are stored in the `SearchSource.search_parameters` field and standardized as follows::

    "query": {
            1: "term1",
            2: "term2",
            3: "1 OR 2"
            }
    "scope": {
            "start_date": 2000,
            "end_date": 2023,
            "language": ["en"],
            "outlet": {"journal": ["Nature"], "booktitle": ["ICIS"]},
            "issn": ["1234-5678"],
            }

- Raw data (+updates)
- Origin generation (for data lineage / provenance) - unique_identifiers or incremental IDs
- Query file implicitly +_query.txt or required as search_parameters?
- Standardization of search_parameters / where are queries stored (list format + file)
- Settings should implement a get_query_dict() (similar to get_query())
- Check crossref __YEAR_SCOPE_REGEX


- SearchSource-specific translation of search queries
- API search-query supercharging
- Retrieval of PDFs
- Coverage reports
- Options for load (e.g., selection or full metadata)

.. _references:

References
-----------------------------

Li, Z., & Rainer, A. (2022). Academic search engines: constraints, bugs, and recommendations. In Proceedings of the 13th International Workshop on Automating Test Case Design, Selection and Evaluation (pp. 25-32). doi: 10.1145/3548659.3561310
