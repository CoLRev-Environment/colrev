# Search

Details of the individual searches are available in the [search_details.csv](search/search_details.csv).


# Removing duplicates

work in progress...
Join the bib/ris/...-files that contain the search result (import in Jabref)
include an id of the original file
deduplicate (jabref: find duplicates + sort by title, by author and check manually for duplicates!)

and remove duplicate BIBTEXKEYs (deduplication based on bibliographic data is done when new entries are added to the [paper.bib](data/paper.bib)).


# Inclusion screening based on titles/abstracts

- Record screening decision: [inclusion.csv](inclusion.csv), column Inclusion_1
- Only paper published in English are considered.
- In a paper is included: acquire PDF for full-text eligibility assessment

#  Completeness of bibliographic data

- todo

# Eligibility assessment based on full-texts

- Record screening decision: [inclusion.csv](inclusion.csv), column Inclusion_2
- If it is excluded:
  - save pdf in the 1-raw-rata/excluded directory
  - create a link in the bibtex entry
- If it is included:
  - save pdf in the data/paper directory
  - create a link in the bibtex entry
  - compare paper meta-data with bibtex entry to make sure it is accurate and complete (including pages etc.). Note: this could be (partially) automated.
  - copy bibtex entry to bibliography (using a crossref link for conference papers, deleting the file-link)
  - Execute backward search for the paper
  - add bibtex entry to the sample (Appendix)

# Data extraction

[data.csv](data.csv), column Extraction


code book...
