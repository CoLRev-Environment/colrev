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
colrev.enlit
============

|VERSION| Version: 0.1.0

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/enlit>`_

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

ENLIT is a tool that supports scholars in exploring new literature:


* It makes **backward searches more efficient** by extracting the references from a literature corpus (set of PDFs) and providing a list without duplicates. It also provides statistics on journals and authors that are cited frequently by the given literature corpus.
* It implements a **new exploratory strategy that facilitates understanding**\ : simply start by reading the most influential papers and skim the remaining papers afterwards. A paper that explains why this strategy is more effective than the traditional skim first and read afterwards approach will be published soon.

Authors


* Philip Empl - University of Regensburg
* Gerit Wagner - Otto-Friedrich-Universität Bamberg

Installation
------------

.. code-block:: bash

   colrev install colrev.enlit

Usage
-----

Run the following command in a CoLRev repository:

.. code-block:: bash

   colrev_enlit

Cite
----

Wagner, G., Empl, P., & Schryen, G. (2020, May). Designing a novel strategy for exploring literature corpora. In *Proceedings of the European Conference on Information Systems*. https://aisel.aisnet.org/ecis2020_rp/44/

Original repository: `link <https://github.com/digital-work-lab/enlit>`_

License
-------

This project is licensed under the MIT License - see the `LICENSE <LICENSE>`_ file for details.
