.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 14pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 14pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 14pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |VERSION| image:: /_static/svg/iconmonstr-product-10.svg
   :width: 15
   :alt: Version
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
colrev_ais_library
==================

|VERSION| Version: 0.1.0

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/ais_library>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - search_source
     - |MATURING|
     - .. code-block::


         colrev search --add colrev_ais_library


Summary
-------

search
------

**Limitation**\ : The AIS eLibrary currently limits search results an 3.000 records (for DB and API searches).

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
