colrev.colrev_curation
======================

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
   * - prep
     - |MATURING|
     - .. code-block::


         colrev prep --add colrev.colrev_curation

   * - data
     - |MATURING|
     - .. code-block::


         colrev data --add colrev.colrev_curation


Summary
-------


.. raw:: html

   <!-- Note: This document is currently under development. It will contain the following elements.

   - description
   - example -->



prep
----

Curation prep: enforces masterdata restrictions.

Masterdata restrictions are useful to specify field requirements related to the ENTRYTYPE, the journal name, and the required fields (volume/number).
They can be set as follows:

.. code-block::

   "data_package_endpoints": [
       {
           "endpoint": "colrev.colrev_curation",
           ...
           "masterdata_restrictions": {
               "1985": {
                   "ENTRYTYPE": "article",
                   "volume": true,
                   "number": true,
                   "journal": "Decision Support Systems"
               },
               "2013": {
                   "ENTRYTYPE": "article",
                   "volume": true,
                   "journal": "Decision Support Systems"
               },
               "2014": {
                   "ENTRYTYPE": "article",
                   "volume": true,
                   "number": false,
                   "journal": "Decision Support Systems"
               }
           },
           ...
       }


.. raw:: html

   <!--
   ## data

   TODO

   ## Links
   -->



dedupe
------

See


* `colrev.curation_full_outlet_dedupe <colrev.curation_full_outlet_dedupe.html>`_
* `colrev.curation_missing_dedupe <colrev.curation_missing_dedupe.html>`_
