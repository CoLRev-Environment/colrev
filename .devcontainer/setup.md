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

```
# Select modules from the EXPLORER, edit them, and test the changes
# Run pre-commit hooks (including tests) and address messages to improve code quality
pcr
# short form for "pre-commit run --all-files" (automatically available in the .bash_aliases file)
# Add selected changes to the Git staging area
git add -p *
# Review the changes to make sure that the next commit will be atomic (Git button on the left)
# Commit 
git commit -m 'message'

```

Note: the pre-commit hooks have a long runtime, but useful messages are displayed early. 

TODO :
- add notes on CoLRev development
- running individual tests
- check whether committed changes need to be pushed
- Link to html version, include a screenshot and highlight the buttons that we refer to