
Extension development
==================================

Developing extensions for CoLRev in Python/R is easy. Examples are available online (e.g., `1 <https://github.com/geritwagner/colrev_endpoint>`_, `2 <https://github.com/geritwagner/local_paper_index>`_, and `3 <https://github.com/geritwagner/paper_feed>`_). We provide examples and instructions below.

**Recommendations**:

- Get paths (as shown in :program:`colrev config`) from REVIEW_MANAGER.paths
- Use the logger (report vs tool/extension)
    - colrev_report logger: infos that are helpful to examine and validate the process, including links to the docs where instructions for tracing and fixing errors are available
    - extension logger: logg infos on the progress. The output should be relatively short and allow users to see the progress and judge whether any errors occurred

- `Add <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics>`_ the ```colrev-extension``` `topic tag on Github <https://github.com/topics/colrev-extension>`_ to allow others to find and use your work


Python
-----------

.. code-block:: python

    import logging
    from colrev_core.process import PrepProcess

    # Initialize the process and notify the ReviewManager
    PREP_PROCESS = PrepProcess()

    REVIEW_MANAGER= PREP_PROCESS.REVIEW_MANAGER
    REVIEW_DATASET = REVIEW_MANAGER.REVIEW_DATASET

    # Load the records and apply changes
    records = REVIEW_DATASET.load_records()
    for record in records:
        ....
        self.report_logger.info('Applied changes...')

    # Save the changes, add them to git, and create commit
    REVIEW_DATASET.save_records(records)
    REVIEW_DATASET.add_record_changes()
    REVIEW_MANAGER.create_commit("Pre-screening (extension X")


R
---

For analytical extensions

.. code-block:: R

    # install.packages("bib2df")
    library(bib2df)

    df <- bib2df("references.bib")
    df

For extensions aimed at changing records

.. code-block:: R

    # install.packages("reticulate")
    library(reticulate)
    colrev_core <- reticulate::import("colrev_core")

     # Initialize the ReviewManager and notify about upcoming process
    PREP_PROCESS <- colrev_core$process$PrepProcess()
    REVIEW_MANAGER = PREP_PROCESS$REVIEW_MANAGER
    REVIEW_DATASET = PREP_PROCESS$REVIEW_DATASET

    # Load the records and apply changes
    records = REVIEW_DATASET$load_records()
