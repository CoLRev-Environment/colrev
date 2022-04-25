
Collaborative Literature Reviews
========================================

.. figure:: ../figures/logo_small.png
   :width: 250
   :align: center
   :alt: Logo

CoLRev provides an open-source next-generation environment for collaborative reviews.
To accomplish major improvements in efficiency, trustworthiness, and richness, CoLRev innovates in key areas:

- leveraging the transparent collaboration model of **git** for the whole literature review process
- desigining a **fault-tolerant and self-explanatory** workflow
- implementing a comprehensive **data provenance** model and **robust identification** schemes
- providing **state-of-the-art algorithms** for each step of the review process
- creating an open and extensible ecosystem of **file-based interfaces**
- fostering **typological pluralism** through different forms of data analysis
- advancing a built-in model for **content curation** and reuse

Getting started
-----------------

After `installing CoLRev <guides/manual.html#installation>`_, use the command-line interface

.. code-block::

   colrev status

The status command displays the current state of the review and guides you to the next steps (`CoLRev operations <guides/manual.html>`_).
After each operation, `check the changes <guides/manual.html#analyze-changes>`_ to complete the three-step cycle:

.. figure:: ../figures/workflow-simple.svg
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

A key feature of CoLRev is its collaboration and content curation model, which makes it easy to use and update curated data while collaborating on a CoLRev project

.. figure:: ../figures/reuse-vision.svg
   :width: 800
   :align: center
   :alt: Reuse vision

Reuse of community-curated data is built into each step and can significantly reduce the efforts required.
The more records are curated, the more you can focus on the search, prescreen/screen and synthesis.
Further details are provided in the `manual <guides/manual.html>`_.


Citing CoLRev
-----------------

Please refer to the present GitHub project:

.. code-block:: BibTeX

   @misc{colrev,
   author = {Wagner, G. and Prester, J.},
   title = {CoLRev - A Framework for Colaborative Literature Reviews},
   howpublished = {\url{https://github.com/geritwagner/colrev_core}},
   publisher = {GitHub},
   year = {2022},
   }

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Contents:

.. toctree::
   :hidden:
   :maxdepth: 1
   :caption: Guidelines

   guides/manual
   cli
   guides/best_practices

.. toctree::
   :hidden:
   :caption: Technical documentation
   :maxdepth: 1

   technical_documentation/colrev
   api
   Contribution guide <https://github.com/geritwagner/colrev_core/blob/main/CONTRIBUTING.md>
   GitHub repository <https://github.com/geritwagner/colrev_core>
   technical_documentation/extensions
   technical_documentation/roadmap
   technical_documentation/credits
   technical_documentation/about
