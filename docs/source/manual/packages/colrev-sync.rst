.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 14pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 14pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 14pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |VERSION| image:: /_static/svg/iconmonstr-product-10.svg
   :width: 15
   :alt: Version
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
colrev-sync
===========

|VERSION| Version: 0.4.0

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev-sync <https://github.com/CoLRev-Environment/colrev-sync>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - na
     - |EXPERIMENTAL|

Summary
-------

The colrev-sync package imports references from CoLRev projects (through local_index) into non-CoLRev paper projects that use Markdown and BibTeX.
If BibTeX citations keys are used in the paper project, the following command retrieves the corresponding bibliographical details and adds them to the BibTeX file:

.. code-block::

   colrev-sync

CoLRev sync can also be used through pre-commit hooks, when the following is included in the ``.pre-commit-config.yaml``\ :

.. code-block::

   -   repo: local
       hooks:
       -   id: colrev-hooks-update
           name: "CoLRev ReviewManager: update"
           entry: colrev-hooks-update
           language: python
           stages: [commit]
           files: 'records.bib|paper.md'
