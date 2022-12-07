.. _Data:

colrev data
---------------------------------------------

The following options for data are available:

.. datatemplate:json:: ../../../../colrev/template/package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Identifier", "package_endpoint_identifier"), ("Description", "short_description"), ("Link", "link")],
        data['data'],
        title='Extensions: data',
        ) }}


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
