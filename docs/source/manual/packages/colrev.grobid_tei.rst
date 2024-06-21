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
colrev.grobid_tei
=================

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/grobid_tei>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - pdf_prep
     - |MATURING|
     - .. code-block::


         colrev pdf-prep --add colrev.grobid_tei


Summary
-------

This package uses GROBID to create annotated TEI documents from PDFs (see `example <https://github.com/CoLRev-Environment/colrev/blob/main/tests/data/WagnerLukyanenkoParEtAl2022.tei.xml>`_\ ).

Running GROBID requires Docker.

pdf-prep
--------

This package can be added to a project using the following command:

.. code-block::

   colrev pdf-prep -a colrev.grobid_tei

Links
-----


.. image:: https://img.shields.io/github/commit-activity/y/kermitt2/grobid?color=green&style=plastic
   :target: https://img.shields.io/github/commit-activity/y/kermitt2/grobid?color=green&style=plastic
   :alt: grobidactivity



* `GRBOBID <https://github.com/kermitt2/grobid>`_\ : parsing annotated PDF content (License: `Apache 2.0 <https://github.com/kermitt2/grobid/blob/master/LICENSE>`_\ )
