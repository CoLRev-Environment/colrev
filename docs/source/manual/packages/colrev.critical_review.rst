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
colrev.critical_review
======================

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/critical_review>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - review_type
     - |STABLE|
     - .. code-block::


         colrev init --type colrev.critical_review


Summary
-------

A critical review is a form of research synthesis that rigorously evaluates existing literature to identify weaknesses, contradictions, and inconsistencies. It assesses each piece of literature against specific criteria to gauge its adequacy, thereby highlighting areas where current knowledge may be unreliable. This approach aids in directing future research by pinpointing specific problems and discrepancies that need to be addressed. Critical reviews are typically either selective or representative in nature, often omitting a comprehensive literature search, and may use various data synthesis methods rooted in either positivist or interpretivist epistemological positions.

If the focus is on research methods, a `critical methodological review <colrev.methodological_review.html>`_ may be appropriate.

Characteristics
---------------

.. list-table::
   :align: left
   :header-rows: 1

   * - Dimension
     - Description
   * - Goal with regard to theory
     - Understanding
   * - Scope of questions
     - Broad
   * - Nature of sources
     - Conceptual and  empirical papers


Data extraction, analysis, and synthesis
----------------------------------------

The following packages are automatically set up in a critical review:


* `colrev.prisma <colrev.prisma.html>`_
* `colrev.paper_md <colrev.paper_md.html>`_

Examples
--------

Bélanger, F., & Crossler, R. E. (2011). Privacy in the digital age: a review of information privacy research in information systems. MIS Quarterly, 35(4), 1017-1041. doi:\ `10.2307/41409971 <https://doi.org/10.2307/41409971>`_

Jones, M. R., & Karsten, H. (2008). Giddens's structuration theory and information systems research. MIS Q1uarterly, 32(1), 127-157. doi:\ `10.2307/25148831 <https://doi.org/10.2307/25148831>`_

Methods papers
--------------

Paré, G., Trudel, M. C., Jaana, M., & Kitsiou, S. (2015). Synthesizing information systems knowledge: A typology of literature reviews. Information & Management, 52(2), 183-199. doi:\ `10.1016/j.im.2014.08.008 <https://doi.org/10.1016/j.im.2014.08.008>`_
