record_not_in_toc
============================

The record should be found in the relevant table-of-content (toc) if a toc is available.

**Problematic value**

.. code-block:: python

    @article{wagner2021exploring,
        title = {A breakthrough paper on microsouring},
        author = {Wagner, Gerit},
        journal = {The Journal of Strategic Information Systems},
        volume = {30},
        number = {4},
        year = {2021},
    }

    # Table-of-contents (based on crossref):
    # The Journal of Strategic Information Systems, 30-4

    Gable, G. and Chan, Y. - Welcome to this 4th issue of Volume 30 of The Journal of Strategic Information Systems
    Mamonov, S. and Peterson, R. - The role of IT in organizational innovation – A systematic literature review
    Eismann, K. and Posegga, O. and Fischbach, K. - Opening organizational learning in crisis management: On the affordances of social media
    Dhillon, G. and Smith, K. and Dissanayaka, I. - Information systems security research agenda: Exploring the gap between research and practice
    Wagner, G. and Prester, J. and Pare, G. - Exploring the boundaries and processes of digital platforms for knowledge work: A review of information systems research
    Hund, A. and Wagner, H. T. and Beimborn, D. and Weitzel, T. - Digital innovation: Review and novel perspective

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
    }

    # Table-of-contents (based on crossref):
    # The Journal of Strategic Information Systems, 30-4

    Gable, G. and Chan, Y. - Welcome to this 4th issue of Volume 30 of The Journal of Strategic Information Systems
    Mamonov, S. and Peterson, R. - The role of IT in organizational innovation – A systematic literature review
    Eismann, K. and Posegga, O. and Fischbach, K. - Opening organizational learning in crisis management: On the affordances of social media
    Dhillon, G. and Smith, K. and Dissanayaka, I. - Information systems security research agenda: Exploring the gap between research and practice
    **Wagner, G. and Prester, J. and Pare, G. - Exploring the boundaries and processes of digital platforms for knowledge work: A review of information systems research**
    Hund, A. and Wagner, H. T. and Beimborn, D. and Weitzel, T. - Digital innovation: Review and novel perspective
