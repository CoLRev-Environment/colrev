name_format_titles
============================

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
