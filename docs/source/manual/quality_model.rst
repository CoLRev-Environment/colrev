
Quality model
==================================

The quality model specifies the necessary checks when a records should transition to ``md_prepared``. The functionality fixing errors is organized in the `prep` package endpoints.

Similar to linters such as pylint, it should be possible to disable selected checks. Failed checks are made transparent by adding the corresponding codes (e.g., `mostly-upper`) to the `colrev_masterdata_provenance` (`notes` field).


.. toctree::
   :caption: Quality checks
   :maxdepth: 3

   quality_model/container_title_abbreviated
   quality_model/doi_not_matching_pattern
   quality_model/erroneous_symbol_in_field
   quality_model/erroneous_term_in_field
   quality_model/erroneous_title_field
   quality_model/html_chars
   quality_model/identical_values_between_title_and_container
   quality_model/incomplete_field
   quality_model/inconsistent_content
   quality_model/inconsistent_with_doi_metadata
   quality_model/inconsistent_with_entrytype
   quality_model/inconsistent_with_url_metadata
   quality_model/isbn_not_matching_pattern
   quality_model/language_format_error
   quality_model/language_unknown
   quality_model/missing_field
   quality_model/mostly_all_caps
   quality_model/name_abbreviated
   quality_model/name_format_separators
   quality_model/name_format_titles
   quality_model/page_range
   quality_model/record_not_in_toc
   quality_model/thesis_with_multiple_authors
   quality_model/year_format
