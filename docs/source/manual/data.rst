Step 6: Data extraction and synthesis
---------------------------------------------

The last step corresponds to the data extraction, analysis and synthesis activities.
Depending on the type of review, this step can involve very different activities and outcomes.

A key distinction is whether the data is approached from an inductive or deductive perspective:

- In **inductive** analyses, researchers approach the literature sample without predefined categories with the purpose of letting the insights and concepts emerge.
- In **deductive** analyses, the literature is approached with a prespecified coding scheme, often with the purpose of evaluating the available evidence on a specific question.

Another dimension is the nature of the analyses and the corresponding level at which researchers engage with prior literature:

- Scientometric analyses are often concerned with structural patterns of publication metadata, author characteristics, or citation networks.
- Descriptive analyses can be dedicated to distributional patterns of research methods, qualitative vs. quantitative designs, or levels of analysis.
- Analyses aimed at aggregating scientific evidence typically involve a structured data extraction, risk-of-bias assessment, and meta-analytic regressions.
- Conceptual synthesis activities can be dedicated to underlying theories and in-depth problematization of meta-theoretical issues.

The outcomes of the last step can involve various elements, such as:

- A synthesis document (manuscript) and complementary appendices
- A bibliography containing the sample in formats such as ris, bib, enl
- Reporting items related to the sample and review process (e.g., profile of the study, PRISMA diagram)
- The project repository including the full sample and intermediate steps
- Complementary web resources (e.g., Github pages)

The available data endpoints, which can be registered in the ``settings.json``, are provided in the data operation page.
Advice on the active data endpoints is provided through ``colrev status``.

Data endpoints also signal the completed records to ``colrev status`` (or ``colrev data``), which update the status in the main records.bib accordingly.
The status of a record is only set to ``rev_synthesized`` when all data endpoints signal completion.
This allows users to efficiently keep track of the records' status and it informs the completion condition, which is displayed in the colrev status and reports (displayed in each commit).

..
    - a manuscript-based synthesis
        - structured data extraction (diffs are displayed using `daff <https://github.com/paulfitz/daff>`_ or the `browser extension <https://chrome.google.com/webstore/detail/github-csv-diff/ngpdjmibpbemokfbmapemhpbmgacebhg/>`_)

    To select the data format, please consult the best practices for different `types of reviews <./best_practices.html#types-of-literature-reviews>`_.


.. toctree::
   :maxdepth: 1
   :caption: Operations

   data/data
