
Load
==================================

:program:`colrev load` loads search results as follows:

- Save file in `search/`.
- Check that the extension corresponds to the file format (see below)
- Run`colrev load`

.. code:: bash

	colrev load [options]


Formats
---------------

- structured formats (csv, xlsx) are imported using standard Python libraries
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


- TXT: `.txt` extension

.. code-block:: text

    Wagner, G., Lukyanenko, R., and Paré, G. (2021). “On the Use of Artificial Intelligence in the Conduct of Literature Reviews”. Journal of Information Technology.
    Webster, J., and Watson, R. T. (2002). Analyzing the past to prepare for the future: Writing a literature review. MIS Quarterly, xiii-xxiii.

- PDF: `.pdf` extension or `_ref_list.pdf` extension


Tracing errors and debugging
-----------------------------------

- Debugging/tracing errors to review_template, bibutils/Grobid/doi.org

- [ ] Explain how to trace errors in the backward-search (grobid extraction, reference consolidation or the original PDF), test cases:

    - without reference consolidation: curl -X POST -H "Accept: application/x-bibtex" -d "consolidateCitations=0&citations=Abbasi, A., Zhou, Y., Deng, S., and Zhang, P. 2018. “Text Analytics to Support Sense-Making in Social Media: A Language-Action Perspective,” MIS Quarterly (42:2), pp. 427-464." localhost:8070/api/processCitation
    - with reference consolidation: curl -X POST -H "Accept: application/x-bibtex" -d "consolidateCitations=1&citations=Abbasi, A., Zhou, Y., Deng, S., and Zhang, P. 2018. “Text Analytics to Support Sense-Making in Social Media: A Language-Action Perspective,” MIS Quarterly (42:2), pp. 427-464." localhost:8070/api/processCitation
    - TEI: curl -X POST -d "consolidateCitations=1&citations=Abbasi, A., Zhou, Y., Deng, S., and Zhang, P. 2018. “Text Analytics to Support Sense-Making in Social Media: A Language-Action Perspective,” MIS Quarterly (42:2), pp. 427-464." localhost:8070/api/processCitation

- [ ] Explain how to trace errors in bibutils:
      cat references.ris  | docker run -i --rm bibutils ris2xml /dev/stdin | docker run -i --rm bibutils xml2bib -b -w /dev/stdin
      cat aisel-ris.ris  | docker run -i --rm bibutils end2xml /dev/stdin | docker run -i --rm bibutils xml2bib -b -w /dev/stdin
