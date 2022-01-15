
Colaborative Literature Reviews
========================================

To install the CoLRev command-line interface, install `git <https://git-scm.com/>`_ and `docker <https://www.docker.com/>`_ and run

.. code-block::

   pip install colrev


CoLRev aspires to be self-explanatory, to anticipate, prevent, and resolve errors, and thereby allow researchers to incorporate different contributions with confidence.
Simply run

.. code-block::

   colrev status

This command will display the current state of the review and guide you to the next steps of the review process (see guidelines below).
After each processing step, make sure to `check the changes <guides/changes.html>`_, effectively following a three-step cycle:


.. figure:: ../figures/workflow-cycle.svg
   :width: 700
   :alt: Workflow cycle

The ambition of CoLRev is to establish principles for conducting highly collaborative reviews involving a team of researchers and algorithms.
An efficient and reliable process relies on

- a standard data structure,
- a shared model for the steps of the review process,
- a transparent versioning system (git), and
- collaboration principles that are monitored automatically.

These elements enable researchers to trace changes and records, conduct different types of (standalone) reviews, incorporate crowdsourced data with ease, and apply state-of-the-art machine-learning algorithms with more confidence.



.. toctree::
   :maxdepth: 2
   :caption: Contents:

.. toctree::
   :maxdepth: 1
   :caption: Guidelines

   guides/overview
   guides/init
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
   :caption: Extensions
   :maxdepth: 1

   extensions/cml_assistant
   extensions/endpoint
   extensions/local_paper_index
   extensions/paper_feed


.. toctree::
   :caption: The CoLRev Standard
   :maxdepth: 1

   architecture/principles
   architecture/extensions
   architecture/roadmap

.. toctree::
   :caption: Resources
   :maxdepth: 1

   resources/best_practices
   resources/resources
   resources/about


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
