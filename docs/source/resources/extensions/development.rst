Extension development process
=============================

Extensions are referred through its respective endpoints, these endpoints can be enabled in ``settings.json`` of a project. The interfaces for the extension endpoints are documented in the :doc:`extension interfaces </dev_docs/extensions>` section.

Extension development base guidelines
-------------------------------------

* In case of External extension, you need to register it by updating ``packages.json`` but it's not required for built-in extensions.
* Follow the recommendations:

  * Get paths from review_manager
  * Use the ``logger`` and ``colrev_report_logger`` to help users examine and validate the process, including links to the docs where instructions for tracing and fixing errors are available.
  * `Add <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics>`_ the ```colrev-extension``` `topic tag on GitHub <https://github.com/topics/colrev-extension>`_ to allow others to find and use your work.

* Check the other extension implementation for getting a good idea on how to proceed
* Try to keep the methods simple. It's better that each methods do one thing, instead of doing many things
* If the extension works with any specific file types, it should be set inside ``supported_extensions`` class variable,  e.g:

  .. code-block:: python

        class BibutilsLoader(JsonSchemaMixin):

            """Loads bibliography files (based on bibutils)
            Supports ris, end, enl, copac, isi, med"""

            supported_extensions = ["ris", "end", "enl", "copac", "isi", "med"]


* set ``ci_supported`` flag to True/False depending on, if this extension is not able to run in CI environment, as asreview is not able to run in CI env, it's ``ci_supported`` flag is False
* Test
* Before committing do a pre-commit test

External extension development process
--------------------------------------
For development and testing purpose it’s convenient to fork the CoLRev repository, setup a venv with the forked repository, and work on the extension. Once the extension is developed, and working as expected, you can make a pull request to original repository to register your extension.

Following steps might be a good starting point.

* Fork and clone CoLRev
* Setup a virtualenv, all the followings steps assumes the same virtualenv used throughout
* Install the cloned CoLRev using pip command ``pip install -e /path/to/cloned/colrev``

   .. note::

      ``-e`` allows editable installation. Any changes made will be available immediately

* Create the extension repository e.g.: https://github.com/CoLRev-Environment/colrev-asreview

   .. note::

      You can simply use `this repository <https://github.com/CoLRev-Environment/colrev-asreview>`_ as the ground for your extension


* Add ``.colrev_endpoints.json`` file to the project, and add the new extension information, e.g.

   ..  code-block:: json

           {
             "authors": "Wagner, Gerit and Prester, Julian",
             "license": "MIT",
             "colrev_version": ">=0.9.0",
             "endpoints": {
                 "prescreen": [
                     {
                         "package_endpoint_identifier": "colrev_asreview.colrev_asreview",
                         "endpoint": "colrev_asreview.colrev_asreview.ASReviewPrescreen"
                     }
                 ]
             }
           }

   This file should be in package root, with the __init__.py, so, the folder structure could be:

   ::

    ...
       ├── project_folder
       │   ├── pyproject.toml
       │   ├── mypy.ini
       │   ├── .pre-commit-config.yaml
       │   ├── colrev_asreview
       │   │   ├── .colrev_endpoints.json
       │   │   ├── __init__.py
       │   │   ├── colrev_asreview.py
    ...

   .. note::

      ``mypy.ini`` and ``.pre-commit-config.yaml`` should be copied from CoLRev repo, for ensuring CoLRev’s coding standards

* Include the endpoints file in the `pyproject.toml <https://github.com/CoLRev-Environment/colrev-asreview/blob/main/pyproject.toml>`_

   ..  code-block:: diff

       ...
         authors = ["Gerit Wagner <gerit.wagner@uni-bamberg.de>", "Julian Prester <julian.prester@sydney.edu.au>"]
         readme = "README.md"
       + include = ["colrev_asreview/.colrev_endpoints.json"]

         [tool.poetry.dependencies]
       ...

* Install the extension ``pip install -e /path/to/colrev_asreview``:
* Register the extension to the cloned CoLRev by editing the ``colrev/template/packages.json`` file e.g.:

   ..  code-block:: diff

       ...
         {
             "module": "colrev",
             "url": "https://github.com/CoLRev-Environment/colrev"
         },
       + {
       +     "module": "colrev_asreview",
       +     "url": "https://github.com/CoLRev-Environment/colrev-asreview"
       + }

* Commit the changes
* Run the ``colrev env --update_package_list`` command, which updates the `package_endpoints.json <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/template/package_endpoints.json>`_, and the `package_status.json <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/template/package_status.json>`_
* Continue developing the extension

* In case of error, ``package_endpoints.json`` file will be deleted. Fix the error, and restore the file from repo, continue until CoLRev successfully register the extension without error
* Tests should be implemented in the extension level first, to ensure extension is working as expected
* Once the development is completed

   *  Remove any debugging code
   *  Do a pre-commit test
   *  Commit and push the changes to GitHub
   *  Create a pull request briefly describing the extension and adding it to the `packages.json <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/template/packages.json>`_.
   *  Once the extension is approved, it will be available to the users

Built-in extension
==================
Built-in extensions are integrated into CoLRev and does initial processing of the record. Implementation wise external and built-in extensions, both are similar.


Built-in extension development process
--------------------------------------

* Same with external extension development process, clone and install forked version. But now the work will be done directly inside CoLRev.
* Built-in extension should be placed under ``colrev/ops/built_in/<operation>`` directory, ``<operation>`` is the directory of the operation it's extending, e.g.: ``colrev/ops/built_in/prescreen/asreview.py``
* Add the extension information in ``colrev/template/package_endpoints.json``, e.g.:

  .. code-block:: json

    "prescreen": [
        {
            "package_endpoint_identifier": "colrev.asreview_prescreen",
            "endpoint": "colrev.ops.built_in.prescreen.asreview.ASReviewPrescreen",
            "status": "|EXPERIMENTAL|",
            "status_linked": "|EXPERIMENTAL|",
            "short_description": "ASReview-based prescreen (`instructions <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/ops/built_in/prescreen/asreview.md>`_)",
            "ci_supported": false
        },

* No need to add the entry in ``packages.json``
* If any additional python package is required, install using ``poetry add <package_name>``. e.g. ``poetry add asreview``
* This is all you need to start working on a built-in extension.
* It's a good idea to commit in current state, before start working.
* As same with external extensions, in case of error, ``package_endpoints.json`` file will be deleted. Fix the error, and restore the file from repo, continue until CoLRev successfully register the extension without error
* Once the extension development is completed, make a PR to the CoLRev, with brief description of the extension.


Examples
========

- `colrev-asreview <https://github.com/CoLRev-Environment/colrev-asreview>`_
