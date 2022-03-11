
Search
==================================

:program:`colrev search` retrieves search results from

- Crossref
- DBLP
- CoLRev projects (local or online)
- Directories containing PDFs
- Curated metadata repositories (through the local index)

.. code:: bash

	colrev search [options]

.. option:: --add TEXT

    Add a new search query.

.. code:: bash

    Examples:

    colrev search -a "RETRIEVE * FROM crossref, dblp WHERE Digital AND Platform"

    colrev search -a "RETRIEVE * FROM dblp SCOPE venue_key='journals/dss' AND journal_abbreviation='Decis. Support Syst.'"

    colrev search -a "RETRIEVE * FROM project SCOPE url='/home/gerit/ownCloud/data/theory'"

    colrev search -a "RETRIEVE * FROM backward_search"

    colrev search -a "RETRIEVE * FROM index WHERE lower(fulltext) like '%digital platform%'"

.. option:: --selected TEXT

    Run selected search
