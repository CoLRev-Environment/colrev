## Summary

OCRmyPDF adds an OCR text layer to scanned PDF files, allowing them to be searched. Its main features are:

- Generates a searchable PDF/A file from a regular PDF
- Places OCR text accurately below the image to ease copy / paste
- Keeps the exact resolution of the original embedded images
- When possible, inserts OCR information as a "lossless" operation without disrupting any other content
- Optimizes PDF images, often producing files smaller than the input file
- If requested, deskews and/or cleans the image before performing OCR
- Validates input and output files
- Distributes work across all available CPU cores
- Uses Tesseract OCR engine to recognize more than 100 languages
- Keeps your private data private.
- Scales properly to handle files with thousands of pages.
- Battle-tested on millions of PDFs.

Running OCRmyPDF requires Docker.

## pdf-prep

OCRmyPDF is contained in the default setup. To add it, run

```
colrev pdf-prep -a colrev.ocrmypddf
```

## Links


![ocrmypdfactivity](https://img.shields.io/github/commit-activity/y/ocrmypdf/OCRmyPDF?color=green&style=plastic)

[OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF): optical-character recognition (License: [MPL-2.0](https://github.com/ocrmypdf/OCRmyPDF/blob/main/LICENSE))

![tesseractactivity](https://img.shields.io/github/commit-activity/y/tesseract-ocr/tesseract?color=green&style=plastic)

[Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (License: [Apache-2.0](https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE))
