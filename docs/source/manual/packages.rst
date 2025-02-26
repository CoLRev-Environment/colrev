Packages
=====================

.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 12pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 12pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 12pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html

.. datatemplate:json:: packages_overview.json

    {{ make_list_table_from_mappings(
        [("Type", "endpoint_type"), ("Identifier", "package_endpoint_identifier"), ("Short description", "short_description"), ("Status", "status")],
        data,
        title='',
        columns=[10,20,50,20]
        ) }}


.. raw:: html

    <script>
    $(document).ready(function() {
        var tables = $('table');
        tables.addClass('sortable');  // Add a custom class to all tables
        tables.DataTable({
            "pageLength": 50,  // Set the default number of entries per page
            "order": []        // Disable initial sorting
        });
    });
    </script>


..
   Note: everything following this line will be replaced by doc_registry_manager

.. toctree::
   :hidden:
   :maxdepth: 1
   :caption: Package Index



   packages/colrev_blank.rst
   packages/colrev_conceptual_review.rst
   packages/colrev_critical_review.rst
   packages/colrev_curated_masterdata.rst
   packages/colrev_descriptive_review.rst
   packages/colrev_literature_review.rst
   packages/colrev_meta_analysis.rst
   packages/colrev_methodological_review.rst
   packages/colrev_narrative_review.rst
   packages/colrev_qualitative_systematic_review.rst
   packages/colrev_scientometric.rst
   packages/colrev_scoping_review.rst
   packages/colrev_theoretical_review.rst
   packages/colrev_umbrella.rst


   packages/colrev_abi_inform_proquest.rst
   packages/colrev_acm_digital_library.rst
   packages/colrev_ais_library.rst
   packages/colrev_arxiv.rst
   packages/colrev_colrev_project.rst
   packages/colrev_crossref.rst
   packages/colrev_dblp.rst
   packages/colrev_ebsco_host.rst
   packages/colrev_eric.rst
   packages/colrev_europe_pmc.rst
   packages/colrev_files_dir.rst
   packages/colrev_github.rst
   packages/colrev_google_scholar.rst
   packages/colrev_ieee.rst
   packages/colrev_jstor.rst
   packages/colrev_local_index.rst
   packages/colrev_open_alex.rst
   packages/colrev_open_citations_forward_search.rst
   packages/colrev_open_library.rst
   packages/colrev_osf.rst
   packages/colrev_pdf_backward_search.rst
   packages/colrev_psycinfo.rst
   packages/colrev_pubmed.rst
   packages/colrev_scopus.rst
   packages/colrev_semanticscholar.rst
   packages/colrev_springer_link.rst
   packages/colrev_synergy_datasets.rst
   packages/colrev_taylor_and_francis.rst
   packages/colrev_trid.rst
   packages/colrev_unknown_source.rst
   packages/colrev_unpaywall.rst
   packages/colrev_web_of_science.rst
   packages/colrev_wiley.rst


   packages/colrev_add_journal_ranking.rst
   packages/colrev_colrev_curation.rst
   packages/colrev_crossref.rst
   packages/colrev_dblp.rst
   packages/colrev_europe_pmc.rst
   packages/colrev_exclude_collections.rst
   packages/colrev_exclude_complementary_materials.rst
   packages/colrev_exclude_languages.rst
   packages/colrev_exclude_non_latin_alphabets.rst
   packages/colrev_general_polish.rst
   packages/colrev_get_doi_from_urls.rst
   packages/colrev_get_masterdata_from_citeas.rst
   packages/colrev_get_masterdata_from_doi.rst
   packages/colrev_get_year_from_vol_iss_jour.rst
   packages/colrev_github.rst
   packages/colrev_local_index.rst
   packages/colrev_open_alex.rst
   packages/colrev_open_library.rst
   packages/colrev_pubmed.rst
   packages/colrev_remove_broken_ids.rst
   packages/colrev_remove_urls_with_500_errors.rst
   packages/colrev_semanticscholar.rst
   packages/colrev_source_specific_prep.rst


   packages/colrev_export_man_prep.rst
   packages/colrev_prep_man_curation_jupyter.rst


   packages/colrev_curation_full_outlet_dedupe.rst
   packages/colrev_curation_missing_dedupe.rst
   packages/colrev_dedupe.rst


   packages/colrev_cli_prescreen.rst
   packages/colrev_conditional_prescreen.rst
   packages/colrev_prescreen_table.rst
   packages/colrev_scope_prescreen.rst


   packages/colrev_download_from_website.rst
   packages/colrev_local_index.rst
   packages/colrev_unpaywall.rst
   packages/colrev_website_screenshot.rst


   packages/colrev_cli_pdf_get_man.rst


   packages/colrev_grobid_tei.rst
   packages/colrev_ocrmypdf.rst
   packages/colrev_remove_coverpage.rst
   packages/colrev_remove_last_page.rst


   packages/colrev_cli_pdf_prep_man.rst


   packages/colrev_cli_screen.rst
   packages/colrev_screen_table.rst


   packages/colrev_bibliography_export.rst
   packages/colrev_colrev_curation.rst
   packages/colrev_github_pages.rst
   packages/colrev_obsidian.rst
   packages/colrev_paper_md.rst
   packages/colrev_prisma.rst
   packages/colrev_profile.rst
   packages/colrev_structured.rst


   packages/colrev_doi_org.rst
   packages/colrev_sync.rst
   packages/colrev_ui_web.rst
