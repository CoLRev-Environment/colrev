Using Extensions
=====================

CoLRev comes with batteries included, i.e., a reference implementation for all steps of the process. At the same time you can easily include other extensions or custom scripts (batteries are swappable). Everything is specified in the settings.json (simply add the extension/script name as the endpoint in the ``settings.json`` of the project):


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

The interfaces for the extension endpoints are documented in the :ref:`extension interfaces <extension interfaces>` section.

Registered extensions are public Python packages that can be installed via PyPI. An extension can have different `endpoints` (see :ref:`extension interfaces <extension interfaces>` for the interfaces). Registered extensions contain a ``.colrev_endpoints.json`` file in the package directory (`colrev <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/.colrev_endpoints.json>`_ provides an example).

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
