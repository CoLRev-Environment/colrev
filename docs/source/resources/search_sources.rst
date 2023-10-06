SearchSources
==================================

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

TODO:

- SearchSource-specific translation of search queries
- Retrieval of PDFs
- Coverage reports
- SearchSource-specific namespaces
