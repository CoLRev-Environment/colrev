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
colrev.exclude_complementary_materials
======================================

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/exclude_complementary_materials>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - prep
     - |MATURING|
     - .. code-block::


         colrev prep --add colrev.exclude_complementary_materials


Summary
-------

The Exclude Complementary Material - Literature Review Prescreening Package is a time-saving software package designed to automate the identification and exclusion of records with specific titles.
The tool recognizes titles such as "Editorial Board," "About the Authors," or "Thanks to Reviewers."

**Key Features**


* Title Pattern Recognition: Utilizes a matching algorithms to identify titles for prescreen exclusion.
* Efficient Workflow: Accelerates the prescreening process, allowing quick focus on relevant literature.

**Benefits**


* Time Savings: Reduces manual screening effort significantly.
* Consistency: Eliminates human error for consistent application of prescreening criteria.

Links to Exclusion Lists
------------------------


* `Exact Matches <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/env/complementary_material_strings.txt>`_
* `Prefixes <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/env/complementary_material_prefixes.txt>`_
* `Keywords <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/env/complementary_material_keywords.txt>`_
