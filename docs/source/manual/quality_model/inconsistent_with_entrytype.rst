inconsistent_with_entrytype
===========================

Some fields are inconsistent with the respective ENTRYTYPE.

**Problematic value**

.. code-block:: python

    @article{SmithParkerWeber2003,
        ...
        booktitle = {First Workshop on ...},
        ...
    }

**Correct value**

.. code-block:: python

    @inproceedings{SmithParkerWeber2003,
        ...
        booktitle = {First Workshop on ...},
        ...
    }

+--------------+-----------------------------------------+
|ENTRYTYPE     | inconsistent fields                     |
+==============+=========================================+
|article       | booktitle                               |
+--------------+-----------------------------------------+
|inproceedings | issue,number,journal                    |
+--------------+-----------------------------------------+
|incollection  |                                         |
+--------------+-----------------------------------------+
|inbook        | journal                                 |
+--------------+-----------------------------------------+
|book          | volume,issue,number,journal             |
+--------------+-----------------------------------------+
|phdthesis     | volume,issue,number,journal,booktitle   |
+--------------+-----------------------------------------+
|masterthesis  | volume,issue,number,journal,booktitle   |
+--------------+-----------------------------------------+
|techreport    | volume,issue,number,journal,booktitle   |
+--------------+-----------------------------------------+
|unpublished   | volume,issue,number,journal,booktitle   |
+--------------+-----------------------------------------+
|online        | journal,booktitle                       |
+--------------+-----------------------------------------+
|misc          | journal,booktitle                       |
+--------------+-----------------------------------------+
