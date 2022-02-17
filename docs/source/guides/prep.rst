
Prepare
==================================


:program:`colrev prep` prepares the metadata. It completes the following steps:

- format fields and drop selected fields (such as broken urls)
- automatically exclude records with non-latin alphabets
- retrieve DOI identifier and metadata from online repositories (e.g., crossref, semantic scholar, DBLP, open library )
- heuristic metadata imrovements

After completion, it creates new local IDs for records that were processed

Operating assumptions and principles:

- Every source of metadata has errors
- Focus efforts on those sources that have the most errors (e.g., GoogleScholar)
- Have errors corrected (see last section)

.. code:: bash

	colrev prep [options]

.. program:: colrev prep

.. option:: --similarity

    Retrieval similarity threshold

.. option:: --reprocess

	Prepare all records with status md_needs_manual_preparation

.. option:: --keep_ids

	Do not change the record IDs. Useful when importing an existing sample.

.. option:: --reset_records ID1,ID2,ID3

    Reset record metadata of records ID1,ID2,ID3 to the imported version.

.. option:: --reset_ids

    Reset IDs that have been changed (to fix the sort order in MAIN_REFERENCES)

.. option:: --set_ids

    Generate and set IDs

.. option:: --update

    Update metadata (based on DOIs)

.. option:: --polish

    Polish the metadata without changing the record status.

    Based on the enhanced TEIs, it conducts a frequency analysis of the reference sections and checks how included and synthesized papers are cited.
    Titles and journals are set to the most frequent values.


When records cannot be prepared automatically, we recommend opening the references.bib with a reference manager (such as Jabref) and preparing the remaining records manually. For example, JabRef allows you to filter records for the *needs_manual_preparation* status:

.. figure:: ../../figures/man_prep_jabref.png
   :alt: Manual preparation with Jabref

Note: after preparing the records, simply run :program:`colrev status`, which will update the status field and formatting according to the CoLRev standard.


In addition, :program:`colrev prep-man` provides an interactive convenience function.

.. code:: bash

	colrev pdf-prep-man [options]


.. option:: --extract

    Extract records for manual_preparation (to csv)

.. option:: --apply

    Apply manual preparation (csv)

.. option:: --stats

    Print statistics of records with status md_needs_manual_preparation



Tracing and correcting errors
-----------------------------------

To trace an error (e.g., incorrect author names)

- use a git client to identify the commit in which the error was introduced (e.g., using gitk: right-click on the line and select *show origin of this line*, or navigate to *blame* on Github)
- identify the ID of the record and search for it in the commit message for further details

If the error was introduced in a 'prep' commit, the commit message will guide you to the source.


Source: crossref/doi.org
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Metadata retrieved from the crossref API (based on DOI) can be checked by visiting the following website:

.. code:: text

    # Replace the DOI:
    https://api.crossref.org/works/DOI

    # Example:
    https://api.crossref.org/works/10.1111/joop.12368

    # To analyze the results,
    # use https://jsonformatter.org/json-viewer

- Errors may be caused by temporary downtime, e.g., of crossref. Status information is available `online <https://status.crossref.org/>`_

- To have DOI metadata corrected, reach out to the organization (journal) that has deposited the metadata (see `here <https://www.crossref.org/documentation/metadata-stewardship/maintaining-your-metadata/updating-your-metadata/>`_)

.. code-block:: text

    Dear XXXX,

    we have just noticed that for our recent paper, DESCRIBE ERROR in the DOI metadata:

    https://api.crossref.org/works/DOI

    Please let me know who could help us to correct this.

    Thank you & best regards,

    ...


Source: DBLP
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Metadata provided by DBLP can be checked by visiting the following website:

.. code:: text

    # Append "?view=bibtex" to the dblp_key

    # Example:
    https://dblp.org/rec/journals/cais/WagnerPS21.html?view=bibtex


`Instructions on having errors corrected in DBLP <https://dblp.org/faq/How+can+I+correct+errors+in+dblp.html>`_.
