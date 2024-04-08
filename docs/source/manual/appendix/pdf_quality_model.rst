PDF quality model
==================================

The quality model specifies the necessary checks when a records should transition to ``pdf_prepared``. The functionality fixing errors is organized in the `pdf-prep` package endpoints.

Similar to linters such as pylint, it should be possible to disable selected checks. Failed checks are made transparent by adding the corresponding codes (e.g., `author-not-in-pdf`) to the `colrev_masterdata_provenance` (`notes` field).

Table of contents
------------------------------

- :any:`no-text-in-pdf`
- :any:`pdf-incomplete`
- :any:`author-not-in-pdf`
- :any:`title-not-in-pdf`
- :any:`coverpage-included`
- :any:`last-page-included`


.. _no-text-in-pdf:

no-text-in-pdf
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

No text in the PDF, need to apply OCR.

.. _pdf-incomplete:

pdf-incomplete
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

PDF incomplete, i.e., the number of pages recorded does not match the number of pages in the PDF document.

.. _author-not-in-pdf:

author-not-in-pdf
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The author names are not in the PDF document.

.. _title-not-in-pdf:

title-not-in-pdf
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The title is not in the PDF document.

.. _coverpage-included:

coverpage-included
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A decorative cover-page is included in the PDF.

.. _last-page-included:

last-page-included
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A decorative last page is included in the PDF.
