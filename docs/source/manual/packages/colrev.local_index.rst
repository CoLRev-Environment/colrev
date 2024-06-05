colrev.local_index
==================

Package
--------------------

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
   * - search_source
     - |MATURING|
     - .. code-block::


         colrev search --add colrev.local_index

   * - prep
     - |MATURING|
     - .. code-block::


         colrev prep --add colrev.local_index

   * - pdf_get
     - |MATURING|
     - .. code-block::


         colrev pdf-get --add colrev.local_index


Summary
-------

This package creates an sqlite database based on local CoLRev packages, providing meta-data and PDFs to other local packages.

To create or update the index, run

.. code-block::

   colrev env -i

search
------

API search
^^^^^^^^^^

.. code-block::

   colrev search --add colrev.local_index -p "title LIKE '%dark side%'"

pdf-get
-------

Retrieves PDF documents from other local CoLRev repositories, given that they are registered, and that the index is updated.


.. raw:: html

   <!-- ## Links -->
