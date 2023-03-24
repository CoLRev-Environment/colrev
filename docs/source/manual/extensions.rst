
Extensions
==================================

CoLRev comes with batteries included, i.e., a reference implementation for all steps of the process.
At the same time you can easily include other extensions or custom scripts (batteries are swappable).
Everything is specified in the settings.json (simply add the extension/script name as the endpoint to any of the `scripts elements <https://github.com/CoLRev-Ecosystem/colrev/blob/main/colrev/template/settings.json>`_):


.. code-block:: diff

   ...
    "screen": {
        "criteria": [],
        "scripts": [
            {
   -             "endpoint": "colrev_built_in.colrev_cli_screen"
   +             "endpoint": "custom_screen_script"
            }
        ]
    },
    ...

The endpoints for extensions are documented in the `extension interfaces <../foundations/extensions.html>`_ section.

Registered extensions are public Python packages that can be installed via PyPI.
They contain an ``endpoints.json`` file in the top-level directory (`colrev_built_in <https://github.com/CoLRev-Ecosystem/colrev/blob/main/endpoints.json>`_ provides an example).
To register a new extension, create a pull request briefly describing the extension and adding it to the `packages.json <https://github.com/CoLRev-Ecosystem/colrev/blob/main/colrev/template/packages.json>`_.
When the review is passed, the details will be added to the `package_endpoints.json <https://github.com/CoLRev-Ecosystem/colrev/blob/main/colrev/template/package_endpoints.json>`_, which also makes them available in the documentation. The development status is automatically added to the `package_status.json <https://github.com/CoLRev-Ecosystem/colrev/blob/main/colrev/template/package_status.json>`_ and can be updated manually once the review is completed.


..
    Mention scripts and non-public python projects
    Check: when packages don't meet the interface specifications, they will automatically fail/be excluded


.. toctree::
   :maxdepth: 3
   :caption: Extension development resources

   extensions/development
   extensions/python
   extensions/r
   extensions/custom_extensions
   extensions/example
