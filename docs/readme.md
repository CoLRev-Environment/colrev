# Documentation

To build the documentation, run

```
make clean
make html
make linkcheck
```

When errors occur during `make html`, it can help to delete the `colrev/docs/source/_autosummary` and rerun `make html`.
