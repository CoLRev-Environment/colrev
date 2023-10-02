pubmedid-not-matching-pattern
============================

Pubmed IDs should be formatted correctly (7 or 8 digits).

**Problematic value**

.. code-block:: python

    colrev.pubmed.pubmedid = {PMID: 1498274774},

**Correct value**

.. code-block:: python

    colrev.pubmed.pubmedid = {33044175},

+-------------------------+
| Fields checked          |
+=========================+
| colrev.pubmed.pubmedid  |
+-------------------------+

- [PMID specification](https://www.nlm.nih.gov/bsd/mms/medlineelements.html#pmid)
