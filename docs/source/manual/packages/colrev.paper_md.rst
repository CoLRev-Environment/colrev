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
colrev.paper_md
===============

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/paper_md>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - data
     - |MATURING|
     - .. code-block::


         colrev data --add colrev.paper_md


Summary
-------

data
----


.. raw:: html

   <!--
   Note: This document is currently under development. It will contain the following elements.

   - description
   - example
   -->



The paper-md endpoint can be used to create a review protocol or a manuscript based on `pandoc <https://pandoc.org/>`_ and `csl citation styles <https://citationstyles.org/>`_.

Pandoc can use different template files to generate word, pdf, or latex outputs (among others).

The ``data/data/paper.md`` file may serve as a review protocol at the beginning and evolve into the final manuscript.

The citation style can be change in the ``data/data/paper.md`` header. The template can be changed in the ``settings.json`` (\ ``data/data_package_endpoints/colrev.paper_md/word_template``\ ).

Upon running the paper-md (as part of ``colrev data``\ ), new records are added after the following marker (as a to-do list):

.. code-block::

   # Coding and synthesis

   _Records to synthesize_:<!-- NEW_RECORD_SOURCE -->

   - @Smith2010
   - @Webster2020

Once record citations are moved from the to-do list to other parts of the manuscript, they are considered synthesized and are set to ``rev_synthesized`` upon running ``colrev data``.

Links
-----


.. image:: https://img.shields.io/github/commit-activity/y/jgm/pandoc?color=green&style=plastic
   :target: https://img.shields.io/github/commit-activity/y/jgm/pandoc?color=green&style=plastic
   :alt: pandocactivity

`pandoc <https://github.com/jgm/pandoc>`_ to convert Markdown to PDF or Word (License: `GPL 2 <https://github.com/jgm/pandoc/blob/main/COPYRIGHT>`_\ )


.. image:: https://img.shields.io/github/commit-activity/y/citation-style-language/styles?color=green&style=plastic
   :target: https://img.shields.io/github/commit-activity/y/citation-style-language/styles?color=green&style=plastic
   :alt: cslactivity

`CSL <https://github.com/citation-style-language/styles>`_ to format citations (License: `CC BY-SA 3.0 <https://github.com/citation-style-language/styles>`_\ )
