

.. _Init:

Problem formulation - init
-------------------------------


:program:`colrev init` initializes a new CoLRev project. It should be called in an empty directory.

.. code:: bash

	colrev init [options]

.. TODO : include options for different types of reviews once available

Once the repository is set up, you can share it with your team (see `instructions <3_collaboration.html>`_).

Instead of initializing a new repository, you can also pull an existing one:

.. code:: bash

	colrev pull https://github.com/u_name/repo_name.git

..
   Settings

   .. code-block:: json

         {
         "project": {
            "id_pattern": "THREE_AUTHORS_YEAR",
            "review_type": "NA",
            "share_stat_req":"processed",
            "delay_automated_processing": true,
            "curated_masterdata": false,
            "curated_fields": []
         },
         "search": {"sources": []},
         "load": {},
         "prep": {
            "fields_to_keep": [],
            "prep_rounds": [
               {
                     "name": "exclusion",
                     "similarity": 1.0,
                     "scripts": [
                        "exclude_non_latin_alphabets",
                        "exclude_languages"
                     ]
               },
               {
                     "name": "high_confidence",
                     "similarity": 0.99,
                     "scripts": [
                        "remove_urls_with_500_errors",
                        "remove_broken_IDs",
                        "global_ids_consistency_check",
                        "prep_curated",
                        "format",
                        "resolve_crossrefs",
                        "get_doi_from_urls",
                        "get_masterdata_from_doi",
                        "get_masterdata_from_crossref",
                        "get_masterdata_from_dblp",
                        "get_masterdata_from_open_library",
                        "get_year_from_vol_iss_jour_crossref",
                        "get_record_from_local_index",
                        "remove_nicknames",
                        "format_minor",
                        "drop_fields",
                        "update_metadata_status"
                     ]
               },
               {
                     "name": "medium_confidence",
                     "similarity": 0.9,
                     "scripts": [
                        "prep_curated",
                        "get_doi_from_sem_scholar",
                        "get_doi_from_urls",
                        "get_masterdata_from_doi",
                        "get_masterdata_from_crossref",
                        "get_masterdata_from_dblp",
                        "get_masterdata_from_open_library",
                        "get_year_from_vol_iss_jour_crossref",
                        "get_record_from_local_index",
                        "remove_nicknames",
                        "remove_redundant_fields",
                        "format_minor",
                        "drop_fields",
                        "update_metadata_status"
                     ]
               },
               {
                     "name": "low_confidence",
                     "similarity": 0.8,
                     "scripts": [
                        "prep_curated",
                        "correct_recordtype",
                        "get_doi_from_sem_scholar",
                        "get_doi_from_urls",
                        "get_masterdata_from_doi",
                        "get_masterdata_from_crossref",
                        "get_masterdata_from_dblp",
                        "get_masterdata_from_open_library",
                        "get_year_from_vol_iss_jour_crossref",
                        "get_record_from_local_index",
                        "remove_nicknames",
                        "remove_redundant_fields",
                        "format_minor",
                        "drop_fields",
                        "update_metadata_status"
                     ]
               }
            ]
         },
         "dedupe": {"merge_threshold": 0.8, "partition_threshold": 0.5},
         "prescreen": {"plugin": null,
                        "mode": null,
                        "scope": []},
         "pdf_get": {"pdf_path_type": "symlink"},
         "pdf_prep": {},
         "screen": {"process": {"overlapp": null,
                     "mode": null,
                     "parallel_independent": null},
                     "criteria": []
               },
         "data": {"data_format": []}
         }
