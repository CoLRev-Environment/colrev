# Literature review template

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

_Currently an alpha-version focused on the command-line._


- Git-based (collaborative) literature reviews
- Easy to learn: one command, `review_template status`, provides an overview and contextual instructions
- Collaboration protocols and consistency checks (pre-commit hooks) aimed at preventing git conflicts
- Traceability of records and changesets
- Designed with methodological and typological pluralism in mind: configurable templates for
  - Informal literature reviews (e.g., for a related work section) or
  - Standalone review papers requiring extraction and analysis of structured data (e.g., critical reviews, descriptive reviews, meta-analysis, qualitative systematic reviews, realist reviews)
  - Standalone review papers requiring interpretive analyses and syntheses of (semi) structured data (e.g., narrative reviews, scoping reviews, theoretical reviews, umbrella reviews)
- Builds on state-of-the-art algorithms
  - Import of structured reference data (BibTeX, RSI, END, CSV, XLSX, based on bibutils) and unstructured reference data (TXT, PDF, based on GROBID)
  - Metadata consolidation based on crossref
  - Identification of duplicates based on active learning (python dedupe)
  - Algorithms for machine-readability of PDFs (ocrmypdf) and annotation (GROBID)
- Cross-platform, open-source, tested, and extensible


# Installation

Requirements: [git](https://git-scm.com/downloads), [a git gui](https://git-scm.com/downloads), [Docker](https://www.docker.com/), [Python 3](https://www.python.org/), and [pip](https://pypi.org/project/pip/).

```
# Installation (currently, while not yet available via pip)
git clone https://github.com/geritwagner/review_template
cd review_template
pip3 install --user -e .
# Once the project is available on PyPI:
# pip install review_template

```

# Usage (CLI)

On the command line iteratively use the following commands:

- `review_template status`: provides an overview of the state of the pipeline and suggests the next steps related to processing (`review_template ...`) and collaboration (`git ...`)
- `review_template COMMAND`: task that processes or analyzes records (e.g., `review_template init`, `review_template process`)
- `git COMMAND`: manage and analyze file versions and collaboration (e.g., `git status`, `git push`, `git pull`)

The goal is that `review_template status` provides contextual instructions for all `review_template ...` and `git ...` commands (simple copy and paste).
Further information is provided in the documentation (add-link).

Example:

### `review_template status`


![Status command and explanation](docs/figures/status_explanation.PNG?raw=true)


### `review_template COMMANDs`

```bash
$review_template
Usage: review_template [OPTIONS] COMMAND [ARGS]...

  Review template pipeline

  Main commands: init | status | process, screen, ...

Options:
  --help  Show this message and exit.

Commands:
  init         Initialize repository
  status       Show status
  process      Process pipeline
  man-comp     Complete records manually
  man-prep     Prepare records manually
  man-dedupe   Process duplicates manually
  prescreen    Execute pre-screen
  screen       Execute screen
  pdfs         Acquire PDFs
  pdf-check    Check PDFs
  back-search  Execute backward search based on PDFs
  data         Execute data extraction
  profile      Generate a sample profile
  validate     Validate changes
  trace        Trace an entry
```

### `git COMMANDs`

For non-expert users of git, the following commands will be suggested depending on the state of the repository:

- `git status` to inspect the state of the local repository
- `gitk` to visualize changes
- `git push` to upload changes to a shared repository
- `git pull` to retrieve changes from a shared repository


# Development status, release, and changes

Note: The status of the pipeline is developmental.
None of the scripts has been tested extensively.
See the [changelog](CHANGELOG.md).

# Contributing

- See [contributing guidelines](CONTRIBUTING.rst).

- Bug reports or feedback? Please use the [issue tracker](https://github.com/geritwagner/review_template/issues) and let us know.

- You are welcome to contribute code and features. To get your work included, fork the repository, implement your changes, and create a [pull request](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests).

# License

MIT License.
