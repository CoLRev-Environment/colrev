colrev dedupe
==================================

.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 12pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 12pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 12pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html

The ``colrev dedupe`` operation identifies and merges duplicate records. Non-duplicate records transition from ``md_prepared`` to ``md_processed``. Duplicate records are integrated based on a quality-aware merge function and the combined record transitions to ``md_processed``. The predecessors of a merged record can be identified through the ``colrev_origin`` list, enabling ex-post validation and offering the possibility to undo merges.

..
    - mention languages (as an open issue/our approach)
    - mention algorithms and safeguards

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

..
    TODO : valudation and colrev dedupe merge/unmerge

    .. option:: --fix_errors

        Load errors as highlighted in the spreadsheets (duplicates_to_validate.xlsx, non_duplicates_to_validate.xlsx) and fix them.

    .. figure:: ../../../figures/duplicate_validation.png
    :alt: Validation of duplicates

The following options for ``dedupe`` are available:

.. datatemplate:json:: ../package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Identifier", "package_endpoint_identifier"), ("Dedupe packages", "short_description"), ("Status", "status")],
        data['dedupe'],
        title='',
        columns=[25,55,20]
        ) }}
