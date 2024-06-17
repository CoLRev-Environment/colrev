# CoLRev release checklist

Additional checks for major releasese:

- Update the Github milestones, close current one, make plans for the next milestones
- Go through the [cli/help pages](https://colrev.readthedocs.io/en/latest/manual/cli.html) and check the order etc.
- Update Docker image versions and test.

For all releases:

- Run `make linkcheck` in the docs, check `docs/build/linkcheck/output.txt` and fix broken links.
- Run [poetry update on GitHub](https://github.com/CoLRev-Environment/colrev/actions/workflows/poetry_update.yml).
- Change released to `True` for the migration script in `ops/upgrade.py`, add a new migration script.
- Update `settings.py - _add_missing_attributes()` to prevent exceptions.
- Update the version in `pyproject.toml`. Check whether other parts of the `pyproject.toml` need to be updated. Check whether dependencies can be removed.
- Update version in `tests/0_core/review_manager_test.py`
- Run `colrev env --update_package_list`.
- Collect release notes and update the `CHANGELOG.md`.
- Update **version** and **date**  and date in `CITATION.cff`.
- Update version in `SECURITY.md`.
- Check: `pyproject.toml` cannot have direct depdencies (Github)
- Run `pip3 install -e .` locally (before testing upgrade in local repositories).
- Commit the changes (`release 0.10.0`).
- Check whether the pre-commit hooks and tests pass locally (``pre-commit run --all``).
- Push to Github. Check whether the installation, tests, and pre-commit hooks pass.
- Run `git tag -s $VERSION` (format: "0.9.1").
- Run `git push` and wait for the GitHub actions to complete successfully.
- Test `colrev upgrade` in local repositories (see `COLREV-UPDATE_ALL.txt`).
- Run `git push --atomic origin main $VERSION`.

- Create [new release on Github](https://github.com/CoLRev-Environment/colrev/releases/new)
    - Select new tag
    - Enter the release notes
    - Publish the release
    - The PyPI version is published through a [github action](https://github.com/CoLRev-Environment/colrev/actions/workflows/publish.yml):  ![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/CoLRev-Ecosystem/colrev/publish.yml)
    - The zenodo version is published automatically
    - Trigger/test the Github-action in a curated metadata repository (using ``colrev-batch-gh-api.py``)

- Update the Zenodo doi in `README.md` and `CITATION.cff`
- Update [example repository](https://github.com/CoLRev-Environment/example) if necessary
- Update the release in the devcontainer of [colrev-template](https://github.com/CoLRev-Environment/colrev-template)

```
mkdir example && cd example
colrev init --example
colrev load
colrev prep
colrev dedupe
colrev prescreen --include_all
colrev pdfs
colrev pdfs --discard
colrev screen --include_all
colrev data
# Manually edit data/data/paper.md
git remote add origin git@github.com:CoLRev-Environment/example.git
git push --set-upstream origin main -f
```
