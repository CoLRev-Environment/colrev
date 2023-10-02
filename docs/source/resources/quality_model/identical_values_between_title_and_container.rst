identical-values-between-title-and-container
============================================

Title and containers (booktitle, journal) should not contain identical values.

**Problematic value**

.. code-block:: python

    title = {MIS Quarterly},
    journal = {MIS Quarterly},

**Correct value**

.. code-block:: python

    title = {A commentary on microsourcing}
    journal = {MIS Quarterly},
