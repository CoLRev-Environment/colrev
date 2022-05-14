
Collaborative Literature Reviews
========================================

.. figure:: ../figures/logo_small.png
   :width: 250
   :align: center
   :alt: Logo

CoLRev is an open-source environment for collaborative reviews.
To make major improvements in terms of efficiency and trustworthiness and to automatically augment records with community-curated content, CoLRev innovates in key areas:

- leveraging the transparent collaboration model of **git** for the entire literature review process
- desigining a **self-explanatory, fault-tolerant, and configurable** user workflow
- creating an extensible ecosystem of **file-based interfaces** following open data standards
- implementing a **granular data provenance** model and a **robust identification** scheme
- incorporating **state-of-the-art algorithms** to provide end-to-end process support
- fostering **typological pluralism** through different forms of data analysis
- advancing a built-in model for **content curation** and reuse

Getting started
-----------------

After installing `git <https://git-scm.com/>`_ and `docker <https://www.docker.com/>`_:

.. code-block::

   # Install
   pip install colrev

   # ... and start with the main command
   colrev status

The status command displays the current state of the review and guides you to the next steps (`CoLRev operations <guides/manual.html>`_).
After each operation, `check the changes <guides/manual.html#analyze-changes>`_ to complete the three-step cycle:

.. figure:: ../figures/workflow.svg
   :width: 400
   :align: center
   :alt: Workflow cycle

Conducting a literature review should be as simple as running the following operations:

.. code-block:: bash

      # Initialize the project
      colrev init

      colrev search --add "FROM crossref WHERE digital"
      # Or store search results in the search directory

      # Load the search results
      colrev load

      # Prepare the metadata
      colrev prep

      # Identify and merge duplicates
      colrev dedupe

      # Conduct a prescreen
      colrev prescreen

      # Get the PDFs for included papers
      colrev pdf-get

      # Prepare the PDFs
      colrev pdf-prep

      # Conduct a screen (using specific criteria)
      colrev screen

      # Complete the data analysis/synthesis
      colrev data

      # Build the paper
      colrev paper

A CoLRev repository is a git repository that follows the CoLRev data standard and is augmented with a content curation model.
The corresponding *colrev pull* and *colrev push* operations make it easy to reuse and update record data from multiple curated repositories while collaborating on a specific project

.. figure:: ../figures/reuse-vision.svg
   :width: 800
   :align: center
   :alt: Reuse vision

Reuse of community-curated data from different sources is built into each operation.
It can substantially reduce required efforts and improve richness, e.g., through annotations of methods, theories, and findings.
The more records are curated, the more you can focus on the synthesis.

Citing CoLRev
-----------------

Please `cite <_static/colrev_citation.bib>`__ the `GitHub project <https://github.com/geritwagner/colrev_core>`__:

Wagner, G. and Prester, J. (2022) CoLRev - A Framework for Collaborative Literature Reviews. Available at https://github.com/geritwagner/colrev_core.

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Contents:

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Guidelines

   Manual <guides/manual>
   guides/cli
   guides/help

.. toctree::
   :hidden:
   :caption: Technical documentation
   :maxdepth: 1

   technical_documentation/colrev
   technical_documentation/api
   technical_documentation/roadmap
   technical_documentation/credits
   technical_documentation/about
