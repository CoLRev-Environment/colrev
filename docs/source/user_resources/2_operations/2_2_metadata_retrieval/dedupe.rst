.. _Dedupe:

Metadata retrieval - dedupe
==================================

TODO

- mention merging as colrev_origin linking (instead of removing duplicate records)
- mention the merge-records function
- mention languages (as an open issue/our approach)
- mention algorithms and safeguards

:program:`colrev dedupe` identifies and merges duplicates as follows:

- Curated journals are queried (using the LocalIndex) to identify duplicates/non-duplicates
- In an active learning process (based on the `dedupeio <https://github.com/dedupeio/dedupe>`_ library), researchers are asked to label pairs of papers
- During the active learning (labeling) process, the LocalIndex is queried to prevent accidental merges (effectively implementing FP safeguards)
- Once enough pairs have been labeled (e.g., at least 50 duplicates and 50 non-duplicates), the remaining records are matched and merged automatically
- To validate the results, spreadsheets are exported in which duplicate and non-duplicate pairs can be checked (taking into consideration the differences in metadata and the confidence provided by the classifier)
- Corrections can be applied by marking pairs in the spreadsheet ("x" in the *error* column), saving the file, and running colrev dedupe -f
- Records from the same source file are not merged automatically (same source merges have a very high probability of introducing erroneous merge decisions)
- In case there are not enough records to train an active learning model, a simple duplicate identification algorithm is applied (followed by a manual labeling of borderline cases)

.. code:: bash

	colrev dedupe [options]

.. option:: --fix_errors

    Load errors as highlighted in the spreadsheets (duplicates_to_validate.xlsx, non_duplicates_to_validate.xlsx) and fix them.

.. figure:: ../../../figures/duplicate_validation.png
   :alt: Validation of duplicates
