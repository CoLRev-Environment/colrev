doi_not_matching_pattern
==================================

The doi field should follow a `predefined pattern <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/qm/checkers/doi_not_matching_pattern.py#L17>`_.

**Problematic value**

.. code-block:: python

    doi = {https://doi.org/10.1016/j.jsis. 2021.101694}

**Correct value**

.. code-block:: python

    doi = {10.1016/j.jsis.2021.101694}

+-----------------+
| Fields checked  |
+=================+
| doi             |
+-----------------+

Links

- `Crossref: DOIs and maching regular expressions <https://www.crossref.org/blog/dois-and-matching-regular-expressions/>`_.
