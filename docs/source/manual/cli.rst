Command-line Interface
========================================
..
   DO NOT DELETE THIS FILE! It contains the all-important `.. autosummary::` directive with `:recursive:` option, without
   which API documentation wouldn't get extracted from docstrings by the `sphinx.ext.autosummary` engine. It is hidden
   (not declared in any toctree) to remove an unnecessary intermediate page; index.rst instead points directly to the
   package page. DO NOT REMOVE THIS FILE!

This documentation provides an overview of the CLI commands and the corresponding operations. The parameters for each command should be stored in the settings.json.

.. click:: colrev.ui_cli.cli:status
   :prog: colrev status
   :nested: full

.. click:: colrev.ui_cli.cli:init
   :prog: colrev init
   :nested: full

.. click:: colrev.ui_cli.cli:retrieve
   :prog: colrev retrieve
   :nested: full

.. click:: colrev.ui_cli.cli:search
   :prog: colrev search
   :nested: full

.. click:: colrev.ui_cli.cli:load
   :prog: colrev load
   :nested: full

.. click:: colrev.ui_cli.cli:prep
   :prog: colrev prep
   :nested: full

.. click:: colrev.ui_cli.cli:prep_man
   :prog: colrev prep-man
   :nested: full

.. click:: colrev.ui_cli.cli:dedupe
   :prog: colrev dedupe
   :nested: full

.. click:: colrev.ui_cli.cli:prescreen
   :prog: colrev prescreen
   :nested: full

.. click:: colrev.ui_cli.cli:screen
   :prog: colrev screen
   :nested: full

.. click:: colrev.ui_cli.cli:pdfs
   :prog: colrev pdfs
   :nested: full

.. click:: colrev.ui_cli.cli:pdf_get
   :prog: colrev pdf-get
   :nested: full

.. click:: colrev.ui_cli.cli:pdf_get_man
   :prog: colrev pdf-get-man
   :nested: full

.. click:: colrev.ui_cli.cli:pdf_prep
   :prog: colrev pdf-prep
   :nested: full

.. click:: colrev.ui_cli.cli:pdf_prep_man
   :prog: colrev pdf-prep-man
   :nested: full

.. click:: colrev.ui_cli.cli:data
   :prog: colrev data
   :nested: full

.. click:: colrev.ui_cli.cli:env
   :prog: colrev env
   :nested: full

.. click:: colrev.ui_cli.cli:clone
   :prog: colrev clone
   :nested: full

.. click:: colrev.ui_cli.cli:pull
   :prog: colrev pull
   :nested: full

.. click:: colrev.ui_cli.cli:push
   :prog: colrev push
   :nested: full

.. click:: colrev.ui_cli.cli:sync
   :prog: colrev sync
   :nested: full

.. click:: colrev.ui_cli.cli:distribute
   :prog: colrev distribute
   :nested: full

.. click:: colrev.ui_cli.cli:validate
   :prog: colrev validate
   :nested: full

.. click:: colrev.ui_cli.cli:trace
   :prog: colrev trace
   :nested: full



..
   https://sphinx-click.readthedocs.io/en/latest/usage/
