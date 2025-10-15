Metadata quality model
==================================

The quality model specifies the necessary checks when a records should transition to ``md_prepared``. The functionality fixing errors is organized in the `prep` package endpoints.

Similar to linters such as pylint, it should be possible to disable selected checks. Failed checks are made transparent by adding the corresponding codes (e.g., `mostly-upper`) to the `colrev_masterdata_provenance` (`notes` field).

Table of contents
------------------------------

:any:`format`

- :any:`mostly-all-caps`
- :any:`html-tags`
- :any:`name-format-titles`
- :any:`name-format-separators`
- :any:`name-particles`
- :any:`year-format`
- :any:`doi-not-matching-pattern`
- :any:`isbn-not-matching-pattern`
- :any:`pubmedid_not_matching_pattern`
- :any:`language-format-error`
- :any:`language-unknown`

:any:`Completeness`

- :any:`missing-field`
- :any:`incomplete-field`
- :any:`container-title-abbreviated`
- :any:`name-abbreviated`

:any:`within-record consistency`

- :any:`inconsistent-with-entrytype`
- :any:`thesis-with-multiple-authors`
- :any:`page-range`
- :any:`identical-values-between-title-and-container`
- :any:`inconsistent-content`

:any:`origin consistency`

- :any:`inconsistent-with-doi-metadata`
- :any:`inconsistent-with-url-metadata`
- :any:`record-not-in-toc`

:any:`common defects`

- :any:`erroneous-symbol-in-field`
- :any:`erroneous-term-in-field`
- :any:`erroneous-title-field`

..
   .. toctree::
      :caption: Format
      :maxdepth: 3

      quality_model/mostly_all_caps
      quality_model/html_tags
      quality_model/name_format_titles
      quality_model/name_format_separators
      quality_model/name_particles
      quality_model/year_format
      quality_model/doi_not_matching_pattern
      quality_model/isbn_not_matching_pattern
      quality_model/language_format_error
      quality_model/language_unknown

   .. toctree::
      :caption: Completeness
      :maxdepth: 3

      quality_model/missing_field
      quality_model/incomplete_field
      quality_model/container_title_abbreviated
      quality_model/name_abbreviated

   .. toctree::
      :caption: Within-record consistency
      :maxdepth: 3

      quality_model/inconsistent_with_entrytype
      quality_model/thesis_with_multiple_authors
      quality_model/page_range
      quality_model/identical_values_between_title_and_container
      quality_model/inconsistent_content

   .. toctree::
      :caption: Origin consistency
      :maxdepth: 3

      quality_model/inconsistent_with_doi_metadata
      quality_model/inconsistent_with_url_metadata
      quality_model/record_not_in_toc


   .. toctree::
      :caption: Common defects
      :maxdepth: 3

      quality_model/erroneous_symbol_in_field
      quality_model/erroneous_term_in_field
      quality_model/erroneous_title_field

.. _format:

Format
-----------------

.. _mostly-all-caps:

mostly-all-caps
^^^^^^^^^^^^^^^^^^^^^

Fields should not contain mostly upper case letters.

**Problematic value**

.. code-block:: python

    title = {AN EMPIRICAL STUDY OF PLATFORM EXIT}

**Correct value**

.. code-block:: python

    title = {An empirical study of platform exit}

+-----------------+
| Fields checked  |
+=================+
| author          |
+-----------------+
| title           |
+-----------------+
| editor          |
+-----------------+
| journal         |
+-----------------+
| booktitle       |
+-----------------+

.. raw:: html

   <hr>

.. _html-tags:

html-tags
^^^^^^^^^^^^^^^^^^^^^^

Fields should not contain HTML tags.

**Problematic value**

.. code-block:: python

    title = {A commentary on <i>microsourcing</i>}

**Correct value**

.. code-block:: python

    title = {A commentary on microsourcing}

Note: abstracts are not checked and may contain html tags.

+-----------------+
| Fields checked  |
+=================+
| title           |
+-----------------+
| journal         |
+-----------------+
| booktitle       |
+-----------------+
| author          |
+-----------------+
| publisher       |
+-----------------+
| editor          |
+-----------------+

.. raw:: html

   <hr>

.. _name-format-titles:

name-format-titles
^^^^^^^^^^^^^^^^^^^^^^

Names should not contain titles, such as "MD", "Dr", "PhD", "Prof", or "Dipl Ing".

**Problematic value**

.. code-block:: python

    @phdthesis{Smith2022,
        ...
        author = {Prof. Smith, M. PhD.},
        ...
    }

**Correct value**

.. code-block:: python

    @phdthesis{Smith2022,
        ...
        author = {Smith, M.},
        ...
    }

+-----------------+
| Fields checked  |
+=================+
| author          |
+-----------------+
| editor          |
+-----------------+

.. raw:: html

   <hr>

.. _name-format-separators:

name-format-separators
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Names should be correctly separated.

**Problematic value**

.. code-block:: python

    author = {Smith, W.; Thompson, U.}

**Correct value**

.. code-block:: python

    author = {Smith, W. and Thompson, U.}

* Author names are separated by " and ".
* Must contain at least two capital letters, and all should be letters
* Should be separated by ``,``
* Must be longer than 5

+-----------------+
| Fields checked  |
+=================+
| author          |
+-----------------+
| editor          |
+-----------------+

.. raw:: html

   <hr>

.. _name-particles:

name-particles
^^^^^^^^^^^^^^^^^^^^^^

Name particles should be formatted correctly and protected.

**Problematic value**

.. code-block:: python

    author = {Brocke, Jan vom}

**Correct value**

.. code-block:: python

    author = {{vom Brocke}, Jan}

+-----------------+
| Fields checked  |
+=================+
| author          |
+-----------------+
| editor          |
+-----------------+

Links

- `CSL specification for particles <https://docs.citationstyles.org/en/stable/specification.html?highlight=von#names>`_
- `Name particles <https://en.wikipedia.org/wiki/Nobiliary_particle>`_


.. raw:: html

   <hr>

.. _year-format:

year-format
^^^^^^^^^^^^^^^^^^^^^^

``year`` should be full year.

**Problematic value**

.. code-block:: python

    year = {2023-01-03}

**Correct value**

.. code-block:: python

    year = {2023}

+-----------------+
| Fields checked  |
+=================+
| year            |
+-----------------+


.. raw:: html

   <hr>

.. _doi-not-matching-pattern:

doi-not-matching-pattern
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The doi field should follow a `predefined pattern <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/record/qm/checkers/doi_not_matching_pattern.py>`_.
It does not start with `http...` and is in upper case.

**Problematic value**

.. code-block:: python

    doi = {https://doi.org/10.1016/j.jsis. 2021.101694}

**Correct value**

.. code-block:: python

    doi = {10.1016/j.jsis.2021.101694}

+-----------------+
| Fields checked  |
+=================+
| doi             |
+-----------------+

Links

- `Crossref: DOIs and maching regular expressions <https://www.crossref.org/blog/dois-and-matching-regular-expressions/>`_.


.. raw:: html

   <hr>

.. _isbn-not-matching-pattern:

isbn-not-matching-pattern
^^^^^^^^^^^^^^^^^^^^^^^^^^^

ISBN should be valid.

**Problematic value**

.. code-block:: python

    isbn = {978316}

**Correct value**

.. code-block:: python

    isbn = {978-3-16-148410-0}

TODO : ISBN-10/ISBN13, how multiple ISBNs are stored

+-----------------+
| Fields checked  |
+=================+
| ibn             |
+-----------------+

.. raw:: html

   <hr>

.. _pubmedid_not_matching_pattern:

pubmedid_not_matching_pattern
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Pubmed IDs should be formatted correctly (7 or 8 digits).

**Problematic value**

.. code-block:: python

    colrev.pubmed.pubmedid = {PMID: 1498274774},

**Correct value**

.. code-block:: python

    colrev.pubmed.pubmedid = {33044175},

+-------------------------+
| Fields checked          |
+=========================+
| colrev.pubmed.pubmedid  |
+-------------------------+

- [PMID specification](https://www.ncbi.nlm.nih.gov/books/NBK3827/#pubmedhelp.MEDLINETagDescriptions)

.. raw:: html

   <hr>

.. _language-format-error:

language-format-error
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ISO 639-3 language code should be valid.

**Problematic value**

.. code-block:: python

    language = {en}

**Correct value**

.. code-block:: python

    language = {eng}

+-----------------+
| Fields checked  |
+=================+
| language        |
+-----------------+

See language_service.


.. raw:: html

   <hr>

.. _language-unknown:

language-unknown
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Record should contain a ISO 639-3 language code.

**Problematic value**

.. code-block:: python

    language = {American English}

**Correct value**

.. code-block:: python

    language = {eng}

+-----------------+
| Fields checked  |
+=================+
| language        |
+-----------------+

See language_service.


.. _completeness:

Completeness
-----------------

.. _missing-field:

missing-field
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Records should contain all required fields for the respective ENTRYTYPE.

**Problematic value**

.. code-block:: python

    @article{Webster2002,
        title = {Analyzing the past to prepare for the future: Writing a literature review},
        author = {Webster, Jane and Watson, Richard T},
        journal = {MIS quarterly},
    }

**Correct value**

.. code-block:: python

    @article{Webster2002,
        title = {Analyzing the past to prepare for the future: Writing a literature review},
        author = {Webster, Jane and Watson, Richard T},
        journal = {MIS quarterly},
        volume = {26},
        number = {2},
        pages = {xiii-xxiii},
    }

See: inconsistent-field

+----------------+----------------------------------------------+
| ENTRYTYPE      | Required fields                              |
+================+==============================================+
| article        | author, title, journal, year, volume, number |
+----------------+----------------------------------------------+
| inproceedings  | author, title, booktitle, year               |
+----------------+----------------------------------------------+
| incollection   | author, title, booktitle, publisher, year    |
+----------------+----------------------------------------------+
| inbook         | author, title, chapter, publisher, year      |
+----------------+----------------------------------------------+
| proceedings    | booktitle, editor, year                      |
+----------------+----------------------------------------------+
| conference     | booktitle, editor, year                      |
+----------------+----------------------------------------------+
| book           | author, title, publisher, year               |
+----------------+----------------------------------------------+
| phdthesis      | author, title, school, year                  |
+----------------+----------------------------------------------+
| bachelorthesis | author, title, school, year                  |
+----------------+----------------------------------------------+
| thesis         | author, title, school, year                  |
+----------------+----------------------------------------------+
| masterthesis   | author, title, school, year                  |
+----------------+----------------------------------------------+
| techreport     | author, title, institution, year             |
+----------------+----------------------------------------------+
| unpublished    | title, author, year                          |
+----------------+----------------------------------------------+
| misc           | author, title, year                          |
+----------------+----------------------------------------------+
| software       | author, title, url                           |
+----------------+----------------------------------------------+
| online         | author, title, url                           |
+----------------+----------------------------------------------+
| other          | author, title, year                          |
+----------------+----------------------------------------------+

.. raw:: html

   <hr>

.. _incomplete-field:

incomplete-field
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Fields should be complete. Fields considered incomplete (truncated) if they have ``...`` at the end.

**Problematic value**

.. code-block:: python

    title = {A commentary on ...}

**Correct value**

.. code-block:: python

    title = {A commentary on microsourcing}

+-----------------+
| Fields checked  |
+=================+
| title           |
+-----------------+
| journal         |
+-----------------+
| booktitle       |
+-----------------+
| author          |
+-----------------+
| abstract        |
+-----------------+


.. raw:: html

   <hr>

.. _container-title-abbreviated:

container-title-abbreviated
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Containers should not be abbreviated.

**Problematic value**

.. code-block:: python

    journal = {MISQ}

**Correct value**

.. code-block:: python

    year = {MIS Quarterly}

Container are considers abbreviated if it is less than 6 characters and all upper case.

+-----------------+
| Fields checked  |
+=================+
| journal         |
+-----------------+
| booktitle       |
+-----------------+

.. raw:: html

   <hr>

.. _name-abbreviated:

name-abbreviated
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Names should not be abbreviated

**Problematic value**

.. code-block:: python

    author = {Smith, W. et. al.}

**Correct value**

.. code-block:: python

    author = {Smith, W. and Thompson, U.}

+-----------------+
| Fields checked  |
+=================+
| author          |
+-----------------+
| editor          |
+-----------------+

.. _within-record consistency:

Within-record consistency
-------------------------------

.. _inconsistent-with-entrytype:

inconsistent-with-entrytype
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Some fields are inconsistent with the respective ENTRYTYPE.

**Problematic value**

.. code-block:: python

    @article{SmithParkerWeber2003,
        ...
        booktitle = {First Workshop on ...},
        ...
    }

**Correct value**

.. code-block:: python

    @inproceedings{SmithParkerWeber2003,
        ...
        booktitle = {First Workshop on ...},
        ...
    }

+--------------+-----------------------------------------+
|ENTRYTYPE     | inconsistent fields                     |
+==============+=========================================+
|article       | booktitle                               |
+--------------+-----------------------------------------+
|inproceedings | issue,number,journal                    |
+--------------+-----------------------------------------+
|incollection  |                                         |
+--------------+-----------------------------------------+
|inbook        | journal                                 |
+--------------+-----------------------------------------+
|book          | volume,issue,number,journal             |
+--------------+-----------------------------------------+
|phdthesis     | volume,issue,number,journal,booktitle   |
+--------------+-----------------------------------------+
|masterthesis  | volume,issue,number,journal,booktitle   |
+--------------+-----------------------------------------+
|techreport    | volume,issue,number,journal,booktitle   |
+--------------+-----------------------------------------+
|unpublished   | volume,issue,number,journal,booktitle   |
+--------------+-----------------------------------------+
|online        | journal,booktitle                       |
+--------------+-----------------------------------------+
|misc          | journal,booktitle                       |
+--------------+-----------------------------------------+

.. raw:: html

   <hr>

.. _thesis-with-multiple-authors:

thesis-with-multiple-authors
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Thesis ``ENTRYTYPE`` should not contain multiple authors.

**Problematic value**

.. code-block:: python

    @phdthesis{SmithParkerWeber2003,
        ...
        author = {Smith, M. and Parker, S. and Weber, R.},
        ...
    }

**Correct value**

.. code-block:: python

    @phdthesis{Smith2003,
        ...
        author = {Smith, M.},
        ...
    }

+----------------------------------------------------------+
| Fields checked                                           |
+==========================================================+
| author [if ENTRYTPYE in thesis|phdthesis|mastertsthesis] |
+----------------------------------------------------------+

.. raw:: html

   <hr>

.. _page-range:

page-range
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Page range should be valid, i.e., the first page should be lower than the last page if the pages are numerical.

**Problematic value**

.. code-block:: python

    pages = {11--9}

**Correct value**

.. code-block:: python

    pages = {11--19}


+-----------------+
| Fields checked  |
+=================+
| pages           |
+-----------------+

.. raw:: html

   <hr>

.. _identical-values-between-title-and-container:

identical-values-between-title-and-container
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Title and containers (booktitle, journal) should not contain identical values.

**Problematic value**

.. code-block:: python

    title = {MIS Quarterly},
    journal = {MIS Quarterly},

**Correct value**

.. code-block:: python

    title = {A commentary on microsourcing}
    journal = {MIS Quarterly},


.. raw:: html

   <hr>

.. _inconsistent-content:

inconsistent-content
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Fields should not contain inconsistent values,

  * Journal should not be from conference or workshop,
  * booktitle should not belong to journal

**Problematic value**

.. code-block:: python

    journal = {Proceedings of the 32nd Conference on ...}

**Correct value**

.. code-block:: python

    booktitle = {Proceedings of the 32nd Conference on ...}

+-----------------+---------------------+
| Fields checked  | Erroneous values    |
+=================+=====================+
| journal         | conference, workshop|
+-----------------+---------------------+
| booktitle       |journal              |
+-----------------+---------------------+

.. _origin consistency:

Origin consistency
-------------------------------

.. _inconsistent-with-doi-metadata:

inconsistent-with-doi-metadata
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Record content needs to be consistent with doi metadata.

**Problematic value**

.. code-block:: python

    @article{wagner2021exploring,
        title = {Analyzing the past to prepare for the future: Writing a literature review},
        author = {Webster, Jane and Watson, Richard T},
        journal = {MIS quarterly},
        volume = {30},
        number = {4},
        pages = {101694},
        year = {2021},
        doi = {10.1016/j.jsis.2021.101694}
    }

    # metadat at crossref:
    # https://api.crossref.org/works/10.1016/j.jsis.2021.101694

    @article{wagner2021exploring,
        title = {Exploring the boundaries and processes of digital platforms for knowledge work: A review of information systems research},
        author = {Wagner, Gerit and Prester, Julian and Paré, Guy},
        journal = {The Journal of Strategic Information Systems},
        volume = {30},
        number = {4},
        pages = {101694},
        year = {2021},
        doi = {10.1016/j.jsis.2021.101694}
    }

**Correct value**

.. code-block:: python

    @article{wagner2021exploring,
        title = {Exploring the boundaries and processes of digital platforms for knowledge work: A review of information systems research},
        author = {Wagner, Gerit and Prester, Julian and Paré, Guy},
        journal = {The Journal of Strategic Information Systems},
        volume = {30},
        number = {4},
        pages = {101694},
        year = {2021},
        doi = {10.1016/j.jsis.2021.101694}
    }

    # metadat at crossref:
    # https://api.crossref.org/works/10.1016/j.jsis.2021.101694

    @article{wagner2021exploring,
        title = {Exploring the boundaries and processes of digital platforms for knowledge work: A review of information systems research},
        author = {Wagner, Gerit and Prester, Julian and Paré, Guy},
        journal = {The Journal of Strategic Information Systems},
        volume = {30},
        number = {4},
        pages = {101694},
        year = {2021},
        doi = {10.1016/j.jsis.2021.101694}
    }

+-----------------+
| Fields checked  |
+=================+
| title           |
+-----------------+
| journal         |
+-----------------+
| author          |
+-----------------+

.. raw:: html

   <hr>

.. _inconsistent-with-url-metadata:

inconsistent-with-url-metadata
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Checks url metadata should be consistent with Zotero generated metadata about the url.

**Problematic value**

.. code-block:: python

    @article{wagner2021exploring,
        title = {Analyzing the past to prepare for the future: Writing a literature review},
        author = {Webster, Jane and Watson, Richard T},
        journal = {MIS quarterly},
        volume = {30},
        number = {4},
        pages = {101694},
        year = {2021},
        url = {https://www.sciencedirect.com/science/article/abs/pii/S096386872100041X}
    }

    # metadat from the url:

    @article{wagner2021exploring,
        title = {Exploring the boundaries and processes of digital platforms for knowledge work: A review of information systems research},
        author = {Wagner, Gerit and Prester, Julian and Paré, Guy},
        journal = {The Journal of Strategic Information Systems},
        volume = {30},
        number = {4},
        pages = {101694},
        year = {2021},
        url = {https://www.sciencedirect.com/science/article/abs/pii/S096386872100041X}
    }

**Correct value**

.. code-block:: python

    @article{wagner2021exploring,
        title = {Exploring the boundaries and processes of digital platforms for knowledge work: A review of information systems research},
        author = {Wagner, Gerit and Prester, Julian and Paré, Guy},
        journal = {The Journal of Strategic Information Systems},
        volume = {30},
        number = {4},
        pages = {101694},
        year = {2021},
        url = {https://www.sciencedirect.com/science/article/abs/pii/S096386872100041X}
    }

    # metadat from the url:

    @article{wagner2021exploring,
        title = {Exploring the boundaries and processes of digital platforms for knowledge work: A review of information systems research},
        author = {Wagner, Gerit and Prester, Julian and Paré, Guy},
        journal = {The Journal of Strategic Information Systems},
        volume = {30},
        number = {4},
        pages = {101694},
        year = {2021},
        url = {https://www.sciencedirect.com/science/article/abs/pii/S096386872100041X}
    }

+-----------------+
| Fields checked  |
+=================+
| author          |
+-----------------+
| title           |
+-----------------+
| year            |
+-----------------+
| journal         |
+-----------------+
| volume          |
+-----------------+
| number          |
+-----------------+

.. raw:: html

   <hr>

.. _record-not-in-toc:

record-not-in-toc
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The record should be found in the relevant table-of-content (toc) if a toc is available.

**Problematic value**

.. code-block:: python

    @article{wagner2021exploring,
        title = {A breakthrough paper on microsouring},
        author = {Wagner, Gerit},
        journal = {The Journal of Strategic Information Systems},
        volume = {30},
        number = {4},
        year = {2021},
    }

    # Table-of-contents (based on crossref):
    # The Journal of Strategic Information Systems, 30-4

    Gable, G. and Chan, Y. - Welcome to this 4th issue of Volume 30 of The Journal of Strategic Information Systems
    Mamonov, S. and Peterson, R. - The role of IT in organizational innovation – A systematic literature review
    Eismann, K. and Posegga, O. and Fischbach, K. - Opening organizational learning in crisis management: On the affordances of social media
    Dhillon, G. and Smith, K. and Dissanayaka, I. - Information systems security research agenda: Exploring the gap between research and practice
    Wagner, G. and Prester, J. and Pare, G. - Exploring the boundaries and processes of digital platforms for knowledge work: A review of information systems research
    Hund, A. and Wagner, H. T. and Beimborn, D. and Weitzel, T. - Digital innovation: Review and novel perspective

**Correct value**

.. code-block:: python

    @article{wagner2021exploring,
        title = {Exploring the boundaries and processes of digital platforms for knowledge work: A review of information systems research},
        author = {Wagner, Gerit and Prester, Julian and Paré, Guy},
        journal = {The Journal of Strategic Information Systems},
        volume = {30},
        number = {4},
        pages = {101694},
        year = {2021},
    }

    # Table-of-contents (based on crossref):
    # The Journal of Strategic Information Systems, 30-4

    Gable, G. and Chan, Y. - Welcome to this 4th issue of Volume 30 of The Journal of Strategic Information Systems
    Mamonov, S. and Peterson, R. - The role of IT in organizational innovation – A systematic literature review
    Eismann, K. and Posegga, O. and Fischbach, K. - Opening organizational learning in crisis management: On the affordances of social media
    Dhillon, G. and Smith, K. and Dissanayaka, I. - Information systems security research agenda: Exploring the gap between research and practice
    Wagner, G. and Prester, J. and Pare, G. - Exploring the boundaries and processes of digital platforms for knowledge work: A review of information systems research
    Hund, A. and Wagner, H. T. and Beimborn, D. and Weitzel, T. - Digital innovation: Review and novel perspective


.. _common defects:

Common defects
-------------------------------

.. _erroneous-symbol-in-field:

erroneous-symbol-in-field
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Fields should not contains invalid symbols.

**Problematic value**

.. code-block:: python

    author = {M�ller, U.}

**Correct value**

.. code-block:: python

    author = {Müller, U.}

Symbols considered erroneous: "�", "™"

+-----------------+
| Fields checked  |
+=================+
| author          |
+-----------------+
| title           |
+-----------------+
| editor          |
+-----------------+
| journal         |
+-----------------+
| booktitle       |
+-----------------+


.. raw:: html

   <hr>

.. _erroneous-term-in-field:

erroneous-term-in-field
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Fields should not contain any erroneous terms.

**Problematic value**

.. code-block:: python

    author = {Smith, F. orcid-0012393}

**Correct value**

.. code-block:: python

    author = {Smith, F.}

+-----------+-------------------------------------------------------------------------------+
| field     | Erroneous terms                                                               |
+===========+===============================================================================+
| author    | http, University, orcid, student, Harvard, Conference, Mrs, Hochschule        |
+-----------+-------------------------------------------------------------------------------+
| title     | research paper, completed research, research in progress, full research paper |
+-----------+-------------------------------------------------------------------------------+


.. raw:: html

   <hr>

.. _erroneous-title-field:

erroneous-title-field
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Title should not contain typical defects.

**Problematic value**

.. code-block:: python

    title = {A I S ssociation for nformation ystems}

**Correct value**

.. code-block:: python

    title = {An empirical study of platform exit}

+-----------------+
| Fields checked  |
+=================+
| title           |
+-----------------+
