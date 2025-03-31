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
colrev_unpaywall
================

|VERSION| Version: 0.1.0

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/unpaywall>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - search_source
     - |MATURING|
     - .. code-block::


         colrev search --add colrev_unpaywall

   * - pdf_get
     - |MATURING|
     - .. code-block::


         colrev pdf-get --add colrev_unpaywall


Summary
-------

The unpaywall package provides legal and open access PDF retrieval for cross-disciplinary research. With access to over 30,000,000 scholarly articles, it offers a convenient way to retrieve PDF documents from the `Unpaywall <https://unpaywall.org/>`_ API.

The search method provides functionality for searching the Unpaywall database. There are two options, one with keywords and one with a complete URL

This package primarily supports the retrieval of PDF documents from the `unpaywall <https://unpaywall.org/>`_ API, which provides access to over 40,000,000 free scholarly articles.

An **email address** is required for API calls for the search and retrieval of PDFs.
By default, the email address used in the git configuration is added to the unpaywall requests. If you would like to use a different email address, use the following command.

.. code-block::

   colrev settings --update-global=packages.pdf_get.colrev.unpaywall.email=<email_address>

search
------

Currently only API search is implemented. Other search types such as MD search or TOC search may be implemented in the future.

API search
^^^^^^^^^^

ℹ️ Restriction: API searches do not support complex queries (yet)

Download search results and store them in the ``data/search/`` directory. When searching for publications, only the title is used. A search on the Unpaywall API can be performed as follows.

Option 1: Search with keywords
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


#. Use the following command to add the endpoint:
   .. code-block::

       colrev search --add colrev.unpaywall

#. Upon entering the command above with no additional parameters, a console interface opens up, in which the user is asked to enter the parameters and query for their search. Enter the keywords for the search by following the `Query & Keyword format <#api-search-query--keyword-format>`_ like described underneath.

API search: Query & Keyword format
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The user can enter a single term or use the Boolean ``AND``\ , ``OR``\ , ``NOT`` for a specific search. The following conditions must be met:


* The boolean operators ``AND``\ , ``OR`` , ``NOT`` must be written in capital letters
* The boolean operators ``AND``\ , ``OR`` , ``NOT`` must be separated from the search term with a whitespace
* If you enter two terms without a boolean operator but a whitespace in between, the default is ``AND``
*
  Search phrases must be enclosed in double quotes ``"``

    ##### Examples


  * A single search term: ``thermometry``
  * Search Phrase: ``"hash table"``
  * Two terms with AND: ``cell AND thermometry`` equals ``cell thermometry``
  * Two terms with OR: ``cell OR thermometry``
  * Negation of a term: ``cell NOT thermometry``

Option 2: Search with URL for simple single-term query
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


#.
   Visit the `Unpaywall Article Search tool <https://unpaywall.org/articles>`_\ , enter the keyword for a simple single-term query and click on "View in API" to copy the URL.

#.
   Use the following command to add the endpoint with the copied URL:
    ##### Example

   .. code-block::

       colrev search --add colrev.unpaywall -p "https://api.unpaywall.org/v2/search?query=thermometry&is_oa=true&email=unpaywall_01@example.com"

Unpaywall Query Parameters
""""""""""""""""""""""""""


*
  ``is_oa:`` (Optional) A boolean value indicating whether the returned records should be Open Access or not.


  * true: filter the results to OA articles
  * false: filter the results to non-OA articles
  * null/unspecified: return the most relevant results regardless of OA status

*
  ``query:`` (Required) Keywords to search for.

* ``email:`` Your email address to access the API. If the email address is manually specified in the URL, this email will be saved and used for later requests.

pdf-get
-------


.. raw:: html

   <!--
   Note: This document is currently under development. It will contain the following elements.

   - description
   - example
   -->



The unpaywall package is activated by default.
If it is not yet activated, run

.. code-block::

   colrev pdf-get -a colrev.unpaywall

Links
-----


* `REST API <https://unpaywall.org/products/api>`_
