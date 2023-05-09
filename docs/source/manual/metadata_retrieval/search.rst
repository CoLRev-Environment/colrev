.. _Search:

colrev search
==================================

.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 12pt
   :target: https://colrev.readthedocs.io/en/latest/foundations/dev_status.html
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 12pt
   :target: https://colrev.readthedocs.io/en/latest/foundations/dev_status.html
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 12pt
   :target: https://colrev.readthedocs.io/en/latest/foundations/dev_status.html

In the ``colrev search`` operation, records (metadata) are retrieved and stored in the ``data/search`` directory. Records retrieved in the search are implicitly in the ``md_retrieved`` status. Search results are retrieved from different sources:

- Search results can be obtained automatically from different APIs as explained below.
- In addition, search results that are obtained manually from academic databases can be added to the ``data/search`` directory.

When running ``colrev search`` iteratively, the unique IDs are used to determine whether search results (individual records) already exist or whether they are new. New records are added and existing records are updated in the search source and the main records (if the metadata changed). This is useful when forthcoming journal papers are assigned to a specific volume/issue, when papers are retracted, or when metadata changes in a CoLRev curation.

Search parameters for each source are stored in the ``settings.json`` (the ``settings.sources`` section).
When records are linked to metadata repositories in the ``prep`` operation, corresponding metadata will be stored in additional metadata SearchSources (with ``md_*`` prefix).
Such metadata SearchSources are also updated in the search. They do not retrieve additional records and they are excluded from statistics such as those displayed in the ``colrev status`` or PRISMA flow charts.

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

    colrev search -a colrev.crossref:"https://search.crossref.org/?q=+microsourcing&from_ui=yes"
    colrev search -a colrev.dblp:"https://dblp.org/search?q=microsourcing"
    colrev search -a colrev.ais_library:"https://aisel.aisnet.org/do/search/?q=microsourcing&start=0&context=509156&facet="
    colrev search -a colrev.pdf_backward_search:default
    colrev search -a colrev.open_citations_forward_search:default
    colrev search -a colrev.local_index:"title LIKE '%dark side%'"
    colrev search -a colrev.colrev_project:"https://github.com/CoLRev-Environment/example"
    colrev search -a /home/user/references.bib

..
    Examples:
    .. colrev search -a colrev.crossref:jissn=19417225

    colrev search -a '{"endpoint": "colrev.dblp","search_parameters": {"scope": {"venue_key": "journals/dss", "journal_abbreviation": "Decis. Support Syst."}}}'

    colrev search -a '{"endpoint": "colrev.colrev_project","search_parameters": {"url": "/home/projects/review9"}}'

    colrev search -a '{"endpoint": "colrev.colrev_project","search_parameters": {"url": "/home/projects/review9"}}'

    colrev search -a '{"endpoint": "colrev.pdfs_dir","search_parameters": {"scope": {"path": "/home/journals/PLOS"}, "sub_dir_pattern": "volume_number", "journal": "PLOS One"}}'

SearchSources are used to keep a trace to the file or API the records originate (using the ``colrev_origin`` field).
This makes iterative searches more efficient.
When search results are added, we apply heuristics to identify their source. Knowing the source matters:

- When you run ``colrev search`` (or ``colrev search --udpate``), the metadata will be updated automatically (e.g., when a paper was retracted, or when fields like citation counts or URLs have changed).
- In addition, some SearchSources have unique data quality issues (e.g., incorrect use of fields or record types). Each source can have its unique preparation steps, and restricting the scope of preparation rules allows us to prevent side effects on other records originating from high-quality sources.

The following SearchSources are covered (additional ones are on the `SearchSource roadmap <https://github.com/CoLRev-Environment/colrev/issues/106>`_):

.. datatemplate:json:: ../../../../colrev/template/package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Identifier", "package_endpoint_identifier"), ("SearchSource packages", "short_description"), ("Status", "status_linked")],
        data['search_source'],
        title='',
        columns=[25,55,20]
        ) }}

Notes:
    - Other SearchSources are handled by "Unknown Source"
    - NA: Not applicable
    - For updates, fixes, and additions of SearchSources, check the `Github issues <https://github.com/CoLRev-Environment/colrev/labels/search_source>`_.
