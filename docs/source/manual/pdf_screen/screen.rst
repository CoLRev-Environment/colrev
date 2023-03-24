
.. _PDF screen:

colrev screen
---------------------------------------------

In the :program:`colrev screen` operation, records transition from ``pdf_prepared`` to ``rev_included`` or ``rev_excluded``. Decisions on individual screening criteria (if any) are reported in the ``screening_criteria`` field.

The selection of screening criteria is recorded when initializing the screen.

.. code:: bash

	colrev screen [options]

    # Include all papers
    colrev screen --include_all

    # Splits the screen between n researchers. Simply share the output with the researchers and ask them to run the commands in their local CoLRev project.
    colrev screen --create_split INT

    # Complete the screen for the specified split.
    colrev screen --split STR


The following options for screen are available:

.. datatemplate:json:: ../../../../colrev/template/package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Screen packages", "short_description"), ("Identifier", "package_endpoint_identifier"), ("Link", "link"), ("Status", "status_linked")],
        data['screen'],
        title='',
        ) }}
