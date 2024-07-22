Development status
==================================

.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 14pt
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 14pt
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 14pt

Currently, CoLRev is recommended for users with technical expertise. We use it for our own projects and the use of Git versioning prevents data losses.
A detailed overview of the project status and the roadmap is provided below. The maturity is rated as follows:

.. list-table::
   :widths: 20 55 25
   :header-rows: 1

   * - Status
     - Description
     - Recommended for
   * - |EXPERIMENTAL|
     - Functionality may not be fully implemented, tested, or documented.
     - **Developers, not for general users.**
   * - |MATURING|
     - Functionality is implemented, partially tested, and documented.
     - **Users with technical expertise.**
   * -  |STABLE|
     - Functionality is fully implemented, including unit and user tests, as well as comprehensive documentation. Reviewed from a technical and methodological perspective.
     - **Everyone.**

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


The status of each package is provided in the operations subpages (:doc:`init </manual/problem_formulation/init>`, :doc:`search </manual/metadata_retrieval/search>`, :doc:`load </manual/metadata_retrieval/load>`, :doc:`prep </manual/metadata_retrieval/prep>`, :doc:`dedupe </manual/metadata_retrieval/dedupe>`, :doc:`prescreen </manual/metadata_prescreen/prescreen>`, :doc:`pdf-get </manual/pdf_retrieval/pdf_get>`, :doc:`pdf-prep </manual/pdf_retrieval/pdf_prep>`, :doc:`screen </manual/pdf_screen/screen>`, :doc:`data </manual/data/data>`). Instructions on adding new packages and having them reviewed are provided in the :doc:`package development </resources/packages/development>` section.

..
    -> TODO : link to criteria

Methods |EXPERIMENTAL|
-----------------------------------------------------------------

**Summary statement**: The operations are :doc:`aligned </manual/operations>` with the established methodological steps of the review process and differences between review types and the typical forms of data analysis are considered during project setup. The *encoding of review methodology* is in progress and requires documentation.

..
    TODO : cover differences between review types in setup/validation

..
    Once CoLRev has matured, UIs should make it accessible to a broader user base. CoLRev is the result of intense prototyping, research and development. We use it for our own projects and believe it is ready to be released - after all, git ensures that your work is never lost.

    Focused on development towards maturity
    Not focused on features

    Design a status page (what's unit/user tested/documented/recommended for testing/users with technical experience/generally)
    Ampel / Test coverage
