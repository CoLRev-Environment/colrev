.. _PDF prep:

colrev pdf-prep
==================================

:program:`colrev pdf-prep` prepares PDFs for the screen and analysis as follows:

- Check whether the PDF is machine readable and apply OCR if necessary
- Identify and remove additional pages and decorations (may interfere with machine learning tools)
- Validate whether the PDF matches the record metadata and whether the PDF is complete (matches the number of pages)
- Create unique PDF identifiers (pdf hashes) that can be used for retrieval and validation (e.g., in crowdsourcing)


.. code:: bash

	colrev pdf-prep [options]

When PDFs cannot be prepared automatically, :program:`colrev pdf-prep-man` provides an interactive convenience function.

.. code:: bash

	colrev pdf-prep-man [options]

The following options for pdf-prep are available:

.. datatemplate:json:: ../../../../colrev/template/package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Identifier", "package_endpoint_identifier"), ("Description", "short_description"), ("Link", "link")],
        data['pdf_prep'],
        title='Extensions: pdf_prep',
        ) }}

The following options for pdf-prep-man are available:

.. datatemplate:json:: ../../../../colrev/template/package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Identifier", "package_endpoint_identifier"), ("Description", "short_description"), ("Link", "link")],
        data['pdf_prep_man'],
        title='Extensions: pdf_prep_man',
        ) }}
