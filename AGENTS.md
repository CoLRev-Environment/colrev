# Repository guidance

## Project structure

- This is the `colrev` Python package (Python 3.10–3.13), with the CLI entry point at `colrev.ui_cli.cli:main`.
- Core workflow and domain code lives under `colrev/` (`ops/`, `record/`, `review_manager.py`, etc.). `colrev/packages/` contains endpoint extensions, many with their own `pyproject.toml`; the package manager discovers installed extensions through Python entry points.
- Tests are grouped by subsystem under `tests/` (including `0_core/`, `0_record/`, `1_env/`, `2_loader/`, `3_packages_search/`, and `review_manager/`). There is also a top-level `tests/cli_test.py`. Test data is in `tests/data/`.

## Python environment

- Use `uv` for dependency management and command execution, and use the project's `.venv` rather than a globally activated Python environment.
- Run checks and project commands with `uv run`.
- If `VIRTUAL_ENV` points to another environment, prefix commands with `env -u VIRTUAL_ENV`, for example `env -u VIRTUAL_ENV uv run pytest tests/0_record/record_test.py`.
- Do not use `uv run --active` or hardcode user-specific virtual environment paths.

## Development and verification

- Use `uv sync --all-extras --dev` to set up the project and development dependencies.
- Run one module with `uv run pytest tests/0_record/record_test.py`; narrow further with `-k "test_name"`. The default pytest run is the quick suite; use `uv run pytest tests --slow` for the full slower suite.
- Run formatting and lint/type checks with `uv run pre-commit run --all-files`. Hooks include autoflake, Black, Pyupgrade, Ruff, Flake8, Mypy, and Pylint, plus an always-run pytest hook. Autoflake, Black, and Ruff may modify files; Pylint is scoped to `colrev/`, while Mypy also checks tests.
- For coverage, see `tests/readme.md` (`uv run coverage run -m pytest`, then `uv run coverage html`).

## Test behavior

- Review `tests/readme.md` for focused test workflows. `tests/review_manager/conftest.py` resets a temporary Git test repository after each test, including `git clean -df`; account for its cleanup and commit resets when debugging state changes.
- Tests under `tests/review_manager/` use an autouse fixture that initializes a `colrev.literature_review` project. Install that package first with `uv run colrev install --uv colrev.literature_review` (or install all internal packages) before running these tests.
- Some tests exercise optional/installed endpoint packages and external service integrations. CI installs endpoint packages with `uv run colrev install --uv <package identifiers>` before package-dependent tests; install relevant packages before interpreting missing-package failures.

## Code conventions

- Prefer named arguments for clarity. Use `record` for `colrev.record.record.Record` objects and `record_dict` for plain dictionaries where both occur.
- Keep endpoint-specific changes in the relevant `colrev/packages/<endpoint>/` package and its tests rather than adding endpoint behavior to unrelated core modules.
