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
colrev.plos
===========

|VERSION| Version: 0.1.0

|MAINTAINER| Maintainer: Olga Girona, Júlia Lopez Marti, Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - search_source
     - |EXPERIMENTAL|
     - .. code-block::


         colrev search --add colrev.plos


Summary
-------

PLOS is a SearchSource providing open access metadata for articles published in PLOS journals. It focuses on life sciences and health but includes articles in other disciplines. Its database contains metadata for thousands of articles across multiple PLOS journals.

Installation
------------

.. code-block:: bash

   colrev install colrev.plos

Usage
-----

API search
^^^^^^^^^^

To make an API search, first introduce the next command:

.. code-block::

   colrev search -a colrev.plos

On the menu displayed, select the option API:

.. code-block::

   2024-12-20 16:22:31 [INFO] Add search package: colrev.plos
   [?] Select SearchType::
    > API
      TOC

Finally introduce a keyword to search:

.. code-block::

   Add colrev.plos as an API SearchSource

   Enter the keywords:

Load
^^^^

.. code-block::

   colrev load

Debugging
---------

In order to test the metada provided for a specific ``DOI`` it can be used the following link:

.. code-block::

   https://api.plos.org/search?q=DOI:

License
-------

This project is licensed under the MIT License - see the `LICENSE <LICENSE>`_ file for details.

Links
-----


* `PLOS API <https://api.plos.org>`_
* `Sorl Search Fileds and Article types <https://api.plos.org/solr/search-fields/>`_
