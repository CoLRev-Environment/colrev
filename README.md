# Literature review template

[![License](https://img.shields.io/github/license/geritwagner/review_template.svg)](https://github.com/geritwagner/review_template/releases/)
[![Python 3.8](https://img.shields.io/badge/python-3.8-blue.svg)](https://www.python.org/downloads/release/python-380/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![GitHub release](https://img.shields.io/github/v/release/geritwagner/review_template.svg)](https://github.com/geritwagner/review_template/releases/)

- Git-based collaborative literature reviews
- Easy to learn: one command, `review_template status`, provides an overview and instructions
- Collaboration protocols and consistency checks ([pre-commit hooks](https://github.com/geritwagner/pipeline-validation-hooks)) aimed at preventing git conflicts
- Traceability of records and changes
- Designed with methodological and typological pluralism in mind: configurable templates for
  - Informal literature reviews (e.g., for a related work section) or
  - Standalone review papers requiring extraction and analysis of structured data (e.g., critical reviews, descriptive reviews, meta-analysis, qualitative systematic reviews, realist reviews)
  - Standalone review papers requiring interpretive analyses and syntheses of (semi) structured data (e.g., narrative reviews, scoping reviews, theoretical reviews, umbrella reviews)
- Builds on state-of-the-art algorithms and benefits from their ongoing improvement
  - Import of structured reference data (BibTeX, RSI, END, CSV, XLSX, based on bibutils) and unstructured reference data (TXT, PDF, based on GROBID)
  - Metadata consolidation based on crossref/doi.org and DBLP
  - Algorithms for machine-readability of PDFs (ocrmypdf) and annotation (GROBID)
- Cross-platform, open-source, tested, and extensible

_Currently an alpha-version focused on the command-line. None of the scripts has been tested extensively._

# Installation and usage

Requirements: [git](https://git-scm.com/downloads), [Docker](https://www.docker.com/), [Python 3](https://www.python.org/), and [pip](https://pypi.org/project/pip/).

```
# Installation (currently, while not yet available via pip)
git clone https://github.com/geritwagner/review_template
cd review_template
pip3 install --user -e .
# Once the project is available on PyPI:
# pip install review_template
```

On the command line, use the following command:

- `review_template status`: provides an overview of the state of the pipeline and suggests the next processing and versioning/collaboration steps (simply copy and paste).

![Status command and explanation](docs/figures/status_explanation.PNG?raw=true)

Further information is available in the documentation (add-link).
For the processing, the following `review_template commands` are available.

```bash
/home/user/repository$review_template
Usage: review_template [OPTIONS] COMMAND [ARGS]...

  Review template pipeline

  Main commands: init | status | process, screen, ...

Options:
  --help  Show this message and exit.

Commands:
  init         Initialize repository
  status       Show status
  process      Process records (automated steps)
  importer     Import records (part of automated processing)
  prepare      Prepare records (part of automated processing)
  dedupe       Deduplicate records (part of automated processing)
  man-prep     Manual preparation of records
  man-dedupe   Manual processing of duplicates
  prescreen    Pre-screen based on titles and abstracts
  screen       Screen based on exclusion criteria and fulltext documents
  pdfs         Retrieve PDFs (part of automated processing)
  pdf-prepare  Prepare PDFs (part of automated processing)
  back-search  Backward search based on PDFs
  data         Extract data
  profile      Generate a sample profile
  validate     Validate changes
  trace        Trace a record
  paper        Build the paper
```

# Credits

We build on the shoulders of amazing projects (growing giants) and benefit from their ongoing improvements

- [GitPython](https://github.com/gitpython-developers/GitPython), which is available under the [BSD 3-Clause License](https://github.com/gitpython-developers/GitPython/blob/main/LICENSE). [![GitPython](https://img.shields.io/github/commit-activity/y/gitpython-developers/GitPython?color=green&style=plastic)](https://github.com/gitpython-developers/GitPython)
- [pre-commit](https://github.com/pre-commit/pre-commit), which is available under the [MIT License](https://github.com/pre-commit/pre-commit/blob/master/LICENSE). [![pre-commit](https://img.shields.io/github/commit-activity/y/pre-commit/pre-commit?color=green&style=plastic)](https://github.com/pre-commit/pre-commit.six)
- [docker-py](https://github.com/docker/docker-py), which is available under the [Apache-2.0 License](https://github.com/docker/docker-py/blob/master/LICENSE). [![docker-py](https://img.shields.io/github/commit-activity/y/docker/docker-py?color=green&style=plastic)](https://github.com/docker/docker-py)
- [pandas](https://github.com/pandas-dev/pandas), which is available under the [BSD 3-Clause License](https://github.com/pandas-dev/pandas/blob/master/LICENSE). [![pandas](https://img.shields.io/github/commit-activity/y/pandas-dev/pandas?color=green&style=plastic)](https://github.com/pandas-dev/pandas)
- [PDFMiner.six](https://github.com/pdfminer/pdfminer.six), which is available under the [MIT License](https://github.com/pdfminer/pdfminer.six/blob/develop/LICENSE). [![PDFMiner.six](https://img.shields.io/github/commit-activity/y/pdfminer/pdfminer.six?color=green&style=plastic)](https://github.com/pdfminer/pdfminer.six)
- [bibtexparser](https://github.com/sciunto-org/python-bibtexparser), which is available under the [BSD License](https://github.com/sciunto-org/python-bibtexparser/blob/master/COPYING).

Dynamically loaded

- [git](https://github.com/git/git), which is available under the [GNU Public License 2 (GPL 2)](https://github.com/git/git/blob/master/COPYING). [![git](https://img.shields.io/github/commit-activity/y/git/git?color=green&style=plastic)](https://github.com/git/git)
- [GROBID](https://github.com/kermitt2/grobid), which is available under the [Apache 2.0 License](https://github.com/kermitt2/grobid/blob/master/LICENSE). [![GROBID](https://img.shields.io/github/commit-activity/y/kermitt2/grobid?color=green&style=plastic)](https://github.com/kermitt2/grobid)
- [OCRmyPDF](https://github.com/jbarlow83/OCRmyPDF), which is available under the [Mozilla Public License 2.0 (MPL-2.0)](https://github.com/jbarlow83/OCRmyPDF/blob/master/LICENSE). [![ocrmypdf](https://img.shields.io/github/commit-activity/y/jbarlow83/OCRmyPDF?color=green&style=plastic)](https://github.com/jbarlow83/OCRmyPDF)
- [pandoc](https://github.com/jgm/pandoc), which is available under the [GNU Public License 2 (GPL 2)](https://github.com/jgm/pandoc/blob/master/COPYRIGHT). [![ocrmypdf](https://img.shields.io/github/commit-activity/y/jgm/pandoc?color=green&style=plastic)](https://github.com/jgm/pandoc)
- [bibutils](http://bibutils.refbase.org/), which is available under the [GNU Public License (GPL)](http://bibutils.refbase.org/).

For meta-data preparation and PDF retrieval, we rely on the following data sources

- [Crossref](https://www.crossref.org/) with over 125,000,000 curated metadata records across disciplines
- [Semantic Scholar](https://www.semanticscholar.org/) with over 175,000,000 records across disciplines
- [dblp](https://dblp.org/) with over 5,750,000 curated metadata records in the IT/IS disciplines
- [Unpaywall](https://unpaywall.org/) with over 30,000,000 free papers

# Contributing, changes, and releases


Contributions, code and features are always welcome

- See [contributing guidelines](CONTRIBUTING.rst).
- Bug reports or feedback? Please use the [issue tracker](https://github.com/geritwagner/review_template/issues) and let us know.
- To get your work included, fork the repository, implement your changes, and create a [pull request](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests).

For further information, see [changes](CHANGELOG.md) and [releases](https://github.com/geritwagner/review_template/releases).

# License

This project is distributed under the [MIT License](LICENSE) the documentation is distributed under the [CC-0](https://creativecommons.org/publicdomain/zero/1.0/) license.
If you contribute to the project, you agree to share your contribution following these licenses.
