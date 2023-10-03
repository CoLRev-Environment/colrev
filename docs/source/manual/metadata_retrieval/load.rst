colrev load
==================================

In the ``colrev load`` operation, search results are added to the main records file following a three-step procedure:

1. For each search results file (in the ``data/search`` directory), the SearchSource and search parameters are validated. For API-based searches, the SearchSource and search parameters are already recorded in the ``settings.json``. For search result files, `heuristics <https://colrev.readthedocs.io/en/latest/foundations/extensions.html#colrev.env.package_manager.SearchSourcePackageEndpointInterface.heuristic>`_ are used to identify the SearchSource (e.g., GoogleScholar or Web of Science) and users are asked to provide the corresponding search parameters, which are stored in the ``settings.json``.

2. The SearchSources convert different filetypes to BiBTeX (see table below) and to apply fixes ensuring consistent field names and values.

3. Records from the search result files are identified based on unique `origin IDs` and added to the main records file (``data/records.bib``). Additional metadata fields are created upon import, including the ``colrev_status``, the ``colrev_origin``, as well as ``colrev_masterdata_provenance`` and ``colrev_data_provenance``. The provenance fields indicate whether the record has quality defects (such as missing fields).

.. code:: bash

	colrev load [options]

Notes on the load conversion:

- Structured formats (csv, xlsx) are imported using standard Python libraries
- Semi-structured formats are imported using bibtexparser or the zotero-translation services (see `supported import formats <https://www.zotero.org/support/kb/importing_standardized_formats>`_)
- Unstructured formats are imported using Grobid (lists of references and pdf reference lists)
