
Quality model
==================================

The quality model specifies the necessary checks when a records should transition to ``md_prepared``. The functionality fixing errors is organized in the `prep` package endpoints.

Similar to linters such as pylint, it should be possible to disable selected checks. Failed checks are made transparent by adding the corresponding codes (e.g., `mostly-upper`) to the `colrev_masterdata_provenance` (`notes` field).


.. toctree::
   :caption: Quality checks
   :maxdepth: 3

   quality_model/doi_not_matching_pattern
