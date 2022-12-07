
Python
==================================


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


