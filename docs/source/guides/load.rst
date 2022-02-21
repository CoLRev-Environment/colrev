
Load
==================================

:program:`colrev load` loads search results as follows:

- Save file in `search/`.
- Check that the extension corresponds to the file format (see below)
- Run`colrev load`, which
    - asks for details on the source (records them in sources.yaml)
    - converts search files (with supported formats) to BiBTex
    - unifies field names (in line with the source)
    - creates an origin link for each record
    - imports the records into the references.bib

.. code:: bash

	colrev load [options]

.. program: colrev load

.. option:: --keep_ids, -k

    Do not change the record IDs. Useful when importing an existing sample.

.. option:: --add_colrev_repo PATH

    Path to a CoLRev repo that should be imported.

.. option:: ----update_colrev_repo_sources

    Update records from CoLRev repos.


Formats
---------------

- Structured formats (csv, xlsx) are imported using standard Python libraries
- Semi-structured formats are imported using bibtexparser or bibutils (.end and .ris)
- Unstructured formats are imported using Grobid (lists of references and pdf reference lists)


- BibTeX: `.bib` extension

.. code-block:: latex

    @article{Wagner2021,
    title={On the Use of Artificial Intelligence in the Conduct of Literature Reviews},
    author={Wagner, G., Lukyanenko, R., and Paré, G.},
    journal={Journal of Information Technology},
    year={2021}
    }


- Endnote: `.end` extension

.. code-block:: text

    %J - Journal of Information Technology
    %A - Wagner, G.
    %A - Lukyanenko, R.
    %A - Paré, G.
    %T - On the Use of Artificial Intelligence in the Conduct of Literature Reviews
    %Y - 2021



- RIS: `.ris` extension

.. code-block:: text

    TY  - JOUR
    TI  - On the Use of Artificial Intelligence in the Conduct of Literature Reviews
    T2  - Journal of Information Technology
    AU  - Wagner, G.
    AU  - Lukyanenko, R.
    AU  - Paré, G.
    PY  - 2021


- CSV: `.csv` extension

.. code-block:: text

    "author", "year", "title", "journal", "volume", "issue", "pages", "doi"
    "Wagner, G., Lukyanenko, R., and Paré, G.", "2021", "On the Use of Artificial Intelligence in the Conduct of Literature Reviews", "Journal of Information Technology", "", "", "", ""
    "Webster, J., and Watson, R. T.", "2002", "Analyzing the past to prepare for the future: Writing a literature review", "MIS Quarterly", "", "", "xiii-xxiii", ""


- EXCEL: `.xlsx` extension


.. list-table::
   :widths: 28 10 28 23 5
   :header-rows: 1

   * - author
     - year
     - title
     - journal
     - ...
   * - Webster and Watson
     - 2002
     - Analyzing the past...
     - MIS Quarterly
     - ...

- TXT: `.txt` extension

.. code-block:: text

    Wagner, G., Lukyanenko, R., and Paré, G. (2021). “On the Use of Artificial Intelligence in the Conduct of Literature Reviews”. Journal of Information Technology.
    Webster, J., and Watson, R. T. (2002). Analyzing the past to prepare for the future: Writing a literature review. MIS Quarterly, xiii-xxiii.

- PDF: `.pdf` extension or `_ref_list.pdf` extension
