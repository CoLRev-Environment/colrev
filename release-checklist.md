# CoLRev release checklist

- Run `make linkcheck` in the docs and fix broken links.
- Run `poetry update`.
- Update Docker image versions and test.
- Collect release notes and update the `CHANGELOG.md`.
- Update version in `CITATION.cff`.
- Update the version in `pyproject.toml`.
- Commit the changes and push to Github. Check whether the installation, tests, and pre-commit hooks pass.
- Run `git evtag sign v$VERSION`.
- Run `git push --atomic origin main v$VERSION`.

- Create [new release on Github](https://github.com/CoLRev-Ecosystem/colrev/releases/new)
    - Select new tag
    - Enter the release notes
    - Publish the release
    - The PyPI version is published through github actions
    - The zenodo version is published automatically

- Run `pip3 install -e .` locally
- Add a new migration script in `ops/upgrade.py`
- Update the [roadmap](https://colrev.readthedocs.io/en/latest/foundations/roadmap.html)
- Run colrev upgrade in local repositories
