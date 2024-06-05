colrev.curated_masterdata
=========================

Package
--------------------

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
   * - review_type
     - |EXPERIMENTAL|
     - .. code-block::


         colrev init --type colrev.curated_masterdata


Summary
-------

Note: This document is currently under development. It will contain the following elements.

Short summary
-------------


* explanation
* goals
* dimensions
* differences between disciplines

Steps and operations
--------------------

To create a new masterdata curation, run

.. code-block::

   colrev init --type colrev.curated_masterdata
   # add crossref
   colrev search --add "crossref:jissn=123456"
   # add further sources (like DBLP)


.. raw:: html

   <!--
   ### Problem formulation
   -->



Metadata retrieval
^^^^^^^^^^^^^^^^^^


* All SearchSources should correspond to metadata-SearchSources (e.g., retrieving the whole journal from Crossref), i.e., the linking to metadata-SearchSources is disabled in the prep operation.
* The curation endpoint supports the specification of ``masterdata_restrictions``\ , defining the name of the outlet, whether volume or issue fields are required (for which time-frame).
* Dedicated dedupe endpoints are activated.


.. raw:: html

   <!--
   ### Metadata prescreen

   ### PDF retrieval

   ### PDF screen

   ### Data extraction and synthesis

   - For manuscript development see separate page for Word/Tex/Md, Reference Managers

   ## Software recommendations

   ## References
   -->
