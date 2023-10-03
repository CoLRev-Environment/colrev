SearchSources
==================================

The SearchSources are an integral part of CoLRev.
They support different steps depending on whether the SearchSource supports file-based exports of search results and/or API-based searches:

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
