.. Load:

colrev load
==================================

:program:`colrev load` loads search results as follows:

- Save reference file in `search/`.
- Check that the extension corresponds to the file format (see below)
- Run `colrev load`, which
    - asks for details on the source (records them in sources.yaml)
    - converts search files (with supported formats) to BiBTex
    - unifies field names (in line with the source)
    - creates an origin link for each record
    - imports the records into the references.bib

.. code:: bash

	colrev load [options]

Formats

- Structured formats (csv, xlsx) are imported using standard Python libraries
- Semi-structured formats are imported using bibtexparser or the zotero-translation services (see `supported import formats <https://www.zotero.org/support/kb/importing_standardized_formats>`_)
- Unstructured formats are imported using Grobid (lists of references and pdf reference lists)
