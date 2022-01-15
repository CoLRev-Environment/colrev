
Principles
====================================

Design and architecture principles.

A literature review is a collaborative process involving human-machine ensembles (authors, algorithms, crowds), which takes search results (metadata) and full-text documents as qualitative, semi-structured input to develop a synthesis. The result can take the form of a codified standalone review paper, a published as a web repository, or a curated locally as a living review.

It is commonly known that data generation processes are error prone (e.g., errors in the reference sections of primary papers, in the database indices, or in the machine-readability of PDFs) and as a result, each record (metadata or PDF) can have multiple data quality problems.
As a direct implication, metadata and PDFs, like data in any other research method, require dedicated preparation steps.

There is variance in how accurately authors and algorithms perform (e.g., disagreements in the screening process or performance of duplicate detection algorithms).
As an implication, control of process reliability (and constant improvement of algorithms) is needed, which requires transparency of atomic changes.

As an implication of error-prone input data and variance in processing accuracy, efficient error-tracing and debugging functionality must be built-in.

With ever growing volumes and heterogeneity of research, there is a growing need to allocate efforts rationally and based on evidence.
As an implication, we need to use prior research as crowdsourcing (e.g., for deduplication), we need to use evidence in the searches.

Literature reviews, in their current form, do not effectively leverage data from prior reviews (e.g., in the duplicate detection process, the preparation of metadata and PDFs, or the classification of documents).
As an implication, a clear vision for effectively establishing reuse paths is needed.


CoLRev consists of the following components:

- `CoLRev`_ command-line interface
- `CoLRev-core`_ (this repository): engine for git-based literature reviews (automatically installed)
- `CoLRev-hooks`_ : pre-commit hooks to validate compliance with CoLRev (automatically installed)

**TODO** :

- Mention shared philosophy/principles, goal of providing an extensible platform
- The goal of CoLRev is to facilitate collaborative reviews, making them more efficient, robust, and powered by SOTA/research-grade algorithms)

.. figure:: ../../figures/macro_framework.png
   :alt: Macro framework

Workflow
---------------

In its basic form, the workflow consists of iteratively calling ```colrev status``` > ```colrev process``` > ```git process```

The workflow is self-explanatory with ```colrev status``` recommending the next ```colrev process``` or ```git process```

The **ReviewManager** supports reviewers in completing the complexity of the review process (e.g., the order of individual steps and their dependencies) in collaborative settings (e.g., requiring synchronization between distributed local repositories).
Essentially, the ReviewManager operates in three modes:

- Autonomous: ReviewManager executes and supervises the process (e.g., loading new records)
- Supervised: ReviewManager is notified before a process is started, usually interactive processes requiring frequent user input (e.g., screening)
- Consulted: ReviewManager is called after files have been modified and checks for consistency (e.g., writing the synthesis)

In addition, the ReviewManager keeps a detailed report of (1) the review environment and parameters (2) the current state of the review, and (3) the individual steps (commands) and the changes applied to the dataset ([example](docs/figures/commit_report.png)).

**TODO**: summarize steps I-IV displayed in the figure

.. figure:: ../../figures/meso_framework.png
   :alt: Meso framework

Processing functions (transitions between record states)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


```load```:  -> ```md_imported```

  - Converts search results stored in the ```search``` directory to BibTex format
  - Combines all individual search results files in one MAIN_REFERENCES file and creates an origin link for each record (in addition to a status field)
  - The origin fields allow ```load``` to operate in an incremental mode (i.e., recognize which records have already been loaded and load only the new ones)
  - Maps field names to a common standard (BibTex) (e.g., Web of Science has "Author_Full_Names", which is "author" in BibTex). This mapping can be dependent on the database/source (and it may change over time).
  - Creates IDs (IDs may be changed in the preparation/deduplication process but ideally, the load process sets most of the IDs to their final values to avoid positional changes of records, for which IDs are the primary sort criterion)
  - Records details for each source (search results file)
  - Loading of each file corresponds to an individual commit (instead of batches across multiple search result files) to facilitate debugging

```prepare```: transition from ```md_imported``` to ```md_prepared``` | ```md_needs_manual_preparation```

  - To transition to ```md_prepared```, metadata of a record has to be complete and consistent
    - Complete means that particular fields are required according to the respective ENTRYTYPE (see prep.py/record_field_requirements, which is based on [BibTex standard](https://en.wikipedia.org/wiki/BibTeX)) and that individual fields have to be complete (e.g., authors not ending with "...", "et al." or "and others"). Records are considered complete if a curated metadata repository confirms that particular fields do not exist for that record (e.g., the journal does not use numbers).
    - Consistent means that consistency rules (as defined in prep.py/record_field_inconsistencies) are not violated.
  - Preparation is a complex process (comprising multiple atomic steps) and as a result, several preparation scripts are applied:
    - Formats fields (e.g., use ML to identify author first/last/middle names and format them)
    - Queries curated metadata repositories (e.g., DOI.ORG, CROSSREF, DBLP, OPEN_LIBRARY) or check ```url```, ```fulltext``` fields to update metadata if there is a high similarity with the curated metadata. Only high-quality metadata repositories are covered and the data returned is considered correct and complete (e.g., useful to conclude that a record is complete if the journal publishes volumes but no individual numbers)
  - If the resulting metadata is not complete and consistent, the record status is set to ```md_needs_manual_preparation```
  - Analyses of the changes applied by each preparation script (e.g., is it an error of the script, of the input data or of the curated repository?) is supported by a detailed report (commit message)
  - Records that have non-latin alphabets (e.g., chinese, greek, arab) are classified as stauts=```md_prescreen_excluded``` because they would require dedicated preparation procedures and deduplication across alphabets would need to be defined.

```man_prep```: transition from ```md_needs_manual_preparation``` to ```md_prepared```

  - Manual process in which researchers check the ```man_prep_hints``` fields (e.g., indicating that the author field is missing) and update the records accordingly

```dedupe```: transition from ```md_prepared``` to ```md_processed```

  - Interactive process (manual labeling), followed by automated classification of remaining records as non-duplicates
  - Identifying and merging duplicates with high accuracy requires the following:
    - Prepared metadata (especially completeness)
    - State-of-the-art duplicate identification algorithms (active learning)
    - FP safeguards (**TODO**) to prevent erroneous merging when records are highly similar but not duplicates (e.g., conference papers published as extended journal versions, or editorials in which all fields are identical, except for the journal-issue)
    - "Domain knowledge": Records can be completely dissimilar but require merging (e.g., conference details linked through a crossref field in BibTex)

**CONTINUE HERE**
  - Duplicate detection should be incremental, i.e., the pool of non-duplicated records is extended incrementally with new records being checked against existing records in the pool. Comparisons between records in the pool are not repeated. This is only possible if we meticulously track the status of records (after md_status=processed or not). Note: incremental merging is not possible with traditional workflows that do not rely on an explicit state model and corresponding fields. This can be a severe limitation for iterative searches!
  - If the similarity between records is not high enough for merging (and not low enough to mark them as non-duplicates), they are marked as "needs_manual_preparation".
  - Efficient analysis requires records to be adjacent in the MAIN_REFERENCES
  - **TODO** We also need to define how records are matched across levels - e.g., book vs. book-chapter, conference proceedings vs. in-proceedings paper

```man_dedupe```

```prescreen```
  - should support the identification of retracted papers, predatory journals, different languages

```pdf_get```
  - should automatically retrieve PDFs published as open access
  - should support the automated retrieval of PDFs from other projects (locally)

```pdf_get_man```

```pdf_prep```
  - Check correspondence between metadata and PDF (to avoid accidentally working with a different paper), check machine readability/OCR (to prevent problems in machine processing and processing by humans/e.g., when using the search functionality of PDF readers), remove additional pages/decorations that may interfere with automated analyses (e.g., cover pages, download-stamps), detect problems in charsets, blank pages etc.
  - Principles: only overwrite PDFs if the original PDF can be restored from git history (otherwise, save a backup copy before editing)
  - Each preparation script takes the last version of the PDF and creates a new copy (if it applies preparation changes). If the last step succeeds, the original PDF will be replaced (if there is a problem, having one PDF for each preparation step facilitates debugging).

```pdf_prep_man```

```screen```

```data```
  - Structured data formats should be stored in line-oriented formats (e.g., yaml/json), otherwise, git diffs can require a lot of cognitive effort to analyze
  - Tools should automatically feed additional records into the synthesis process/document sections and track whether each record has been synthesized (completeness condition)

- Each script: print detailed (minimal) information for potential error reporting
- TBD: principle: use all services that are made available


Versioning and collaboration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- **TODO**: Summarize main advantages of git for collaborative literature reviews (collaborative codification, processing of semi-structured data)

- Git (as a synonym for distributed versioning systems): line-based versioning of text-files (challenge: merging)
- A commit corresponds to an individual processing step
- Version-history  (explicitly show where flexibility is needed - data extraction/analysis) - also mention git history (principles), commit messages, collaboration principles (local IDs)
- Pre-commit hooks advantage: the versioning system takes care of it (regardless of whether robots or researchers edit the content). We should use the hooks to avoid commits of broken states (untraceable changes). The hooks should exercise relatively strict control because not all authors of a review may be familiar with git/all principles of the review_template. For experts, it is always possible to override the hooks (--no-verify).
- One-branch principle (do not consider branching in the pipeline (yet??))
- Principle: commits should correspond to manual vs. automated contributions. They should reflect the degree to which checking is necessary. For instance, it makes sense to split the merging process into separate commits (the automated/identical ones and the manual ones)
- Git versions should be frequent but also well thought-through and checked/reviewed (no automated mixing/syncing of work with the project as in database-tools)
- Committed changes should be as small as possible for collaboration/merging purposes (also for checking/restoring)
- Scripts should add their changes to the index

Data
---------------

The CoLRev framework is based on an opinionated and well-justified selection of data structures, file-paths and operating principles.
Ideally, constraining the set of possible data formatting and storage options improves workflow efficiency (because tools and researchers share the same philosophy of data) without any side-effects on the analysis and synthesis process/outcomes.

The main goal of data structuring is to give users a transparent overview of (1) the detailed changes that were made, (2) by whom, and (3) why.
Having access to these data and being able ot analyze them efficiently is of critical importance to

1. develop confidence in the review process,
2. communicate and justify the trustworthiness of the results,
3. improve individual contributions (e.g., train research assistants, to validate algorithms),
4. be in a position to identify and remove contributions of individuals (algorithms or researchers) in case systematic errors are introduced,
5. efficiently extract data on individual steps (e.g., deduplication) for reuse (e.g., crowdsourcing)

Examples of transparency in different stages are provided below.

To accomplish these goals, CoLRev tracks a status for each record.

- The status is used to determine the current state of the review project
- It is used by the ReviewManager to determine which operations are valid according to the processing order (e.g., records must be prepared before they are considered for duplicate removal, PDFs have to be acquired before the main inclusion screen)
- Tracking record status enables incremental duplicate detection (record pairs that have passed deduplication once do not need to be checked again in the next iterations)
- Strictly adhering to the state machine allows us to rely on a simple data structure (e.g., status="synthesized" implies pdf_prepared, md_prepared, rev_included, rev_prescreen_included - no need to check consistency between different screening decisions)

.. figure:: ../../figures/micro_framework.png
   :alt: Micro framework

Examples of transparency in preparation, deduplication, and screening:

.. figure:: ../../figures/change_example1.png
   :alt: Change example 1

Note : in this case, we see that the record was prepared (changing the status from ```md_imported``` to ```md_prepared```) based on the LINKED_URL (as explained by the ```metadata_source``` field).
The doi was extracted from the website (url) and used to update and complete the metadata (after checking whether it corresponds with the existing ```title```, ```author```, .... fields).
The processing report (part of the commit message) provides further details.

.. figure:: ../../figures/change_example2.png
   :alt: Change example 2

**TODO**: include examples for deduplication and screening.


Raw data sources
- Transformed to BibTex by CoLRev to facilitate more efficient processing
- Can be immutable (e.g., results extracted from databases) * Exception: fixing incompatibilities with BibTex Standard
- Can be in append-mode or even update-mode (e.g., for feeds that regularly query databases or indices like Crossref)

The MAIN_REFERENCES contain all records.
They are considered the "single version of truth" (with the corresponding version history).
They are sorted according to IDs, which makes it easy to examine deduplication decisions. Once propagated to the review process (the prescreen), the ID field (e.g., BaranBerkowicz2021) is considered immutable and used to identify the record throughout the review process.
To facilitate an efficient visual analysis of deduplication decisions (and preparation changes), CoLRev attempts to set the final IDs (based on formatted and completed metadata) when importing records into the MAIN_REFERENCEs (IDs may be updated until the deduplication step if the author and year fields change).

ID formats, such as three-author+year (automatically generated by CoLRev), is recommended because

  - semantic IDs are easier to remember (compared to arbitrary ones like DOIs or numbers that are incremented),
  - global identifiers (like DOIs or Web of Science accession numbers) are not available for every record (such as conference papers, books, or unpublished reports),
  - shorter formats (like first-author+year) may often require arbitrary suffixes

Individual records in the MAIN_REFERENCES are augmented with

- the ```status``` field to track the current state of each record in the review process and to facilitate efficient analyses of changes (without jumping between a references file and a screening sheet/data sheet/manuscript)
- the ```origin``` field to enable traceability and analyses (in both directions)


The order of the first fields is fixed to enable efficient status checks.

.. code-block:: latex

    @article{BaranBerkowicz2021,
      origin          = {PoPCites.bibtex.bib/pop00082},
      status          = {md_prepared},
      metadata_source = {LINKED_URL},
      doi             = {10.3390/su13116494},
      author          = {Baran, Grzegorz and Berkowicz, Aleksandra},
      journal         = {Sustainability},
      title           = {Digital Platform Ecosystems as Living Labs for Sustainable Entrepreneurship and Innovation},
      year            = {2021},
      number          = {11},
      volume          = {13},
      url             = {https://www.mdpi.com/2071-1050/13/11/6494/pdf},
    }

BibTex:

- Quasi-standard format that is supported by most reference managers and literature review tools for input/output [1](https://en.wikipedia.org/wiki/Comparison_of_reference_management_software).
- BibTex is easier for humans to analyze in git-diffs because field names are not abbreviated (this is not the case for Endnote .enl or .ris formats), it is line-based (column-based formats like csv are hard to analyze in git diffs), and it contains less syntactic markup that makes it difficult to read (e.g., XML or MODS).
- BibTex is easy to edit manually (in contrast to JSON) and does not force users to prepare the whole dataset at a very granular level (like CSL-JSON/YAML, which requires each author name to be split into the first, middle, and last name).
- BibTex can be augmented (including additional fields for the record origin, status, etc.)
- BibTex is more flexible (allowing for new record types to be defined) compared to structured formats (e.g., SQL)


.. _CoLRev: https://github.com/geritwagner/colrev
.. _CoLRev-core: https://github.com/geritwagner/colrev_core
.. _CoLRev-hooks: https://github.com/geritwagner/colrev-hooks
.. _CoLRev-extensions: https://github.com/topics/colrev-extension
