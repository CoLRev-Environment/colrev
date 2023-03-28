# CoLRev release checklist

- Run `make linkcheck` in the docs and fix broken links.
- Run `poetry update`.
- Change released to `True` for the migration script in `ops/upgrade.py`, add a new migration script
- Update version in `tests/2_ops/ops_test.py`
- Run `colrev env --update_package_list`.
- Update Docker image versions and test.
- Collect release notes and update the `CHANGELOG.md`.
- Update version in `CITATION.cff`.
- Update the version in `pyproject.toml`. Check whether other parts of the `pyproject.toml` need to be updated.
- Update the [roadmap](https://colrev.readthedocs.io/en/latest/foundations/roadmap.html)
- Commit the changes.
- Push to Github. Check whether the installation, tests, and pre-commit hooks pass.
- Run `git tag -s $VERSION`.
- Run `pip3 install -e .` locally (before testing upgrade in local repositories).
- Test `colrev upgrade` in local repositories
- Run `git push --atomic origin main $VERSION`.

- Create [new release on Github](https://github.com/CoLRev-Environment/colrev/releases/new)
    - Select new tag
    - Enter the release notes
    - Publish the release
    - The PyPI version is published through a [github action](https://github.com/CoLRev-Environment/colrev/actions/workflows/publish.yml):  ![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/CoLRev-Ecosystem/colrev/publish.yml)
    - The zenodo version is published automatically
    - Trigger/test the Github-action in a curated metadata repository
