
A. Appendix
==================================


Publication
------------------

TODO: how to publish  (include a license, link at colrev/make it discoverable, do not include paywalled PDFs - not even in the history )


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

- Get paths (as shown in :program:`colrev config`) from REVIEW_MANAGER.paths
- Use the logger (report vs tool/extension)
    - colrev_report logger: log info that are helpful to examine and validate the process, including links to the docs where instructions for tracing and fixing errors are available
    - extension logger: log info on the progress. The output should be relatively short and allow users to see the progress and judge whether any errors occurred

- `Add <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics>`_ the ```colrev-extension``` `topic tag on GitHub <https://github.com/topics/colrev-extension>`_ to allow others to find and use your work


Python
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    import logging
    from colrev_core.review_manager import ReviewManager
    from colrev_core.process import PrepProcess

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
    colrev_core <- reticulate::import("colrev_core")

    # Initialize the ReviewManager
    REVIEW_MANAGER <- colrev_core$review_manager$ReviewManager()

    # Initialize the PrepProcess and notify about upcoming process
    PREP_PROCESS <- colrev_core$process$PrepProcess(REVIEW_MANAGER)

    REVIEW_DATASET = PREP_PROCESS$REVIEW_DATASET

    # Load the records and apply changes
    records = REVIEW_DATASET$load_records()


Example: colrev_cml_assistant
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Aimed at supporting crowdsourcing and machine-learning based on CoLRev datasets.

Link to the repository: `colrev_cml_assistant <https://github.com/geritwagner/colrev_cml_assistant>`_.

Example: colrev_endpoint
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Aimed at making it easy to integrate with other tools by operating endpoints that support the export and loading of data.
For example, EndPoint supports the collaboration with Endnote (and other reference mangers) or `ASReview <https://github.com/asreview/asreview>`_ for the prescreen.

Example:

.. code-block:: sh

    # In a colrev repository, run
    colrev_endpoint add type endnote

    # Create an export enl file
    colrev_endpoint export
    # the file is created in /endpoint/endnote/references.enl

    # The following exports will contain new records exclusively
    colrev_endpoint export

    # Import the library to update the main references.bib
    colrev_endpoint load path_to_library.enl

Link to the repository: `colrev_endpoint <https://github.com/geritwagner/colrev_endpoint>`_.


Custom script extensions
^^^^^^^^^^^^^^^^^^^^^^^^^^

Store the following script in the project dir and include filename in settings

.. code-block:: python

   #!/usr/bin/env python3

   class CustomPrepare:
      @classmethod
      def prepare(cls, PREP_RECORD):

         PREP_RECORD.data["journal"] = PREP_RECORD.data["journal"].replace('MISQ', 'MIS Quarterly')

         return PREP_RECORD


   if __name__ == "__main__":
      pass
