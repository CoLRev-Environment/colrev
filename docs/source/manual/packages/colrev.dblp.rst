colrev.dblp
===========

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


         colrev search --add colrev.dblp

   * - prep
     - |MATURING|
     - .. code-block::


         colrev prep --add colrev.dblp


Summary
-------

The table shows the search sources available in the dblp package. The main source is dblp.org, which provides curated metadata for computer science and information technology. The size of the database is over 5,750,000 entries.

search
------

API search
^^^^^^^^^^

ℹ️ Restriction: API searches do not support complex queries (yet)

Run a search on dblp.org and paste the url in the following command:

.. code-block::

   colrev search --add colrev.dblp -p "https://dblp.org/search?q=microsourcing"

TOC search
^^^^^^^^^^

TODO

prep
----

linking metadata

Links
-----


* License: `Open Data Commons ODC-BY 1.0 license <https://dblp.org/db/about/copyright.html>`_
* `DBLP <https://dblp.org/>`_
