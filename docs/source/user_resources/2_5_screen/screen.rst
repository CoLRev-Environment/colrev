
.. _PDF screen:

colrev screen
---------------------------------------------

:program:`colrev screen` supports interactive screening based on a list of exclusion criteria

.. code:: bash

	colrev screen [options]

.. option:: --include_all

    Include all papers

The following options for screen are available:

.. datatemplate:json:: ../../../../colrev/template/package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Identifier", "package_endpoint_identifier"), ("Description", "short_description"), ("Link", "link")],
        data['screen'],
        title='Extensions: screen',
        ) }}
