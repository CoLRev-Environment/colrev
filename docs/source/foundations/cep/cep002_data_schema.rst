CEP002 - Data schema
===========================

+----------------+------------------------------+
| **Author**     | Carlo Tang, Gerit Wagner     |
+----------------+------------------------------+
| **Status**     | Draft                        |
+----------------+------------------------------+
| **Created**    | 2023-10-02                   |
+----------------+------------------------------+
| **Discussion** | TODO : link-to-issue         |
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

Each record has an ENTRYTYPE with respective required fields. Required and inconsistent fields are evaluated by the QualityModel (the `missing-field <https://colrev.readthedocs.io/en/latest/resources/quality_model.html#missing-field>_ and `inconsistent-with-entrytype <https://colrev.readthedocs.io/en/latest/resources/quality_model.html#inconsistent-with-entrytype>`_ checkers).

.. raw:: html

   <!--
   - fields (like title) can have a different meaning depending on the entrytype?!
   -->

In the following listing are 14 available bibtex entry types with their respective required fields (data elements) (source: `bibtex.eu <https://bibtex.eu/types/>`__).
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

The following field sets are distinguished:

- IDENTIFYING_FIELD_KEYS
- colrev_data_provenance/colrev_masterdata_provenance

.. _fields:

Fields
---------------------------------------------------------------------

Standardized field names, explanations, and field value restrictions

.. <!--

   standardisierte Feldbezeichnungen, Erklärungen, Wertebeschränkung

   -->

   <!--
   TBD:
   - latex/html characters?

   NOTE from record.py
       identifying_field_keys = [
           "title",
           "author",
           "year",
           "journal",
           "booktitle",
           "chapter",
           "publisher",
           "volume",
           "number",
           "pages",
           "editor",
       ]
   -->


.. Identifying metadata (record.py):
.. TODO : create table

Mandatory fields across all entrytypes:

-  title
-  author
-  year

Mandatory fields depending on entrytype (examples):

-  journal
-  booktitle
-  chapter
-  publisher
-  volume
-  number
-  pages
-  editor

Non-Mandatory fields:

- ....


.. verweisen auf entsprechende quality checks, fuer autor, namen sind schon
checks implementiert fuer jahr ” ” fuer seitenzahl ” ”

   <!-- what about special characters like [!?,;/-_...] in certain fields? -->

   <!--PART 2.2 extracted into extra file, regex to be implemented into code-->


Identifiers:…

   <!--PART 2.3 -->

Complementary/optional fields:

-  language: ISO 639-1 standard language codes
-  abstract: anything goes
-  keywords: integers, strings, “,”
-  url:
-  eprint:
-  note: anything goes, but some sources use them for specific
   information e.g. scopus.bib “cited by”
-  cited_by: current number of citations (volatile)

.. _schema mapping:

Schema Mapping
---------------------------------------------------------------------

Colrev data schema (main records) - SearchSources (raw search results/feed)

.. Feldbezeichnung ohne prefix erhalten, autor, titel, sind standardisiert,
.. dlbp key ist nicht standardisiert, wird umgewandelt @Gerit
..    <!--PART 3
   SearchSources durchschauen aus colrev/ops/built_in/searchsorces -> .py Dateien, erste Übersicht/Aufstellung
   ebsco_host
   eric
   europe_pmc
   google_scholar
   ieee
   ieee_api
   jstor
   local_index
   open_alex
   open_citations_forward_search
   open_library
   pdf_backward_search
   pdfs_dir
   psycinfo
   pubmed
   scopus@book{
   springer_link
   synergy_datasets
   taylor_and_francis
   trid
   unknown_source
   utils
   video_dir
   web_of_science
   website
   wiley
   __init__
   abi_inform_proquest
   acm_digital_library
   aisel
   colrev_project
   crossref
   dblp
   doi_org
   -->


“unified colrev fields” (like title, author, …) do not have a prefix (in main records.bib)
Default: all other fields are added to records.bib with a “namespace prefix” (e.g., colrev.synergy.method)

Example: mapping notes with “Cited by” content to cited_by fields (scopus)

Give an example (document the specific cases in the SearchSources)

Following fields will be transformed and standardized:

- records.bib  <-> search-source
- title        <-> colrev.crossref.title
- author       <-> colrev.crossref.author
- year         <-> colrev.crossref.year
- journal      <-> colrev.crossref.journal
- journal      <-> colrev.psycinfo.T2 IF colrev.pycinfo.TY == "JOUR"
- booktitle    <-> colrev.crossref.booktitle
- chapter      <-> colrev.crossref.chapter
- publisher    <-> colrev.crossref.publisher
- volume       <-> colrev.crossref.volume
- number       <-> colrev.crossref.number
- pages        <-> colrev.crossref.page
.. variation is intentional: "page" gets transformed to "pages"
- editor       <-> colrev.crossref.editor
- colrev.synergy.method <-> colrev.synergy.method

Keys cannot be transformed and standardized, they remain immutable once created

- colrev.dblp.key              <-> colrev.dblp.key
- colrev.openalex.key          <-> colrev.openalex.key
.. each search source will get its custom namespace, see excample below

.. **TODO : anticipate upgrade of existing projects** mittlerweile
umgesetzt, name space pull request

namespace example: @article{ID1, title = {Title1}, colrev.dblp.key =
{de123414}, }

..    <!--
   colrev/colrev/ops/built_in/search_sources/*.py
   -->

.. _defect codes:

Defect codes
----------------------------

Defect codes are stored in the field provenance. They can be ignored as false positives based on the `IGNORE:` prefix.

The standardized defect codes are in the `QualityModel <https://colrev.readthedocs.io/en/latest/resources/quality_model.html>_ and `PDFQualityModel <https://colrev.readthedocs.io/en/latest/resources/pdf_quality_model.html>`_

.. _test data:

Test data values
------------------------------
Five different entry examples for dummy values used in the tests.

.. _entrytype-article-1:

ENTRYTYPE: article
------------------

@article{ID274107,
   author                        = {Marilena, Ferdinand and Ethelinda Aignéis},
   title                         = {Article title},
   journal                       = {Journal name},
   year                          = {2020},
   volume                        = {23},
   number                        = {78},
}


ENTRYTYPE: book
---------------

@book{ID438965,
   author                        = {Romilius, Milivoj and Alphaeus, Cheyanne},
   year                          = {2020},
   title                         = {Book title},
   publisher                     = {Publisher name},
   address                       = {Publisher address},
}


ENTRYTYPE: conference
---------------------

@conference{ID461901,
   author                        = {Derry, Wassa and Wemba, Sandip},
   title                         = {Conference title},
   booktitle                     = {Conference book title},
   year                          = {2020},
}


ENTRYTYPE: inproceedings
------------------------

@inproceedings{ID110380,
   author                        = {Raanan, Cathrine and Philomena, Miigwan},
   title                         = {Inproceedings title},
   booktitle                     = {Inproceedings book title},
   year                          = {2020},
}


ENTRYTYPE: phdthesis
--------------------

@phdthesis{ID833501,
   author                        = {Davie, Ulyana},
   title                         = {PhD thesis title},
   school                        = {PhD school name},
   year                          = {2020},
}


Links informing the standard
------------------------------------------------------------

-  first source `bibtex.com <https://www.bibtex.com/e/entry-types/>`__
   required and optional fields are not specified
-  better `bibtex.eu <https://bibtex.eu/types/>`__
-  but not consistent across different bibtex manager, e.g. “field” or
   “manual” in following tool:
   `Bib-it <https://bib-it.sourceforge.net/help/fieldsAndEntryTypes.php>`__
-  listing of field variables and in which entry they are required
   https://www.bibtex.com/format/fields/
-  https://www.nlm.nih.gov/bsd/mms/medlineelements.html, examples of
   different fields and descriptions
-  `bibTeX Definition in Web Ontology Language (OWL) Version
   0.2 <https://zeitkunst.org/bibtex/0.2/>`__
-  `it is master"s"thesis, not masterthesis <https://tex.stackexchange.com/questions/415204/masterthesis-doesnt-work-for-bibtex-citation>`__
