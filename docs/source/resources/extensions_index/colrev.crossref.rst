
Crossref
========

search
------

API search
^^^^^^^^^^

It is possible to copy the url from the `search.crossref.org <https://search.crossref.org/?q=microsourcing&from_ui=yes>`_ UI and add it as follows:

.. code-block::

   colrev search -a colrev.crossref -p "query=microsourcing;years=2000-2010"
   colrev search -a colrev.crossref -p "https://search.crossref.org/?q=+microsourcing&from_ui=yes"

TOC search
^^^^^^^^^^

Whole journals can be added based on their issn:

.. code-block::

   colrev search -a colrev.crossref -p "issn=1234-5678"

prep
----

Crossref linking

Note: This document is currently under development. It will contain the following elements.


* description
* example

Links
-----


* `Crossref <https://www.crossref.org/>`_
* 
  `License <https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-metadata-license-information/>`_

* 
  `Issue: AND Operators not yet supported <https://github.com/fabiobatalha/crossrefapi/issues/20>`_

To test the metadata provided for a particular ``DOI`` use:

.. code-block::

   https://api.crossref.org/works/DOI
