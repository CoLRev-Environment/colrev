
.. _Fulltext retrieval:

Step 4: Fulltext retrieval
==================================

The step of fulltext retrieval refers to the activities to acquire fulltext documents (PDFs) as well as to ascertain or improve their quality.
It should ensure that fulltext documents correspond to their associated metadata (no mismatches), that they are machine readable (OCR and semantically anotated), that unnecessary materials (such as coverpages) are removed.

PDFs are stored in the ``data/pdfs`` directory.
Per default, PDF documents are not versioned by git to ensure that CoLRev repositories can be published without violating copyright restrictions.
Versioning large collections of PDFs in git repositories would also lead to declining performance and as a "binary" file format, PDFs generally lack readable git diffs.

It is recommended to share PDFs through file synchronization clients and to create a symlink pointing from the colrev-repository/data/pdfs to the respective directory used for file sharing.

..
   - Explain state intermediate transitions
   - Mention that more detailed commands (prep, prep-man, ...) will be suggested if colrev retrieve does not result in all records transitioning to md_processed

Fulltext retrieval consists of the following operations:

- pdf-get operation:
   - Retrieves PDFs from sources like the local_index or unpaywall
   - Refers to ``pdf-get-man`` as the manual fallback

- pdf-prep operation:
   - Prepares the PDF
   - Refers to ``pdf-prep-man`` as the manual fallback


.. toctree::
   :maxdepth: 3
   :caption: Operations

   2_4_fulltext_retrieval/pdf_get
   2_4_fulltext_retrieval/pdf_prep
