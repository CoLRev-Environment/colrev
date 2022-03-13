
Collaborative Literature Reviews
========================================

CoLRev (Collaborative Literature Reviews) aims at facilitating highly collaborative literature reviews involving teams of researchers, state-of-the-art algorithms, and content curated by the research community.
The core proposition is that the transparent collaboration model of git, combined with a robust content-based identification scheme, and a content curation model can enable literature review processes that are more trustworthy, more efficient, and richer.


Getting started
-----------------

CoLRev is implemented in Python and should be compatible with Windows, MacOS, and Linux.
To install the CoLRev command-line interface, install `git <https://git-scm.com/>`_ and `docker <https://www.docker.com/>`_ and run

.. code-block::

   pip install colrev

To use the colrev command-line interface, run

.. code-block::

   colrev status

The colrev status command displays the current state of the review and guides you to the next steps (see `guidelines <guides/user_documentation.html>`_).
After each processing step, make sure to `check the changes <guides/changes.html>`_, effectively following a three-step cycle:

.. figure:: ../figures/workflow-cycle.svg
   :width: 700
   :alt: Workflow cycle

Conducting a full literature review should be as simple as running the following commands (each one followed by `git status`/`gitk` and `colrev status`):

.. code-block:: bash

      # Initialize the project
      colrev init

      colrev search --add "RETRIEVE * FROM crossref WHERE digital"
      # Or store search results in the search directory

      # Load the seach results
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

Further details are provided in the `user documentation <guides/user_documentation.html>`_.

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Contents:

.. toctree::
   :hidden:
   :maxdepth: 1
   :caption: Guidelines

   guides/user_documentation
   guides/extensions
   guides/best_practices

.. toctree::
   :hidden:
   :caption: Technical documentation
   :maxdepth: 1

   technical_documentation/colrev
   Contribution guide <https://github.com/geritwagner/colrev_core/blob/main/CONTRIBUTING.md>
   Github repository <https://github.com/geritwagner/colrev_core>
   technical_documentation/extension_development
   technical_documentation/roadmap
   technical_documentation/about
