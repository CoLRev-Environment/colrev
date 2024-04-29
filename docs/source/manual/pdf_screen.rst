Step 5: PDF screen
---------------------------------------------

The PDF screen refers to the final inclusion or exclusion of records based on PDF documents.
In this step, screening criteria, which can be inclusion or exclusion criteria, are a means to making these decisions more transparent (e.g., in a PRISMA flow chart).
Records are only included when none of the criteria is violated.
This step is typically conducted manually, although tools may increasingly augment the screen.

As a means to controlling and reducing subjective inclusion decisions, the screen can be completed in a parallel indepedent mode.
Similar to the prescreen, authors screen their subsets of records on separate git branches.
CoLRev supports the reconciliation with the ``colrev merge`` operation.

Although most methodological sources suggest to complete the screen before the data analysis and synthesis step, others propose an integrated cycle of materials screening, assessment, mapping, and synthesis.
In CoLRev, this can be accomplished by means of a retrospective screen, in which all records are included initially (using ``colrev screen --include_all_always``), but potentialy excluded during the cycle iterations.
For example, this can be done using the `EXCLUDE annotation <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/packages/paper_md/README.md>`_ in a paper.

..
   TODO : add colrev screen --exclude IDs

Similar to the prescreen, it is possible to skip the screen temporarily (``colrev screen --include_all``) or permanently (``colrev screen --include_all_always``).
This may be particularly useful in scientometric studies.

.. toctree::
   :maxdepth: 1
   :caption: Operations

   pdf_screen/screen
