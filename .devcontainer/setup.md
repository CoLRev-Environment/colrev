# CoLRev development

## Codespaces

- Start the codespace session on your target branch/fork.
- Remember to [stop](https://docs.github.com/de/codespaces/developing-in-a-codespace/stopping-and-starting-a-codespace) the codespace after the development session.
- **Warning**: If you *delete* the codespace, your changes are deleted.

## Project vs. package directory

The `.../colrev (main)` directory is the **package directory** containing the functionality.

CoLRev projects are created in a separate **project directory** containing the data.
To create a project directory, create a separate terminal (`+` button on the right) and run the following commands:

```
cd ..
mkdir test_project
cd test_project
colrev init
```

The project directory can be used to test your changes to the CoLRev code (in the package directory).

When running a `colrev` command in the project directory (or any other directory), the current code from the package directory is used because it was set up using the `pip install -e .` command. With this command, the pip Python package manager makes the CoLRev package available on the system in editable mode, i.e., changes to the package are available when using a `colrev` command in the project directory.

Note: you can check the setup by running `pip list` and `pip show colrev`.

## Development best practices

Changes/commits/tests/git graph (local?)

TODO :
- TBD: pip install -e .?
- add notes on CoLRev development
- add bash alias (e.g., pcr)
- running individual tests
