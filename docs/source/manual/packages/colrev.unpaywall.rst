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
colrev.unpaywall
================

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/unpaywall>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - pdf_get
     - |MATURING|
     - .. code-block::


         colrev pdf-get --add colrev.unpaywall


Summary
-------

The unpaywall package provides legal and open access PDF retrieval for cross-disciplinary research. With access to over 30,000,000 scholarly articles, it offers a convenient way to retrieve PDF documents from the `Unpaywall <https://unpaywall.org/>`_ API.

This package supports retrieval of PDF documents from the `unpaywall <https://unpaywall.org/>`_ API, which provides access to over 40,000,000 free scholarly articles.

pdf-get
-------


.. raw:: html

   <!--
   Note: This document is currently under development. It will contain the following elements.

   - description
   - example
   -->



The unpaywall package is activated by default.
If it is not yet activated, run

.. code-block::

   colrev pdf-get -a colrev.unpaywall

By default, the email address used in the git configuration is added to the unpaywall requests.

If you would like to use a different email address, use the following command

.. code-block::

   colrev settings --update-global=packages.pdf_get.colrev.unpaywall.email=<email_address>

Links
-----


* `REST API <https://unpaywall.org/products/api>`_
