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
colrev.files_dir
================

|VERSION| Version: 0.1.0

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/files_dir>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - search_source
     - |MATURING|
     - .. code-block::


         colrev search --add colrev.files_dir


Summary
-------

search
------

FILES  search
^^^^^^^^^^^^^

.. code-block::

   colrev search --add colrev.files_dir


* PDF metadata extracted based on PDF hashes and the local_index (clone curations and run ``colrev env --index``\ ).
* PDF metadata extracted based on `GROBID <https://github.com/kermitt2/grobid>`_

For metadata curations, i.e., repositories containing all PDFs organized in directories for volumes/issues, it is possible to set the ``scope`` parameter in the ``settings.json``\ , ensuring that the journal name, entrytype, and volume/issue is set automatically.

.. code-block:: json

   {
       "platform": "colrev.files_dir",
       "search_results_path": "data/search/pdfs.bib",
       "search_type": "FILES",
       "search_string": "",
       "search_parameters": {
           "scope": {
               "subdir_pattern": "volume_number",
               "type": "journal",
               "journal": "MIS Quarterly",
               "path": "data/pdfs"
           },
       },
       "version": "0.1.0"
   }


.. raw:: html

   <!-- ## Links -->
