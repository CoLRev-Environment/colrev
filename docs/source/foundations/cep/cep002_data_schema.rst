CEP002 - Data schema
===========================

+----------------+------------------------------+
| **Author**     | Carlo Tang, Gerit Wagner     |
+----------------+------------------------------+
| **Status**     | Draft                        |
+----------------+------------------------------+
| **Created**    | 2023-10-02                   |
+----------------+------------------------------+

Table of contents
------------------------------

:any:`abstract`

:any:`entrytypes`

:any:`field sets`

:any:`fields`

:any:`schema mapping`

:any:`defect codes`

:any:`test data`

.. _abstract:

Abstract
------------------------------

This document describes the standard data schema for CoLRev records, including ENTRYTYPEs, and record fields.
Fields can be part of field sets, with corresponding metadata stored in the provenance fields (colrev_data_provenance, colrev_masterdata_provenance), and quality defects tracked by defect codes.
It also outlines principles for mapping schemata from the feed records (retrieved from SearchSources), and provides unified test data.

.. _entrytypes:

ENTRYTYPEs
------------------------------------------------

Each record has an ENTRYTYPE with respective required fields. Required and inconsistent fields are evaluated by the QualityModel (the `missing-field <https://colrev-environment.github.io/colrev/manual/appendix/quality_model.html#missing-field>_ and `inconsistent-with-entrytype <https://colrev-environment.github.io/colrev/manual/appendix/quality_model.html#inconsistent-with-entrytype>`_ checkers).

Note that fields (like title) can have a different meaning depending on the ENTRYTYPEs.

In the following listing are available bibtex ENTRYTYPEs with their respective required fields (data elements) (source: `bibtex.eu <https://bibtex.eu/types/>`__).
Additional information and optional fields can be accessed with the link included in the name of each entry type.

ENTRYTYPE : `article <https://bibtex.eu/types/article/>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  author
-  title
-  journal
-  year
-  volume (if exists)
-  number (if exists)

ENTRYTYPE: `book <https://bibtex.eu/types/book/>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  author
-  year
-  title
-  publisher
-  address

ENTRYTYPE: `conference <https://bibtex.eu/types/conference/>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  author
-  title
-  booktitle
-  year

ENTRYTYPE: `inbook <https://bibtex.eu/types/inbook/>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  author
-  title (i.e., chapter)
-  booktitle
-  publisher
-  year

ENTRYTYPE: `incollection <https://bibtex.eu/types/incollection/>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  author
-  title - TBD: chapter?
-  booktitle
-  publisher
-  year

ENTRYTYPE: `inproceedings <https://bibtex.eu/types/inproceedings/>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  author
-  title
-  booktitle
-  year

ENTRYTYPE: `manual <https://bibtex.eu/types/manual/>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  title
-  year

ENTRYTYPE: `mastersthesis <https://bibtex.eu/types/mastersthesis/>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  author
-  title
-  school
-  year

ENTRYTYPE: `misc <https://bibtex.eu/types/misc/>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  author
-  title
-  year

ENTRYTYPE: `phdthesis <https://bibtex.eu/types/phdthesis/>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  author
-  title
-  school
-  year

ENTRYTYPE: `proceedings <https://bibtex.eu/types/proceedings/>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  title
-  year

ENTRYTYPE: `techreport <https://bibtex.eu/types/techreport/>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  author
-  title
-  institution
-  year
-  number (if exists)

ENTRYTYPE: `unpublished <https://bibtex.eu/types/unpublished/>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  author
-  title
-  institution
-  year

.. _field sets:

Field sets
---------------------------------------------------------------------

The following field sets are distinguished (**work-in-progress**):

- IDENTIFYING_FIELD_KEYS
- colrev_data_provenance/colrev_masterdata_provenance


.. _fields:

Fields
---------------------------------------------------------------------

Standardized field names and explanations.
Value restrictions are implemented in the QualityModel.

Fields should be in unicode (i.e., not contain latex or html characters or tags).

Fields not listed in the ENTRYTYPEs section are optional.

-  author (Last-name, FirstName - separated by " and "; institutional authors are escaped with double braces; particles are escaped with last names using braces)
-  title
-  year
-  journal
-  booktitle
-  chapter
-  publisher
-  volume
-  number
-  pages
-  editor (format: see author)
-  language (ISO 639-1 standard language codes)
-  abstract
-  keywords (separated by ",")
-  url
-  fulltext
-  note: containing custom notes entered by users (note fields from SearchSources do not replace this field)
-  cited_by: current number of citations (volatile)

**work-in-progress**

- Identifiers
- title fields in different languages (e.g., title_deu)

.. _schema mapping:

Schema Mapping
---------------------------------------------------------------------

Upon load, the SearchSource fields are mapped to the standardized fields.
This is necessary to handle naming conflicts (e.g., field name "authors" in one SearchSource and "author" in another), and type/domain conflicts (e.g., "citations" containing an integer in one SearchSoruce and a list of citing papers in another).
Fields which cannot be mapped receive a SearchSource-specific prefix (e.g., "colrev.dblp.dblp_key").

The schema mapping should be completed in the search methods. Search feeds should contain raw (non-prefixed) fields.

.. _defect codes:

Defect codes
----------------------------

Defect codes are stored in the field provenance. They can be ignored as false positives based on the `IGNORE:` prefix.

The standardized defect codes are in the `QualityModel <https://colrev-environment.github.io/colrev/manual/appendix/quality_model.html>`_ and `PDFQualityModel <https://colrev-environment.github.io/colrev/manual/appendix/pdf_quality_model.html>`_.

.. _test data:

Test data values
------------------------------
Five different entry examples for dummy values used in the tests.

.. _entrytype-article-1:

.. code-block::

   @article{ID274107,
      author                        = {Marilena, Ferdinand and Ethelinda Aignéis},
      title                         = {Article title},
      journal                       = {Journal name},
      year                          = {2020},
      volume                        = {23},
      number                        = {78},
   }

   @book{ID438965,
      author                        = {Romilius, Milivoj and Alphaeus, Cheyanne},
      year                          = {2020},
      title                         = {Book title},
      publisher                     = {Publisher name},
      address                       = {Publisher address},
   }


   @conference{ID461901,
      author                        = {Derry, Wassa and Wemba, Sandip},
      title                         = {Conference title},
      booktitle                     = {Conference book title},
      year                          = {2020},
   }

   @inproceedings{ID110380,
      author                        = {Raanan, Cathrine and Philomena, Miigwan},
      title                         = {Inproceedings title},
      booktitle                     = {Inproceedings book title},
      year                          = {2020},
   }

   @phdthesis{ID833501,
      author                        = {Davie, Ulyana},
      title                         = {PhD thesis title},
      school                        = {PhD school name},
      year                          = {2020},
   }


Links informing the standard
------------------------------------------------------------

-  `author formatting guidelines <https://tp.libguides.com/c.php?g=920621&p=6640859>`__
-  first source `bibtex.com <https://www.bibtex.com/e/entry-types/>`__
   required and optional fields are not specified
-  better `bibtex.eu <https://bibtex.eu/types/>`__
-  but not consistent across different bibtex manager, e.g. “field” or
   “manual” in following tool:
   Bib-it (SourceForge project documentation)
-  listing of field variables and in which entry they are required
   https://www.bibtex.com/format/fields/
-  https://www.ncbi.nlm.nih.gov/books/NBK3827/, examples of
   different fields and descriptions
-  `bibTeX Definition in Web Ontology Language (OWL) Version
   0.2 <https://zeitkunst.org/bibtex/0.2/>`__
-  `it is master"s"thesis, not masterthesis <https://tex.stackexchange.com/questions/415204/masterthesis-doesnt-work-for-bibtex-citation>`__
