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
colrev.scope_prescreen
======================

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/scope_prescreen>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - prescreen
     - |MATURING|
     - .. code-block::


         colrev prescreen --add colrev.scope_prescreen


Summary
-------

prescreen
---------

This package uses a predefined scope to apply prescreening decisions automatically. For example, papers can be excluded based on the date of publication or their language. There are two use main use cases:


#. The Scope Prescreen runs before a manual prescreen. In this case, papers are either marked as ``rev_prescreen_excluded``\ , or remain ``md_processed``. Afterwards, all papers in ``md_processed`` are prescreened manually based on their topic.
#. The Scope Prescreen is the only prescreen package activated in the settings. In this case, papers are marked as ``rev_prescreen_excluded`` or ``rev_prescreen_included``. Fully automated prescreening may not be appropriate for all types of reviews.

The Scope Prescreen can be added as follows:

.. code-block::

   colrev prescreen -a colrev.scope_prescreen -p "TimeScopeFrom=2010"

**Prerequesite**\ : The endpoint colrev.add_journal_ranking in the settings of prep must be installed.
"colrev prep" must have been executed and journal_ranking must be included in metadata.

**Description**\ : Use case: User is able to decide whether journals, which are not included in any ranking, will be marked as "rev_prescreen_included" or as "rev_prescreen_excluded".
