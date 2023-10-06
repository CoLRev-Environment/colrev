Step 2: Metadata retrieval
---------------------------------------------

The step of metadata retrieval refers to the process of formulating and executing a **search strategy**, which involves operations related to obtaining search results from different sources, as well as loading, preparing, and deduplicating them.
This step can be technically demanding due to limited functionality of data sources and data quality issues, and methodologically demanding because there are no simple recipes to formulate an effective search strategy.

..
   - DBs not supporting automated/API-based access (i.e., requiring manual retrieval of search results),
   - TBD: Explain / illustrate state intermediate transitions

Standalone literature reviews are typically based on a search strategy, which comprises the following elements:

- The **search scope** can restrict the journals, disciplines (based on reasons related to their topics or source reputation), time, or publication type (grey vs. academic literature).
- The **search type and iterations** can be exploratory or systematic, and may evolve throughout the search iterations.
- The **combination of search techniques, sources, and parameters**. Search techniques can be database searches, citation searches (backward or forward snowballing), table-of-content searches, for example. Examples of sources are available :doc:`here </manual/metadata_retrieval/search>`. For databases, the parameters (or search strings) can be developed based on a concept matrix (e.g., in line with the PICO framework), boolean operators, and search query translation tools.
- The **termination rule** specifies the criteria for stopping the search process.

The methodological choices related to the search strategy should be documented for reporting purposes. This can be done in the ``data/paper.md`` or the ``readme.md``.

Metadata retrieval is a high-level operation consisting of the following operations:

- The ``search`` operation, which obtains search results automatically (using an API) or from a file provided by the user, and records information related to the search source (search parameters).

- The ``load`` operation, which converts all search results (metadata) to the same format (BibTex) and add to the same dataset (``data/record.bib`` file). Each record is linked to the origins that remain in the ``data/search`` directory.

- The ``prep`` operation, which evaluates and improves the data quality of records. This is necessary to ensure adequate performance of deduplication algorithms and to reduce manual efforts for polishing reference sections. If manual preparation is required, records are set to the ``md_needs_manual_preparation`` state and the ``colrev status`` advises users on how to proceed.

- The ``dedupe`` operation, which links records pointing to the same paper to create a dataset without duplicates. Specifically, duplicate records are merged in a way that preserves their links to the respective origin records and allows users to undo merges at any time (no simple removing of duplicates).

To start the retrieval operation, add search results to the ``data/search`` directory and run:

.. code:: bash

	colrev retrieve

The design of the retrieval operations ensures that searches can be conducted in a highly iterative way.
In particular, this pertains to an efficient flow of new records through the process and mechanisms to handle changes (e.g., when papers are retracted).

..
   - Mention that more detailed commands (prep, prep-man, ...) will be suggested if colrev retrieve does not result in all records transitioning to md_processed

.. toctree::
   :maxdepth: 1
   :caption: Operations

   metadata_retrieval/search
   metadata_retrieval/load
   metadata_retrieval/prep
   metadata_retrieval/dedupe
