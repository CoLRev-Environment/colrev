
Extensions
====================================

Extensions of CoLRev are available on `Github <https://github.com/topics/colrev-extension>`_ and guidelines on extension development are available in `this section <architecture/extension_development.html>`_.
A few examples are summarized below.


colrev_endpoint
-----------------

Aimed at making it easy to integrate other tools by operating endpoints that support the export and loading of data.
For example, EndPoint supports the collaboration with Endnote (and other reference mangers) or `ASReview <https://github.com/asreview/asreview>`_ for the prescreen.

Example:

.. code-block:: sh

    # In a colrev repository, run
    colrev_endpoint add type endnote

    # Create an export enl file
    colrev_endpoint export
    # the file is created in /endpoint/endnote/references.enl

    # The following exports will contain new records exclusively
    colrev_endpoint export

    # Import the library to update the main references.bib
    colrev_endpoint load path_to_library.enl

Link to the repository: `colrev_endpoint <https://github.com/geritwagner/colrev_endpoint>`_.


paper-feed
-----------------

Aimed at providing a continuous feed of recent research by retrieving (new) papers from databases like Crossref and DBLP.
It's vision is to facilitate **living reviews** in which researchers can efficiently disseminate the latest publications and distribute them to their local topic (CoLRev) repositories and projects.

Example:

.. code-block:: sh

    # In a colrev repository, run
    paper_feed init --fname ISR.bib --qname "Information Systems Research" --jissn '15369323'

    # To update the feed by retrieving all /the latest papers:
    paper_feed update

Link to the repository: `paper_feed <https://github.com/geritwagner/paper_feed>`_.


local-paper-index
-------------------

Aimed at indexing PDFs on a local machine, allowing any other local CoLRev project to retrieve them.


Example:

.. code-block:: sh

    # In a colrev repository, add a directory containing PDFs:
    local_paper_index index --add-path /home/user/journals/PLOS

    # Index PDFs:
    local_paper_index index

Link to the repository: `local_paper_index <https://github.com/geritwagner/local_paper_index>`_.


colrev_cml_assistant
-----------------------

Aimed at supporting crowdsourcing and machine-learning based on CoLRev datasets.

Link to the repository: `colrev_cml_assistant <https://github.com/geritwagner/colrev_cml_assistant>`_.
