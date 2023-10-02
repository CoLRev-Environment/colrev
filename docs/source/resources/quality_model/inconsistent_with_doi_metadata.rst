inconsistent-with-doi-metadata
==============================

Record content needs to be consistent with doi metadata.

**Problematic value**

.. code-block:: python

    @article{wagner2021exploring,
        title = {Analyzing the past to prepare for the future: Writing a literature review},
        author = {Webster, Jane and Watson, Richard T},
        journal = {MIS quarterly},
        volume = {30},
        number = {4},
        pages = {101694},
        year = {2021},
        doi = {10.1016/j.jsis.2021.101694}
    }

    # metadat at crossref:
    # https://api.crossref.org/works/10.1016/j.jsis.2021.101694

    @article{wagner2021exploring,
        title = {Exploring the boundaries and processes of digital platforms for knowledge work: A review of information systems research},
        author = {Wagner, Gerit and Prester, Julian and Paré, Guy},
        journal = {The Journal of Strategic Information Systems},
        volume = {30},
        number = {4},
        pages = {101694},
        year = {2021},
        doi = {10.1016/j.jsis.2021.101694}
    }

**Correct value**

.. code-block:: python

    @article{wagner2021exploring,
        title = {Exploring the boundaries and processes of digital platforms for knowledge work: A review of information systems research},
        author = {Wagner, Gerit and Prester, Julian and Paré, Guy},
        journal = {The Journal of Strategic Information Systems},
        volume = {30},
        number = {4},
        pages = {101694},
        year = {2021},
        doi = {10.1016/j.jsis.2021.101694}
    }

    # metadat at crossref:
    # https://api.crossref.org/works/10.1016/j.jsis.2021.101694

    @article{wagner2021exploring,
        title = {Exploring the boundaries and processes of digital platforms for knowledge work: A review of information systems research},
        author = {Wagner, Gerit and Prester, Julian and Paré, Guy},
        journal = {The Journal of Strategic Information Systems},
        volume = {30},
        number = {4},
        pages = {101694},
        year = {2021},
        doi = {10.1016/j.jsis.2021.101694}
    }

+-----------------+
| Fields checked  |
+=================+
| title           |
+-----------------+
| journal         |
+-----------------+
| author          |
+-----------------+
