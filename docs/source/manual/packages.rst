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



   packages/colrev.blank.rst
   packages/colrev.conceptual_review.rst
   packages/colrev.critical_review.rst
   packages/colrev.curated_masterdata.rst
   packages/colrev.descriptive_review.rst
   packages/colrev.literature_review.rst
   packages/colrev.meta_analysis.rst
   packages/colrev.methodological_review.rst
   packages/colrev.narrative_review.rst
   packages/colrev.qualitative_systematic_review.rst
   packages/colrev.scientometric.rst
   packages/colrev.scoping_review.rst
   packages/colrev.theoretical_review.rst
   packages/colrev.umbrella.rst


   packages/colrev.abi_inform_proquest.rst
   packages/colrev.acm_digital_library.rst
   packages/colrev.ais_library.rst
   packages/colrev.arxiv.rst
   packages/colrev.colrev_project.rst
   packages/colrev.crossref.rst
   packages/colrev.dblp.rst
   packages/colrev.ebsco_host.rst
   packages/colrev.eric.rst
   packages/colrev.europe_pmc.rst
   packages/colrev.files_dir.rst
   packages/colrev.github.rst
   packages/colrev.google_scholar.rst
   packages/colrev.ieee.rst
   packages/colrev.jstor.rst
   packages/colrev.local_index.rst
   packages/colrev.open_alex.rst
   packages/colrev.open_citations_forward_search.rst
   packages/colrev.open_library.rst
   packages/colrev.osf.rst
   packages/colrev.pdf_backward_search.rst
   packages/colrev.plos.rst
   packages/colrev.prospero.rst
   packages/colrev.psycinfo.rst
   packages/colrev.pubmed.rst
   packages/colrev.scopus.rst
   packages/colrev.semanticscholar.rst
   packages/colrev.springer_link.rst
   packages/colrev.synergy_datasets.rst
   packages/colrev.taylor_and_francis.rst
   packages/colrev.trid.rst
   packages/colrev.unknown_source.rst
   packages/colrev.unpaywall.rst
   packages/colrev.web_of_science.rst
   packages/colrev.wiley.rst


   packages/colrev.add_journal_ranking.rst
   packages/colrev.colrev_curation.rst
   packages/colrev.crossref.rst
   packages/colrev.dblp.rst
   packages/colrev.europe_pmc.rst
   packages/colrev.exclude_collections.rst
   packages/colrev.exclude_complementary_materials.rst
   packages/colrev.exclude_languages.rst
   packages/colrev.exclude_non_latin_alphabets.rst
   packages/colrev.general_polish.rst
   packages/colrev.get_doi_from_urls.rst
   packages/colrev.get_masterdata_from_citeas.rst
   packages/colrev.get_masterdata_from_doi.rst
   packages/colrev.get_year_from_vol_iss_jour.rst
   packages/colrev.github.rst
   packages/colrev.local_index.rst
   packages/colrev.open_alex.rst
   packages/colrev.open_library.rst
   packages/colrev.pubmed.rst
   packages/colrev.remove_broken_ids.rst
   packages/colrev.remove_urls_with_500_errors.rst
   packages/colrev.semanticscholar.rst
   packages/colrev.source_specific_prep.rst


   packages/colrev.cli_prep_man.rst
   packages/colrev.export_man_prep.rst
   packages/colrev.prep_man_curation_jupyter.rst


   packages/colrev.curation_full_outlet_dedupe.rst
   packages/colrev.curation_missing_dedupe.rst
   packages/colrev.dedupe.rst


   packages/colrev.colrev_cli_prescreen.rst
   packages/colrev.conditional_prescreen.rst
   packages/colrev.genai.rst
   packages/colrev.prescreen_table.rst
   packages/colrev.scope_prescreen.rst


   packages/colrev-scidb.rst
   packages/colrev.download_from_website.rst
   packages/colrev.local_index.rst
   packages/colrev.unpaywall.rst
   packages/colrev.website_screenshot.rst


   packages/colrev.colrev_cli_pdf_get_man.rst


   packages/colrev.grobid_tei.rst
   packages/colrev.ocrmypdf.rst
   packages/colrev.remove_coverpage.rst
   packages/colrev.remove_last_page.rst


   packages/colrev.colrev_cli_pdf_prep_man.rst


   packages/colrev.colrev_cli_screen.rst
   packages/colrev.genai.rst
   packages/colrev.screen_table.rst


   packages/colrev.bibliography_export.rst
   packages/colrev.colrev_curation.rst
   packages/colrev.genai.rst
   packages/colrev.github_pages.rst
   packages/colrev.obsidian.rst
   packages/colrev.paper_md.rst
   packages/colrev.prisma.rst
   packages/colrev.profile.rst
   packages/colrev.ref_check.rst
   packages/colrev.structured.rst


   packages/colrev-sync.rst
   packages/colrev.doi_org.rst
   packages/colrev.enlit.rst
   packages/colrev.ui_web.rst
