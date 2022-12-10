.. _Search:

colrev search
==================================


:program:`colrev search` retrieves search results from different `SearchSources <../6_sources.html>`_.

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
