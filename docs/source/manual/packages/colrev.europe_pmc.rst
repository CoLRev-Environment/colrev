colrev.europe_pmc
=================

- Maintainer: Gerit Wagner
- License: MIT

.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 14pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 14pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 14pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
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
