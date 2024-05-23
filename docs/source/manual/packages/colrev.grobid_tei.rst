colrev.grobid_tei
=================

- Maintainer: Gerit Wagner
- License: MIT

.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 14pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 14pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 14pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - pdf_prep
     - |MATURING|
     - .. code-block::


         colrev pdf-prep --add colrev.grobid_tei


Summary
-------

This package uses GROBID to create annotated TEI documents from PDFs (see `example <https://github.com/CoLRev-Environment/colrev/blob/main/tests/data/WagnerLukyanenkoParEtAl2022.tei.xml>`_\ ).

Running GROBID requires Docker.

pdf-prep
--------

This package can be added to a project using the following command:

.. code-block::

   colrev pdf-prep -a colrev.grobid_tei

Links
-----


.. image:: https://img.shields.io/github/commit-activity/y/kermitt2/grobid?color=green&style=plastic
   :target: https://img.shields.io/github/commit-activity/y/kermitt2/grobid?color=green&style=plastic
   :alt: grobidactivity



* `GRBOBID <https://github.com/kermitt2/grobid>`_\ : parsing annotated PDF content (License: `Apache 2.0 <https://github.com/kermitt2/grobid/blob/master/LICENSE>`_\ )
