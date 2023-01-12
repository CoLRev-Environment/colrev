<p align="center">
<img src="../../figures/logo_small.png" width="400">
</p>

# Collaborative Literature Reviews (CoLRev)

[![License](https://img.shields.io/github/license/geritwagner/colrev.svg)](https://github.com/geritwagner/colrev/releases/)
[![Python 3.8](https://img.shields.io/badge/python-3.8-blue.svg)](https://www.python.org/downloads/release/python-380/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![GitHub release](https://img.shields.io/github/v/release/geritwagner/colrev.svg)](https://github.com/geritwagner/colrev/releases/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](https://makeapullrequest.com)

CoLRev is an open-source environment for collaborative reviews.
To make major improvements in terms of efficiency and trustworthiness and to automatically augment reviews with community-curated content, CoLRev advances the design of review technology at the intersection of methods, engineering, cognition, and community building.
Compared to other environments, the following features stand out:

- an **extensible and open platform** based on shared data and process standards
- builds on **git** and its transparent collaboration model for the entire literature review process
- offers a **self-explanatory, fault-tolerant, and configurable** user workflow
- implements a granular **data provenance** model and **robust identification** schemes
- provides **end-to-end process support** and allows you to **plug in state-of-the-art tools**
- enables **typological and methodological pluralism** throughout the process
- operates a **built-in model for content curation** and reuse

## Getting started

After installing [git](https://git-scm.com/) and [docker](https://www.docker.com/):

```
# Install
git clone https://github.com/geritwagner/colrev && cd colrev && pip install .
# or
pip install colrev

# ... and start with the main command
colrev status
```

**The workflow** consists of three steps. This is all you need to remember. The status command displays the current state of the review and guides you to the next [operation](docs/build/user_resources/manual.html).
After each operation, [validate the changes](docs/build/user_resources/manual/1_workflow.html#colrev-validate).

<p align="center">
<img src="../../figures/workflow.svg" width="700">
</p>

<!-- .. figure:: docs/figures/workflow.svg
   :width: 600
   :align: center
   :alt: Workflow cycle -->

**The operations** allow you to complete a literature review. It should be as simple as running the following commands:

```
# Initialize the project, formulate the objectives, specify the review type
colrev init

# Store search results in the data/search directory
# Load, prepare, and deduplicate the metadata reocrds
colrev retrieve

# Conduct a prescreen
colrev prescreen

# Get and prepare the PDFs
colrev pdfs

# Conduct a screen based on PDFs
colrev screen

# Complete the forms of data analysis and synthesis, as specified in the settings
colrev data

```

For each operation, the **colrev settings** document the tools and parameters. You can rely on the built-in reference implementation of colrev, specify external tools, or include custom scripts. The settings are adapted to the type of review and suggest reasonable defaults. You have the option to customize and adapt.


<p align="center">
<img src="../../figures/settings.svg" width="700">
</p>

<!-- .. figure:: ../figures/settings.svg
   :width: 600
   :align: center
   :alt: Settings -->


**The project collaboration loop** allows you to synchronize the project repository with your team.
The *colrev pull* and *colrev push* operations make it easy to collaborate on a specific project while reusing and updating record data from multiple curated repositories.
In essence, a CoLRev repository is a git repository that follows the CoLRev data standard and is augmented with a record-level curation loop.

**The record curation loop** proposes a new vision for the review process.
Reuse of community-curated data from different sources is built into each operation.
It can substantially reduce required efforts and improve richness, e.g., through annotations of methods, theories, and findings.
The more records are curated, the more you can focus on the synthesis.


<p align="center">
<img src="../../figures/reuse-vision_loop.svg" width="800">
</p>

<!-- .. figure:: ../figures/reuse-vision_loop.svg
   :width: 800
   :align: center
   :alt: Reuse vision -->

Further information is provided in the [documentation](docs/source/index.rst), the developer [api reference](docs/build/technical_documentation/api.html), and the [CoLRev framework](docs/build/technical_documentation/colrev.html) summarizing the scientific foundations.

## Contributing, changes, and releases

Contributions, code and features are always welcome

- See [contributing guidelines](CONTRIBUTING.md), [help page](docs/build/user_resources/help.html), and [github repository](https://github.com/geritwagner/colrev).
- Bug reports or feedback? Please use the [issue tracker](https://github.com/geritwagner/colrev/issues) and let us know.
- To get your work included, fork the repository, implement your changes, and create a [pull request](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests).

For further information, see [changes](CHANGELOG.md) and [releases](https://github.com/geritwagner/colrev/releases).

## License

This project is distributed under the [MIT License](LICENSE) the documentation is distributed under the [CC-0](https://creativecommons.org/publicdomain/zero/1.0/) license.
If you contribute to the project, you agree to share your contribution following these licenses.

## Citing CoLRev

Please [cite](docs/_static/colrev_citation.bib) the project as follows:

Wagner, G. and Prester, J. (2022) CoLRev - A Framework for Collaborative Literature Reviews. Available at https://github.com/geritwagner/colrev.
