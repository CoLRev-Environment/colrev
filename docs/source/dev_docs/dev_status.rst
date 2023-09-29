
Development status
==================================

.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 14pt
   :target: https://colrev.readthedocs.io/en/latest/foundations/dev_status.html
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 14pt
   :target: https://colrev.readthedocs.io/en/latest/foundations/dev_status.html
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 14pt
   :target: https://colrev.readthedocs.io/en/latest/foundations/dev_status.html

Currently, CoLRev is recommended for users with technical expertise. We use it for our own projects and the use of Git versioning prevents data losses.
A detailed overview of the project status and the roadmap is provided below. The maturity is rated as follows:

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - Status
     - Description
   * - |EXPERIMENTAL|
     - Functionality may not be fully implemented, tested, or documented. **Recommended for developers, not for general users.**
   * - |MATURING|
     - Functionality is implemented, partially tested, and documented. **Recommended for users with technical expertise.**
   * -  |STABLE|
     - Functionality is fully implemented, including unit and user tests, as well as comprehensive documentation. Reviewed from a technical and methodological perspective. **Recommended for use.**

The goal is to release new versions on a bi-monthly basis. The current focus is on the data management and integration with Git. Once CoLRev has matured, UIs should make it accessible to a broader user base. For details see the `milestones on GitHub <https://github.com/CoLRev-Environment/colrev/milestones>`_.


Core functionality |MATURING|
-----------------------------------------------------------------

**Summary statement**: The core functionality related to data management, operations, and environment services are fairly well documented and tested, although work is still in progress.

..
    To activate:
    - Dataset: |MATURING|
    - Records: |MATURING|
    - ReviewManager: |MATURING|
    - Operation load: |MATURING|
    - Operation prep: |MATURING|
    - Operation dedupe: |MATURING|
    - Operation prescreen: |MATURING|
    - Operation pdfs: |MATURING|
    - Operation screen: |MATURING|
    - Operation data: |MATURING|
    - Other operations: |MATURING|

    - Pyton API
    - R API/package

Collaboration |MATURING|
-----------------------------------------------------------------

**Summary statement**: The collaboration model relies on established git mechanisms. CoLRev partly supports the collaboration by applying formatting and consistency checks. More specific collaboration principles and guidelines are currently developed.

Packages |EXPERIMENTAL|
-----------------------------------------------------------------

**Summary statement**: The packages are generally under heavy development. Packages vary in maturity but most are not yet completed and require testing as well as documentation. At the same time, we use most packages regularly and quickly fix bugs.

..
    - We focus on those package that are suggested as part of the default initial setup (a table overview follows)
    - it should become clear whether there are mature packages for each operation (which ones)


The status of each package is provided in the operations subpages (`init <../manual/problem_formulation/init.html>`_, `search <../manual/metadata_retrieval/search.html>`_, `load <../manual/metadata_retrieval/load.html>`_, `prep <../manual/metadata_retrieval/prep.html>`_, `dedupe <../manual/metadata_retrieval/dedupe.html>`_, `prescreen <../manual/metadata_prescreen/prescreen.html>`_, `pdf-get <../manual/pdf_retrieval/pdf_get.html>`_, `pdf-prep <../manual/pdf_retrieval/pdf_prep.html>`_, `screen <../manual/pdf_screen/screen.html>`_, `data <../manual/data/data.html>`_) Instructions on adding new packages and having them reviewed are provided in the `extensions <../manual/extensions.html>`_ section.

..
    -> TODO : link to criteria

Methods |EXPERIMENTAL|
-----------------------------------------------------------------

**Summary statement**: The operations are `aligned <../manual/operations.html>`_ with the established methodological steps of the review process and differences between review types and the typical forms of data analysis are considered during project setup. The *encoding of review methodology* is in progress and requires documentation.

..
    TODO : cover differences between review types in setup/validation

..
    Once CoLRev has matured, UIs should make it accessible to a broader user base. CoLRev is the result of intense prototyping, research and development. We use it for our own projects and believe it is ready to be released - after all, git ensures that your work is never lost.

    Focused on development towards maturity
    Not focused on features

    Design a status page (what's unit/user tested/documented/recommended for testing/users with technical experience/generally)
    Ampel / Test coverage
