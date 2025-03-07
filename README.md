
<p align="center">
<img src="https://raw.githubusercontent.com/CoLRev-Ecosystem/colrev/main/docs/figures/logo_small.png" width="400">
</p>

<div align="center">

[![DOI](https://zenodo.org/badge/363073613.svg)](https://zenodo.org/badge/latestdoi/363073613)
[![PyPI - Version](https://img.shields.io/pypi/v/colrev?color=blue)](https://pypi.org/project/colrev/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/colrev)
[![License](https://img.shields.io/github/license/CoLRev-Ecosystem/colrev.svg)](https://github.com/CoLRev-Environment/colrev/releases/)
![Documentation Status](https://img.shields.io/github/actions/workflow/status/CoLRev-Ecosystem/colrev/docs_deploy.yml?label=documentation)
![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/CoLRev-Ecosystem/colrev/tests.yml?label=tests)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/CoLRev-Ecosystem/colrev/main.svg)](https://results.pre-commit.ci/latest/github/CoLRev-Ecosystem/colrev/main)
![Coverage](https://raw.githubusercontent.com/CoLRev-Ecosystem/colrev/main/tests/coverage.svg)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/bd4e44c6cda646e4b9e494c4c4d9487b)](https://app.codacy.com/gh/CoLRev-Environment/colrev/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
![GitHub last commit](https://img.shields.io/github/last-commit/CoLRev-Ecosystem/colrev)
[![Downloads](https://static.pepy.tech/badge/colrev/month)](https://pepy.tech/project/colrev)
[![OpenSSF Best Practices](https://bestpractices.coreinfrastructure.org/projects/7148/badge)](https://bestpractices.coreinfrastructure.org/projects/7148)
[![SWH](https://archive.softwareheritage.org/badge/origin/https://github.com/CoLRev-Environment/colrev/)](https://archive.softwareheritage.org/browse/origin/?origin_url=https://github.com/CoLRev-Environment/colrev/)<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/badge/all_contributors-32-green.svg?style=flat-square)](#contributors)
<!-- ALL-CONTRIBUTORS-BADGE:END -->
<!-- ![PyPI](https://img.shields.io/pypi/v/colrev) -->

</div>

# Collaborative Literature Reviews (CoLRev)

CoLRev is an open-source environment for collaborative literature reviews. It integrates with differerent synthesis tools, takes care of the data, and facilitates Git-based collaboration.

To accomplish these goals, CoLRev advances the design of review technology at the intersection of methods, design, cognition, and community building.
The following features stand out:

- Supports all literature review steps: problem formulation, search, dedupe, (pre)screen, pdf retrieval and preparation, and synthesis
- An open and extensible environment based on shared data and process standards
- Builds on git and its transparent collaboration model for the entire literature review process
- Offers a self-explanatory, fault-tolerant, and configurable user workflow
- Operates a model for data quality, content curation, and reuse
- Enables typological and methodological pluralism throughout the process

![Demo](docs/source/_static/demo.gif)

For details, consult the [documentation](https://colrev-environment.github.io/colrev/).

## Demo

You can try a live demonstration of CoLRev via GitHub codespaces: [start demo](https://github.com//codespaces/new?hide_repo_select=true&ref=main&repo=767717822).

## Related work (preview)

The following shows a comparison of CoLRev with related tools.

> [!Note]
> **This is a preview.** We plan to document and link the criteria, verify each cell, and invite the developers of the other tools to comment on the overview (documenting responses if the developers agree).

<!--
inspiration: https://github.com/lycheeverse/lychee?tab=readme-ov-file
TODO : link (maybe present a short version) and reprint in the docs
focus on "workflow platforms", i.e., software that supports the search, selection, data extraction steps (end-to-end)
present short version, long version in the docs
-->

| **Criteria**                                  | **CoLRev**                        | [**LitStudy**](https://github.com/NLeSC/litstudy)  | [**BUHOS**](https://github.com/clbustos/buhos)  | [**Covidence**](https://www.covidence.org/)   |
|-----------------------------------------------|-----------------------------------|----------------------------------|---------------------------------|---------------------------------|
| **Review types**                              |                                   |                                  |                                 |                                 |
| Supports different genres of review methods   | ![yes]                            | ![no]                            | ![no]                           | ![no]                           |
| Extensibility                                 | ![yes]                            | ![maybe]                         | ![maybe]                        | ![no]                           |
| **Process steps**                             |                                   |                                  |                                 |                                 |
| Review objectives and protocol                | ![yes]                            | ![yes]                           | ![yes]                          | ![yes]                          |
| Search                                        | ![yes]                            | ![yes]                           | ![yes]                          | ![yes]                          |
| Duplicate handling                            | ![yes]                            | ![no]                            | ![maybe]                        | ![maybe]                        |
| (Pre)Screen                                   | ![yes]                            | ![maybe]                         | ![yes]                          | ![yes]                          |
| Data extraction                               | ![yes]                            | ![maybe]                         | ![yes]                          | ![yes]                          |
| Data analysis and quality appraisal           | ![yes]                            | ![maybe]                         | ![yes]                          | ![yes]                          |
| Synthesis and reporting                       | ![yes]                            | ![yes]                           | ![yes]                          | ![yes]                          |
| **Process qualities**                         |                                   |                                  |                                 |                                 |
| Extensibility                                 | ![yes]                            | ![yes]                           | ![no]                           | ![no]                           |
| Extensions                                    | 102                               | 0                                | 0                               | 0                               |
| Search updates                                | ![yes]                            | ![no]                            | ![maybe]                        | ![maybe]                        |
| Search: APIs                                  | ![yes]                            | ![yes]                           | ![yes]                          | ![no]                           |
| Metadata preparation                          | ![yes]                            | ![yes]                           | ![yes]                          | ![maybe]                        |
| Retract checks                                | ![yes]                            | ![no]                            | ![no]                           | ![yes]                          |
| PDF retrieval                                 | ![yes]                            | ![no]                            | ![no]                           | ![yes]                          |
| PDF preparation                               | ![yes]                            | ![no]                            | ![maybe]                        | ![maybe]                        |
| Status tracking                               | ![yes]                            | ![no]                            | ![yes]                          | ![yes]                          |
| **Collaboration**                             |                                   |                                  |                                 |                                 |
| Large teams                                   | ![yes]                            | ![maybe]                         | ![maybe]                        | ![maybe]                        |
| Algorithms                                    | ![yes]                            | ![yes]                           | ![maybe]                        | ![maybe]                        |
| **Data management**                           |                                   |                                  |                                 |                                 |
| Transparency                                  | ![yes]                            | ![no]                            | ![no]                           | ![no]                           |
| Validation                                    | ![yes]                            | ![no]                            | ![no]                           | ![no]                           |
| Reporting (e.g., PRISMA)                      | ![yes]                            | ![no]                            | ![yes]                          | ![yes]                          |
| Publication of review                         | ![yes]                            | ![yes]                           | ![no]                           | ![no]                           |
| **Platform**                                  |                                   |                                  |                                 |                                 |
| OSI-approved license                          | ![yes]                            | ![yes]                           | ![yes]                          | ![no]                           |
| Peer-reviewed                                 | ![no]                             | ![yes]                           | ![yes]                          | ![no]                           |
| Technology                                    | Python                            | Python                           | Ruby                            | Proprietary                     |
| Setup                                         | Local or cloud                    | Local or cloud                   | Server                          | Server                          |
| Interface                                     | CLI, Programmatic (GUI planned)   | Jupyter Notebook                 | Web-UI                          | Web-UI                          |
| Contributors                    | ![GitHub contributors](https://img.shields.io/github/contributors-anon/CoLRev-Environment/colrev) | ![GitHub contributors](https://img.shields.io/github/contributors-anon/NLeSC/litstudy) | ![GitHub contributors](https://img.shields.io/github/contributors-anon/clbustos/buhos) | NA                                                                     |
| Commits                         | ![GitHub total commits](https://img.shields.io/github/commit-activity/t/CoLRev-Environment/colrev) | ![GitHub total commits](https://img.shields.io/github/commit-activity/t/NLeSC/litstudy) | ![GitHub total commits](https://img.shields.io/github/commit-activity/t/clbustos/buhos) | NA                                                                     |
| Last commit                     | ![GitHub last commit](https://img.shields.io/github/last-commit/CoLRev-Environment/colrev)  | ![GitHub last commit](https://img.shields.io/github/last-commit/NLeSC/litstudy)  | ![GitHub last commit](https://img.shields.io/github/last-commit/clbustos/buhos)  | NA                                                                     |
| Pull requests         | ![GitHub Issues or Pull Requests](https://img.shields.io/github/issues-pr-closed/CoLRev-Environment/colrev)  | ![GitHub Issues or Pull Requests](https://img.shields.io/github/issues-pr-closed/NLeSC/litstudy)  | ![GitHub Issues or Pull Requests](https://img.shields.io/github/issues-pr-closed/clbustos/buhos)  | NA                                                                     |
| Forks         | ![GitHub forks](https://img.shields.io/github/forks/CoLRev-Environment/colrev)  | ![GitHub forks](https://img.shields.io/github/forks/NLeSC/litstudy)  | ![GitHub forks](https://img.shields.io/github/forks/clbustos/buhos)  | NA                                                                     |
| Last release                    | ![GitHub last release](https://img.shields.io/github/release-date/CoLRev-Environment/colrev)  | ![GitHub last release](https://img.shields.io/github/release-date/NLeSC/litstudy)  | ![GitHub last release](https://img.shields.io/github/release-date-pre/clbustos/buhos)  | NA                                                                     |
| Current release              | ![Releases](https://img.shields.io/github/release/CoLRev-Environment/colrev?label=Releases) | ![Releases](https://img.shields.io/github/release/NLeSC/litstudy?label=Releases) | ![GitHub Release](https://img.shields.io/github/v/release/clbustos/buhos?include_prereleases)| NA |

## Contributing, changes, and releases

Contributions, code and features are always welcome

- See [contributing guidelines](CONTRIBUTING.md), [help page](https://colrev-environment.github.io/colrev/manual/help.html), and [github repository](https://github.com/CoLRev-Environment/colrev).
- Bug reports or feedback? Please use the [issue tracker](https://github.com/CoLRev-Environment/colrev/issues) and let us know.
- To get your work included, fork the repository, implement your changes, and create a [pull request](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests).

For further information, see [tests](tests/readme.md), [changes](CHANGELOG.md), and [releases](https://github.com/CoLRev-Environment/colrev/releases).

## Contributors

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/geritwagner"><img src="https://avatars.githubusercontent.com/u/3872815?v=4?s=100" width="100px;" alt="Gerit Wagner"/><br /><sub><b>Gerit Wagner</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=geritwagner" title="Code">💻</a> <a href="https://github.com/CoLRev-Environment/colrev/commits?author=geritwagner" title="Documentation">📖</a> <a href="#data-geritwagner" title="Data">🔣</a> <a href="#content-geritwagner" title="Content">🖋</a> <a href="#example-geritwagner" title="Examples">💡</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://julianprester.com"><img src="https://avatars.githubusercontent.com/u/4706870?v=4?s=100" width="100px;" alt="Julian Prester"/><br /><sub><b>Julian Prester</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=julianprester" title="Code">💻</a> <a href="https://github.com/CoLRev-Environment/colrev/commits?author=julianprester" title="Documentation">📖</a> <a href="#data-julianprester" title="Data">🔣</a> <a href="#content-julianprester" title="Content">🖋</a> <a href="https://github.com/CoLRev-Environment/colrev/issues?q=author%3Ajulianprester" title="Bug reports">🐛</a> <a href="#ideas-julianprester" title="Ideas, Planning, & Feedback">🤔</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/tmahmood"><img src="https://avatars.githubusercontent.com/u/34904?v=4?s=100" width="100px;" alt="Tarin Mahmood"/><br /><sub><b>Tarin Mahmood</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=tmahmood" title="Code">💻</a> <a href="https://github.com/CoLRev-Environment/colrev/commits?author=tmahmood" title="Tests">⚠️</a> <a href="https://github.com/CoLRev-Environment/colrev/commits?author=tmahmood" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/dengdenglele"><img src="https://avatars.githubusercontent.com/u/28404427?v=4?s=100" width="100px;" alt="dengdenglele"/><br /><sub><b>dengdenglele</b></sub></a><br /><a href="#data-dengdenglele" title="Data">🔣</a> <a href="https://github.com/CoLRev-Environment/colrev/commits?author=dengdenglele" title="Documentation">📖</a> <a href="https://github.com/CoLRev-Environment/colrev/commits?author=dengdenglele" title="Tests">⚠️</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/mhlbrsimon"><img src="https://avatars.githubusercontent.com/u/83401831?v=4?s=100" width="100px;" alt="mhlbrsimon"/><br /><sub><b>mhlbrsimon</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=mhlbrsimon" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/ossendorfluca"><img src="https://avatars.githubusercontent.com/u/112037612?v=4?s=100" width="100px;" alt="ossendorfluca"/><br /><sub><b>ossendorfluca</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=ossendorfluca" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/katharinaernst"><img src="https://avatars.githubusercontent.com/u/131549085?v=4?s=100" width="100px;" alt="katharinaernst"/><br /><sub><b>katharinaernst</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=katharinaernst" title="Code">💻</a></td>
    </tr>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/einfachjessi"><img src="https://avatars.githubusercontent.com/u/131001755?v=4?s=100" width="100px;" alt="einfachjessi"/><br /><sub><b>einfachjessi</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=einfachjessi" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Janus678"><img src="https://avatars.githubusercontent.com/u/131582517?v=4?s=100" width="100px;" alt="Janus678"/><br /><sub><b>Janus678</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=Janus678" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/frxdericz"><img src="https://avatars.githubusercontent.com/u/131789939?v=4?s=100" width="100px;" alt="frxdericz"/><br /><sub><b>frxdericz</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=frxdericz" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/MalouSchmidt"><img src="https://avatars.githubusercontent.com/u/131263679?v=4?s=100" width="100px;" alt="MalouSchmidt"/><br /><sub><b>MalouSchmidt</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=MalouSchmidt" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/RheaDoesStuff"><img src="https://avatars.githubusercontent.com/u/74066245?v=4?s=100" width="100px;" alt="RheaDoesStuff"/><br /><sub><b>RheaDoesStuff</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=RheaDoesStuff" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Cohen2000"><img src="https://avatars.githubusercontent.com/u/113113352?v=4?s=100" width="100px;" alt="Cohen2000"/><br /><sub><b>Cohen2000</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=Cohen2000" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/RobertAhr"><img src="https://avatars.githubusercontent.com/u/131687952?v=4?s=100" width="100px;" alt="RobertAhr"/><br /><sub><b>RobertAhr</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=RobertAhr" title="Code">💻</a></td>
    </tr>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/ThomasFleischmann"><img src="https://avatars.githubusercontent.com/u/131684139?v=4?s=100" width="100px;" alt="ThomasFleischmann"/><br /><sub><b>ThomasFleischmann</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=ThomasFleischmann" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/AntonFrisch"><img src="https://avatars.githubusercontent.com/u/131719653?v=4?s=100" width="100px;" alt="AntonFrisch"/><br /><sub><b>AntonFrisch</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=AntonFrisch" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/LouisLangenhan"><img src="https://avatars.githubusercontent.com/u/148447366?v=4?s=100" width="100px;" alt="LouisLangenhan"/><br /><sub><b>LouisLangenhan</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=LouisLangenhan" title="Code">💻</a> <a href="https://github.com/CoLRev-Environment/colrev/commits?author=LouisLangenhan" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Peteer98"><img src="https://avatars.githubusercontent.com/u/148191162?v=4?s=100" width="100px;" alt="Peter Eckhardt"/><br /><sub><b>Peter Eckhardt</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=Peteer98" title="Code">💻</a> <a href="https://github.com/CoLRev-Environment/colrev/commits?author=Peteer98" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/user123projekt"><img src="https://avatars.githubusercontent.com/u/149078858?v=4?s=100" width="100px;" alt="User123projekt"/><br /><sub><b>User123projekt</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=User123projekt" title="Code">💻</a> <a href="https://github.com/CoLRev-Environment/colrev/commits?author=User123projekt" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/LuminousLynx"><img src="https://avatars.githubusercontent.com/u/148456911?v=4?s=100" width="100px;" alt="LuminousLynx"/><br /><sub><b>LuminousLynx</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=LuminousLynx" title="Code">💻</a> <a href="https://github.com/CoLRev-Environment/colrev/commits?author=LuminousLynx" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/koljarinne"><img src="https://avatars.githubusercontent.com/u/167416691?v=4?s=100" width="100px;" alt="koljarinne"/><br /><sub><b>koljarinne</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=koljarinne" title="Code">💻</a></td>
    </tr>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/k-schnickmann"><img src="https://avatars.githubusercontent.com/u/168131195?v=4?s=100" width="100px;" alt="Karl Schnickmann"/><br /><sub><b>Karl Schnickmann</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=k-schnickmann" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/edensarrival"><img src="https://avatars.githubusercontent.com/u/42614229?v=4?s=100" width="100px;" alt="edensarrival"/><br /><sub><b>edensarrival</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=edensarrival" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/U1TIM4T3"><img src="https://avatars.githubusercontent.com/u/167421727?v=4?s=100" width="100px;" alt="U1TIM4T3"/><br /><sub><b>U1TIM4T3</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=U1TIM4T3" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/annaglr"><img src="https://avatars.githubusercontent.com/u/76491696?v=4?s=100" width="100px;" alt="Anna Geßler"/><br /><sub><b>annaglr</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=annaglr" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/0xmtyset"><img src="https://avatars.githubusercontent.com/u/160525679?v=4?s=100" width="100px;" alt="0xmtyset"/><br /><sub><b>0xmtyset</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=0xmtyset" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/tobiaspffl"><img src="https://avatars.githubusercontent.com/u/134608287?v=4?s=100" width="100px;" alt="tobiaspffl"/><br /><sub><b>tobiaspffl</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=tobiaspffl" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/CelinaSchwarz"><img src="https://avatars.githubusercontent.com/u/71493743?v=4?s=100" width="100px;" alt="CelinaSchwarz"/><br /><sub><b>CelinaSchwarz</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=CelinaSchwarz" title="Code">💻</a></td>
    </tr>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/QuynhMaiNguyen"><img src="https://avatars.githubusercontent.com/u/167417535?v=4?s=100" width="100px;" alt="QuynhMaiNguyen"/><br /><sub><b>QuynhMaiNguyen</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=QuynhMaiNguyen" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/pmao0907"><img src="https://avatars.githubusercontent.com/u/167312265?v=4?s=100" width="100px;" alt="pmao0907"/><br /><sub><b>pmao0907</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=pmao0907" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/MingxinJiang"><img src="https://avatars.githubusercontent.com/u/132772605?v=4?s=100" width="100px;" alt="MingxinJiang"/><br /><sub><b>MingxinJiang</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=MingxinJiang" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/JohannesDiel"><img src="https://avatars.githubusercontent.com/u/167763043?v=4?s=100" width="100px;" alt="JohannesDiel"/><br /><sub><b>JohannesDiel</b></sub></a><br /><a href="https://github.com/CoLRev-Environment/colrev/commits?author=JohannesDiel" title="Code">💻</a></td>
    </tr>
  </tbody>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

## License

This project is distributed under the [MIT License](LICENSE) the documentation is distributed under the [CC-0](https://creativecommons.org/publicdomain/zero/1.0/) license.
If you contribute to the project, you agree to share your contribution following these licenses.

## Citing CoLRev

Please cite the project as follows:

Wagner, G. and Prester, J. (2024) CoLRev - An open-source environment for Collaborative Literature Reviews. Available at https://github.com/CoLRev-Environment/colrev. doi:[10.5281/zenodo.11668338](https://dx.doi.org/10.5281/zenodo.11668338)

[yes]: ./docs/figures/yes.svg
[no]: ./docs/figures/no.svg
[maybe]: ./docs/figures/maybe.svg
