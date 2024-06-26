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
colrev.descriptive_review
=========================

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/descriptive_review>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - review_type
     - |STABLE|
     - .. code-block::


         colrev init --type colrev.descriptive_review


Summary
-------

Descriptive reviews aim to reveal patterns or trends in prior research without aggregating empirical evidence, or contributing to theory development. These reviews collect, codify, and analyze papers to derive insights related to the frequency of topics, authors, methods, or publication types, for instance. Results are typically tabulated or illustrated in the form of charts.

Characteristics
---------------

.. list-table::
   :align: left
   :header-rows: 1

   * - Dimension
     - Description
   * - Goal with regard to theory
     - Describing
   * - Scope of questions
     - Broad
   * - Nature of sources
     - Often restricted to empirical papers


Data extraction, analysis, and synthesis
----------------------------------------

The following packages are automatically set up in a descriptive review:


* `colrev.prisma <colrev.prisma.html>`_
* `colrev.profile <colrev.profile.html>`_
* `colrev.colrev_structured <colrev.colrev_structured.html>`_
* `colrev.paper_md <colrev.paper_md.html>`_

Examples
--------

Dahlberg, T., Mallat, N., Ondrus, J., & Zmijewska, A. (2008). Past, present and future of mobile payments research: A literature review. *Electronic Commerce Research and Applications*\ , 7(2), 165-181. doi:\ `10.1016/j.elerap.2007.02.001 <https://doi.org/10.1016/j.elerap.2007.02.001>`_

Sidorova, A., Evangelopoulos, N., Valacich, J. S., & Ramakrishnan, T. (2008). Uncovering the intellectual core of the information systems discipline. *MIS Quarterly* 32(3), 467-482. doi:\ `10.2307/25148852 <https://doi.org/10.2307/25148852>`_
