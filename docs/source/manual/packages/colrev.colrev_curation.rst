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
colrev.colrev_curation
======================

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/colrev_curation>`_

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
