
Extensions
==================================

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

The available (built-in) extensions are documented in the respective operations pages (`init <2_1_problem_formulation/init.html>`_, `search <2_2_metadata_retrieval/search.html>`_, `load <2_2_metadata_retrieval/load.html>`_, `prep <2_2_metadata_retrieval/prep.html>`_, `dedupe <2_2_metadata_retrieval/dedupe.html>`_, `prescreen <2_3_metadata_prescreen/prescreen.html>`_, `pdf_get <2_4_fulltext_retrieval/pdf_get.html>`_, `pdf_prep <2_4_fulltext_retrieval/pdf_prep.html>`_, `screen <2_5_screen/screen.html>`_, `data <2_6_data/data.html>`_).


.. toctree::
   :maxdepth: 3
   :caption: Extension development resources

   5_extensions/development
   5_extensions/python
   5_extensions/r
   5_extensions/custom_extensions
   5_extensions/example
