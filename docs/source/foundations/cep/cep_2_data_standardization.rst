CEP 2: Data standardization
====================================

+----------------+------------------------------+
| **Author**     | Carlo Tang, Gerit Wagner     |
+----------------+------------------------------+
| **Status**     | Draft                        |
+----------------+------------------------------+
| **Created**    | 2023-10-02                   |
+----------------+------------------------------+
| **Discussion** | TODO : link-to-issue         |
+----------------+------------------------------+

CEP000 - CEP Purpose and Guidelines
===================================

What is a CEP?
--------------

CEP stands for CoLRev Enhancement Proposal. A CEP is a design document
providing information to the CoLRev community, or describing a new
feature for CoLRev or its processes or environment. The CEP should
provide a concise technical specification of the feature and a rationale
for the feature. (inspired by PEP, Python Enhancment Propsals
https://peps.python.org/pep-0001/)

CEP001 - Colrev data schema
===========================

ENTRYTYPEs and their respective required fields 
------------------------------------------------

.. verlinken auf missing und inconsistent with entry type

.. raw:: html

   <!-- 
   - fields (like title) can have a different meaning depending on the entrytype?!
   -->

In the following listing are 14 available bibtex entry types with their
respective required fields (data elements) (source:
`bibtex.eu <https://bibtex.eu/types/>`__). Additional information and
optional fields can be accessed with the link included in the name of
each entry type.

ENTRYTYPE : `article <https://bibtex.eu/types/article/>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  author
-  title
-  journal
-  volume (if exists)
-  number (if exists)

ENTRYTYPE: `book <https://bibtex.eu/types/book/>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  author
-  year
-  title
-  publisher
-  address

ENTRYTYPE: `booklet <https://bibtex.eu/types/booklet/>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  title
-  author
-  howpublished
-  address
-  years

ENTRYTYPE: `conference <https://bibtex.eu/types/conference/>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  author
-  title
-  booktitle
-  year

ENTRYTYPE: `inbook <https://bibtex.eu/types/inbook/>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  author
-  title - TBD: chapter?
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

`it is master"s"thesis, not masterthesis <https://tex.stackexchange.com/questions/415204/masterthesis-doesnt-work-for-bibtex-citation>`__

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

Standardized field names, explanations, and field value restrictions 
---------------------------------------------------------------------

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

-  title: string,
-  author: TODO: Format: “LastName, FirstName and LastName, FirstName”,
   how to handle “vom Brocke”?
-  year: integer, :raw-latex:`\d{4}`
-  journal: string,
-  booktitle: string
-  chapter: integer
-  publisher: string
-  volume: integer
-  number: integer
-  pages: integer, I II III V X
-  editor: string

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

Schema Mapping: Colrev data schema (main records) - SearchSources
=================================================================

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
   scopus
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


“unified colrev fields” (like title, author, …) do not have a prefix (in
main records.bib) Default: all other fields are added to records.bib
with a “namespace prefix” (e.g., colrev.synergy.method)

Example: mapping notes with “Cited by” content to cited_by fields
(scopus)

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


Standardized test data
======================

Used for tests fakewerte standardisieren fakedaten ueber alle search
sources hinweg einen standard journal article man muss sich nicht mehr
in jeden Testdatensatz eindenken

.. _entrytype-article-1:

ENTRYTYPE: article
------------------

@article{ID1, author = {Smith, Tom and Walter, Tim}, title = {An
empirical study}, journal = {Nature}, }

CoLRev Data Element (Field) Descriptions
========================================

This document describes the major elements (or fields) found on the
CoLRev display format for CoLRev records. Some elements (e.g., Comment
In) are not mandatory and will not appear in every record. Other
elements (e.g., Author, MeSH term, Registry Number) may appear multiple
times in one record. Some of the elements on this list are searchable
fields in PubMed. For searching instructions, see the Search Field Tags
section of PubMed Help. This document is supplementary information, to
be used in conjuction with PubMed Help.

CoLRev XML data element descriptions are also available (There are
additional fields in the XML data)???

Links informing the standard
============================

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

TODO
====

-  `bibTeX Definition in Web Ontology Language (OWL) Version
   0.2 <https://zeitkunst.org/bibtex/0.2/>`__
