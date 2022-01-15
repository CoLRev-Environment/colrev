
Dedupe
==================================

:program:`colrev dedupe` identifies and merges duplicates as follows:

- In an active learning process (based on the `dedupe <https://github.com/dedupeio/dedupe>`_ library), researchers are asked to label pairs of papers
- Once enough pairs have been labeled (e.g., at least 50 duplicates and 50 non-duplicates), the remaining records are matched and merged automatically
- To validate the results, spreadsheets are exported in which duplicate and non-duplicate pairs can be checked (taking into consideration the differences in metadata and the confidence provided by the classifier)
- Corrections can be applied by marking pairs in the spreasheet and running colrev dedupe -f

.. code:: bash

	colrev dedupe [options]

TODO: include a screenshot of the spreadsheet
