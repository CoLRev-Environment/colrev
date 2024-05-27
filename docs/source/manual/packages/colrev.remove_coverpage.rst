colrev.remove_coverpage
=======================

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
   * - pdf_prep
     - |MATURING|
     - .. code-block::


         colrev pdf-prep --add colrev.remove_coverpage


Summary
-------

This package removes common cover pages added by publishers or registries.

Examples of cover pages detected are:


* Researchgate
* JSTOR
* Scholarworks
* Emerald
* INFORMS
* AIS eLibrary
* Taylor and Francis

pdf-prep
--------

This package is included in many default setups.
