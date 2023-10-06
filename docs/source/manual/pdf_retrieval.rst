Step 4: PDF retrieval
==================================

The step of PDF retrieval refers to the activities to acquire PDF documents (or documents in other formats) as well as to ascertain or improve their quality.
It should ensure that PDF documents correspond to their associated metadata (no mismatches), that they are machine readable (OCR and semantically annotated), and that unnecessary materials (such as cover pages) are removed.

PDFs are stored in the ``data/pdfs`` directory.
Per default, PDF documents are not versioned by git to ensure that CoLRev repositories can be published without violating copyright restrictions.

It is recommended to share PDFs through file synchronization clients and to create a symlink pointing from the ``colrev-repository/data/pdfs`` to the respective directory used for file sharing.

..
   - Versioning large collections of PDFs in git repositories would also lead to declining performance and as a "binary" file format, PDFs generally lack readable git diffs.
   - Explain state intermediate transitions
   - Mention that more detailed commands (prep, prep-man, ...) will be suggested if colrev retrieve does not result in all records transitioning to md_processed

PDF retrieval is a high-level operation consisting of the following operations:

- The ``pdf-get`` operation, which retrieves PDFs from sources like the local_index or unpaywall. It may refer users to ``pdf-get-man`` as the manual fallback when the record state is set to ``pdf_needs_manual_retrieval``.

- The ``pdf-prep`` operation, which refers to the preparation of PDF documents. It may refer users to ``pdf-prep-man`` as the manual fallback when the record state is set to ``pdf_needs_manual_preparation``.

To start the ``pdfs`` operation, run:

.. code:: bash

	colrev pdfs

.. toctree::
   :maxdepth: 1
   :caption: Operations

   pdf_retrieval/pdf_get
   pdf_retrieval/pdf_prep
