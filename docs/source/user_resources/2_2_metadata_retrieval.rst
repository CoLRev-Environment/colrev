.. _Metadata retrieval:

Step 2: Metadata retrieval
---------------------------------------------

The step of metadata retrieval refers to the process of formulating and executing a **search strategy**, which involves operations related to obtaining search results from different sources, as well as loading, preparing, and deduplicating them.
This step can be technically demanding due to limited functionality of data sources and data quality issues, and methodologically demanding because there are no simple recipes to formulate an effective search strategy.

..
   - DBs not supporting automated/API-based access (i.e., requiring manual retrieval of search results),
   - TBD: Explain / illustrate state intermediate transitions

Standalone literature reviews are typically based on a search strategy, which comprises the following elements:

   - The **search type** can be exploratory or systematic, and may evolve throughout several iterations.
   - The **search scope** can restrict the journals, disciplines (based on reasons related to their topics or source reputation), time, or publication type (grey vs. academic literature).
   - The **combination of search techniques, sources, and parameters**. Search techniques can be database searches, citation searches (backward or forward snowballing), table-of-content searches, for example. Examples of sources are available `here </user_resources/6_sources.html>`_. For databases, the parameters (or search strings) can be developed based on a concept matrix (e.g., in line with the PICO framework), boolean operators, and search query translation tools.
   - It can also be helpful to specify a termination rule for the search.
   - The methodological choices related to the search strategy should be documented for reporting purposes. This  can be done in the ``data/paper.md`` or the ``readme.md``.

- Search operation:
   - Record information related to the search source (search parameters)
   - Obtain search results automatically (using an API) or from a file provided by the user

- Load operation:
   - Convert all search results (metadata) to the same format (BibTex) and add to the same dataset (data/record.bib file)

- Prep operation:
   - Data quality, consistency/linking to metadata sources

- Dedupe operation:
   - Linking, not removing (like deleting)

..
   - Mention that more detailed commands (prep, prep-man, ...) will be suggested if colrev retrieve does not result in all records transitioning to md_processed

.. toctree::
   :maxdepth: 3
   :caption: Operations

   2_2_metadata_retrieval/search
   2_2_metadata_retrieval/load
   2_2_metadata_retrieval/prep
   2_2_metadata_retrieval/dedupe
