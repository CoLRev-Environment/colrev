.. _Search:

colrev search
==================================


- mention how to add papers suggested by colleagues (as recommended by methodologists)
- Illustrate the different options: API (Crossref, Pubmed, ...), reference files (bibtex, enl, ris, ...), spreadsheets (xlsx, csv, ...), papers (PDFs), lists of references (md file or PDF reference sections), local-index, other colrev projects
- types of sources should correspond to SearchSourceType

:program:`colrev search` retrieves search results from different `SearchSources <../6_sources.html>`_.

.. code:: bash

	colrev search [options]

.. code:: bash

    Short-form examples:

    colrev search -a https://dblp.org/search?q=microsourcing

    colrev search -a https://search.crossref.org/?q=+microsourcing&from_ui=yes

    colrev search -a backward-search

    Examples:

    colrev search -a '{"endpoint": "colrev_built_in.crossref","search_parameters": {"query": "digital+platform"}}'

    colrev search -a '{"endpoint": "colrev_built_in.dblp","search_parameters": {"scope": {"venue_key": "journals/dss", "journal_abbreviation": "Decis. Support Syst."}}}'

    colrev search -a '{"endpoint": "colrev_built_in.colrev_project","search_parameters": {"url": "/home/projects/review9"}}'

    colrev search -a '{"endpoint": "colrev_built_in.pdf_backward_search","search_parameters": {"scope": {"colrev_status": "rev_included|rev_synthesized"}}}'

    colrev search -a '{"endpoint": "colrev_built_in.colrev_project","search_parameters": {"url": "/home/projects/review9"}}'

    colrev search -a '{"endpoint": "colrev_built_in.local_index","search_parameters": {"query": {"simple_query_string": {"query": "microsourcing"}}}}'

    colrev search -a '{"endpoint": "colrev_built_in.pdfs_dir","search_parameters": {"scope": {"path": "/home/journals/PLOS"}, "sub_dir_pattern": "volume_number", "journal": "PLOS One"}}'


.. option:: --selected TEXT

    Run selected search
