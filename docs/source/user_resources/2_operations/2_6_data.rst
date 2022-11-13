.. _Data:

Data extraction and synthesis - data
---------------------------------------------

:program:`colrev data` supports the data extraction, analysis and synthesis. Depending on the type of review, this may involve

- a manuscript-based synthesis
    - structured data extraction (diffs are displayed using `daff <https://github.com/paulfitz/daff>`_ or the `browser extension <https://chrome.google.com/webstore/detail/github-csv-diff/ngpdjmibpbemokfbmapemhpbmgacebhg/>`_)

To select the data format, please consult the best practices for different `types of reviews <./best_practices.html#types-of-literature-reviews>`_.

To set the data format, run any (combination) of the following:

.. code:: bash

    colrev data --add_endpoint MANUSCRIPT
    colrev data --add_endpoint STRUCTURED
    colrev data --add_endpoint PRISMA
    colrev data --add_endpoint ZETTLR
    colrev data --add_endpoint ENDNOTE

Depending on the data format, the :program:`colrev data` command

- adds new records to the manuscript (paper.md, after the <!-- NEW_RECORD_SOURCE --> marker)
- creates (enhanced) TEI files

.. code:: bash

	colrev data [options]

.. option:: --profile

    Generate a sample profile.

.. option:: --reading_heuristics

    Calculate heuristic (influence of each paper within the selected sample) to prioritize reading efforts (see :cite:p:`WagnerEmplSchryen2020`.).

.. TODO: include examples (figure) for data --profile/--reading_heuristics

Links and references for standalone literature reviews will be made available here (TODO).
