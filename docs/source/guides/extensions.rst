
Extensions
====================================

Extensions of CoLRev are available on `GitHub <https://github.com/topics/colrev-extension>`_ and guidelines on extension development are available in `this section <architecture/extension_development.html>`_.
A few examples are summarized below.


colrev_endpoint
-----------------

Aimed at making it easy to integrate with other tools by operating endpoints that support the export and loading of data.
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


colrev_cml_assistant
-----------------------

Aimed at supporting crowdsourcing and machine-learning based on CoLRev datasets.

Link to the repository: `colrev_cml_assistant <https://github.com/geritwagner/colrev_cml_assistant>`_.
