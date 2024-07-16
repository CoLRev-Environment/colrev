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
colrev.europe_pmc
=================

Package
--------------------

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

prep
----

EuropePMC linking

Links
-----


* `Europe PMC <https://europepmc.org/>`_
* License: `may contain copyrighted material, unless stated otherwise <https://europepmc.org/Copyright>`_
* `Field definitions <https://europepmc.org/docs/EBI_Europe_PMC_Web_Service_Reference.pdf>`_
