colrev.record.PrepRecord
========================

.. currentmodule:: colrev.record

.. autoclass:: PrepRecord
   :members:
   :show-inheritance:
   :inherited-members:
   :special-members: __call__, __add__, __mul__



   .. rubric:: Methods

   .. autosummary::
      :nosignatures:

      ~PrepRecord.abbreviate_container
      ~PrepRecord.add_colrev_ids
      ~PrepRecord.add_data_provenance
      ~PrepRecord.add_data_provenance_note
      ~PrepRecord.add_masterdata_provenance
      ~PrepRecord.add_masterdata_provenance_note
      ~PrepRecord.add_provenance_all
      ~PrepRecord.change_ENTRYTYPE
      ~PrepRecord.check_potential_retracts
      ~PrepRecord.complete_provenance
      ~PrepRecord.container_is_abbreviated
      ~PrepRecord.copy
      ~PrepRecord.copy_prep_rec
      ~PrepRecord.create_colrev_id
      ~PrepRecord.extract_pages
      ~PrepRecord.extract_text_by_page
      ~PrepRecord.format_author_field
      ~PrepRecord.format_bib_style
      ~PrepRecord.format_if_mostly_upper
      ~PrepRecord.fuse_best_field
      ~PrepRecord.get_abbrev_container_min_len
      ~PrepRecord.get_colrev_id
      ~PrepRecord.get_colrev_pdf_id
      ~PrepRecord.get_container_title
      ~PrepRecord.get_data
      ~PrepRecord.get_diff
      ~PrepRecord.get_field_provenance
      ~PrepRecord.get_incomplete_fields
      ~PrepRecord.get_inconsistencies
      ~PrepRecord.get_origins
      ~PrepRecord.get_pages_in_pdf
      ~PrepRecord.get_quality_defects
      ~PrepRecord.get_record_similarity
      ~PrepRecord.get_retrieval_similarity
      ~PrepRecord.get_similarity
      ~PrepRecord.get_similarity_detailed
      ~PrepRecord.get_tei_filename
      ~PrepRecord.get_text_from_pdf
      ~PrepRecord.get_toc_key
      ~PrepRecord.get_value
      ~PrepRecord.has_incomplete_fields
      ~PrepRecord.has_inconsistent_fields
      ~PrepRecord.has_overlapping_colrev_id
      ~PrepRecord.has_quality_defects
      ~PrepRecord.import_provenance
      ~PrepRecord.masterdata_is_complete
      ~PrepRecord.masterdata_is_curated
      ~PrepRecord.merge
      ~PrepRecord.missing_fields
      ~PrepRecord.pdf_get_man
      ~PrepRecord.pdf_man_prep
      ~PrepRecord.preparation_break_condition
      ~PrepRecord.preparation_save_condition
      ~PrepRecord.prescreen_exclude
      ~PrepRecord.print_citation_format
      ~PrepRecord.print_diff_pair
      ~PrepRecord.remove_accents
      ~PrepRecord.remove_field
      ~PrepRecord.remove_quality_defect_notes
      ~PrepRecord.rename_field
      ~PrepRecord.reset_pdf_provenance_notes
      ~PrepRecord.set_fields_complete
      ~PrepRecord.set_masterdata_complete
      ~PrepRecord.set_masterdata_consistent
      ~PrepRecord.set_status
      ~PrepRecord.shares_origins
      ~PrepRecord.status_to_prepare
      ~PrepRecord.unify_pages_field
      ~PrepRecord.update_by_record
      ~PrepRecord.update_field
      ~PrepRecord.update_masterdata_provenance
      ~PrepRecord.update_metadata_status





   .. rubric:: Attributes

   .. autosummary::

      ~PrepRecord.dict_fields_keys
      ~PrepRecord.identifying_field_keys
      ~PrepRecord.list_fields_keys
      ~PrepRecord.pp
      ~PrepRecord.preferred_sources
      ~PrepRecord.provenance_keys
      ~PrepRecord.record_field_inconsistencies
      ~PrepRecord.record_field_requirements
      ~PrepRecord.data
