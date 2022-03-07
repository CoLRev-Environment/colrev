
Colaborative Literature Reviews
========================================

The Colaborative Literature Reviews (CoLRev) framework provides a standardized environment, an extensible core engine, and a reference implementation for conducting highly collaborative reviews with a team of researchers and state-of-the-art algorithms.
A reliable and efficient process requires

- a standard data structure,
- a shared model for the steps of the review process,
- dedicated procedures for metadata and fulltext preparation,
- principles for trustworthy use of algorithmic and crowdsourced changes,
- a powerful versioning system (git) that makes changes transparent, and
- collaboration principles that are monitored automatically.

CoLRev aspires to be self-explanatory, to anticipate, prevent, and resolve errors, and thereby allow researchers to orchestrate researcher-crowd-machine ensembles with confidence.
Simply `install the colrev environment <guides/installation.html>`_ and run

.. code-block::

   colrev status

This command displays the current state of the review and guides you to the next steps (see `guidelines <guides/overview.html>`_).
After each processing step, make sure to `check the changes <guides/changes.html>`_, effectively following a three-step cycle:

.. figure:: ../figures/workflow-cycle.svg
   :width: 700
   :alt: Workflow cycle

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Contents:

.. toctree::
   :hidden:
   :maxdepth: 1
   :caption: Guidelines

   guides/installation
   guides/overview
   guides/init
   guides/search
   guides/load
   guides/prep
   guides/dedupe
   guides/prescreen
   guides/pdf_get
   guides/pdf_prep
   guides/screen
   guides/data
   guides/paper

.. toctree::
   :hidden:
   :caption: Framework
   :maxdepth: 1

   framework/colrev
   framework/extension_development
   framework/roadmap

.. toctree::
   :hidden:
   :caption: Resources
   :maxdepth: 1

   resources/extensions
   resources/best_practices
   Github repository <https://github.com/geritwagner/colrev_core>
   resources/about
