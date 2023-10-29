R
=================================

For analytical packages:

.. code-block:: R

    # install.packages("bib2df")
    library(bib2df)

    df <- bib2df("references.bib")
    df

For packages aimed at changing records:

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
