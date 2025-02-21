# Contributing

Contributions are welcome, and they are greatly appreciated! Every little bit
helps, and credit will always be given.

You can contribute in many ways:

## Types of Contributions

### Report Bugs

Report bugs at https://github.com/CoLRev-Environment/colrev/issues.

If you are reporting a bug, please include:

* Your operating system name and version.
* Any details about your local setup that might be helpful in troubleshooting.
* Detailed steps to reproduce the bug.

### Fix Bugs

Look through the GitHub issues for bugs. Anything tagged with "bug" and "help
wanted" is open to whoever wants to implement it.

### Implement Features

Look through the GitHub issues for features. Anything tagged with "enhancement"
and "help wanted" is open to whoever wants to implement it.

### Write Documentation

CoLRev could always use more documentation, whether as part of the
official CoLRev docs, in docstrings, or even on the web in blog posts,
articles, and such.

#### Submit Feedback

The best way to send feedback is to file an issue at https://github.com/CoLRev-Environment/colrev/issues.

If you are proposing a feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible, to make it easier to implement.
* Remember that this is a volunteer-driven project, and that contributions are welcome :)

## Get Started!

Ready to contribute? Here's how to set up `colrev` for local development.

1. Fork the `colrev` repo on GitHub.
2. Clone your fork locally:

    ```
    git clone git@github.com:your_name_here/colrev.git
    ```

3. Install your local copy into a virtualenv. Assuming you have uv installed, this is how you set up your fork for local development:

    ```
    uv venv
    uv pip install --editable .
    ```

4. Create a branch for local development:

    ```
    git checkout -b name-of-your-bugfix-or-feature
    ```

   Now you can make your changes locally.

5. When you're done making changes, check that your changes pass the
   tests and pre-commit hooks:

    ```
    pytest
    pre-commit run -a
    ```

6. Commit your changes and push your branch to GitHub:

    ```
    git add .
    git commit -m "Your detailed description of your changes."
    git push origin name-of-your-bugfix-or-feature
    ```

7. Submit a pull request through the GitHub website.

## Troubleshooting

### If you get error regarding mock being not available

Install `pytest-mock`

```
pip install pytest-mock
```

### If you get invalid cross-device link error

It is because the `/tmp` folder is not in same drive as your home drive. Use `pytest --basetemp=<a_path_inside_your_home_folder>`

Beware, everything inside the folder will be deleted, so make sure you use the folder only for test.

### Iterative testing

To test and develop code, it may be helpful to use an example dataset (CoLRev repository) with chained commands, which automatically reset to the previous version and repeat the operation. For example, such a command could look like this:

```
git reset --hard faaf5d7f5e6 && colrev prep && gitk
```

## Pull Request Guidelines

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests.
2. If the pull request adds functionality, the docs should be updated. Put
   your new functionality into a function with a docstring, and add the
   feature to the list in README.rst.
3. The pull request should work for Python 3.5, 3.6, 3.7 and 3.8, and for PyPy. Check
   https://travis-ci.com/CoLRev-Ecosystem/colrev/pull_requests
   and make sure that the tests pass for all supported Python versions.

## Add yourself as Contributor

Colrev uses `@all-contributors` to add contributors. You can add yourself as contributor by commenting on an Issue or
Pull Request, by asking @all-contributors:

```
@all-contributors please add @<username> for <contributions>
```

[Bot usage](https://allcontributors.org/docs/en/bot/usage)

## Coding standards

- Named parameters are preferred over positional parameters to avoid ambiguity and facilitate code refactoring.
- Variable names should help to avoid ambiguities and indicate their type if necessary (e.g., record for colrev.record.record.Record and record_dict for dicts).
- All tests and code linters (pre-commit-hooks) should pass.

## Release

See [release checklist](release-checklist.md).
