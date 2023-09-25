thesis_with_multiple_authors
============================

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
