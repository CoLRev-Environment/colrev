# Unit tests

![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/CoLRev-Ecosystem/colrev/tests.yml)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/CoLRev-Ecosystem/colrev/main.svg)](https://results.pre-commit.ci/latest/github/CoLRev-Ecosystem/colrev/main)
![Coverage](https://raw.githubusercontent.com/CoLRev-Ecosystem/colrev/main/tests/coverage.svg)

- The tests should be completed quickly.
- Core functionality and extensions (including the built-in reference implementation) should be tested separately.
- It should be easy to analyze failed tests and to add test cases.
- After running the following commands, a detailed coverage report is available at ``htmlcov/index.html``

```
coverage run -m pytest
coverage html
rm tests/coverage.svg
coverage-badge -o tests/coverage.svg

# Keep tests short (check the ones that take most of the time)
pytest --durations=5

# Run individual test modules
pytest tests/0_core/record_test.py
# Run individual test methods
pytest tests/0_core/record_test.py -k "test_update_metadata_status"
```

Note: after each test, conf.run_around_tests() restores the state of the repository (even if tests fail!). For debugging, it may be helpful to deactivate the code temporarily.


References

- [Effective Python Testing With Pytest](https://realpython.com/pytest-python-testing/)
