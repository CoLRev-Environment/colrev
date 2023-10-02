page-range
============================

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
