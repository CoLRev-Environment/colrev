colrev\_core.review\_dataset.ReviewDataset
==========================================

.. currentmodule:: colrev_core.review_dataset

.. autoclass:: ReviewDataset
   :members:
   :show-inheritance:
   :inherited-members:
   :special-members: __call__, __add__, __mul__



   .. rubric:: Methods

   .. autosummary::
      :nosignatures:

      ~ReviewDataset.add_changes
      ~ReviewDataset.add_record_changes
      ~ReviewDataset.add_setting_changes
      ~ReviewDataset.behind_remote
      ~ReviewDataset.check_corrections_of_curated_records
      ~ReviewDataset.check_main_references_duplicates
      ~ReviewDataset.check_main_references_origin
      ~ReviewDataset.check_main_references_screen
      ~ReviewDataset.check_main_references_status_fields
      ~ReviewDataset.check_persisted_ID_changes
      ~ReviewDataset.check_propagated_IDs
      ~ReviewDataset.check_sources
      ~ReviewDataset.check_status_transitions
      ~ReviewDataset.create_commit
      ~ReviewDataset.file_in_history
      ~ReviewDataset.format_main_references
      ~ReviewDataset.get_commit_message
      ~ReviewDataset.get_last_commit_sha
      ~ReviewDataset.get_missing_files
      ~ReviewDataset.get_origin_state_dict
      ~ReviewDataset.get_record_header_list
      ~ReviewDataset.get_record_state_list
      ~ReviewDataset.get_record_state_list_from_file_obj
      ~ReviewDataset.get_remote_commit_differences
      ~ReviewDataset.get_repo
      ~ReviewDataset.get_states_set
      ~ReviewDataset.get_tree_hash
      ~ReviewDataset.has_changes
      ~ReviewDataset.import_file
      ~ReviewDataset.load_field_dict
      ~ReviewDataset.load_from_git_history
      ~ReviewDataset.load_origin_records
      ~ReviewDataset.load_records_dict
      ~ReviewDataset.load_sources
      ~ReviewDataset.parse_bibtex_str
      ~ReviewDataset.parse_records_dict
      ~ReviewDataset.propagated_ID
      ~ReviewDataset.pull_if_repo_clean
      ~ReviewDataset.read_next_record
      ~ReviewDataset.remote_ahead
      ~ReviewDataset.remove_file
      ~ReviewDataset.replace_field
      ~ReviewDataset.reprocess_id
      ~ReviewDataset.reset_log_if_no_changes
      ~ReviewDataset.retrieve_IDs_from_bib
      ~ReviewDataset.retrieve_by_colrev_id
      ~ReviewDataset.retrieve_data
      ~ReviewDataset.retrieve_prior
      ~ReviewDataset.retrieve_records_from_history
      ~ReviewDataset.save_field_dict
      ~ReviewDataset.save_record_list_by_ID
      ~ReviewDataset.save_records_dict
      ~ReviewDataset.save_records_dict_to_file
      ~ReviewDataset.set_IDs
      ~ReviewDataset.update_colrev_ids
      ~ReviewDataset.update_record_by_ID





   .. rubric:: Attributes

   .. autosummary::

      ~ReviewDataset.dict_fields
      ~ReviewDataset.list_fields
