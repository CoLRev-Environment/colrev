colrev.ais_library
==================

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


         colrev search --add colrev.ais_library


Summary
-------

search
------

DB search
^^^^^^^^^

Run a search on `aisel.aisnet.org <https://aisel.aisnet.org/>`_.

Download the search results (advanced search, format:Bibliography Export, click Search) and store them in the ``data/search/`` directory.

.. code-block::

   colrev search --add colrev.ais_library

API search
^^^^^^^^^^

Copy the search link and add an API search (replacing the link):

.. code-block::

   colrev search --add colrev.ais_library -p "https://aisel.aisnet.org/do/search/?q=microsourcing&start=0&context=509156&facet="

Note: Complex queries can be entered in the basic search field. Example:

.. code-block::

   title:microsourcing AND ( digital OR online)

Links
-----

`AIS eLibrary <https://aisel.aisnet.org/>`_
