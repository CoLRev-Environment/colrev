
Collaborative Literature Reviews
========================================

.. figure:: https://raw.githubusercontent.com/geritwagner/colrev/main/docs/figures/logo_small.png
   :width: 400
   :align: center
   :alt: Logo


CoLRev is an open-source environment for collaborative reviews.
To make major improvements in terms of efficiency and trustworthiness and to automatically augment reviews with community-curated content, CoLRev advances the design of review technology at the intersection of methods, engineering, cognition, and community building.
Compared to other environments, the following features stand out:

- an **extensible and open platform** based on shared data and process standards
- builds on **git** and its transparent collaboration model for the entire literature review process
- offers a **self-explanatory, fault-tolerant, and configurable** user workflow
- implements a granular **data provenance** model and **robust identification** schemes
- provides **end-to-end process support** and allows you to **plug in state-of-the-art tools**
- enables **typological and methodological pluralism** throughout the process
- operates a **built-in model for content curation** and reuse

Getting started
---------------------------------------

After installing `git <https://git-scm.com/>`_ and `docker <https://www.docker.com/>`_:


.. code-block::

   # Install
   pip install colrev

   # ... and start with the main command
   colrev status


**The workflow** consists of three steps. This is all you need to remember. The status command displays the current state of the review and guides you to the next [operation](docs/build/user_resources/manual.html).
After each operation, [validate the changes](docs/build/user_resources/manual/1_workflow.html#colrev-validate).

.. figure:: https://raw.githubusercontent.com/geritwagner/colrev/51b566b6a2fffedda1a5ab5df14a0f387326460b/docs/figures/workflow.svg
   :width: 600
   :align: center
   :alt: Workflow cycle

**The operations** allow you to complete a literature review. It should be as simple as running the following commands:


.. code-block::

   # Initialize the project, formulate the objectives, specify the review type
   colrev init

   # Store search results in the data/search directory
   # Load, prepare, and deduplicate the metadata reocrds
   colrev retrieve

   # Conduct a prescreen
   colrev prescreen

   # Get and prepare the PDFs
   colrev pdfs

   # Conduct a screen based on PDFs
   colrev screen

   # Complete the forms of data analysis and synthesis, as specified in the settings
   colrev data

For each operation, the **colrev settings** document the tools and parameters. You can rely on the built-in reference implementation of colrev, specify external tools, or include custom scripts. The settings are adapted to the type of review and suggest reasonable defaults. You have the option to customize and adapt.

.. figure:: https://raw.githubusercontent.com/geritwagner/colrev/51b566b6a2fffedda1a5ab5df14a0f387326460b/docs/figures/settings.svg
   :width: 600
   :align: center
   :alt: Settings


**The project collaboration loop** allows you to synchronize the project repository with your team.
The *colrev pull* and *colrev push* operations make it easy to collaborate on a specific project while reusing and updating record data from multiple curated repositories.
In essence, a CoLRev repository is a git repository that follows the CoLRev data standard and is augmented with a record-level curation loop.

**The record curation loop** proposes a new vision for the review process.
Reuse of community-curated data from different sources is built into each operation.
It can substantially reduce required efforts and improve richness, e.g., through annotations of methods, theories, and findings.
The more records are curated, the more you can focus on the synthesis.


.. figure:: https://raw.githubusercontent.com/geritwagner/colrev/51b566b6a2fffedda1a5ab5df14a0f387326460b/docs/figures/reuse-vision_loop.svg
   :width: 800
   :align: center
   :alt: Reuse vision

Further information is provided in the `documentation <docs/source/index.rst>`_, the developer `api reference <docs/build/technical_documentation/api.html>`_, and the `CoLRev framework <docs/build/technical_documentation/colrev.html>`_ summarizing the scientific foundations.


.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Contents:

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: User resources

   Introduction <user_resources/manual>
   user_resources/1_operations
   user_resources/2_workflow
   user_resources/2_1_problem_formulation
   user_resources/2_2_metadata_retrieval
   user_resources/2_3_metadata_prescreen
   user_resources/2_4_pdf_retrieval
   user_resources/2_5_pdf_screen
   user_resources/2_6_data
   user_resources/3_collaboration
   user_resources/4_curation
   user_resources/5_extensions
   user_resources/6_sources
   user_resources/credits
   user_resources/help

.. toctree::
   :hidden:
   :caption: Documentation and governance
   :maxdepth: 1

   foundations_governance/colrev
   technical_documentation/api
   technical_documentation/cli
   technical_documentation/extensions
   foundations_governance/roadmap
   foundations_governance/about


.. toctree::
   :hidden:
   :caption: Links
   :maxdepth: 1

   Github repository <https://github.com/geritwagner/colrev>
   PyPI <https://pypi.org/project/colrev/>
