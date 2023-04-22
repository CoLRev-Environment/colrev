# ReviewType: Curated masterdata repository

Note: This document is currently under development. It will contain the following elements.

## Short summary

- explanation
- goals
- dimensions
- differences between disciplines

## Steps and operations

To create a new masterdata curation, run

```
colrev init --type colrev_built_in.curated_masterdata
# add crossref
colrev search -a "crossref:jissn=123456"
# add further sources (like DBLP)

```

### Problem formulation

### Metadata retrieval

- All SearchSources should correspond to metadata-SearchSources (e.g., retrieving the whole journal from Crossref), i.e., the linking to metadata-SearchSources is disabled in the prep operation.
- The curation endpoint supports the specification of ``masterdata_restrictions``, defining the name of the outlet, whether volume or issue fields are required (for which time-frame).
- Dedicated dedupe endpoints are activated.

### Metadata prescreen

### PDF retrieval

### PDF screen

### Data extraction and synthesis

- For manuscript development see separate page for Word/Tex/Md, Reference Managers

## Software recommendations

## References
