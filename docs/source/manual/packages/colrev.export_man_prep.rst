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
colrev.export_man_prep
======================

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/export_man_prep>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - prep_man
     - |MATURING|
     - .. code-block::


         colrev prep-man --add colrev.export_man_prep


Summary
-------

prep-man
--------

This package provides functionality aimed at


* exporting records that need to be prepared,
* fixing the errors manually (with the relevant error codes and explanations)
* importing the prepared records


#. Export the md_needs_manual_preparation cases

.. code-block::

   colrev prep-man

Exports the ``records_prep_man.bib`` (containing the records) and the ``records_prep_man_info.csv`` (containing the error codes).


#. Manually fix the errors

Manually change the bib file (based on error codes in csv file)
Error code descriptions are available `here <https://colrev.readthedocs.io/en/latest/resources/quality_model.html>`_.


#. (Re) import the records

.. code-block::

   colrev prep-man

Notes:


* There is no need to change the colrev_status fields (it will be reevaluated upon import)
* The colrev_status field can be used to override error codes
* It can also be set to rev_prescreen_excluded (or the entry can be deleted)
* When ENTRYTYPEs need to be corrected, change the ENTRYTYPE, and run ``colrev prep-man`` twice (remove the BIB and CSV file before the second run). This will reapply the field requirements for the new ENTRYTYPE. For example, if a record needs to switch from ``article`` to ``inproceedings``\ , reapplying the field requirements will create the ``booktitle`` field and indicate that the ``journal``\ , ``volume``\ , and ``number`` fields are no longer needed.

Links
-----
