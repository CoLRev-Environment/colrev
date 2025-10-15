colrev prep
==================================

.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 12pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 12pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 12pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html

In the ``colrev prep`` operation, records with sufficient metadata quality transition from ``md_imported`` to ``md_prepared`` (``md_needs_manual_preparation`` otherwise). The benefit of separating high and low-quality metadata is that efforts to fix metadata can be allocated more precisely, which is important for duplicate identification and for ensuring high-quality sample metadata as well as reference sections.

Quality rules:

- Completeness of fields based on rules and external sources, e.g., a journal article requires author, title, year, journal, volume (and issue) fields
- Completeness of field values, e.g., author fields should not end with "and others", journal fields should not end with "..."
- Consistency between fields, e.g., inproceedings records cannot have a journal field
- Format consistency, e.g., fields should not be capitalized, author fields should be formatted correctly, DOIs should follow a predefined pattern
- Consistency between metadata associated with ids, e.g., metadata associated with the DOI should be in line with the metadata associated displayed on the website (linked in the URL field)

..
    -> explain the rules/criteria (with examples) in the architecture rationales (or the colrev framework)

Preparation procedures (the specific preparation depends on the specified settings, they typically consist of steps like the following):

- General rules, such as resolving BiBTeX cross-references, formatting DOI fields, and determining the language of records
- SearchSource-specific rules to fix quality defects, such as incorrect use of field names (without affecting other SearchSources)
- Linking and update based on high-quality metadata-sources, i.e., retrieve DOI identifier and metadata from online repositories (e.g., crossref, semantic scholar, DBLP, open library)
- Linking and update based on with CoLRev curations, which establishes a quality curation loop
- Automated prescreen exclusion of retracted records, complementary materials (such as "About our authors" or "Editorial board"), or records using non-latin alphabets

**Note.** When records are linked and updated based on SearchSources in the ``prep`` operation, corresponding metadata will be stored in additional metadata `SearchSources <search sources>` (with ``md_*`` prefix).
Such metadata `SearchSources <search sources>` are also updated in the search. They do not retrieve additional records and they are excluded from statistics such as those displayed in the ``colrev status`` or PRISMA flow charts.

Before starting the ``colrev prep-man`` operation, it is recommended to check the most common quality defects and to consider implementing preparation rules to fix these defects automatically (after rerunning ``prep``).

..
    - heuristic metadata improvements
    - describe rounds/confidence values
    - explain debugging, reset/validate
    - expain the benefits of curated metadata, mention corrections (polishing?)
    Rare cases: rev_prescreen_excluded
    - Link to methods papers/rationales (e.g., general deduplication papers mentioning the need for preprocessing)

    After completion, it creates new local IDs for records that were processed

    Operating assumptions and principles:

    - Every source of metadata has errors
    - Focus efforts on those sources that have the most errors (e.g., GoogleScholar)
    - Have errors corrected (see last section)

    state that prep may take longer to avoid frequent API calls (service unavailability)


.. code:: bash

	colrev prep [options]

..
    When records cannot be prepared automatically, we recommend opening the references.bib with a reference manager (such as Jabref) and preparing the remaining records manually. For example, JabRef allows you to filter records for the *needs_manual_preparation* status:

    .. figure:: ../../../figures/man_prep_jabref.png
    :alt: Manual preparation with Jabref

    Note: after preparing the records, simply run ``colrev status``, which will update the status field and formatting according to the CoLRev standard.


In addition, ``colrev prep-man`` provides convenience functions to prepare records manually (addressing the quality defects listed for each field).

Users can decide to set the `colrev_status` field to `md_prepared` and override existing quality defect codes (which may be false positives).
The `colrev_status` field is not changed in the following operations unless new quality defect codes are discovered and added (e.g., in `colrev prep --polish`).

.. code:: bash

	colrev pdf-prep-man [options]

..
    Tracing and correcting errors

    To trace an error (e.g., incorrect author names)

    - use a git client to identify the commit in which the error was introduced (e.g., using gitk: right-click on the line and select *show origin of this line*, or navigate to *blame* on GitHub)
    - identify the ID of the record and search for it in the commit message for further details

    If the error was introduced in a 'prep' commit, the commit message will guide you to the source.

The following options for ``prep`` are available:

.. datatemplate:json:: ../package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Identifier", "package_endpoint_identifier"), ("Preparation packages", "short_description"), ("Status", "status")],
        data['prep'],
        title='',
        ) }}

The following options for ``prep-man`` are available:

.. datatemplate:json:: ../package_endpoints.json


    {{ make_list_table_from_mappings(
        [("Identifier", "package_endpoint_identifier"), ("Manual preparation packages", "short_description"), ("Status", "status")],
        data['prep_man'],
        title='',
        columns=[25,55,20]
        ) }}
