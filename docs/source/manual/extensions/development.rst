Extension Development Process
=============================

Extensions are referred through its respective endpoints, these endpoints can be enabled in ``settings.json`` of a project. The interfaces for the extension endpoints are documented in the `extension interfaces <../foundations/extensions.html>`_ section.

Following process are possible to extend through extensions.

+---------------+------------------------------------------------------+
| Process       | Explanation                                          |
+===============+======================================================+
| Review Type   | Perform Review operation                             |
+---------------+------------------------------------------------------+
| Search Source | Tries to find out source of the provided literature  |
+---------------+------------------------------------------------------+
| Load          | Converts document to record                          |
| Conversion    |                                                      |
+---------------+------------------------------------------------------+
| Prep          | Prepares records based on different metadata         |
+---------------+------------------------------------------------------+
| Prep Man      | Manual preparation of record                         |
+---------------+------------------------------------------------------+
| Dedupe        | Dedups records using different sources               |
+---------------+------------------------------------------------------+
| Prescreen     | Prescreen the records                                |
+---------------+------------------------------------------------------+
| PDF Get       | Retrieves PDF from different sources                 |
+---------------+------------------------------------------------------+
| PDF Get Man   | Manually get PDF                                     |
+---------------+------------------------------------------------------+
| PDF Prep      | Preps PDF, validates for completeness                |
+---------------+------------------------------------------------------+
| PDF Prep Man  | Manual preparation [Not yet implemented]             |
+---------------+------------------------------------------------------+
| Screen        | Screen records                                       |
| Package       |                                                      |
+---------------+------------------------------------------------------+
| Data Package  | Export records that are not in all sources for       |
|               | analyses                                             |
+---------------+------------------------------------------------------+


For development and testing purpose it’s convenient to fork the CoLRev repository, setup a venv with the forked repository, and work on the extension. Once the extension is developed, and working as expected, you can make a pull request to original repository to register your extension

Following steps might be a good starting point.

* Fork and clone CoLRev
* Setup a virtualenv, all the followings steps assumes the same virtualenv used throughout
* Install the cloned CoLRev using pip command ``pip install -e /path/to/cloned/colrev``

   .. note::

      ``-e`` allows editable installation. Any changes made will be available immediately

* Create the extension repository
* Add ``.colrev_endpoints.json`` file to the project, and add the new extension information, e.g.

   ..  code-block:: json

           {
             "authors": "Wagner, Gerit and Prester, Julian",
             "license": "MIT",
             "colrev_version": ">=0.6.0",
             "endpoints": {
                 "prescreen": [
                     {
                         "package_endpoint_identifier": "a_prescreen_extension",
                         "endpoint": "module.path.to.extension.PythonClassName"
                     }
                 ]
             }
           }

   This file should be in package root, so, the folder structure could be:

   ::

    ...
       ├── project_folder
       │   ├── pyproject.toml
       │   ├── mypy.ini
       │   ├── .pre-commit-config.yaml
       │   ├── a_prescreen_extension
       │   │   ├── __init__.py
       │   │   ├── extension.py
       │   │   ├── .colrev_endpoints.json
    ...

   .. note::

      ``mypy.ini`` and ``.pre-commit-config.yaml`` should be copied from CoLRev repo, for ensuring CoLRev’s coding standards

* Install the extension ``pip install -e /path/to/new/extension``
* Register the extension to the cloned CoLRev by editing the ``colrev/template/packages.json`` file e.g:

   ..  code-block:: diff

       ...
         {
             "module": "colrev",
             "url": "https://github.com/colrev/colrev"
         },
       + {
       +     "module": "a_prescreen_extension",
       +     "url": "<url_to_repository>"
       + }

* Commit the changes
* Run the ``colrev env --update_package_list`` command, which updates the `package_endpoints.json <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/template/package_endpoints.json>`_, and the `package_status.json <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/template/package_status.json>`_
* Continue developing the extension. Follow the recommendations:

   * Get paths from review_manager
   * Use the ``logger`` and ``colrev_report_logger`` to help users examine and validate the process, including links to the docs where instructions for tracing and fixing errors are available.
   * `Add <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics>`_ the ```colrev-extension``` `topic tag on GitHub <https://github.com/topics/colrev-extension>`_ to allow others to find and use your work.

* In case of error, ``package_endpoints.json`` file will be deleted. Fix the error, and restore the file from repo, continue until CoLRev successfully register the extension without error
* Tests should be implemented in the extension level first, to ensure extension is working as expected
* Once the development is completed

   *  Remove any debugging code
   *  Do a pre-commit test
   *  Commit and push the changes to GitHub
   *  Create a pull request briefly describing the extension and adding it to the `packages.json <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/template/packages.json>`_.
   *  Once the extension is approved, it will be available to the users

Testing
=======

**TODO: add how to implement test in the extension**
