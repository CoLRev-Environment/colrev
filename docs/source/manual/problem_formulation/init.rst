
.. _Init:

colrev init
-------------------------------


``colrev init`` initializes a new CoLRev project. It requires an empty directory.
With this operation, the directories and files, including the git history, are set up.
Ideally, the selected review type is passed as a parameter:

.. code:: bash

	colrev init --type REVIEW_TYPE

With this parameter, the ``settings.json`` file is created with reasonable defaults for the selected review type. For example, a theoretical review may involve an emergent data analysis and synthesis approach, while a meta-analysis would involve a structured data extraction and a PRISMA flow chart for transparent reporting.




The specific setup of the available review types is available in the following table:

.. datatemplate:json:: ../../../../colrev/template/package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Review type", "short_description"), ("Identifier", "package_endpoint_identifier"), ("Link", "link"), ("Status", "status_linked")],
        data['review_type'],
        title='',
        ) }}


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
