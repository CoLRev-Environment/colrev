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
colrev.eric
===========

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner, Rhea Nguyen, Malou Schmidt, Frederic Fischer, Janus Fiegen, Albert Borchardt

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/eric>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - search_source
     - |EXPERIMENTAL|
     - .. code-block::


         colrev search --add colrev.eric


Summary
-------

search
------

DB search
^^^^^^^^^

Download search results and store in ``data/search/`` directory.

API search
^^^^^^^^^^

ℹ️ Restriction: API searches do not support complex queries (yet)

A search on the ERIC API can be performed as follows:

.. code-block::

   colrev search --add colrev.eric -p "https://api.ies.ed.gov/eric/?search=blockchain"

This command searches the core fields title, author, source, subject, and description of the entered search string (here: blockchain). The data is always returned in json format (xml and csv are not yet supported).

A field search can also be used if only a search for a string in a specific field is wanted:

.. code-block::

   colrev search --add colrev.eric -p "https://api.ies.ed.gov/eric/?search=author: Creamer, Don"

This command returns all records by author Don Creamer.

If several strings are to be searched for in different fields, the AND operator can be used:

.. code-block::

   colrev search --add colrev.eric -p "https://api.ies.ed.gov/eric/?search=author:Creamer, Don AND title: Alternative"

This command returns all records by author Don Creamer that have the string "Alternative" in the title.

In addition, the start parameter the starting record number for the returned results set can be determined and the rows parameter can be used to determine how many records are to be returned (by default start hat the value 0 and rows the value 2000):

.. code-block::

   colrev search --add colrev.eric -p "https://api.ies.ed.gov/eric/?search=blockchain&start=0&rows=5"

This command returns 5 records with starting record number 0.

Links
-----


* `ERIC <https://eric.ed.gov/>`_
* `ERIC API <https://eric.ed.gov/?api>`_
