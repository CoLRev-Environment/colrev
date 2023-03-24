.. _PDF prep:

colrev pdf-prep
==================================

In the ``colrev pdf-prep`` operation, records transition from ``pdf_imported`` to ``pdf_prepared`` or ``pdf_needs_manual_preparation``.
Depending on the settings, this operation may involve any of the following:

- Check whether the PDF is machine readable and apply OCR if necessary
- Identify and remove additional pages and decorations (may interfere with machine learning tools)
- Validate whether the PDF matches the record metadata and whether the PDF is complete (matches the number of pages)
- Create unique PDF identifiers (pdf hashes) that can be used for retrieval and validation (e.g., in crowdsourcing)

Per default, CoLRev keeps a backup of PDFs that are changed by the ``pdf-prep`` operation. The ``keep_backup_of_pdfs`` option of the ``pdf_prep`` settings can be modified to change this behavior:

..
    :program:`colrev pdf-prep` prepares PDFs for the screen and analysis as follows:
    - Mention discard

.. code:: bash

	colrev pdf-prep [options]


The following options for pdf-prep are available:

.. datatemplate:json:: ../../../../colrev/template/package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Description", "short_description"), ("Identifier", "package_endpoint_identifier"), ("Link", "link"), ("Status", "status_linked")],
        data['pdf_prep'],
        title='',
        ) }}

When PDFs cannot be prepared automatically, the ``colrev pdf-prep-man`` operation provides an interactive convenience function with records transitioning from ``pdf_needs_manual_preparation`` to ``pdf_prepared``.

.. code:: bash

	colrev pdf-prep-man [options]

The following options for ``pdf-prep-man`` are available:

.. datatemplate:json:: ../../../../colrev/template/package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Description", "short_description"), ("Identifier", "package_endpoint_identifier"), ("Link", "link"), ("Status", "status_linked")],
        data['pdf_prep_man'],
        title='',
        ) }}
