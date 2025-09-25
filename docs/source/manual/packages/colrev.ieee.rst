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
colrev.ieee
===========

|VERSION| Version: 0.1.0

|MAINTAINER| Maintainer: Rhea Nguyen, Malou Schmidt, Frederic Fischer, Janus Fiegen, Albert Borchardt, Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/ieee>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - search_source
     - |EXPERIMENTAL|
     - .. code-block::


         colrev search --add colrev.ieee


Summary
-------

search
------

DB search
^^^^^^^^^

csv export is preferred because the other formats (bib/ris) do not export the url (which includes the accession number). The accession number is important for search updates.

API search
^^^^^^^^^^

ℹ️ Restriction: API searches do not support complex queries (yet)

Download search results and store in ``data/search/`` directory.

Data from the IEEE database can be retrieved with the URL from the `https://www.ieee.org/ <https://ieeexploreapi.ieee.org/api/v1/search/articles?parameter&apikey=>`_. Add the URL as follows:

.. code-block::

   colrev search --add colrev.ieee -p "https://ieeexploreapi.ieee.org/api/v1/search/articles?parameter=microsourcing"

All configured metadata fields, the abstract and the document text are queried.

It is not necessary to pass an API key as a parameter here. In order to keep the key secret, you will be prompted to enter it through user input if it is not already stored in the settings. The api key can be requested via the `IEEE Xplore API Portal <https://developer.ieee.org/member/register>`_.

Specific parameters can also be searched for, such as issn, isbn, doi, article_number, author, publication_year. For each of these, append "parameter=value" to the URL.

.. code-block::

   colrev search --add colrev.ieee -p "https://ieeexploreapi.ieee.org/api/v1/search/articles?issn=1063-6919"

Multiple parameters can be concatenated using the "&" symbol.

.. code-block::

   colrev search --add colrev.ieee -p "https://ieeexploreapi.ieee.org/api/v1/search/articles?publication_year=2019&abstract=microsourcing"

If your search query includes Boolean operators, add "queryText=query" to the URL.

.. code-block::

   colrev search --add colrev.ieee -p "https://ieeexploreapi.ieee.org/api/v1/search/articles?booleanText=(rfid%20AND%20%22internet%20of%20things%22)"

Format of the search-history file (DB search):

.. code-block:: json

   {
       "search_string": "microsourcing",
       "platform": "colrev.ieee",
       "search_results_path": "data/search/ieee.bib",
       "search_type": "DB",
       "version": "0.1.0"
   }

Format of the search-history file (API search):

.. code-block:: json

   {
       "search_string": "",
       "platform": "colrev.ieee",
       "search_results_path": "data/search/ieee_api.bib",
       "search_type": "API",
       "search_parameters": {
           "query": "microsourcing",
       },
       "version": "0.1.0"
   }

Links
-----


* `IEEEXplore <https://ieeexplore.ieee.org/>`_
