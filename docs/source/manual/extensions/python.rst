
Python
==================================

TODO: short sentence or description is missing here

.. code-block:: python

    import colrev.review_manager

    # Initialize the ReviewManager
    review_manager = colrev.review_manager.ReviewManager()

    # Get an operation and notify the ReviewManager
    prep_operation = review_manager.get_prep_operation()

    # Load the records and apply changes
    records = review_manger.dataset.load_records_dict()
    for record in records.values():
        ....

    # Save the changes, add them to git, and create commit
    review_manager.dataset.save_records_dict(records=records)
    review_manager.dataset.add_record_changes()
    review_manager.create_commit("Pre-screening (extension X")
