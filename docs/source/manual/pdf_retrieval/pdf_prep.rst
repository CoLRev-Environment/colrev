colrev pdf-prep
==================================

.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 12pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 12pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 12pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html

In the ``colrev pdf-prep`` operation, records transition from ``pdf_imported`` to ``pdf_prepared`` or ``pdf_needs_manual_preparation``.
Depending on the settings, this operation may involve any of the following:

- Check whether the PDF is machine readable and apply OCR if necessary
- Identify and remove additional pages and decorations (may interfere with machine learning tools)
- Validate whether the PDF matches the record metadata and whether the PDF is complete (matches the number of pages)
- Create unique PDF identifiers (PDF hashes) that can be used for retrieval and validation (e.g., in crowdsourcing)

Per default, CoLRev keeps a backup of PDFs that are changed by the ``pdf-prep`` operation. The ``keep_backup_of_pdfs`` option of the ``pdf_prep`` settings can be modified to change this behavior:

..
    ``colrev pdf-prep`` prepares PDFs for the screen and analysis as follows:
    - Mention discard

.. code:: bash

	colrev pdf-prep [options]


The following options for ``pdf-prep`` are available:

.. datatemplate:json:: ../package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Identifier", "package_endpoint_identifier"), ("Description", "short_description"), ("Status", "status")],
        data['pdf_prep'],
        title='',
        columns=[25,55,20]
        ) }}

The ``colrev pdf-prep-man`` operation provides an interactive convenience function for PDFs that cannot be prepared automatically, with records transitioning from ``pdf_needs_manual_preparation`` to ``pdf_prepared``.

.. code:: bash

	colrev pdf-prep-man [options]

The following options for ``pdf-prep-man`` are available:

.. datatemplate:json:: ../package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Identifier", "package_endpoint_identifier"), ("Description", "short_description"), ("Status", "status")],
        data['pdf_prep_man'],
        title='',
        columns=[25,55,20]
        ) }}
