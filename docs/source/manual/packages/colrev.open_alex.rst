colrev.open_alex
================

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


         colrev search --add colrev.open_alex

   * - prep
     - |EXPERIMENTAL|
     - .. code-block::


         colrev prep --add colrev.open_alex


Summary
-------

search
------

API search
^^^^^^^^^^

ℹ️ Restriction: API searches do not support complex queries (yet)

.. code-block::

   colrev search --add colrev.open_alex -p "..."

prep
----

Links meta data from OpenAlex to existing records.

Debugging
---------

To test the metadata provided for a particular ``open_alex_id`` use:

.. code-block::

   https://api.openalex.org/works/OPEN_ALEX_ID

Links
-----


* `OpenAlex <https://openalex.org/>`_
* `License <https://docs.openalex.org/additional-help/faq#how-is-openalex-licensed>`_
