html_tags
============================

Fields should not contain HTML tags.

**Problematic value**

.. code-block:: python

    title = {A commentary on <i>microsourcing</i>}

**Correct value**

.. code-block:: python

    title = {A commentary on microsourcing}

Note: abstracts are not checked and may contain html tags.

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
| publisher       |
+-----------------+
| editor          |
+-----------------+
