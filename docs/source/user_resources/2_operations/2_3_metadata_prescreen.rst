
.. _Metadata prescreen:

Metadata prescreen - prescreen
---------------------------------------------

TODO

- colrev prescreen --split
- explain how to complete a parallel independent prescreen (colrev merge)
- explain how to skip the prescreen
- mention possible transitions to md_needs_manual_preparation


:program:`colrev prescreen` supports interactive prescreening

.. code:: bash

	colrev prescreen [options]

.. option:: --include_all

    Include all papers (do not implement a formal prescreen)

.. option:: --create_split INT

    Splits the prescreen between n researchers. Simply share the output with the researchers and ask them to run the commands in their local CoLRev project.

.. option:: --split STR

    Complete the prescreen for the specified split.

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
