
PDF prep
==================================

:program:`colrev pdf-prep` prepares PDFs for the screenand analysis as follows:

- Check whether the PDF is machine readable and apply OCR if necessary
- Identify and remove additional pages and decorations (may interfere with machine learning tools)
- Validate whether the PDF matches the record metadata and whether the PDF is complete (matches the number of pages)
- Create unique PDF identifiers (can be used for validation in crowdsourcing initiatives)

When PDFs cannot be prepared automatically, :program:`colrev pdf-prep-man` provides an interactive convenience function.

.. code:: bash

	colrev pdf-prep [options]


.. code:: bash

	colrev pdf-prep-man [options]
