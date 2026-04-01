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
colrev.prospero
===============

|VERSION| Version: 0.1.0

|MAINTAINER| Maintainer: Ammar Al-Balkhi, Phuc Tran, Olha Komashevska, Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - search_source
     - |EXPERIMENTAL|
     - .. code-block::


         colrev search --add colrev.prospero


Summary
-------

`PROSPERO <https://www.crd.york.ac.uk/prospero/#searchadvanced>`_ is an international database of prospectively registered systematic reviews in health and social care, welfare, public health, education, crime, justice, and international development, where there is a health related outcome.

Installation
^^^^^^^^^^^^

.. code-block:: bash

   colrev install colrev.prospero

search
^^^^^^

Download the search results and store them in the data/search/ directory.

.. code-block::

   colrev search --add colrev.prospero

The search is done using keywords that can be entered into the console.

load
^^^^

It is possible to save the records after search. All records that were found during the search will be saved to a data/records.bib file. Load function will add the records to the file or update existing one.

.. code-block::

   colrev load

Links
-----


* `PROSPERO <https://www.crd.york.ac.uk/prospero/>`_

License
-------

This project is licensed under the MIT License - see the `LICENSE <LICENSE>`_ file for details.
