colrev.dataset.Dataset
======================

.. currentmodule:: colrev.dataset

.. autoclass:: Dataset
   :members:
   :show-inheritance:
   :inherited-members:
   :special-members: __call__, __add__, __mul__



   .. rubric:: Methods

   .. autosummary::
      :nosignatures:

      ~Dataset.add_changes
      ~Dataset.add_record_changes
      ~Dataset.add_setting_changes
      ~Dataset.behind_remote
      ~Dataset.check_fields
      ~Dataset.check_main_records_duplicates
      ~Dataset.check_main_records_origin
      ~Dataset.check_main_records_screen
      ~Dataset.check_persisted_id_changes
      ~Dataset.check_propagated_ids
      ~Dataset.check_sources
      ~Dataset.check_status_transitions
      ~Dataset.create_commit
      ~Dataset.file_in_history
      ~Dataset.format_records_file
      ~Dataset.get_commit_message
      ~Dataset.get_committed_origin_states_dict
      ~Dataset.get_crossref_record
      ~Dataset.get_currently_imported_origin_list
      ~Dataset.get_last_commit_sha
      ~Dataset.get_last_records_filecontents
      ~Dataset.get_missing_files
      ~Dataset.get_next_id
      ~Dataset.get_nr_in_bib
      ~Dataset.get_origin_state_dict
      ~Dataset.get_record_header_list
      ~Dataset.get_record_state_list
      ~Dataset.get_records_curated_currentl
      ~Dataset.get_records_curated_prior_from_history
      ~Dataset.get_remote_commit_differences
      ~Dataset.get_repo
      ~Dataset.get_states_set
      ~Dataset.get_tree_hash
      ~Dataset.get_untracked_files
      ~Dataset.has_changes
      ~Dataset.has_untracked_search_records
      ~Dataset.import_file
      ~Dataset.inplace_change
      ~Dataset.load_field_dict
      ~Dataset.load_from_git_history
      ~Dataset.load_origin_records
      ~Dataset.load_records_dict
      ~Dataset.parse_bibtex_str
      ~Dataset.parse_records_dict
      ~Dataset.propagated_id
      ~Dataset.pull_if_repo_clean
      ~Dataset.read_next_record
      ~Dataset.records_changed
      ~Dataset.records_file_in_history
      ~Dataset.remote_ahead
      ~Dataset.remove_file_from_git
      ~Dataset.replace_field
      ~Dataset.reprocess_id
      ~Dataset.reset_log_if_no_changes
      ~Dataset.retrieve_by_colrev_id
      ~Dataset.retrieve_ids_from_bib
      ~Dataset.retrieve_prior
      ~Dataset.retrieve_records_from_history
      ~Dataset.retrieve_status_data
      ~Dataset.save_record_list_by_id
      ~Dataset.save_records_dict
      ~Dataset.save_records_dict_to_file
      ~Dataset.set_ids
      ~Dataset.update_colrev_ids
      ~Dataset.update_record_by_id





   .. rubric:: Attributes

   .. autosummary::

      ~Dataset.RECORDS_FILE_RELATIVE
      ~Dataset.records_file
