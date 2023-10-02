isbn-not-matching-pattern
============================

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
