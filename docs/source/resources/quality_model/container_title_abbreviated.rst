container-title-abbreviated
===========================

Containers should not be abbreviated.

**Problematic value**

.. code-block:: python

    journal = {MISQ}

**Correct value**

.. code-block:: python

    year = {MIS Quarterly}

Container are considers abbreviated if it is less than 6 characters and all upper case.

+-----------------+
| Fields checked  |
+=================+
| journal         |
+-----------------+
| booktitle       |
+-----------------+
