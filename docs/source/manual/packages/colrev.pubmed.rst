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
colrev.pubmed
=============

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/pubmed>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - search_source
     - |MATURING|
     - .. code-block::


         colrev search --add colrev.pubmed

   * - prep
     - |MATURING|
     - .. code-block::


         colrev prep --add colrev.pubmed


Summary
-------

PubMed is a free search engine that provides access to a vast collection of biomedical literature. It allows users to search for articles, abstracts, and citations from various sources, including scientific journals and research papers. PubMed is widely used by researchers, healthcare professionals, and students to find relevant information in the field of medicine and life sciences.

search
------

API search
^^^^^^^^^^

ℹ️ Restriction: API searches do not support complex queries (yet)

To add a pubmed API search, enter the query in the `Pubmed web interface <https://pubmed.ncbi.nlm.nih.gov/>`_\ , run the search, copy the url and run:

.. code-block::

   colrev search --add colrev.pubmed -p "https://pubmed.ncbi.nlm.nih.gov/?term=fitbit"

prep
----

PubMed linking

Links
-----


* `Data field descriptions <https://www.nlm.nih.gov/bsd/mms/medlineelements.html>`_
* `Pubmed <https://pubmed.ncbi.nlm.nih.gov/>`_
