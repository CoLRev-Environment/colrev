.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 14pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 14pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 14pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
.. |GIT_REPO| image:: /_static/svg/iconmonstr-code-fork-1.svg
   :width: 15
   :alt: Git repository
.. |LICENSE| image:: /_static/svg/iconmonstr-copyright-2.svg
   :width: 15
   :alt: Licencse
.. |MAINTAINER| image:: /_static/svg/iconmonstr-user-29.svg
   :width: 20
   :alt: Maintainer
.. |DOCUMENTATION| image:: /_static/svg/iconmonstr-book-17.svg
   :width: 15
   :alt: Documentation
colrev.ocrmypdf
===============

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/ocrmypdf>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - pdf_prep
     - |MATURING|
     - .. code-block::


         colrev pdf-prep --add colrev.ocrmypdf


Summary
-------

OCRmyPDF adds an OCR text layer to scanned PDF files, allowing them to be searched. Its main features are:


* Generates a searchable PDF/A file from a regular PDF
* Places OCR text accurately below the image to ease copy / paste
* Keeps the exact resolution of the original embedded images
* When possible, inserts OCR information as a "lossless" operation without disrupting any other content
* Optimizes PDF images, often producing files smaller than the input file
* If requested, deskews and/or cleans the image before performing OCR
* Validates input and output files
* Distributes work across all available CPU cores
* Uses Tesseract OCR engine to recognize more than 100 languages
* Keeps your private data private.
* Scales properly to handle files with thousands of pages.
* Battle-tested on millions of PDFs.

Running OCRmyPDF requires Docker.

pdf-prep
--------

OCRmyPDF is contained in the default setup. To add it, run

.. code-block::

   colrev pdf-prep -a colrev.ocrmypddf

Links
-----


.. image:: https://img.shields.io/github/commit-activity/y/ocrmypdf/OCRmyPDF?color=green&style=plastic
   :target: https://img.shields.io/github/commit-activity/y/ocrmypdf/OCRmyPDF?color=green&style=plastic
   :alt: ocrmypdfactivity


`OCRmyPDF <https://github.com/ocrmypdf/OCRmyPDF>`_\ : optical-character recognition (License: `MPL-2.0 <https://github.com/ocrmypdf/OCRmyPDF/blob/main/LICENSE>`_\ )


.. image:: https://img.shields.io/github/commit-activity/y/tesseract-ocr/tesseract?color=green&style=plastic
   :target: https://img.shields.io/github/commit-activity/y/tesseract-ocr/tesseract?color=green&style=plastic
   :alt: tesseractactivity


`Tesseract OCR <https://github.com/tesseract-ocr/tesseract>`_ (License: `Apache-2.0 <https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE>`_\ )
