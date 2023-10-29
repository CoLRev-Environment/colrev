Credits
==================================

The CoLRev reference implementation builds on the shoulders of amazing projects (growing giants) and benefits from their ongoing improvements.
Projects that power CoLRev:


.. |pybtexactivity| image:: https://img.shields.io/github/commit-activity/y/live-clones/pybtex?color=green&style=plastic
   :height: 12pt

.. |gitactivity| image:: https://img.shields.io/github/commit-activity/y/git/git?color=green&style=plastic
   :height: 12pt

.. |precommitactivity| image:: https://img.shields.io/github/commit-activity/y/pre-commit/pre-commit?color=green&style=plastic
   :height: 12pt

.. |dockerpyactivity| image:: https://img.shields.io/github/commit-activity/y/docker/docker-py?color=green&style=plastic
   :height: 12pt

.. |dedupeioactivity| image:: https://img.shields.io/github/commit-activity/y/dedupeio/dedupe?color=green&style=plastic
   :height: 12pt

.. |pandasactivity| image:: https://img.shields.io/github/commit-activity/y/pandas-dev/pandas?color=green&style=plastic
   :height: 12pt

.. |pdfmineractivity| image:: https://img.shields.io/github/commit-activity/y/pdfminer/pdfminer.six?color=green&style=plastic
   :height: 12pt

.. |zoterotranslatoractivity| image:: https://img.shields.io/github/commit-activity/y/zotero/translators?color=green&style=plastic
   :height: 12pt

.. |ocrmypdfactivity| image:: https://img.shields.io/github/commit-activity/y/ocrmypdf/OCRmyPDF?color=green&style=plastic
   :height: 12pt

.. |tesseractactivity| image:: https://img.shields.io/github/commit-activity/y/tesseract-ocr/tesseract?color=green&style=plastic
   :height: 12pt

.. |grobidactivity| image:: https://img.shields.io/github/commit-activity/y/kermitt2/grobid?color=green&style=plastic
   :height: 12pt

.. |pandocactivity| image:: https://img.shields.io/github/commit-activity/y/jgm/pandoc?color=green&style=plastic
   :height: 12pt

.. |cslactivity| image:: https://img.shields.io/github/commit-activity/y/citation-style-language/styles?color=green&style=plastic
   :height: 12pt

.. |asreviewactivity| image:: https://img.shields.io/github/commit-activity/y/asreview/asreview?color=green&style=plastic
   :height: 12pt


.. list-table::
   :widths: 54 24 22
   :header-rows: 1
   :class: fullwidthtable

   * - SearchSources (search, load, prep)
     - Field
     - Size
   * - `Crossref <https://www.crossref.org/>`_ (metadata deposited by publishers)
     - Cross-disciplinary
     - > 125,000,000
   * - `Europe PMC <https://europepmc.org/>`_, including PubMed Central (PMC) (metadata)
     - Life sciences
     - > 40,000,000
   * - `Semantic Scholar <https://www.semanticscholar.org/>`_ (metadata)
     - Cross-disciplinary
     - > 175,000,000
   * - `dblp <https://dblp.org/>`_ (curated metadata)
     - IT/IS
     - > 5,750,000
   * - `Open Library <https://openlibrary.org/>`_ (curated metadata, books)
     - Cross-disciplinary
     - > 20,000,000
   * - `CiteAs.org <https://citeas.org/>`_ (metadata on research software, datasets, etc.)
     - Cross-disciplinary
     - Unknown

.. list-table::
   :widths: 54 24 22
   :header-rows: 1
   :class: fullwidthtable

   * - Dedupe
     - License
     - Activity
   * - `dedupe <https://github.com/dedupeio/dedupe>`_ : duplicate identification (active learning)
     - `MIT <https://github.com/dedupeio/dedupe/blob/main/LICENSE>`__
     - |dedupeioactivity|

.. list-table::
   :widths: 54 24 22
   :header-rows: 1
   :class: fullwidthtable

   * - Prescreen
     - License
     - Activity
   * - `ASReview <https://github.com/asreview/asreview>`_ : active-learning-based prescreen
     - Apache-2.0 license
     - |asreviewactivity|

.. list-table::
   :widths: 54 24 22
   :header-rows: 1
   :class: fullwidthtable

   * - PDF retrieval
     - Field
     - Size
   * - `Unpaywall <https://unpaywall.org/>`_ (legal/OA PDF retrieval)
     - Cross-disciplinary
     - > 30,000,000
   * - Retrieval of PDFs from local (indexed) repositories
     - varies
     - varies

.. list-table::
   :widths: 54 24 22
   :header-rows: 1
   :class: fullwidthtable

   * - PDF preparation
     - License
     - Activity
   * - `PDFMiner.six <https://github.com/pdfminer/pdfminer.six>`_ : PDF management
     - `MIT <https://github.com/pdfminer/pdfminer.six/blob/master/LICENSE>`__
     - |pdfmineractivity|
   * - `OCRmyPDF <https://github.com/ocrmypdf/OCRmyPDF>`_ \*: OCR tasks
     - `MPL-2.0 <https://github.com/ocrmypdf/OCRmyPDF/blob/main/LICENSE>`__
     - |ocrmypdfactivity|
   * - `Tesseract OCR <https://github.com/tesseract-ocr/tesseract>`_ \*: OCR tasks
     - `Apache-2.0 <https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE>`__
     - |tesseractactivity|
   * - `GROBID <https://github.com/kermitt2/grobid>`_ \*: parsing annotated PDF content
     - `Apache 2.0 <https://github.com/kermitt2/grobid/blob/master/LICENSE>`__
     - |grobidactivity|

.. list-table::
   :widths: 54 24 22
   :header-rows: 1
   :class: fullwidthtable

   * - Data & analysis
     - License
     - Activity
   * - `pandoc <https://github.com/jgm/pandoc>`_ \*: creating manuscripts
     - `GPL 2 <https://github.com/jgm/pandoc/blob/main/COPYRIGHT>`__
     - |pandocactivity|
   * - `CSL <https://github.com/citation-style-language/styles>`_ \*: formatting citations
     - `CC BY-SA 3.0 <https://github.com/citation-style-language/styles>`__
     - |cslactivity|

.. list-table::
   :widths: 54 24 22
   :header-rows: 1
   :class: fullwidthtable

   * - Core functionality
     - License
     - Activity
   * - `git <https://github.com/git/git>`_ \*: versioning and collaboration
     - `GPL 2 <https://github.com/git/git/blob/master/COPYING>`__
     - |gitactivity|
   * - `pre-commit <https://github.com/pre-commit/pre-commit>`_ : checks and reports
     - `MIT <https://github.com/pre-commit/pre-commit/blob/main/LICENSE>`__
     - |precommitactivity|
   * - `docker-py <https://github.com/docker/docker-py>`_ : accessing microservices
     - `Apache-2.0 <https://github.com/docker/docker-py/blob/main/LICENSE>`__
     - |dockerpyactivity|
   * - `pybtex <https://bitbucket.org/pybtex-devs/pybtex/src>`_ \*: Saving and loading record data (BiBTeX)
     - `MIT <https://bitbucket.org/pybtex-devs/pybtex/src/master/COPYING>`__
     - |pybtexactivity|
   * - `pandas <https://github.com/pandas-dev/pandas>`_ for record management
     - `BSD 3 <https://github.com/pandas-dev/pandas/blob/main/LICENSE>`__
     - |pandasactivity|

\* dynamically loaded
