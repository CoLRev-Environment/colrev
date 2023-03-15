.. _Data:

colrev data
---------------------------------------------

In the :program:`colrev data` operation, records transition from `rev_included` to `rev_synthesized`. The data analysis and synthesis can involve different activities (data endpoints). A record only transitions to `rev_synthesized` when **all** synthesis activities were completed.

Parallel independent data extraction is only supported through the built-in git mechanisms (merges). This works best for line-based contents. For csvs, daff may be helpful.

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

    colrev data --add colrev_built_in.manuscript
    colrev data --add colrev_built_in.structured
    colrev data --add colrev_built_in.prisma
    ...

To export the bibliography in different formats, run any of the following:

.. code:: bash

    colrev data --add endnote
    colrev data --add zotero
    colrev data --add jabref
    colrev data --add mendeley
    colrev data --add citavi
    colrev data --add rdf_bibliontology


The following options for data are available:

.. datatemplate:json:: ../../../../colrev/template/package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Data packages", "short_description"), ("Identifier", "package_endpoint_identifier"), ("Link", "link")],
        data['data'],
        title='',
        ) }}



.. TODO: include examples (figure) for data --profile/--reading_heuristics

Links and references for standalone literature reviews will be made available here (TODO).
