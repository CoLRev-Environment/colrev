
Reference implementation
========================================
..
   DO NOT DELETE THIS FILE! It contains the all-important `.. autosummary::` directive with `:recursive:` option, without
   which API documentation wouldn't get extracted from docstrings by the `sphinx.ext.autosummary` engine. It is hidden
   (not declared in any toctree) to remove an unnecessary intermediate page; index.rst instead points directly to the
   package page. DO NOT REMOVE THIS FILE!


CoLRev comes with batteries included, i.e., a reference implementation for all steps of the process.
At the same time you can easily include other extensions or custom scripts (batteries are swappable).
Everything is specified in the settings.json (simply add the extension/script name as the endpoint to any of the `scripts elements <https://github.com/geritwagner/colrev/blob/main/colrev/template/settings.json>`_):


.. code-block:: diff

   ...
    "screen": {
        "criteria": [],
        "scripts": [
            {
   -             "endpoint": "colrev_cli_screen"
   +             "endpoint": "custom_screen_script"
            }
        ]
    },
    ...

The available (built-in) scripts are documented here:

.. autosummary::
   :toctree: _autosummary
   :template: custom-module-template.rst
   :recursive:

   colrev.ops.built_in
