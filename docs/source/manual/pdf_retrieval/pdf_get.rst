.. _PDF get:

colrev pdf-get
==================================
In the ``colrev pdf-get`` operation, records transition from ``rev_prescreen_included`` to ``pdf_imported`` or ``pdf_needs_manual_retrieval``. 
It is possible to adapt the settings for ``pdf_required_for_screen_and_synthesis``, ``pdf_path_type``, and ``rename_pdfs``.

The retrieval based on ``colrev_built_in.local_index`` may retrieve up to 80 or 90% of the PDFs, especially when larger PDF collections are stored locally and when multiple authors use ``colrev pdf-get`` to collect PDFs from their local machines.
When PDFs cannot be retrieved automatically, CoLRev provides an interactive convenience function ``colrev pdf-get-man``.

..
    - Mention discard

    :program:`colrev pdf-get` retrieves PDFs based on

    - unpaywall.org
    - any other local CoLRev repository


.. code:: bash

	colrev pdf-get [options]

Per default, CoLRev creates symlinks (setting ``pdf_path_type=symlink``). To copy PDFs to the repository per default, set ``pdf_path_type=copy`` in ``settings.json``.

.. link to justification of pdf handling (reuse/shared settings)
.. the use of shared/team PDFs is built in (just clone and index!)

The following options for ``pdf-get`` are available:

.. datatemplate:json:: ../../../../colrev/template/package_endpoints.json

    {{ make_list_table_from_mappings(
        [("PDF get packages", "short_description"), ("Identifier", "package_endpoint_identifier"), ("Link", "link")],
        data['pdf_get'],
        title='',
        ) }}


In the ``colrev pdf-get-man`` operation, records transition from ``pdf_needs_manual_retrieval`` to ``pdf_imported`` or ``pdf_not_available``.

..
     goes through the list of missing PDFs and asks the researcher to retrieve it:

    - when the PDF is available, name it as ID.pdf (based on the ID displayed) and move it to the pdfs directory
    - if it is not available, simply enter "n" to mark it as *not_available* and continue

.. code:: bash

	colrev pdf-get-man [options]


The following options for ``pdf-get-man`` are available:

.. datatemplate:json:: ../../../../colrev/template/package_endpoints.json

    {{ make_list_table_from_mappings(
        [("PDF prep packages", "short_description"), ("Identifier", "package_endpoint_identifier"), ("Link", "link")],
        data['pdf_get_man'],
        title='',
        ) }}
