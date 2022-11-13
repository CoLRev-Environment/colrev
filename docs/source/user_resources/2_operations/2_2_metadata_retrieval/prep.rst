.. _Prepare:

Metadata retrieval - prep
==================================

TODO

- describe the state transitions (md_processed, md_needs_manual_preparation, rev_prescreen_excluded)
- describe rounds/confidence values
- describe metadata-sources/rule-bsed approaches/source-specific rules (the always-apply rationale),
- explain debugging, reset/validate
- expain the benefits of curated metadata, mention corrections (polishing?)
- Link to methods papers/rationales (e.g., general deduplication papers mentioning the need for preprocessing)

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
