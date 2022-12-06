.. _Search:

colrev search
==================================

:program:`colrev search` retrieves search results from

- Crossref
- DBLP
- CoLRev projects (local or online)
- Directories containing PDFs
- Curated metadata repositories (through the local index)

.. code:: bash

	colrev search [options]

.. code:: bash

    Examples:

    colrev search -a '{"endpoint": "colrev_built_in.crossref","search_parameters": {"query": "digital+platform"}}'

    colrev search -a '{"endpoint": "colrev_built_in.dblp","search_parameters": {"scope": {"venue_key": "journals/dss", "journal_abbreviation": "Decis. Support Syst."}}}'

    colrev search -a '{"endpoint": "colrev_built_in.colrev_project","search_parameters": {"url": "/home/projects/review9"}}'

    colrev search -a '{"endpoint": "colrev_built_in.pdf_backward_search","search_parameters": {"scope": {"colrev_status": "rev_included|rev_synthesized"}}}'

    colrev search -a '{"endpoint": "colrev_built_in.colrev_project","search_parameters": {"url": "/home/projects/review9"}}'

    colrev search -a '{"endpoint": "colrev_built_in.local_index","search_parameters": {"query": "digital AND (platform OR market)"}}'

    colrev search -a '{"endpoint": "colrev_built_in.pdfs_dir","search_parameters": {"scope": {"path": "/home/journals/PLOS"}, "sub_dir_pattern": "volume_number", "journal": "PLOS One"}}'


.. option:: --selected TEXT

    Run selected search

Note:

- The query syntax is based on `sqlite <https://www.sqlite.org/lang.html>`_ (pandasql). You can test and debug your queries `here <https://sqliteonline.com/>`_.
- Journal ISSNs for crossref searches can be retrieved from the `ISSN Portal <https://portal.issn.org/>`_
