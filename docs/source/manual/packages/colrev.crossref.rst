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
colrev.crossref
===============

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/crossref>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - search_source
     - |MATURING|
     - .. code-block::


         colrev search --add colrev.crossref

   * - prep
     - |MATURING|
     - .. code-block::


         colrev prep --add colrev.crossref


Summary
-------

`Crossref <https://www.crossref.org/>`_ is a SearchSource that contains metadata deposited by publishers. It is cross-disciplinary and has a size of over 125,000,000 records.

search
------

API search
^^^^^^^^^^

ℹ️ Restriction: API searches do not support complex queries (yet)

It is possible to copy the url from the `search.crossref.org <https://search.crossref.org/?q=microsourcing&from_ui=yes>`_ UI and add it as follows:

.. code-block::

   colrev search --add colrev.crossref -p "query=microsourcing"
   colrev search --add colrev.crossref -p "https://search.crossref.org/?q=+microsourcing&from_ui=yes"


.. raw:: html

   <!--
   TODO:
   colrev search --add colrev.crossref -p "query=microsourcing;years=2000-2010"
   -->



TOC search
^^^^^^^^^^

Whole journals can be added based on their issn:

.. code-block::

   colrev search --add colrev.crossref -p "issn=2162-9730"

prep
----

Crossref generally offers high-quality meta data, making it an effective source to link and update existing records.

Debugging
---------

To test the metadata provided for a particular ``DOI`` use:

.. code-block::

   https://api.crossref.org/works/DOI

Links
-----


* `Crossref <https://www.crossref.org/>`_
* `License <https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-metadata-license-information/>`_
* `Crossref types <https://api.crossref.org/types>`_
* `Issue: AND Operators not yet supported <https://github.com/fabiobatalha/crossrefapi/issues/20>`_
