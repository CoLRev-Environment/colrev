colrev\_core.prep.Preparation
=============================

.. currentmodule:: colrev_core.prep

.. autoclass:: Preparation
   :members:
   :show-inheritance:
   :inherited-members:
   :special-members: __call__, __add__, __mul__



   .. rubric:: Methods

   .. autosummary::
      :nosignatures:

      ~Preparation.check_DBs_availability
      ~Preparation.check_precondition
      ~Preparation.correct_recordtype
      ~Preparation.crossref_json_to_record
      ~Preparation.drop_fields
      ~Preparation.exclude_languages
      ~Preparation.exclude_non_latin_alphabets
      ~Preparation.format
      ~Preparation.format_author_field
      ~Preparation.format_minor
      ~Preparation.get_doi_from_sem_scholar
      ~Preparation.get_doi_from_urls
      ~Preparation.get_link_from_doi
      ~Preparation.get_masterdata_from_crossref
      ~Preparation.get_masterdata_from_dblp
      ~Preparation.get_masterdata_from_doi
      ~Preparation.get_masterdata_from_open_library
      ~Preparation.get_record_from_local_index
      ~Preparation.get_year_from_vol_iss_jour_crossref
      ~Preparation.global_ids_consistency_check
      ~Preparation.log_notifications
      ~Preparation.main
      ~Preparation.prep_curated
      ~Preparation.prepare
      ~Preparation.print_doi_metadata
      ~Preparation.remove_broken_IDs
      ~Preparation.remove_nicknames
      ~Preparation.remove_redundant_fields
      ~Preparation.remove_urls_with_500_errors
      ~Preparation.reset
      ~Preparation.reset_ids
      ~Preparation.reset_records
      ~Preparation.resolve_crossrefs
      ~Preparation.retrieve_dblp_records
      ~Preparation.retrieve_doi_metadata
      ~Preparation.retrieve_md_from_url
      ~Preparation.retrieve_record_from_semantic_scholar
      ~Preparation.set_ids
      ~Preparation.update_doi_md
      ~Preparation.update_metadata_status





   .. rubric:: Attributes

   .. autosummary::

      ~Preparation.HTML_CLEANER
      ~Preparation.MAX_RETRIES_ON_ERROR
      ~Preparation.PAD
      ~Preparation.TIMEOUT
      ~Preparation.alphabet_detector
      ~Preparation.cache_path
      ~Preparation.doi_regex
      ~Preparation.fields_to_drop
      ~Preparation.fields_to_keep
      ~Preparation.language_detector
      ~Preparation.requests_headers
      ~Preparation.session
