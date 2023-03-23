
.. _Metadata prescreen:

colrev prescreen
---------------------------------------------

In the :program:`colrev prescreen` operation, transitions from `md_processed` to `rev_prescreen_included` or `rev_prescreen_excluded` are recorded.

The prescreen can be split among multiple authors (using ``colrev prescreen --split n``).
Each author can independently screen the selection of records on a separate git branch.
The reconciliation of partially overlapping independent prescreens (in separate git branches) is supported by ``colrev merge``.

In addition to the different prescreening options, it is also possible to deactivate the prescreen for the current iteration (using ``colrev prescreen --include_all``)
or in general (using ``colrev prescreen --include_all_always``).

..
    - mention possible transitions to md_needs_manual_preparation

:program:`colrev prescreen` supports interactive prescreening

.. code:: bash

    colrev prescreen [options]

    # Include all papers (do not implement a formal prescreen)
    colrev prescreen --include_all

    # Splits the prescreen between n researchers. Simply share the output with the researchers and ask them to run the commands in their local CoLRev project.
    colrev prescreen --create_split INT

    # Complete the prescreen for the specified split.
    colrev prescreen --split STR


The following options for prescreen are available:

.. datatemplate:json:: ../../../../colrev/template/package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Prescreen packages", "short_description"), ("Identifier", "package_endpoint_identifier"), ("Link", "link")],
        data['prescreen'],
        title='',
        ) }}


..
    The settings can be used to specify scope variables which are applied automatically before the manual prescreen:

    .. code-block:: json

            "prescreen": {"plugin": null,
                        "mode": null,
                        "scope": [
                                {
                                    "TimeScopeFrom": 2000
                                },
                                {
                                    "TimeScopeTo": 2010
                                },
                                {
                                    "OutletExclusionScope": {
                                        "values": [
                                            {
                                                "journal": "Science"
                                            }
                                        ],
                                        "list": [
                                            {
                                                "resource": "predatory_journals_beal"
                                            }
                                        ]
                                    }
                                },
                                {
                                    "OutletInclusionScope": {
                                        "values": [
                                            {
                                                "journal": "Nature"
                                            },
                                            {
                                                "journal": "MIS Quarterly"
                                            }
                                        ]
                                    }
                                },
                                ]
                        }
