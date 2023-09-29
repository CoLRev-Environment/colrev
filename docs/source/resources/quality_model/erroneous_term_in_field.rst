erroneous_term_in_field
=======================

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
