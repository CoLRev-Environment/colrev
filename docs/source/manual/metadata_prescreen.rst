
.. _Metadata prescreen:

Step 3: Metadata prescreen
---------------------------------------------

The metadata prescreen refers to the inclusion or exclusion of records based on titles and abstracts (if available).
It's main purpose is to reduce the number of records by excluding those that are clearly irrelevant to the review objectives.
When in doubt, records can be retained or included provisionally to decide in step 5, i.e., the screen based on full-text documents.

The prescreen can be split among multiple authors (using ``colrev prescreen --split n``).
Each author can independently screen the selection of records on a separate git branch.
The reconciliation of partially overlapping independent prescreens (in separate git branches) is supported by ``colrev merge``.

In addition to the different prescreening options (such as rule-based or machine-learning-supported prescreens),
it is also possible to deactivate the prescreen for the current iteration (using ``colrev prescreen --include_all``)
or in general (using ``colrev prescreen --include_all_always``).

.. toctree::
   :maxdepth: 3
   :caption: Operations

   metadata_prescreen/prescreen
