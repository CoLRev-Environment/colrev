incomplete-field
============================

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
