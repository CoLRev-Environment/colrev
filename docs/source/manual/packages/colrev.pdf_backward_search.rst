colrev.pdf_backward_search
==========================

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


         colrev search --add colrev.pdf_backward_search


Summary
-------

search
------

BACKWARD_SEARCH
^^^^^^^^^^^^^^^

One strategy could be to start with a relatively high threshold for the number of intext citations and to iteratively decrease it, and update the search:
colrev search --add colrev.pdf_backward_search:min_intext_citations=2

Citation data is automatically consolidated with open-citations data to improve data quality.

based on `GROBID <https://github.com/kermitt2/grobid>`_

.. code-block::

   colrev search --add colrev.pdf_backward_search
   colrev search --add colrev.pdf_backward_search -p min_intext_citations=2

**Conducting selective backward searches**

A selective backward search for a single paper and selected references can be conducted by running

.. code-block::

   colrev search -bws record_id

References can be selected interactively for import.


.. raw:: html

   <!-- ## Links -->
