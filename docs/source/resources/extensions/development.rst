Package development process
=============================

Packages are referred through its respective endpoints, these endpoints can be enabled in ``settings.json`` of a project. The interfaces for the package endpoints are documented in the :doc:`package interfaces </dev_docs/extensions>` section.

Package development base guidelines
-------------------------------------

* In case of external packages, you need to register it by updating ``packages.json`` but it's not required for built-in packages.
* Follow the recommendations:

  * Get paths from review_manager
  * Use the ``logger`` and ``colrev_report_logger`` to help users examine and validate the process, including links to the docs where instructions for tracing and fixing errors are available.
  * `Add <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics>`_ the ```colrev-packages``` `topic tag on GitHub <https://github.com/topics/colrev-package>`_ to allow others to find and use your work.

* Check the other package implementations for getting a good idea on how to proceed
* Try to keep the methods simple. It's better that each methods do one thing, instead of doing many things
* Set ``ci_supported`` flag to True/False depending on, if this package is not able to run in CI environment, as asreview is not able to run in CI env, it's ``ci_supported`` flag is False
* Test
* Before committing do a pre-commit test

External package development process
--------------------------------------
For development and testing purpose it’s convenient to fork the CoLRev repository, setup a venv with the forked repository, and work on the package. Once the package is developed, and working as expected, you can make a pull request to original repository to register your package.

Following steps might be a good starting point.

* Fork and clone CoLRev
* Setup a virtualenv, all the followings steps assumes the same virtualenv used throughout
* Install the cloned CoLRev using pip command ``pip install -e /path/to/cloned/colrev``

   .. note::

      ``-e`` allows editable installation. Any changes made will be available immediately

* Create the package repository e.g.: https://github.com/CoLRev-Environment/colrev-asreview

   .. note::

      You can simply use `this repository <https://github.com/CoLRev-Environment/colrev-asreview>`_ as the ground for your package


* Add ``.colrev_endpoints.json`` file to the project, and add the new package information, e.g.

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

* Install the expackagetension ``pip install -e /path/to/colrev_asreview``:
* Register the package to the cloned CoLRev by editing the ``colrev/template/packages.json`` file e.g.:

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
* Continue developing the package

* In case of error, ``package_endpoints.json`` file will be deleted. Fix the error, and restore the file from repo, continue until CoLRev successfully register the package without error
* Tests should be implemented in the package level first, to ensure package is working as expected
* Once the development is completed

   *  Remove any debugging code
   *  Do a pre-commit test
   *  Commit and push the changes to GitHub
   *  Create a pull request briefly describing the package and adding it to the `packages.json <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/template/packages.json>`_.
   *  Once the package is approved, it will be available to the users

Built-in packages
=====================

Built-in packages are integrated into CoLRev and does initial processing of the record. Implementation wise external and built-in packages, both are similar.


Built-in packages development process
--------------------------------------

* Same with external package development process, clone and install forked version. But now the work will be done directly inside CoLRev.
* Built-in packages should be placed under ``colrev/ops/built_in/<operation>`` directory, ``<operation>`` is the directory of the operation it's extending, e.g.: ``colrev/ops/built_in/prescreen/asreview.py``
* Add the package information in ``colrev/template/package_endpoints.json``, e.g.:

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
* This is all you need to start working on a built-in package.
* It's a good idea to commit in current state, before start working.
* As same with external packages, in case of error, ``package_endpoints.json`` file will be deleted. Fix the error, and restore the file from repo, continue until CoLRev successfully register the extenpackagesion without error
* Once the package development is completed, make a PR to the CoLRev, with brief description of the package.


Examples
========

- `colrev-asreview <https://github.com/CoLRev-Environment/colrev-asreview>`_
