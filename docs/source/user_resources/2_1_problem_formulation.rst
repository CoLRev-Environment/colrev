

.. _Problem formulation:

Step 1: Problem formulation
==================================

Literature reviews begin with the problem formulation step in which reviewers **specify the objective, the review type and its characteristics, the focal concepts, and the plans for how the review team will conduct the review**.
This step may be informal and evolve throughout the review process, or be more formal and even involve a review protocol.

..
   does not involve any records, but it can be updated throughout the process (e.g., after an exploratory search was completed)

Methodological guidelines emphasize that the objectives and the review types, as well as the following methodological choices, should be coherent.
It is therefore recommended to familiarize with the different types of review (**TODO: link to resources/classifications/ideally a database overview**).


Once the objective, review type, etc. are specified, the CoLRev project can be initialized.
With the ``colrev init`` operation, the required directories and files, including the git history, are set up.
Ideally, the selected review type is passed as a parameter (as described `here <2_1_problem_formulation/init.html>`_).
With this parameter, ``colrev init`` creates a ``settings.json`` file containing reasonable defaults for the review type.
For example, a theoretical review may involve an emergent data analysis and synthesis approach, while a meta-analysis will involve a structured data extraction and a PRISMA flow chart for transparent reporting.

The review objective and additional details can be added to the ``data/paper.md`` file.
This file may also serve as the review protocol and evolve into the final review manuscript.

..
   - working hypothesis: differences between review types primarily manifest in the data stage (in the other steps, it is mostly a question of parameters)
   - Indicate that different forms of `data <2_6_data/data.html>`data analysis are activated by the selected review types  (per default)
   - mention settings (but do not display complete settings.json, which is too long?)


.. toctree::
   :maxdepth: 3
   :caption: Operations

   2_1_problem_formulation/init
