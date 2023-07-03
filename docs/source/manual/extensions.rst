
Extensions
==================================

Extensions can be added to extend any of CoLRev's process. Following process are possible to customize. Extensions
are referred through its respective endpoints, these endpoints can be enabled in `settings.json` of a project.
For an extension to be available, it must be registered to CoLRev's package list.

~~NOTE: Need to add explanation of each process~~
__NOTE: Added better explanation of each process__

| Process         | Explanation                                             |
|:----------------|:--------------------------------------------------------|
| Review Type     | Perform Review operation                                |
| Search Source   | Tries to find out source of the provided literature     |
| Load Conversion | Converts document to record                             |
| Prep            | Prepares records based on different metadata            |
| Prep Man        | Manual preparation of record                            |
| Dedupe          | Dedups records using different sources                  |
| Prescreen       | Prescreen the records                                   |
| PDF Get         | Retrieves PDF from different sources                    |
| PDF Get Man     | Manually get PDF                                        |
| PDF Prep        | Preps PDF, validates for completeness                   |
| PDF Prep Man    | Manual preparation [Not yet implemented]                |
| Screen Package  | Screen records                                          |
| Data Package    | Export records that are not in all sources for analyses |


The interfaces for the extension endpoints are documented in the [extension interfaces](https://colrev.readthedocs.io/en/latest/foundations/extensions.html) section.

## Development process of an extension

For development and testing purpose it's better to fork CoLRev repository, setup venv with forked repository, and work
on the extension. Once the extension is developed, and working as expected, you can create a pull request to original
repo

Therefore, following steps might be a good starting point.

1. Fork and clone CoLRev
2. Setup a virtualenv
3. Install the cloned CoLRev using pip command
   ```pip install -e /path/to/cloned/colrev```

   `-e` allows editable installation. Any changes made in the clone will be available immediately
5. Create the extension repository
6. Add `.colrev_endpoints.json` file, and add the new extensions information, e.g.
   ```json
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
   ```
   This file should be in package root, so, the folder structure could be, mypy.ini and .pre-commit-config.yaml should
   be copied from CoLRev repo for following CoLRev's coding standards

    ```
   ├── project_folder
   │   ├── pyproject.toml
   │   ├── .colrev_endpoints.json
   │   ├── a_prescreen_extension
   │   │   ├── __init__.py
   │   │   ├── extension.py

   ```

7. Use the same virtualenv setup while developing the extension
8. Install the extension ```pip install -e /path/to/new/extension```
9. Complete developing the extension. Follow the recommendations:
   * Get paths from review_manager
   * Use the logger and colrev_report_logger to help users examine and validate the process, including links to the docs
     where instructions for tracing and fixing errors are available.
   * Add the `colrev-extension` topic tag on GitHub to allow others to find and use your work.
10. Register the extension to the cloned CoLRev by editing the `colrev/template/packages.json` file, commit the change
11. Run `colrev env --update_package_list` command, this should update `package_endpoints.json` and
   the `package_status.json`.
12. In case of error, `package_endpoints.json` file will be deleted. Fix the error, and
   restore the file from repo, repeat step `10` until CoLRev successfully register the extension without error
13. Tests should be implemented in the extension level first
14. Once the development is completed
    * Remove any development code
    * Do a pre-commit test
    * Push the changes to GitHub
    * Make a PR to original repo


# Testing
__TODO: add how to implement test in the extension__




CoLRev comes with batteries included, i.e., a reference implementation for all steps of the process.
At the same time you can easily include other extensions or custom scripts (batteries are swappable).
Everything is specified in the settings.json (simply add the extension/script name as the endpoint in the ``settings.json`` of the project):


.. code-block:: diff

   ...
    "screen": {
        "criteria": [],
        "screen_package_endpoints": [
            {
   -             "endpoint": "colrev.colrev_cli_screen"
   +             "endpoint": "custom_screen_script"
            }
        ]
    },
    ...

The interfaces for the extension endpoints are documented in the `extension interfaces <../foundations/extensions.html>`_ section.

Registered extensions are public Python packages that can be installed via PyPI.
An extension can have different `endpoints` (see `extension interfaces <../foundations/extensions.html>`_ for the interfaces).
Registered extensions contain a ``.colrev_endpoints.json`` file in the top-level directory (`colrev <https://github.com/CoLRev-Environment/colrev/blob/main/.colrev_endpoints.json>`_ provides an example).

To *register a new extension*:

1. Create a pull request briefly describing the extension and adding it to the `packages.json <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/template/packages.json>`_. If you add an endpoint to CoLRev (built-in), you can skip this step.

To create a new extension endpoint:

1. Add the extension endpoint to the ``.colrev_endpoints.json`` file in the project.
2. Run the ``colrev env --update_package_list`` command, which updates the `package_endpoints.json <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/template/package_endpoints.json>`_, and the `package_status.json <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/template/package_status.json>`_. This makes the extension available to CoLRev users and in the documentation.
3. Create a pull request.

**Recommendations**:

- Get paths from ``review_manager``
- Use the ``logger`` and ``colrev_report_logger`` to help users examine and validate the process, including links to the docs where instructions for tracing and fixing errors are available.
- `Add <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics>`_ the ```colrev-extension``` `topic tag on GitHub <https://github.com/topics/colrev-extension>`_ to allow others to find and use your work.

..
    Mention scripts and non-public python projects
    Check: when packages don't meet the interface specifications, they will automatically fail/be excluded


.. toctree::
   :maxdepth: 3
   :caption: Extension development resources

   extensions/development
   extensions/python
   extensions/r
   extensions/custom_extensions
