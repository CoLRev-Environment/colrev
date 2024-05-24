colrev.arxiv
============

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
     - |EXPERIMENTAL|
     - .. code-block::


         colrev search --add colrev.arxiv


Summary
-------

Add the search source
---------------------

API
^^^

ℹ️ Restriction: API searches do not support complex queries (yet)

.. code-block::

   colrev search --add colrev.arxiv -p "https://arxiv.org/search/?query=fitbit&searchtype=all&abstracts=show&order=-announced_date_first&size=50"

Links
-----


* `arXiv <https://arxiv.org/>`_
