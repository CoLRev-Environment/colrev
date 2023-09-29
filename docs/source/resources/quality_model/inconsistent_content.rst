inconsistent_content
============================

Fields should not contain inconsistent values,

  * Journal should not be from conference or workshop,
  * booktitle should not belong to journal

**Problematic value**

.. code-block:: python

    journal = {Proceedings of the 32nd Conference on ...}

**Correct value**

.. code-block:: python

    booktitle = {Proceedings of the 32nd Conference on ...}

+-----------------+---------------------+
| Fields checked  | Erroneous values    |
+=================+=====================+
| journal         | conference, workshop|
+-----------------+---------------------+
| booktitle       |journal              |
+-----------------+---------------------+
