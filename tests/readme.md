# Unit tests

- The tests should be completed quickly.
- Core functionality and extensions (including the built-in reference implementation) should be tested separately.
- It should be easy to analyze failed tests and to add test cases.
- After running the following commands, a detailed coverage report is available at ``htmlcov/index.html``

```
pytest
coverage run -m pytest
coverage html
rm coverage.svg
coverage-badge -o coverage.svg
```
