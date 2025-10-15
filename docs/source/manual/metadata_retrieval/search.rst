colrev search
==================================

.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 12pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 12pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 12pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html

In the ``colrev search`` operation, the SearchSource is added to the project settings, and record metadata are retrieved.
SearchSources keep track of the associated queries, as well as the search results files in the `data/search` directory (see :doc:`SearchSources </foundations/cep/cep003_search_sources>`).
Two steps are necessary to add a SearchSource and run a search:

.. code-block:: bash

    # Add a new SearchSource interactively
    colrev search --add

    # Run search for all SearchSources in the settings
    colrev search

    # Run search for selected SearchSources
    colrev search --select

..
    For search result files, `heuristics <../../dev_docs/packages/package_base_classes.html#colrev.package_manager.package_base_classes.SearchSourcePackageBaseClass.heuristic>`_ are used to identify the SearchSource (e.g., GoogleScholar or Web of Science) and users are asked to provide the corresponding search parameters, which are stored in the ``settings.json``.

Updating the search is very easy: simply run `colrev search` again. API searches will be updated automatically, and instructions will be given to update DB searches.

The following table provides an overview of the different types of SearchSources, linking to the list of SearchSources below.
The development of additional SearchSources is tracked in the `SearchSource roadmap <https://github.com/CoLRev-Environment/colrev/issues/106>`_).

..
    https://www.tablesgenerator.com/text_tables#

+----------+--------------------------------------------------------------------------------------------------------+---------------------+-----------+
| Type     | Description                                                                                            | Retrieval           | Query     |
+----------+--------------------------------------------------------------------------------------------------------+---------------------+-----------+
| DB       | Traditional search in an academic database:                                                            | Manual              | Mandatory |
|          |                                                                                                        |                     |           |
|          | - Manually execute the search and export results from database                                         |                     |           |
|          | - Add search results to data/search                                                                    |                     |           |
|          | - Add query to data/search                                                                             |                     |           |
|          | - Run colrev load (a heuristic method automatically identifies the database)                           |                     |           |
|          |                                                                                                        |                     |           |
|          | See :ref:`overview of DB searches <db searches>`                                                       |                     |           |
+----------+--------------------------------------------------------------------------------------------------------+---------------------+-----------+
| API      | Automated API search:                                                                                  | Automated           | Mandatory |
|          |                                                                                                        |                     |           |
|          | - Run colrev -a colrev.XXX to interactively add the SearchSource including the query                   |                     |           |
|          | - Run colrev search to automatically retrieve records based on query                                   |                     |           |
|          | - Run colrev search again for new search iterations and updates of record metadata                     |                     |           |
|          |                                                                                                        |                     |           |
|          | See :ref:`overview of API searches <api searches>`                                                     |                     |           |
+----------+--------------------------------------------------------------------------------------------------------+---------------------+-----------+
| BACKWARD | Backward citation search:                                                                              | Automated or manual | Optional  |
|          |                                                                                                        |                     |           |
|          | - Run colrev -a colrev.XXX to interactively add the SearchSource including parameters (if any)         |                     |           |
|          | - Run colrev search to execute backward search                                                         |                     |           |
|          | - Manual addition of search results is possible                                                        |                     |           |
|          |                                                                                                        |                     |           |
|          | See :ref:`overview of BACKWARD searches <backward searches>`                                           |                     |           |
+----------+--------------------------------------------------------------------------------------------------------+---------------------+-----------+
| FORWARD  | Forward citation search:                                                                               | Automated or manual | Optional  |
|          |                                                                                                        |                     |           |
|          | - Run colrev -a colrev.XXX to interactively add the SearchSource including parameters (if any)         |                     |           |
|          | - Run colrev search to execute forward search                                                          |                     |           |
|          | - Manual addition of search results is possible                                                        |                     |           |
|          |                                                                                                        |                     |           |
|          | See :ref:`overview of FORWARD searches <forward searches>`                                             |                     |           |
+----------+--------------------------------------------------------------------------------------------------------+---------------------+-----------+
| TOC      | Table-of-content search:                                                                               | Automated or manual | Mandatory |
|          |                                                                                                        |                     |           |
|          | - Run colrev -a colrev.XXX to interactively add the SearchSource including parameters                  |                     |           |
|          | - Run colrev search to retrieve all records from the selected journal(s) or conference(s)              |                     |           |
|          |                                                                                                        |                     |           |
|          | See :ref:`overview of TOC searches <toc searches>`                                                     |                     |           |
+----------+--------------------------------------------------------------------------------------------------------+---------------------+-----------+
| OTHER    | Non-systematic lookup searches or complementary searches:                                              | Manual              | Optional  |
|          |                                                                                                        |                     |           |
|          | - Papers suggested by colleagues, or serendipituous look-up searches                                   |                     |           |
|          | - Add search results to data/search                                                                    |                     |           |
|          | - Run colrev load                                                                                      |                     |           |
|          |                                                                                                        |                     |           |
|          | See :ref:`overview of OTHER searches <other searches>`                                                 |                     |           |
+----------+--------------------------------------------------------------------------------------------------------+---------------------+-----------+
| FILES    | Extraction of metadata from files:                                                                     | Automated           | Optional  |
|          |                                                                                                        |                     |           |
|          | - Run colrev -a colrev.XXX to interactively add the SearchSource including parameters (if any)         |                     |           |
|          | - Metadata is extracted from files (e.g., PDFs) in a selected directory (see colrev.files_dir)         |                     |           |
|          |                                                                                                        |                     |           |
|          | See :ref:`overview of FILES searches <file searches>`                                                  |                     |           |
+----------+--------------------------------------------------------------------------------------------------------+---------------------+-----------+
| MD       | Metadata SearchSource:                                                                                 | Automated           | NA        |
|          |                                                                                                        |                     |           |
|          | - Record metadata are retrieved to **amend existing records** as part of the prep operation            |                     |           |
|          | - No additional records are added                                                                      |                     |           |
|          |                                                                                                        |                     |           |
|          | See :ref:`overview of MD searches <md searches>`                                                       |                     |           |
+----------+--------------------------------------------------------------------------------------------------------+---------------------+-----------+

..
    TODO :

    - mention how to add papers suggested by colleagues (as recommended by methodologists)
    - Illustrate the different options: API (Crossref, Pubmed, ...), reference files (bibtex, enl, ris, ...), spreadsheets (xlsx, csv, ...), papers (PDFs), lists of references (md file or PDF reference sections), local-index, other colrev projects
    - types of sources should correspond to SearchSourceType
    - Per default, API-based searches only retrieve/add the most recent records. A full search and update of all records can be started with the --rerun flag.
    - add an illustration of sources (how they enable active flows)

..
    Examples:

    .. code-block:: bash

        colrev search -a colrev.crossref -p "https://search.crossref.org/?q=+microsourcing&from_ui=yes"
        colrev search -a colrev.dblp -p "https://dblp.org/search?q=microsourcing"
        colrev search -a colrev.ais_library -p "https://aisel.aisnet.org/do/search/?q=microsourcing&start=0&context=509156&facet="
        colrev search -a colrev.pdf_backward_search
        colrev search -a colrev.open_citations_forward_search
        colrev search -a colrev.local_index -p "title LIKE '%dark side%'"
        colrev search -a colrev.colrev_project -p "url=https://github.com/CoLRev-Environment/example"
        colrev search -a colrev.unknown_source -p /home/user/references.bib

    Examples:
    .. colrev search -a colrev.crossref:jissn=19417225

    colrev search -a '{"endpoint": "colrev.dblp","search_parameters": {"scope": {"venue_key": "journals/dss", "journal_abbreviation": "Decis. Support Syst."}}}'

    colrev search -a '{"endpoint": "colrev.colrev_project","search_parameters": {"url": "/home/projects/review9"}}'

    colrev search -a '{"endpoint": "colrev.colrev_project","search_parameters": {"url": "/home/projects/review9"}}'

    colrev search -a '{"endpoint": "colrev.files_dir","search_parameters": {"scope": {"path": "/home/journals/PLOS"}, "sub_dir_pattern": "volume_number", "journal": "PLOS One"}}'

.. _db searches:

DB searches
--------------------

.. datatemplate:json:: ../search_source_types.json

    {{ make_list_table_from_mappings(
        [("SearchSource packages", "short_description"), ("Identifier", "package_endpoint_identifier"), ("Status", "status")],
        data['DB'],
        title='',
        columns=[55,25,20]
        ) }}

.. _api searches:

API searches
--------------------

.. datatemplate:json:: ../search_source_types.json

    {{ make_list_table_from_mappings(
        [("SearchSource packages", "short_description"), ("Identifier", "package_endpoint_identifier"), ("Status", "status")],
        data['API'],
        title='',
        columns=[55,25,20]
        ) }}

.. _toc searches:

TOC searches
--------------------

.. datatemplate:json:: ../search_source_types.json

    {{ make_list_table_from_mappings(
        [("SearchSource packages", "short_description"), ("Identifier", "package_endpoint_identifier"), ("Status", "status")],
        data['TOC'],
        title='',
        columns=[55,25,20]
        ) }}

.. _backward searches:

BACKWARD_SEARCH searches
----------------------------------------

.. datatemplate:json:: ../search_source_types.json

    {{ make_list_table_from_mappings(
        [("SearchSource packages", "short_description"), ("Identifier", "package_endpoint_identifier"), ("Status", "status")],
        data['BACKWARD_SEARCH'],
        title='',
        columns=[55,25,20]
        ) }}

.. _forward searches:

FORWARD_SEARCH searches
----------------------------------------

.. datatemplate:json:: ../search_source_types.json

    {{ make_list_table_from_mappings(
        [("SearchSource packages", "short_description"), ("Identifier", "package_endpoint_identifier"), ("Status", "status")],
        data['FORWARD_SEARCH'],
        title='',
        columns=[55,25,20]
        ) }}

.. _file searches:

FILES searches
-------------------

.. datatemplate:json:: ../search_source_types.json

    {{ make_list_table_from_mappings(
        [("SearchSource packages", "short_description"), ("Identifier", "package_endpoint_identifier"), ("Status", "status")],
        data['FILES'],
        title='',
        columns=[55,25,20]
        ) }}


.. _other searches:

OTHER searches
--------------------

.. datatemplate:json:: ../search_source_types.json

    {{ make_list_table_from_mappings(
        [("SearchSource packages", "short_description"), ("Identifier", "package_endpoint_identifier"), ("Status", "status")],
        data['OTHER'],
        title='',
        columns=[55,25,20]
        ) }}


.. _md searches:

MD searches
--------------------

.. datatemplate:json:: ../search_source_types.json

    {{ make_list_table_from_mappings(
        [("SearchSource packages", "short_description"), ("Identifier", "package_endpoint_identifier"), ("Status", "status")],
        data['MD'],
        title='',
        columns=[55,25,20]
        ) }}
