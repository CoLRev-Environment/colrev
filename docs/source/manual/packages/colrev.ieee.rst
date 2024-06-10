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
colrev.ieee
===========

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner, Rhea Nguyen, Malou Schmidt, Frederic Fischer, Janus Fiegen, Albert Borchardt

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

Links
-----


* `IEEEXplore <https://ieeexplore.ieee.org/>`_
