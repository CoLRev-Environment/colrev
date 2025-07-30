"""Pre-commit-hooks interface, automatically set up for every CoLRev project:

.. code-block:: yaml

    default_language_version:
        python: python3

    # colrev hooks are not (yet) available in pre-commit-ci
    ci:
        skip: [colrev-hooks-format, colrev-hooks-check]

    repos:
    -   repo: local
        hooks:
        -   id: colrev-hooks-format
            name: "CoLRev ReviewManager: format"
            entry: colrev-hooks-format
            language: python
            stages: [commit]
            pass_filenames: false
        -   id: colrev-hooks-check
            name: "CoLRev ReviewManager: check"
            entry: colrev-hooks-check
            language: python
            stages: [commit]
            pass_filenames: false
        -   id: colrev-hooks-report
            name: "CoLRev ReviewManager: report"
            entry: colrev-hooks-report
            language: python
            stages: [prepare-commit-msg]
        -   id: colrev-hooks-share
            name: "CoLRev ReviewManager: share"
            entry: colrev-hooks-share
            language: python
            stages: [push]
            pass_filenames: false"""

__author__ = """Gerit Wagner"""
__email__ = "gerit.wagner@uni-bamberg.de"
