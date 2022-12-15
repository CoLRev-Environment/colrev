
Sources
==================================

SearchSources are a key component of CoLRev. We keep track from which source the records originate. When search results are added, we apply heuristics to identify their source. Knowing the source matters:

- When you run `colrev search` (or `colrev search --udpate`), the metadata will be updated automatically (e.g., when a paper was retracted, or when fiels like citation counts or urls have changed).
- In addition, some SearchSources have unique data quality issues (e.g., incorrect use of fields or record types). Each source can have its unique preparation steps, and restricting the scope of preparation rules allows us to prevent side effects on other records originating from high-quality sources.


TODO : add an illustration of sources (how they enable active flows)

The following SearchSources are covered

.. datatemplate:json:: ../../../colrev/template/package_endpoints.json

    {{ make_list_table_from_mappings(
        [("SearchSource", "link"), ("Identifier", "package_endpoint_identifier"), ("Heuristics", "heuristic"), ("API search", "api_search"), ("Search instructions", "instructions")],
        data['search_source'],
        title='',
        ) }}

    Notes:
     - Other SearchSources are handled by "Unknown Source"
     - Heuristics enable automated detection of the SearchSources upon load
     - ONI: Output not identifiable (e.g., BibTeX/RIS files lack unique features to identify the original SearchSource)
     - NA: Not applicable
     - For updates, fixes, and additions of SearchSources, check the `Github issues <https://github.com/geritwagner/colrev/labels/search_source>`_.
