name_format_separators
============================

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
