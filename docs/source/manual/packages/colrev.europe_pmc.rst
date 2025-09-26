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
colrev.europe_pmc
=================

|VERSION| Version: 0.1.0

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/europe_pmc>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - search_source
     - |MATURING|
     - .. code-block::


         colrev search --add colrev.europe_pmc

   * - prep
     - |MATURING|
     - .. code-block::


         colrev prep --add colrev.europe_pmc


Summary
-------

Europe PMC is a comprehensive database that includes metadata from PubMed Central (PMC) and provides access to over 40 million records.

search
------

API search
^^^^^^^^^^

.. code-block::

   colrev search --add colrev.europe_pmc -p "https://europepmc.org/search?query=fitbit%20AND%20gamification%20AND%20RCT%20AND%20diabetes%20mellitus"

Format of the search-history file (DB search):

.. code-block:: json

   {
       "search_string": "TITLE:\"microsourcing\"",
       "platform": "colrev.europe_pmc",
       "search_results_path": "data/search/europe_pmc.bib",
       "search_type": "DB",
       "version": "0.1.0"
   }

Format of the search-history file (API search):

.. code-block:: json

   {
       "search_string": "",
       "platform": "colrev.europe_pmc",
       "search_results_path": "data/search/europe_pmc_api.bib",
       "search_type": "API",
       "search_parameters": {
           "query": "TITLE:%22microsourcing%22"
       },
       "version": "0.1.0"
   }

prep
----

EuropePMC linking

Links
-----


* `Europe PMC <https://europepmc.org/>`_
* License: `may contain copyrighted material, unless stated otherwise <https://europepmc.org/Copyright>`_
* `Field definitions <https://europepmc.org/docs/EBI_Europe_PMC_Web_Service_Reference.pdf>`_
