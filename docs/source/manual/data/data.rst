colrev data
---------------------------------------------

.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 12pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 12pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 12pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html

In the ``colrev data`` operation, records transition from ``rev_included`` to ``rev_synthesized``. The data analysis and synthesis can involve different activities (data endpoints). A record only transitions to ``rev_synthesized`` when **all** synthesis activities were completed.

Parallel independent data extraction is only supported through the built-in git mechanisms (merges). This works best for line-based contents. For ``csv`` files, daff may be helpful.

..
    reconciliation should focus on categorical data more than numerical data?

.. code:: bash

    colrev data [options]

    # Generate a sample profile.
    colrev data --profile

    # Calculate heuristic (influence of each paper within the selected sample) to prioritize reading efforts (see :cite:p:`WagnerEmplSchryen2020`.).
    colrev data --reading_heuristics


To set the data format, run any (combination) of the following:

.. code:: bash

    colrev data --add colrev.manuscript
    colrev data --add colrev.structured
    colrev data --add colrev.prisma
    ...

To export the bibliography in different formats, run any of the following:

.. code:: bash

    colrev data --add endnote
    colrev data --add zotero
    colrev data --add jabref
    colrev data --add mendeley
    colrev data --add citavi


The following options for ``data`` are available:

.. datatemplate:json:: ../../package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Identifier", "package_endpoint_identifier"), ("Data packages", "short_description"), ("Status", "status")],
        data['data'],
        title='',
        columns=[25,55,20]
        ) }}



..
    TODO: include examples (figure) for data --profile/--reading_heuristics
    Links and references for standalone literature reviews will be made available here (TODO).
