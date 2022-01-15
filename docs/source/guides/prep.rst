
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

When records cannot be prepared automatically, :program:`colrev prep-man` provides an interactive convenience function.

.. code:: bash

	colrev prep [options]

.. program:: colrev prep

.. option:: --similarity

    Retrieval similarity threshold

.. option:: --reprocess

	Prepare all records with status md_needs_manual_preparation

.. option:: --keep_ids

	Do not change the record IDs. Useful when importing an existing sample.


.. option:: --reset_records

    Reset record metadata to the imported version. Format: --reset_records ID1,ID2,ID3

.. option:: --reset_ids

    Reset IDs that have been changed (to fix the sort order in MAIN_REFERENCES)

.. option:: --set_ids

    Generate and set IDs

.. option:: --update

    Update metadata (based on DOIs)


.. code:: bash

	colrev pdf-prep-man [options]


.. option:: --extract

    Extract records for manual_preparation (to csv)

.. option:: --apply

    Apply manual preparation (csv)

.. option:: --stats

    Print statistics of records with status md_needs_manual_preparation


Tracing errors and debugging
-----------------------------------

- Errors may be caused by temporary downtime, e.g., of crossref. Status information is available `online <https://status.crossref.org/>`_

- DOI data can be checked by querying the crossref API (changing the url parameters accordingly)

.. code:: text

    http://api.crossref.org/works?query.container-title=%22MIS+Quarterly%22&query=%2216+2%22

or by retrieving the metadata from doi.org (changing the url parameter accordingly)

.. code:: bash

    curl -iL -H "accept: application/vnd.citationstyles.csl+json" -H "Content-Type: application/json" http://dx.doi.org/10.1111/joop.12368

or through crossref:

.. code:: text

    # To test the metadata provided for a particular DOI use:
    https://api.crossref.org/works/DOI


Having errors corrected
-----------------------------------


- Having errors corrected in `DBLP <https://dblp.org/faq/How+can+I+correct+errors+in+dblp.html>`_



TBD: integrate into debugger?

- To have DOI metadata corrected, reach out to the organization (journal) that has deposited the metadata (see `here <https://www.crossref.org/documentation/metadata-stewardship/maintaining-your-metadata/updating-your-metadata/>`_)


.. code-block:: text

    Dear XXXX,

    we have just noticed that for our recent paper, DESCRIBE ERROR in the DOI metadata:

    https://api.crossref.org/works/DOI

    Please let me know who could help us to correct this.

    Thank you & best regards,

    ...
