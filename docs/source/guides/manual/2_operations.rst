
2. Operations
==================================

TODO : add introductory paragraph and reduce options (link to the cli reference)

.. _Init:

Init
---------------------------------------------

:program:`colrev init` initializes a new CoLRev project. It should be called in an empty directory.

.. code:: bash

	colrev init [options]

.. TODO : include options for different types of reviews once available

Once the repository is set up, you can share it with your team (see `instructions <3_collaboration.html>`_).

Instead of initializing a new repository, you can also pull an existing one:

.. code:: bash

	colrev pull https://github.com/u_name/repo_name.git

Settings

.. code-block:: json

      {
      "project": {
         "id_pattern": "THREE_AUTHORS_YEAR",
         "review_type": "NA",
         "share_stat_req":"processed",
         "delay_automated_processing": true,
         "curated_masterdata": false,
         "curated_fields": []
      },
      "search": {"sources": []},
      "load": {},
      "prep": {
         "fields_to_keep": [],
         "prep_rounds": [
            {
                  "name": "exclusion",
                  "similarity": 1.0,
                  "scripts": [
                     "exclude_non_latin_alphabets",
                     "exclude_languages"
                  ]
            },
            {
                  "name": "high_confidence",
                  "similarity": 0.99,
                  "scripts": [
                     "remove_urls_with_500_errors",
                     "remove_broken_IDs",
                     "global_ids_consistency_check",
                     "prep_curated",
                     "format",
                     "resolve_crossrefs",
                     "get_doi_from_urls",
                     "get_masterdata_from_doi",
                     "get_masterdata_from_crossref",
                     "get_masterdata_from_dblp",
                     "get_masterdata_from_open_library",
                     "get_year_from_vol_iss_jour_crossref",
                     "get_record_from_local_index",
                     "remove_nicknames",
                     "format_minor",
                     "drop_fields",
                     "update_metadata_status"
                  ]
            },
            {
                  "name": "medium_confidence",
                  "similarity": 0.9,
                  "scripts": [
                     "prep_curated",
                     "get_doi_from_sem_scholar",
                     "get_doi_from_urls",
                     "get_masterdata_from_doi",
                     "get_masterdata_from_crossref",
                     "get_masterdata_from_dblp",
                     "get_masterdata_from_open_library",
                     "get_year_from_vol_iss_jour_crossref",
                     "get_record_from_local_index",
                     "remove_nicknames",
                     "remove_redundant_fields",
                     "format_minor",
                     "drop_fields",
                     "update_metadata_status"
                  ]
            },
            {
                  "name": "low_confidence",
                  "similarity": 0.8,
                  "scripts": [
                     "prep_curated",
                     "correct_recordtype",
                     "get_doi_from_sem_scholar",
                     "get_doi_from_urls",
                     "get_masterdata_from_doi",
                     "get_masterdata_from_crossref",
                     "get_masterdata_from_dblp",
                     "get_masterdata_from_open_library",
                     "get_year_from_vol_iss_jour_crossref",
                     "get_record_from_local_index",
                     "remove_nicknames",
                     "remove_redundant_fields",
                     "format_minor",
                     "drop_fields",
                     "update_metadata_status"
                  ]
            }
         ]
      },
      "dedupe": {"merge_threshold": 0.8, "partition_threshold": 0.5},
      "prescreen": {"plugin": null,
                     "mode": null,
                     "scope": []},
      "pdf_get": {"pdf_path_type": "symlink"},
      "pdf_prep": {},
      "screen": {"process": {"overlapp": null,
                  "mode": null,
                  "parallel_independent": null},
                  "criteria": []
            },
      "data": {"data_format": []}
      }

.. _Search:

Search
---------------------------------------------

:program:`colrev search` retrieves search results from

- Crossref
- DBLP
- CoLRev projects (local or online)
- Directories containing PDFs
- Curated metadata repositories (through the local index)

.. code:: bash

	colrev search [options]

.. code:: bash

    Examples:

    colrev search -a "FROM CROSSREF WHERE Digital AND Platform SCOPE journal_issn='1506-2941'"

    colrev search -a "FROM DBLP SCOPE venue_key='journals/dss' AND journal_abbreviation='Decis. Support Syst.'"

    colrev search -a "FROM COLREV_PROJECT SCOPE url='/home/projects/review9'"

    colrev search -a "FROM BACKWARD_SEARCH SCOPE colrev_status='rev_included|rev_synthesized'"

    colrev search -a "FROM INDEX WHERE lower(fulltext) like '%digital platform%'"

    colrev search -a "FROM PDFS SCOPE path='/home/journals/PLOS' WITH sub_dir_pattern='volume_number' AND journal='PLOS One'"

.. option:: --selected TEXT

    Run selected search

Note:

- The query syntax is based on `sqlite <https://www.sqlite.org/lang.html>`_ (pandasql). You can test and debug your queries `here <https://sqliteonline.com/>`_.
- Journal ISSNs for crossref searches can be retrieved from the `ISSN Portal <https://portal.issn.org/>`_

.. _Load:

Load
---------------------------------------------

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


.. _Prepare:

Prepare
---------------------------------------------

:program:`colrev prep` prepares the metadata. It completes the following steps:

- format fields and drop selected fields (such as broken urls)
- automatically exclude records with non-latin alphabets
- retrieve DOI identifier and metadata from online repositories (e.g., crossref, semantic scholar, DBLP, open library )
- heuristic metadata improvements

.. state that prep may take longer to avoid frequent API calls (service unavailability)

After completion, it creates new local IDs for records that were processed

Operating assumptions and principles:

- Every source of metadata has errors
- Focus efforts on those sources that have the most errors (e.g., GoogleScholar)
- Have errors corrected (see last section)

.. code:: bash

	colrev prep [options]

When records cannot be prepared automatically, we recommend opening the references.bib with a reference manager (such as Jabref) and preparing the remaining records manually. For example, JabRef allows you to filter records for the *needs_manual_preparation* status:

.. figure:: ../../../figures/man_prep_jabref.png
   :alt: Manual preparation with Jabref

Note: after preparing the records, simply run :program:`colrev status`, which will update the status field and formatting according to the CoLRev standard.


In addition, :program:`colrev prep-man` provides an interactive convenience function.

.. code:: bash

	colrev pdf-prep-man [options]


.. option:: --extract

    Extract records for manual_preparation (to csv)

.. option:: --apply

    Apply manual preparation (csv)


Tracing and correcting errors


To trace an error (e.g., incorrect author names)

- use a git client to identify the commit in which the error was introduced (e.g., using gitk: right-click on the line and select *show origin of this line*, or navigate to *blame* on GitHub)
- identify the ID of the record and search for it in the commit message for further details

If the error was introduced in a 'prep' commit, the commit message will guide you to the source.

.. _Dedupe:

Dedupe
---------------------------------------------

:program:`colrev dedupe` identifies and merges duplicates as follows:

- Curated journals are queried (using the LocalIndex) to identify duplicates/non-duplicates
- In an active learning process (based on the `dedupeio <https://github.com/dedupeio/dedupe>`_ library), researchers are asked to label pairs of papers
- During the active learning (labeling) process, the LocalIndex is queried to prevent accidental merges (effectively implementing FP safeguards)
- Once enough pairs have been labeled (e.g., at least 50 duplicates and 50 non-duplicates), the remaining records are matched and merged automatically
- To validate the results, spreadsheets are exported in which duplicate and non-duplicate pairs can be checked (taking into consideration the differences in metadata and the confidence provided by the classifier)
- Corrections can be applied by marking pairs in the spreadsheet ("x" in the *error* column), saving the file, and running colrev dedupe -f
- Records from the same source file are not merged automatically (same source merges have a very high probability of introducing erroneous merge decisions)
- In case there are not enough records to train an active learning model, a simple duplicate identification algorithm is applied (followed by a manual labeling of borderline cases)

.. code:: bash

	colrev dedupe [options]

.. option:: --fix_errors

    Load errors as highlighted in the spreadsheets (duplicates_to_validate.xlsx, non_duplicates_to_validate.xlsx) and fix them.

.. figure:: ../../../figures/duplicate_validation.png
   :alt: Validation of duplicates

.. _Prescreen:

Pre-screen
---------------------------------------------

:program:`colrev prescreen` supports interactive prescreening

.. code:: bash

	colrev prescreen [options]

.. option:: --include_all

    Include all papers (do not implement a formal prescreen)

.. option:: --create_split INT

    Splits the prescreen between n researchers. Simply share the output with the researchers and ask them to run the commands in their local CoLRev project.

.. option:: --split STR

    Complete the prescreen for the specified split.

The settings can be used to specify scope variables which are applied automatically before the manual prescreen:

.. code-block:: json

        "prescreen": {"plugin": null,
                    "mode": null,
                    "scope": [
                            {
                                "TimeScopeFrom": 2000
                            },
                            {
                                "TimeScopeTo": 2010
                            },
                            {
                                "OutletExclusionScope": {
                                    "values": [
                                        {
                                            "journal": "Science"
                                        }
                                    ],
                                    "list": [
                                        {
                                            "resource": "predatory_journals_beal"
                                        }
                                    ]
                                }
                            },
                            {
                                "OutletInclusionScope": {
                                    "values": [
                                        {
                                            "journal": "Nature"
                                        },
                                        {
                                            "journal": "MIS Quarterly"
                                        }
                                    ]
                                }
                            },
                            ]
                    }


.. _PDF get:

PDF get
---------------------------------------------

:program:`colrev pdf-get` retrieves PDFs based on

- unpaywall.org
- any other local CoLRev repository

This may retrieve up to 80 or 90% of the PDFs, especially when larger PDF collections are stored locally and when multiple authors use :program:`colrev pdf-get` to collect PDFs from their local machines.
When PDFs cannot be retrieved automatically, CoLRev provides an interactive convenience function :program:`colrev pdf-get-man`.

.. code:: bash

	colrev pdf-get [options]

Per default, CoLRev creates symlinks (setting `PDF_PATH_TYPE=SYMLINK`). To copy PDFs to the repository per default, set `PDF_PATH_TYPE=COPY` in settings.json.

.. link to justification of pdf handling (reuse/shared settings)
.. the use of shared/team PDFs is built in (just clone and index!)

:program:`colrev pdf-get-man` goes through the list of missing PDFs and asks the researcher to retrieve it:

- when the PDF is available, name it as ID.pdf (based on the ID displayed) and move it to the pdfs directory
- if it is not available, simply enter "n" to mark it as *not_available* and continue

.. code:: bash

	colrev pdf-get-man [options]

.. _PDF prep:

PDF prep
---------------------------------------------

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

.. _Screen:

Screen
---------------------------------------------

:program:`colrev screen` supports interactive screening based on a list of exclusion criteria

.. code:: bash

	colrev screen [options]

.. option:: --include_all

    Include all papers

.. _Data:

Data
---------------------------------------------

:program:`colrev data` supports the data extraction, analysis and synthesis. Depending on the type of review, this may involve

- a manuscript-based synthesis
    - structured data extraction (diffs are displayed using `daff <https://github.com/paulfitz/daff>`_ or the `browser extension <https://chrome.google.com/webstore/detail/github-csv-diff/ngpdjmibpbemokfbmapemhpbmgacebhg/>`_)

To select the data format, please consult the best practices for different `types of reviews <./best_practices.html#types-of-literature-reviews>`_.

To set the data format, run any (combination) of the following:

.. code:: bash

    colrev data --add_endpoint MANUSCRIPT
    colrev data --add_endpoint STRUCTURED
    colrev data --add_endpoint PRISMA
    colrev data --add_endpoint ZETTLR
    colrev data --add_endpoint ENDNOTE

Depending on the data format, the :program:`colrev data` command

- adds new records to the manuscript (paper.md, after the <!-- NEW_RECORD_SOURCE --> marker)
- creates (enhanced) TEI files

.. code:: bash

	colrev data [options]

.. option:: --profile

    Generate a sample profile.

.. option:: --reading_heuristics

    Calculate heuristic (influence of each paper within the selected sample) to prioritize reading efforts (see :cite:p:`WagnerEmplSchryen2020`.).

.. TODO: include examples (figure) for data --profile/--reading_heuristics

.. _Paper:

Paper
---------------------------------------------

:program:`colrev paper` builds the final paper (e.g., PDF, Word) from the markdown document paper.md using `pandoc <https://github.com/jgm/pandoc>`_.


.. code:: bash

	colrev paper [options]

Links and references for standalone literature reviews will be made available here (TODO).

**References**

.. [WagnerEtAl2020] Wagner, G. and Empl, P. and Schryen, G. (2020). Designing a novel strategy for exploring literature corpora. *Proceedings of the European Conference on Information Sytems*.
