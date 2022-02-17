
PDF prep
==================================

:program:`colrev pdf-prep` prepares PDFs for the screenand analysis as follows:

- Check whether the PDF is machine readable and apply OCR if necessary
- Identify and remove additional pages and decorations (may interfere with machine learning tools)
- Validate whether the PDF matches the record metadata and whether the PDF is complete (matches the number of pages)
- Create unique PDF identifiers (pdf hashes) that can be used for retrieval and validation (e.g., in crowdsourcing)


.. code:: bash

	colrev pdf-prep [options]

.. option:: --update_hashes

    Regenerate pdf_hashes

.. option:: --reprocess

    Prepare all PDFs again (pdf_needs_manual_preparation)

..
	--get_hashes : a convenience function

When PDFs cannot be prepared automatically, :program:`colrev pdf-prep-man` provides an interactive convenience function.

.. code:: bash

	colrev pdf-prep-man [options]

.. option:: --stats

    Print statistics of records with status pdf_needs_manual_preparation
