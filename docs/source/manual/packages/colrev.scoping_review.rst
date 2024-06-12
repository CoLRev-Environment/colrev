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
colrev.scoping_review
=====================

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/scoping_review>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - review_type
     - |STABLE|
     - .. code-block::


         colrev init --type colrev.scoping_review


Summary
-------

A scoping review aims to provide an initial overview of the potential size and nature of the available literature on a particular topic. Researchers use scoping reviews to examine the extent, range, and nature of research activities, determine the feasibility of a full systematic review, or identify gaps in existing research. These reviews prioritize breadth over depth and strive to be as comprehensive as possible within practical constraints. Inclusion and exclusion criteria are essential to filter studies relevant to the initial research questions, and at least two independent coders are recommended for the screen. Unlike systematic reviews, scoping reviews often do not assess the methodological quality of included studies, which is a debated aspect of their methodology.

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
   * - Focus
     - Emergent topics (with 3-5 or 10 years of research)
   * - Nature of sources
     - Conceptual, empirical, and grey literature (quality appraisal is not essential)


Data extraction, analysis, and synthesis
----------------------------------------


* The reporting of the methodological process typically involves a PRISMA chart.
* Typically follows a structured yet flexible approach to comprehensively map the existing literature on a topic.
* Data extraction forms typically cover basic study details (e.g., authors, publication year, study design), as well as specific data related to the research questions (e.g., key findings, methodologies, sample characteristics).
* The data charting or mapping involves organizing extracted data into a charting table or figure, allowing researchers to visualize and compare information across studies. This step involves summarizing key points and identifying patterns or trends.

The following packages are automatically set up in a scoping review:


* `colrev.prisma <colrev.prisma.html>`_
* `colrev.colrev_structured <colrev.colrev_structured.html>`_
* `colrev.paper_md <colrev.paper_md.html>`_

Examples
--------

Archer, N., Fevrier-Thomas, U., Lokker, C., McKibbon, K. A., & Straus, S. E. (2011). Personal health records: a scoping review. *Journal of the American Medical Informatics Association*\ , 18(4), 515-522. doi:\ `10.1136/amiajnl-2011-000105 <https://doi.org/10.1136/amiajnl-2011-000105>`_

Smith, H. J., Dinev, T., & Xu, H. (2011). Information privacy research: an interdisciplinary review. *MIS Quarterly*\ , 989-1015. doi:\ `10.2307/41409970 <https://doi.org/10.2307/41409970>`_

Methods papers
--------------

Arksey, H., & O'Malley, L. (2005). Scoping studies: towards a methodological framework. *International Journal of Social Research Methodology*\ , 8(1), 19-32. doi: `10.1080/1364557032000119616 <https://doi.org/10.1080/1364557032000119616>`_

Levac, D., Colquhoun, H., & O'Brien, K. K. (2010). Scoping studies: advancing the methodology. *Implementation Science*\ , 5, 1-9. doi:\ `10.1186/1748-5908-5-69 <https://doi.org/10.1186/1748-5908-5-69>`_

Tricco, A. C. et al. (2018). PRISMA Extension for Scoping Reviews (PRISMA-ScR): Checklist and Explanation. *Annals Internal Medicine* (169:7), pp. 467–473. doi: `10.7326/M18-0850 <https://doi.org/10.7326/M18-0850>`_
