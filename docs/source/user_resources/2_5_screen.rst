
.. _PDF screen:

Step 5: Full-text screen
---------------------------------------------

The full-text screen refers to the final inclusion or exclusion of records based on full-text documents.
Screening criteria, which can be inclusion or exclusion criteria, are a means to making these decisions more transparent (e.g., in a PRISMA flow chart).
Records are only included when none of the criteria is violated.

As a means to controlling and reducing subjective, idiosyncratic inclusion decisions, the screen can be completed in a parallel indepedent mode (using ``colrev screen --split n``).
Similar to the prescreen, authors screen their subsets of records on separate git branches.
CoLRev supports the reconciliation with the ``colrev merge`` operation.

Although most methodological sources suggest to complete the screen before the data analysis and synthesis step, others propose an integrated cycle of materials screening, assessment, mapping, and synthesis.
In CoLRev, this can be accomplished by means of a "retrospective screen", in which all records are included initially (using ``colrev screen --include_all_always``), but potentialy excluded during the cycle iterations.
For example, this can be done using the `EXCLUDE annotation <https://github.com/geritwagner/colrev/blob/main/colrev/ops/built_in/data/manuscript.py#L405>`_ in a synthesis document.

..
   TODO : add colrev screen --exclude IDs

Similar to the prescreen, it is possible to skip the screen temporarily (``colrev screen --include_all``) or permanently (``colrev screen --include_all_always``).
This may be particularly useful in scientometric studies.

The screen step corresponds to a single operation:

.. toctree::
   :maxdepth: 3
   :caption: Operations

   2_5_screen/screen
