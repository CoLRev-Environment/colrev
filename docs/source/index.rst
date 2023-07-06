
Collaborative Literature Reviews
========================================

.. figure:: https://raw.githubusercontent.com/CoLRev-Ecosystem/colrev/main/docs/figures/logo_small.png
   :width: 400
   :align: center
   :alt: Logo

CoLRev is an open-source environment for collaborative literature reviews. It integrates with differerent synthesis tools, takes care of the data, and facilitates Git-based collaboration.

To accomplish these goals, CoLRev advances the design of review technology at the intersection of methods, design, cognition, and community building.
The following features stand out:

- An open and extensible environment based on data and process standards
- Builds on git and its transparent collaboration model for the entire literature review process
- Offers a self-explanatory, fault-tolerant, and configurable user workflow
- Operates a model for data quality, content curation, and reuse
- Provides validate and undo operations
- Enables typological and methodological pluralism throughout the process (`in-progress <https://github.com/CoLRev-Environment/colrev/issues/110>`_)

Please consult the `statements of development status <https://colrev.readthedocs.io/en/latest/foundations/dev_status.html>`_. A brief overview presented at ESMARConf2023 is available on `YouTube <https://www.youtube.com/watch?v=yfGGraQC6vs>`_.

Getting started
---------------------------------------

After installing `git <https://git-scm.com/>`_ and `docker <https://www.docker.com/>`_ (Docker is optional but recommended):

.. code-block::

   # Install
   pip install colrev

   # ... and start with the main command
   colrev status

The CoLRev environment supports for the whole literature review process:

.. figure:: ../figures/figure-docs.png
   :width: 600
   :align: center
   :alt: Workflow cycle


Completing a literature review should be as simple as running the following commands:

.. code-block::

   # Formulate the objectives, initialize the project, specify the review type
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

Further information is provided in the `documentation <index.html>`_, the developer `API reference <foundations/api.html>`_, and the `CoLRev framework <foundations/colrev.html>`_ summarizing the scientific foundations.


.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Contents:

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Manual

   Introduction <manual/manual>
   manual/operations
   manual/workflow
   manual/problem_formulation
   manual/setup
   manual/metadata_retrieval
   manual/metadata_prescreen
   manual/pdf_retrieval
   manual/pdf_screen
   manual/data
   manual/collaboration
   manual/curation
   manual/quality_model
   manual/extensions
   manual/reference_manager
   manual/credits
   manual/help

.. toctree::
   :hidden:
   :caption: Documentation and governance
   :maxdepth: 1

   foundations/colrev
   foundations/api
   foundations/cli
   foundations/extensions
   foundations/dev_status
   foundations/about


.. toctree::
   :hidden:
   :caption: Links
   :maxdepth: 1

   Github repository <https://github.com/CoLRev-Environment/colrev>
   PyPI <https://pypi.org/project/colrev/>
