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
colrev.semanticscholar
======================

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner, Louis Langenhan, Peter Eckhardt, Amadou-Choumoussidine Kouotou-Ngapout, Robert Theis

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/semanticscholar>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - search_source
     - |EXPERIMENTAL|
     - .. code-block::


         colrev search --add colrev.semanticscholar

   * - prep
     - |EXPERIMENTAL|
     - .. code-block::


         colrev prep --add colrev.semanticscholar


Summary
-------

Semantic Scholar is a cross-disciplinary search source with a vast collection of over 175 million items.

This class supports the search function for Semantic Scholar via an unofficial python client (link below).

search
------

So far, only API search is implemented. Other search types such as MD search or TOC search might be implemented in the future. All search results are saved as a standardized dictionary in the colrev feed and a distinctive ``data/search/{query_parameters}date.bib`` file, the filename of which contains the query and the date of the search.

API search
^^^^^^^^^^

ℹ️ Restriction: API searches do not support complex queries (yet)

The API search is launched with the following command:

.. code-block::

   colrev search --add colrev.semanticscholar

Upon entering the command above with no additional parameters, a console interface opens up, in which the user is asked to enter the parameters and query for their search.

API search: The user interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the main menu, the user can decide whether they want to search for a single paper or author, or conduct a full keyword search. Authors can be searched for via their distinct SemanticScholar-ID, which the user is asked to enter into the console. Papers can be searched for by different IDs - SemanticScholarID, DOI, ArXiv etc.

If the user opted for a full keyword search, they are asked to enter a series of search parameters: A query, a yearspan, fields of study, publication types etc. These parameters restrict the search within the SemanticScholar library to recieve more precise results.

For all search parameters except the query, the user can press the ``enter`` key to leave them blank. The query then will not restrict the search in the respective parameters, resulting in an increasingly broad search and more returned papers.

When asked about the fields of study and the publication types, the user can select one or multiple values by navigating the list with ``uparrow`` and ``downarrow`` and selecting and unselecting with ``rightarrow`` or ``space``. Pressing ``enter`` will confirm the choice.

Please note that some user entries require a specific format and will be validated by the UI. If the format is not satisfied, the user will be asked to make a different entry. Here are some examples:

.. code-block::

   S2Ids (Paper or author) --> A String of alphanumeric characters
   yearspan                --> Specific format, e.g.: "2020", "2020-" (from 2020 until this year), "-2020", "2020-2023"
   venues                  --> Multiple entries in csv format possible, e.g.: "Venue A,Venue B,Venue C"
   API key                 --> A String of 40 alphanumeric characters
   Other IDs (DOI,MAG...)  --> Respective ID format, e.g. "10.XXXXX/XXXXX" for DOI

If the user decides to conduct a search without entering any search parameters, the interface will immediately close the program and no search will be attempted.

API search: API key for SemanticScholar
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

While it is not necessary to enter an API key to conduct a search in SemanticScholar, we highly recommend it. Without an API key, SemanticScholar only allows limited access attempts per minute. This might lead to the site being unavailable for a short time. An API key can be requested via the SemanticScholar API (link below). Once a valid API key was entered, it will be saved in the ``SETTINGS`` file. Subsequent searches of SematicScholar will now include this API key. Every time a new search is conducted, the user will have the opportunity to change or delete the stored API key via the user interface.

API search: Search results
~~~~~~~~~~~~~~~~~~~~~~~~~~

After retrieving the items from Semantic Scholar, they are transformed into the standard colrev ``BibTeX`` format and saved in the result file mentioned above.

Please note that, unfortunately, the format of SemanticScholar outputs does not produce sufficiently clear information to fill in every colrev field. Disparities, e.g. in the definition of publication types (== "ENTRYTYPES" in colrev), may lead to ambigous information about a paper, its type or its venue. To prevent misinformation, papers will be marked as ``miscellaneaous``\ , if the publication type is not determinable. Other fields, especially regarding books, such as ``EDITOR``\ , ``EDITION`` or ``ADDRESS`` are not supported at all by SemanticScholar and thus cannot be filled in.

SemanticScholar also does not distinguish between forthcoming or retracted entries. Thus, entries unfortunately cannot be flagged as such in the result file.

API search: Not yet supported features
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

So far, the ``rerun`` functionality, which provides a more efficient way of redoing a search, is not implemented. Per default, rerun is set to ``true``\ , which means that every time a query is entered again, a full search will be conducted. The functionality might be added in the future.

Additionally, the result file has not been adapted to author search yet. Although it is still possible to search for authors by their S2-ID, the result file will not include any useful information but the url to the authors' web page in Semantic Scholar.

prep
----

Semantic scholar can be used to link metadata to existing records.

Links
-----


* `SemanticScholar <https://www.semanticscholar.org>`_
* `SemanticScholarAPI <https://www.semanticscholar.org/product/api/tutorial#searching-and-retrieving-paper-details>`_
* `SemanticScholarAPIDocumentation <https://api.semanticscholar.org/api-docs/>`_
* `SemanticScholarPythonClient <https://github.com/danielnsilva/semanticscholar>`_
