erroneous-symbol-in-field
=========================

Fields should not contains invalid symbols.

**Problematic value**

.. code-block:: python

    author = {M�ller, U.}

**Correct value**

.. code-block:: python

    author = {Müller, U.}

Symbols considered erroneous: "�", "™"

+-----------------+
| Fields checked  |
+=================+
| author          |
+-----------------+
| title           |
+-----------------+
| editor          |
+-----------------+
| journal         |
+-----------------+
| booktitle       |
+-----------------+
