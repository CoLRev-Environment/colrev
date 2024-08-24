# Documentation

[![Documentation Status](https://readthedocs.org/projects/colrev/badge/?version=latest)](https://colrev.readthedocs.io/en/latest/?badge=latest)

To build the documentation locally, run

```
make clean
make html
make linkcheck
```

When errors occur during `make html`, it can help to delete the `colrev/docs/source/foundations/_autosummary` and rerun `make html`.

Once available on Github, the documentation is automatically published at [readthedocs](https://colrev.readthedocs.io/en/latest/) (status information is available [here](https://readthedocs.org/projects/colrev/builds/)).


```
python -m sphinx.ext.intersphinx https://colrev.readthedocs.io/en/stable/objects.inv
```

## Asciinema cli recordings

Use [asciinema](https://docs.asciinema.org/getting-started/) to record cli sessions.

Create the gif based on agg:

```
docker run --rm -it -u $(id -u):$(id -g) -v $PWD:/data agg colrev_demo.cast --font-size 20 --cols 130 demo.gif
```
