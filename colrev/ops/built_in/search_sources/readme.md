# SearchSources

## Overview

TODO :

- the tables should be generated automatically from the code!
- move TODOs to github issues/link in roadmap


NAA: no API available
ONI: output not identifiable (missing distinct features)
NA: not applicable

| SearchSource                                                             | prep/masterdata | API-based search |
| ------------------------------------------------------------------------ | --------------- | ---------------- |
| LocalIndex                                                               | supported       | supported        |
| CoLRev projects                                                          | supported       |                  |
| Unknown Source                                                           | NA              | NA               |
| PDF backward search ([GROBID](https://github.com/kermitt2/grobid))       | NA              | supported        |
| Directory containing PDFs ([GROBID](https://github.com/kermitt2/grobid)) | NA              | supported        |
| Directory containing Video files                                         | NA              | supported        |


| SearchSource                                                            | Heuristics | prep/masterdata | API-based search                                                            |
| ----------------------------------------------------------------------- | ---------- | --------------- | --------------------------------------------------------------------------- |
| [ACM Digital Library](https://dl.acm.org/)                              | supported  | NAA             | NAA                                                                         |
| [AIS eLibrary](https://aisel.aisnet.org/)                               | supported  | NAA             | NAA                                                                         |
| [Crossref](https://www.crossref.org/)/[doi.org](https://www.doi.org/)   | ONI        | supported       | supported [1](https://api.crossref.org/swagger-ui/index.html)               |
| [DBLP](https://dblp.org/)                                               | supported  | supported       | supported [1](https://dblp.org/faq/How+to+use+the+dblp+search+API.html)     |
| [ERIC](https://eric.ed.gov/)                                            | ONI        | **TODO**        | **TODO** [1](https://eric.ed.gov/?api)                                      |
| [Europe PMC](https://europepmc.org/)                                    | supported  | supported       | supported                                                                   |
| [GoogleScholar](https://scholar.google.de/)                             | supported  | NAA             | NAA                                                                         |
| [IEEE Xplore](https://ieeexplore.ieee.org/)                             | supported  | **TODO**        | **TODO** per registration, PySDK available [1](https://developer.ieee.org/) |
| [JSTOR](https://www.jstor.org/)                                         | supported  | NAA             | NAA                                                                         |
| [OpenLibrary](https://openlibrary.org/)                                 | NA         | supported       | **TODO**                                                                    |
| [PsycInfo](https://www.apa.org/pubs/databases/psycinfo)                 | ONI        | NAA             | NAA                                                                         |
| [PubMed](https://pubmed.ncbi.nlm.nih.gov/)                              | supported  | **TODO**        | **TODO** see Europe PMC [1](https://www.ncbi.nlm.nih.gov/books/NBK25497/)   |
| [Transport Research International Documentation](https://trid.trb.org/) | supported  | **TODO**        | **TODO** (RSS feeds)                                                        |
| [Wiley](https://onlinelibrary.wiley.com/)                               | supported  | **TODO**        | **TODO** per registration                                                   |


Paywalled

| SearchSource                                                            | Heuristics | prep/masterdata | API-based search                                                        |
| ----------------------------------------------------------------------- | ---------- | --------------- | ----------------------------------------------------------------------- |
| [Scopus](https://www.scopus.com/)                                       |            |                 |                                                                         |
| [Web of Science](https://www.webofknowledge.com)                        |            |                 |                                                                         |


## TODO


| SearchSource  | Heuristics | prep/masterdata | API-based search                     |
| ------------- | ---------- | --------------- | ------------------------------------ |
| EbscoHost     |            |                 |                                      |
| ProQuest      |            |                 |                                      |
| ScienceDirect |            |                 |                                      |
| OVID          |            |                 |                                      |
| CINAHL        |            |                 |                                      |
| ArXiv         |            |                 | [1](http://arxiv.org/help/api/index) |
| SpringerLink  |            |                 |                                      |

- VirtualHealthLibrary
- BielefeldAcademicSearchEngine
- AMiner
- CiteSeerX
- DirectoryOfOpenAccessJournals
- EducationResourcesInformationCenter
- SemanticScholar
- WorldCat
- WorldWideScience

- Github (TBD)

## Resources

- [Overview of APIs for scholarly resources](https://guides.lib.berkeley.edu/information-studies/apis)
