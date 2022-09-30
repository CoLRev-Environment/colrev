
A. Appendix
==================================


Publication
------------------

TODO: how to publish  (include a license, link at colrev/make it discoverable, do not include paywalled PDFs - not even in the history )

call colrev prep --polish (e.g., to update references that were in print when retrieved but have been published in the meantime)

Curation
------------------

TODO: introductory guidelines on curating repositories


Extension
------------------


Extensions of CoLRev are available on `GitHub <https://github.com/topics/colrev-extension>`_. Guidelines on extension development and a few examples are summarized below.

Extension development
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Developing CoLRev extensions in Python/R is easy. Instructions and examples are provided below.

**Recommendations**:

- Get paths (as shown in :program:`colrev settings`) from REVIEW_MANAGER.paths
- Use the logger (report vs tool/extension)
    - colrev_report logger: log info that are helpful to examine and validate the process, including links to the docs where instructions for tracing and fixing errors are available
    - extension logger: log info on the progress. The output should be relatively short and allow users to see the progress and judge whether any errors occurred

- `Add <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics>`_ the ```colrev-extension``` `topic tag on GitHub <https://github.com/topics/colrev-extension>`_ to allow others to find and use your work


Python
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    import logging
    from colrev.review_manager import ReviewManager
    from colrev.operations import PrepProcess

    # Initialize the ReviewManager
    REVIEW_MANAGER = ReviewManager()

    # Initialize the process and notify the ReviewManager
    PREP_PROCESS = PrepProcess(REVIEW_MANAGER)

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
    colrev <- reticulate::import("colrev")

    # Initialize the ReviewManager
    REVIEW_MANAGER <- colrev$review_manager$ReviewManager()

    # Initialize the PrepProcess and notify about upcoming process
    PREP_PROCESS <- colrev$process$PrepProcess(REVIEW_MANAGER)

    REVIEW_DATASET = PREP_PROCESS$REVIEW_DATASET

    # Load the records and apply changes
    records = REVIEW_DATASET$load_records()


Example: colrev_cml_assistant
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Aimed at supporting crowdsourcing and machine-learning based on CoLRev datasets.

Link to the repository: `colrev_cml_assistant <https://github.com/geritwagner/colrev_cml_assistant>`_.

Custom script extensions
^^^^^^^^^^^^^^^^^^^^^^^^^^

To develop a custom extension script, run the command for the respective operation:

.. code-block::

    colrev search -scs
    colrev prep -scs
    colrev prescreen -scs
    colrev pdf-get -scs
    colrev pdf-prep -scs
    colrev pdf-prep -scs
    colrev screen -scs
    colrev data -scs
