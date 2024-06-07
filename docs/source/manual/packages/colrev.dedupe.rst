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
colrev.dedupe
=============

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/dedupe>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - dedupe
     - |STABLE|
     - .. code-block::


         colrev dedupe --add colrev.dedupe


Summary
-------

BibDedupe is an open-source Python library for deduplication of bibliographic records, tailored for literature reviews. Unlike traditional deduplication methods, BibDedupe focuses on entity resolution, linking duplicate records instead of simply deleting them.


.. image:: https://joss.theoj.org/papers/b954027d06d602c106430e275fe72130/status.svg
   :target: https://joss.theoj.org/papers/b954027d06d602c106430e275fe72130
   :alt: status


**Features**


* Automated Duplicate Linking with Zero False Positives: BibDedupe automates the duplicate linking process with a focus on eliminating false positives.
* Preprocessing Approach: BibDedupe uses a preprocessing approach that reflects the unique error generation process in academic databases, such as author re-formatting, journal abbreviation or translations.
* Entity Resolution: BibDedupe does not simply delete duplicates, but it links duplicates to resolve the entitity and integrates the data. This allows for validation, and undo operations.
* Programmatic Access: BibDedupe is designed for seamless integration into existing research workflows, providing programmatic access for easy incorporation into scripts and applications.
* Transparent and Reproducible Rules: BibDedupe's blocking and matching rules are transparent and easily reproducible to promote reproducibility in deduplication processes.
* Continuous Benchmarking: Continuous integration tests running on GitHub Actions ensure ongoing benchmarking, maintaining the library's reliability and performance across datasets.
* Efficient and Parallel Computation: BibDedupe implements computations efficiently and in parallel, using appropriate data structures and functions for optimal performance.

dedupe
------

The `bib-dedupe <https://github.com/CoLRev-Environment/bib-dedupe>`_ package is the default deduplication module for CoLRev.
It is activated by default and is responsible for removing duplicate entries in the data.

Cite
----

.. code-block::

   @article{Wagner_BibDedupe_An_Open-Source_2024,
           author  = {Wagner, Gerit},
           doi     = {10.21105/joss.06318},
           journal = {Journal of Open Source Software},
           month   = may,
           number  = {97},
           pages   = {6318},
           title   = {{BibDedupe: An Open-Source Python Library for Bibliographic Record Deduplication}},
           url     = {https://joss.theoj.org/papers/10.21105/joss.06318},
           volume  = {9},
           year    = {2024}
           }

Links
-----


* `bib-dedupe <https://github.com/CoLRev-Environment/bib-dedupe>`_
* `Documentation <https://colrev-environment.github.io/bib-dedupe/>`_
* `Evaluation <https://colrev-environment.github.io/bib-dedupe/evaluation.html>`_
