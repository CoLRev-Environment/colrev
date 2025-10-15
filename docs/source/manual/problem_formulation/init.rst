colrev init
-------------------------------

.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 12pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 12pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 12pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html


``colrev init`` initializes a new CoLRev project. It requires an empty directory.
With this operation, the directories and files, including the git history, are set up.
It is recommended to select a review type using the ``--type`` parameter:

.. code:: bash

	colrev init --type

Depending on the selected review type, the ``settings.json`` file is created with reasonable defaults. For example, a theoretical review may involve an emergent data analysis and synthesis approach, while a meta-analysis would involve a structured data extraction and a PRISMA flow chart for transparent reporting.

Once the CoLRev project is set up, it can be pushed to a Git server and shared with the team (see :doc:`instructions </manual/collaboration>`).

The specific setup of the available review types is available in the following table:

.. datatemplate:json:: ../package_endpoints.json

    {{ make_list_table_from_mappings(
        [("Identifier", "package_endpoint_identifier"), ("Review type", "short_description"), ("Status", "status")],
        data['review_type'],
        title='',
        columns=[25,55,20]
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
