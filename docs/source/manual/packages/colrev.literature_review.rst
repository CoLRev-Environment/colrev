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
colrev.literature_review
========================

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/literature_review>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - review_type
     - |STABLE|
     - .. code-block::


         colrev init --type colrev.literature_review


Summary
-------

This ReviewType contains a basic setup for literature reviews. It is a good choice to try the CoLRev system. Similar to the other packages for review types, it can be used to complete a review project and report each step for a standalone review paper.

For standalone review papers, it is recommended to use a specific review type, such as a `scoping review <colrev.scoping_review.html>`_ or a `qualitative systematic review <colrev.qualitative_systematic_review.html>`_.

Characteristics
---------------


* N/A. The characteristics of literature reviews vary considerably when no review type is specified.

Data extraction, analysis, and synthesis
----------------------------------------


* For the synthesis, the `colrev.paper_md <colrev.paper_md.html>`_ is activated, which creates the ``data/data/paper.md`` file. This file can be used to keep notes, draft a review protocol, and to write a synthesis. Based on the ``paper.md``\ , the ``output/paper.docx`` is generated automatically.
* To extract structured data, or conduct other forms of analysis and synthesis, other `data packages <https://colrev.readthedocs.io/en/latest/manual/data/data.html>`_ can be activated.

Textbooks
---------

Fink, A. (2019). Conducting research literature reviews: From the internet to paper. Sage publications. ISBN: 9781544318462.

Hart, C. (2018). Doing a literature review: Releasing the research imagination. Sage publications. ISBN: 9781526423146.
