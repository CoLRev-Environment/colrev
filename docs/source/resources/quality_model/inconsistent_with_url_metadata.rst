inconsistent-with-url-metadata
==============================

Checks url metadata should be consistent with Zotero generated metadata about the url.

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
        url = {https://www.sciencedirect.com/science/article/abs/pii/S096386872100041X}
    }

    # metadat from the url:

    @article{wagner2021exploring,
        title = {Exploring the boundaries and processes of digital platforms for knowledge work: A review of information systems research},
        author = {Wagner, Gerit and Prester, Julian and Paré, Guy},
        journal = {The Journal of Strategic Information Systems},
        volume = {30},
        number = {4},
        pages = {101694},
        year = {2021},
        url = {https://www.sciencedirect.com/science/article/abs/pii/S096386872100041X}
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
        url = {https://www.sciencedirect.com/science/article/abs/pii/S096386872100041X}
    }

    # metadat from the url:

    @article{wagner2021exploring,
        title = {Exploring the boundaries and processes of digital platforms for knowledge work: A review of information systems research},
        author = {Wagner, Gerit and Prester, Julian and Paré, Guy},
        journal = {The Journal of Strategic Information Systems},
        volume = {30},
        number = {4},
        pages = {101694},
        year = {2021},
        url = {https://www.sciencedirect.com/science/article/abs/pii/S096386872100041X}
    }

+-----------------+
| Fields checked  |
+=================+
| author          |
+-----------------+
| title           |
+-----------------+
| year            |
+-----------------+
| journal         |
+-----------------+
| volume          |
+-----------------+
| number          |
+-----------------+
