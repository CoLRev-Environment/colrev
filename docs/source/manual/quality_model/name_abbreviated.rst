name_abbreviated
============================

Names should not be abbreviated

**Problematic value**

.. code-block:: python

    author = {Smith, W. et. al.}

**Correct value**

.. code-block:: python

    author = {Smith, W. and Thompson, U.}

TODO: An author field is considered incomplete if first name is missing, which is indicated by a ``,`` at the end of the author name

+-----------------+
| Fields checked  |
+=================+
| author          |
+-----------------+
| editor          |
+-----------------+
