
PDF get
==================================

:program:`colrev pdf-get` retrieves PDFs based on

- unpaywall.org
- other local CoLRev repositories (in particular local PDF collections, as indexed by local_paper_index)

When PDFs cannot be retrieved automatically, :program:`colrev pdf-get-man` provides an interactive convenience function.

.. code:: bash

	colrev pdf-get [options]

.. option:: --copy-to-repo

    Copy PDFs to the repository (otherwise, links are created, but PDFs remain in their original locations)

.. option:: --rename

    Automatically rename PDFs (to their local IDs)


.. code:: bash

	colrev pdf-get-man [options]
