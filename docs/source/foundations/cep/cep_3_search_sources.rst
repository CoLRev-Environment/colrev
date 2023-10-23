CEP 3: SearchSources
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

:any:`summary`
:any:`search types`
:any:`search parameters`


.. _summary:

Summary
----------------

The SearchSources are an integral part of CoLRev.
They support different steps depending on whether the SearchSource supports file-based exports of search results and/or API-based searches:

Knowing the source matters:

- When you run ``colrev search`` (or ``colrev search --udpate``), the metadata will be updated automatically (e.g., when a paper was retracted, or when fields like citation counts or URLs have changed).
- In addition, some SearchSources have unique data quality issues (e.g., incorrect use of fields or record types). Each source can have its unique preparation steps, and restricting the scope of preparation rules allows us to prevent side effects on other records originating from high-quality sources.

SearchSources are used to keep a trace to the file or API the records originate (using the ``colrev_origin`` field).
This makes iterative searches more efficient.
When running ``colrev search`` iteratively, the unique IDs are used to determine whether search results (individual records) already exist or whether they are new. New records are added and existing records are updated in the search source and the main records (if the metadata changed). This is useful when forthcoming journal papers are assigned to a specific volume/issue, when papers are retracted, or when metadata changes in a CoLRev curation.

Records retrieved in the search are implicitly in the ``md_retrieved`` status.


TODO : add lists of all SearchSources supporting DB / API / ... searches

Generally for automated searches: run "colrev search -a SOURCE_NAME" to add search and query.

TODO : where are queries stored (list format + file)


File-based exports:

- for new search results files, the `heuristics` method identifies the original source (such as Web of Science)

API-based searches:

- the `add_endpoint` method is used to (interactively) specify parameters of a new API-based search
- the `run_search` method retrieves results and stores them in a search feed
- the `get_masterdata` method can be used in the prep operation to link records from the search source to existing records in the dataset

Both file-based and API-based searches:

- the `load` method can read different file formats and fix formatting errors specific to the search source
- the `prepare` method applies SearchSource-specific rules



.. _search types:

Search types
------------------------------

.. _search parameters:

Search parameters
------------------------------

Search parameters are stored in the `SearchSource.search_parameters` field and standardized as follows::

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

    TODO : check crossref __YEAR_SCOPE_REGEX

TODO
------------------

- SearchSource-specific namespaces (see CEP2)
- Experimental/mature: parameters must be validated (before adding source and before running search), tests, docs implemented, unique_ids should be tested/recommended
- settings should implement a get_query_dict() (similar to get_query())
- print statistics after DB search (validate new file against file in history)

.. list-table:: Load
   :widths: 40 60
   :header-rows: 1

   * - Format
     - Utility
   * - BibTeX
     - :doc:`colrev.ops.load_utils_bib </dev_docs/_autosummary/colrev.ops.load_utils_bib>`
   * - CSV/XLSX
     - :doc:`colrev.ops.load_utils_table </dev_docs/_autosummary/colrev.ops.load_utils_table>`
   * - ENL
     - :doc:`colrev.ops.load_utils_enl </dev_docs/_autosummary/colrev.ops.load_utils_enl>`
   * - Markdown (reference section as unstructured text)
     - :doc:`colrev.ops.load_utils_md </dev_docs/_autosummary/colrev.ops.load_utils_md>`
   * - NBIB
     - :doc:`colrev.ops.load_utils_nbib </dev_docs/_autosummary/colrev.ops.load_utils_nbib>`
   * - RIS
     - :doc:`colrev.ops.load_utils_ris </dev_docs/_autosummary/colrev.ops.load_utils_ris>`


TODO : implement load_utils for csl/xml/json...

Development roadmap:
- SearchSource-specific translation of search queries
- Retrieval of PDFs
- Coverage reports
