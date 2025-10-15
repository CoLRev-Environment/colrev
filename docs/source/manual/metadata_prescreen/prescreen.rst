colrev prescreen
---------------------------------------------

.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 12pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 12pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 12pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html

In the ``colrev prescreen`` operation, the records transition from ``md_processed`` to ``rev_prescreen_included`` or ``rev_prescreen_excluded``.
The order of prescreening is defined in the settings file.
Typically, automated prescreening packages are applied first, followed by manual prescreening.

The prescreen can be split among multiple authors (using ``colrev prescreen --split n``).
Each author can independently screen the selection of records on a separate git branch.
The reconciliation of partially overlapping independent prescreens (in separate git branches) is supported by ``colrev merge``.

In addition to the different prescreening options, it is also possible to deactivate the prescreen for the current iteration (using ``colrev prescreen --include_all``)
or in general (using ``colrev prescreen --include_all_always``).

..
    - mention possible transitions to md_needs_manual_preparation

``colrev prescreen`` supports interactive prescreening:

.. code:: bash

    colrev prescreen [options]

    # Include all papers (do not implement a formal prescreen)
    colrev prescreen --include_all

    # Splits the prescreen between n researchers. Simply share the output with the researchers and ask them to run the commands in their local CoLRev project.
    colrev prescreen --create_split INT

    # Complete the prescreen for the specified split.
    colrev prescreen --split STR


The following options for ``prescreen`` are available:

.. datatemplate:json:: ../package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Identifier", "package_endpoint_identifier"), ("Prescreen packages", "short_description"), ("Status", "status")],
        data['prescreen'],
        title='',
        columns=[25,55,20]
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
