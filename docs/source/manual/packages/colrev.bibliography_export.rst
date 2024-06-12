.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 14pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 14pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 14pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
.. |GIT_REPO| image:: /_static/svg/iconmonstr-code-fork-1.svg
   :width: 15
   :alt: Git repository
.. |LICENSE| image:: /_static/svg/iconmonstr-copyright-2.svg
   :width: 15
   :alt: Licencse
.. |MAINTAINER| image:: /_static/svg/iconmonstr-user-29.svg
   :width: 20
   :alt: Maintainer
.. |DOCUMENTATION| image:: /_static/svg/iconmonstr-book-17.svg
   :width: 15
   :alt: Documentation
colrev.bibliography_export
==========================

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/bibliography_export>`_

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
