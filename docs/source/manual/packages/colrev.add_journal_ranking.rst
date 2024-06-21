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
colrev.add_journal_ranking
==========================

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner, Alexa Steinheimer, Robert Ahr, Thomas Fleischmann, Anton Liam Frisch

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/add_journal_ranking>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - prep
     - |EXPERIMENTAL|
     - .. code-block::


         colrev prep --add colrev.add_journal_ranking


Summary
-------

prep
----

**Prerequisite** Initial ranking data is extracted from ranking.csv into SQLite Database sqlite_index.db with 'colrev env -i'.

**Description**

The add_journal_ranking package allows the user to add a ranking to the records metadata for additional automated prescreen options. While iterating through the records, this class calls the get_journal_rankings method to access the sqlite_index.db to compare if a journal_name is in one or more of the saved rankings. These rankings are being saved in the records metadata.

Example:

.. code-block::

   journal_ranking = {Senior Scholars' List of Premier Journals}, or
   journal_ranking = {not included in a ranking},

Should the journal be in the Beall's Predatory Journal list, then the record will be marked as "Predatory Journal: Do not include!" and be predestined to be excluded in the scope_prescreen process.

Example:

.. code-block::

   journal_ranking = {Predatory Journal: Do not include!},

The journal ranking will also be used in the colrev prescreen method and allows the user to decide if the record should be marked as 'rev_prescreen_excluded' or 'rev_prescreen_included'.

For further information see `scope_prescreen <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/packages/prescreen/scope_prescreen.md>`_.
