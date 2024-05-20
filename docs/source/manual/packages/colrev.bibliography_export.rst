colrev.bibliography_export
==========================

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
   * - data
     - |EXPERIMENTAL|
     - .. code-block::


         colrev data --add colrev.bibliography_export


Summary
-------

data
----

This endpoint exports the records in different bibliographical formats, which can be useful when the team works with a particular reference manager.

To add an endpoint, run any of the following:

.. code-block::

   colrev data -a colrev.bibliography_export -p zotero
   colrev data -a colrev.bibliography_export -p jabref
   colrev data -a colrev.bibliography_export -p citavi
   colrev data -a colrev.bibliography_export -p BiBTeX
   colrev data -a colrev.bibliography_export -p RIS
   colrev data -a colrev.bibliography_export -p CSV
   colrev data -a colrev.bibliography_export -p EXCEL


.. raw:: html

   <!-- ## Links -->
