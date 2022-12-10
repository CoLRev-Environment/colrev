.. _Data:

colrev data
---------------------------------------------

The following options for data are available:

.. datatemplate:json:: ../../../../colrev/template/package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Data packages", "short_description"), ("Identifier", "package_endpoint_identifier"), ("Link", "link")],
        data['data'],
        title='',
        ) }}


To set the data format, run any (combination) of the following:

.. code:: bash

    colrev data --add_endpoint colrev_built_in.manuscript
    colrev data --add_endpoint colrev_built_in.structured
    colrev data --add_endpoint colrev_built_in.prisma
    ...

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
