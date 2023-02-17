.. _Search:

colrev search
==================================

In the :program:`colrev search` operation, search results are obtained from different sources:

- Search results can be obtained automatically from different APIs as explained below.
- In addition, search results that are obtained manually from academic databases can be added to the `data/search` directory.

Search parameters for each source are stored in the settings.sources section.

..
    TODO :

    - mention how to add papers suggested by colleagues (as recommended by methodologists)
    - Illustrate the different options: API (Crossref, Pubmed, ...), reference files (bibtex, enl, ris, ...), spreadsheets (xlsx, csv, ...), papers (PDFs), lists of references (md file or PDF reference sections), local-index, other colrev projects
    - types of sources should correspond to SearchSourceType
    - Per default, API-based searches only retrieve/add the most recent records. A full search and update of all records can be started with the --rerun flag.
    - add an illustration of sources (how they enable active flows)

.. code-block:: bash

    colrev search [options]

    # Add a new search source
    colrev search --add TEXT

    # Run search for a selected source
    colrev search --selected TEXT


Examples:

.. code-block:: bash

    colrev search -a "https://search.crossref.org/?q=+microsourcing&from_ui=yes"
    colrev search -a "https://dblp.org/search?q=microsourcing"
    colrev search -a "https://aisel.aisnet.org/do/search/?q=microsourcing&start=0&context=509156&facet="
    colrev search -a backward-search
    colrev search -a forward-search
    colrev search -a "local_index:title LIKE '%dark side%'"

..
    Examples:
    .. colrev search -a colrev_built_in.crossref:jissn=19417225

    colrev search -a '{"endpoint": "colrev_built_in.dblp","search_parameters": {"scope": {"venue_key": "journals/dss", "journal_abbreviation": "Decis. Support Syst."}}}'

    colrev search -a '{"endpoint": "colrev_built_in.colrev_project","search_parameters": {"url": "/home/projects/review9"}}'

    colrev search -a '{"endpoint": "colrev_built_in.colrev_project","search_parameters": {"url": "/home/projects/review9"}}'

    colrev search -a '{"endpoint": "colrev_built_in.pdfs_dir","search_parameters": {"scope": {"path": "/home/journals/PLOS"}, "sub_dir_pattern": "volume_number", "journal": "PLOS One"}}'

SearchSources are used to keep a trace to the file or API the records originate (using the `colrev_origin` field).
This makes iterative searches more efficient.
When search results are added, we apply heuristics to identify their source. Knowing the source matters:

- When you run `colrev search` (or `colrev search --udpate`), the metadata will be updated automatically (e.g., when a paper was retracted, or when fiels like citation counts or urls have changed).
- In addition, some SearchSources have unique data quality issues (e.g., incorrect use of fields or record types). Each source can have its unique preparation steps, and restricting the scope of preparation rules allows us to prevent side effects on other records originating from high-quality sources.

The following SearchSources are covered (additional ones are on the `SearchSource roadmap <https://github.com/CoLRev-Ecosystem/colrev/issues/106>`_):

.. datatemplate:json:: ../../../../colrev/template/package_endpoints.json

    {{ make_list_table_from_mappings(
        [("SearchSource", "link"), ("Identifier", "package_endpoint_identifier"), ("Heuristics", "heuristic"), ("API search", "api_search"), ("Search instructions", "instructions")],
        data['search_source'],
        title='',
        ) }}

Notes:
    - Other SearchSources are handled by "Unknown Source"
    - Heuristics enable automated detection of the SearchSources upon load
    - ONI: Output not identifiable (e.g., BibTeX/RIS files lack unique features to identify the original SearchSource)
    - NA: Not applicable
    - For updates, fixes, and additions of SearchSources, check the `Github issues <https://github.com/CoLRev-Ecosystem/colrev/labels/search_source>`_.
