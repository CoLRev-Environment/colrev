
PDF get
==================================

:program:`colrev pdf-get` retrieves PDFs based on

- unpaywall.org
- any other local CoLRev repository (including `local_paper_index <extensions/local_paper_index.html>`_)

This may retrieve up to 80 or 90% of the PDFs, especially when larger PDF collections are stored locally and when multiple authors use :program:`colrev pdf-get` to collect PDFs from their local machines.
When PDFs cannot be retrieved automatically, CoLRev provides an interactive convenience function :program:`colrev pdf-get-man`.

.. code:: bash

	colrev pdf-get [options]

.. option:: --copy-to-repo

    Copy PDFs to the repository (otherwise, links are created, but PDFs remain in their original locations)

.. option:: --rename

    Automatically rename PDFs (to their local IDs)


:program:`colrev pdf-get-man` goes through the list of missing PDFs and asks the researcher to retrieve it:

- when the PDF is available, name it as ID.pdf (based on the ID displayed) and move it to the pdfs directory
- if it is not available, simply enter "n" to mark it as *not_available* and continue

.. code:: bash

	colrev pdf-get-man [options]
