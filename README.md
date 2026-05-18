
<p align="center">
<img src="https://raw.githubusercontent.com/CoLRev-Environment/colrev/main/docs/figures/logo_small.png" alt="CoLRev logo" width="400">
</p>

<div align="center">

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.18762354-blue)](https://doi.org/10.5281/zenodo.18762354)
[![PyPI - Version](https://img.shields.io/pypi/v/colrev?color=blue)](https://pypi.org/project/colrev/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/colrev)
[![License](https://img.shields.io/github/license/CoLRev-Environment/colrev.svg)](https://github.com/CoLRev-Environment/colrev/releases/)
![Documentation Status](https://img.shields.io/github/actions/workflow/status/CoLRev-Environment/colrev/docs_deploy.yml?label=documentation)
![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/CoLRev-Environment/colrev/tests.yml?label=tests)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/CoLRev-Environment/colrev/main.svg)](https://results.pre-commit.ci/latest/github/CoLRev-Environment/colrev/main)
![Coverage](https://raw.githubusercontent.com/CoLRev-Environment/colrev/main/tests/coverage.svg)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/bd4e44c6cda646e4b9e494c4c4d9487b)](https://app.codacy.com/gh/CoLRev-Environment/colrev/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
![GitHub last commit](https://img.shields.io/github/last-commit/CoLRev-Environment/colrev)
[![Downloads](https://static.pepy.tech/badge/colrev/month)](https://pepy.tech/project/colrev)
[![OpenSSF Best Practices](https://bestpractices.coreinfrastructure.org/projects/7148/badge)](https://bestpractices.coreinfrastructure.org/projects/7148)
[![SWH](https://archive.softwareheritage.org/badge/origin/https://github.com/CoLRev-Environment/colrev/)](https://archive.softwareheritage.org/browse/origin/?origin_url=https://github.com/CoLRev-Environment/colrev/)<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
![GitHub contributors](https://img.shields.io/github/contributors-anon/CoLRev-Environment/colrev)
<!-- ALL-CONTRIBUTORS-BADGE:END -->
<!-- ![PyPI](https://img.shields.io/pypi/v/colrev) -->

# Collaborative Literature Reviews (CoLRev)

</div>

CoLRev is an open-source environment for collaborative literature reviews. It integrates with different synthesis tools, takes care of the data, and facilitates Git-based collaboration.

To accomplish these goals, CoLRev advances the design of review technology at the intersection of methods, design, cognition, and community building.
The following features stand out:

- Supports all literature review steps: problem formulation, search, dedupe, (pre)screen, PDF retrieval and preparation, and synthesis
- An open and extensible environment based on shared data and process standards
- Builds on git and its transparent collaboration model for the entire literature review process
- Builds on peer-reviewed libraries developed for CoLRev:
  [search-query](https://github.com/CoLRev-Environment/search-query) for loading, linting, translating, saving, improving, and automating academic search queries, and
  [BibDedupe](https://github.com/CoLRev-Environment/bib-dedupe) for bibliographic record deduplication
- Offers a self-explanatory, fault-tolerant, and configurable user workflow
- Operates a model for data quality, content curation, and reuse
- Enables typological and methodological pluralism throughout the process

![Demo](https://raw.githubusercontent.com/CoLRev-Environment/colrev/main/docs/source/_static/demo.gif)

For details, consult the [documentation](https://colrev-environment.github.io/colrev/).

## Demo

You can try a live demonstration of CoLRev via GitHub Codespaces: [start demo](https://github.com//codespaces/new?hide_repo_select=true&ref=main&repo=767717822).

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

| **Criteria**                                  | **CoLRev**                         | [**LitStudy**](https://github.com/NLeSC/litstudy)| [**BUHOS**](https://github.com/clbustos/buhos)  | [**Covidence**](https://www.covidence.org/)   |
|-----------------------------------------------|------------------------------------|----------------------------------|----------------------------------|----------------------------------|
| **Review types**                              |                                    |                                  |                                  |                                  |
| Supports different genres of review methods   | ✅                                 | ❌                               | ❌                               | ❌                               |
| Extensibility                                 | ✅                                 | ⚠️                               | ⚠️                               | ❌                               |
| **Process steps**                             |                                    |                                  |                                  |                                  |
| Review objectives and protocol                | ✅                                 | ✅                               | ✅                               | ✅                               |
| Search                                        | ✅                                 | ✅                               | ✅                               | ✅                               |
| Duplicate handling                            | ✅                                 | ⚠️                               | ⚠️                               | ⚠️                               |
| (Pre)Screen                                   | ✅                                 | ⚠️                               | ✅                               | ✅                               |
| Data extraction                               | ✅                                 | ⚠️                               | ✅                               | ✅                               |
| Data analysis and quality appraisal           | ✅                                 | ⚠️                               | ✅                               | ✅                               |
| Synthesis and reporting                       | ✅                                 | ✅                               | ✅                               | ✅                               |
| **Process qualities**                         |                                    |                                  |                                  |                                  |
| Extensibility                                 | ✅                                 | ✅                               | ❌                               | ❌                               |
| Extensions                                    | [111](https://colrev-environment.github.io/colrev/manual/packages.html) | 0                              | 0                                | 0                               |
| Search updates                                | ✅                                 | ❌                               | ⚠️                               | ⚠️                               |
| Search: APIs                                  | ✅ ([19](https://colrev-environment.github.io/colrev/manual/metadata_retrieval/search.html#api-searches)) | ✅ (7)                           | ❌                               | ❌                               |
| Metadata preparation                          | ✅                                 | ✅                               | ✅                               | ⚠️                               |
| Retract checks                                | ✅                                 | ❌                               | ❌                               | ✅                               |
| PDF retrieval                                 | ✅                                 | ❌                               | ❌                               | ✅                               |
| PDF preparation                               | ✅                                 | ❌                               | ⚠️                               | ⚠️                               |
| Status tracking                               | ✅                                 | ❌                               | ✅                               | ✅                               |
| **Collaboration**                             |                                   |                                  |                                 |                                 |
| Large teams                                   | ✅                                 | ⚠️                               | ⚠️                               | ⚠️                               |
| Algorithms                                    | ✅                                 | ✅                               | ⚠️                               | ⚠️                               |
| **Data management**                           |                                   |                                  |                                 |                                 |
| Transparency                                  | ✅                                 | ❌                               | ❌                               | ❌                               |
| Validation                                    | ✅                                 | ❌                               | ❌                               | ❌                               |
| Reporting (e.g., PRISMA)                      | ✅                                 | ❌                               | ✅                               | ✅                               |
| Publication of review                         | ✅                                 | ✅                               | ❌                               | ❌                               |
| **Platform**                                  |                                   |                                  |                                 |                                 |
| OSI-approved license                          | ✅                                 | ✅                               | ✅                               | ❌                               |
| Peer-reviewed                                 | ⚠️ Core libraries peer-reviewed   | ✅                               | ✅                               | ❌                               |
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

- See [contributing guidelines](CONTRIBUTING.md), [help page](https://colrev-environment.github.io/colrev/manual/help.html), and [GitHub repository](https://github.com/CoLRev-Environment/colrev).
- Bug reports or feedback? Please use the [issue tracker](https://github.com/CoLRev-Environment/colrev/issues) and let us know.
- To get your work included, fork the repository, implement your changes, and create a [pull request](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests).

For further information, see [tests](tests/readme.md), [changes](CHANGELOG.md), and [releases](https://github.com/CoLRev-Environment/colrev/releases).

### Thank You to Our Contributors

<table align="center">
  <tbody>
    <tr>
      <td><a href="https://github.com/geritwagner"><img src="https://avatars.githubusercontent.com/u/3872815?v=4&s=100" width="60" height="60" alt="Gerit Wagner" title="Gerit Wagner"></a></td>
      <td><a href="https://julianprester.com"><img src="https://avatars.githubusercontent.com/u/4706870?v=4&s=100" width="60" height="60" alt="Julian Prester" title="Julian Prester"></a></td>
      <td><a href="https://github.com/tmahmood"><img src="https://avatars.githubusercontent.com/u/34904?v=4&s=100" width="60" height="60" alt="Tarin Mahmood" title="Tarin Mahmood"></a></td>
      <td><a href="https://github.com/dengdenglele"><img src="https://avatars.githubusercontent.com/u/28404427?v=4&s=100" width="60" height="60" alt="dengdenglele" title="dengdenglele"></a></td>
      <td><a href="https://github.com/mhlbrsimon"><img src="https://avatars.githubusercontent.com/u/83401831?v=4&s=100" width="60" height="60" alt="mhlbrsimon" title="mhlbrsimon"></a></td>
      <td><a href="https://github.com/ossendorfluca"><img src="https://avatars.githubusercontent.com/u/112037612?v=4&s=100" width="60" height="60" alt="ossendorfluca" title="ossendorfluca"></a></td>
      <td><a href="https://github.com/katharinaernst"><img src="https://avatars.githubusercontent.com/u/131549085?v=4&s=100" width="60" height="60" alt="katharinaernst" title="katharinaernst"></a></td>
    </tr>
    <tr>
      <td><a href="https://github.com/einfachjessi"><img src="https://avatars.githubusercontent.com/u/131001755?v=4&s=100" width="60" height="60" alt="einfachjessi" title="einfachjessi"></a></td>
      <td><a href="https://github.com/Janus678"><img src="https://avatars.githubusercontent.com/u/131582517?v=4&s=100" width="60" height="60" alt="Janus678" title="Janus678"></a></td>
      <td><a href="https://github.com/frxdericz"><img src="https://avatars.githubusercontent.com/u/131789939?v=4&s=100" width="60" height="60" alt="frxdericz" title="frxdericz"></a></td>
      <td><a href="https://github.com/MalouSchmidt"><img src="https://avatars.githubusercontent.com/u/131263679?v=4&s=100" width="60" height="60" alt="MalouSchmidt" title="MalouSchmidt"></a></td>
      <td><a href="https://github.com/RheaDoesStuff"><img src="https://avatars.githubusercontent.com/u/74066245?v=4&s=100" width="60" height="60" alt="RheaDoesStuff" title="RheaDoesStuff"></a></td>
      <td><a href="https://github.com/Cohen2000"><img src="https://avatars.githubusercontent.com/u/113113352?v=4&s=100" width="60" height="60" alt="Cohen2000" title="Cohen2000"></a></td>
      <td><a href="https://github.com/RobertAhr"><img src="https://avatars.githubusercontent.com/u/131687952?v=4&s=100" width="60" height="60" alt="RobertAhr" title="RobertAhr"></a></td>
    </tr>
    <tr>
      <td><a href="https://github.com/ThomasFleischmann"><img src="https://avatars.githubusercontent.com/u/131684139?v=4&s=100" width="60" height="60" alt="ThomasFleischmann" title="ThomasFleischmann"></a></td>
      <td><a href="https://github.com/AntonFrisch"><img src="https://avatars.githubusercontent.com/u/131719653?v=4&s=100" width="60" height="60" alt="AntonFrisch" title="AntonFrisch"></a></td>
      <td><a href="https://github.com/LouisLangenhan"><img src="https://avatars.githubusercontent.com/u/148447366?v=4&s=100" width="60" height="60" alt="LouisLangenhan" title="LouisLangenhan"></a></td>
      <td><a href="https://github.com/Peteer98"><img src="https://avatars.githubusercontent.com/u/148191162?v=4&s=100" width="60" height="60" alt="Peter Eckhardt" title="Peter Eckhardt"></a></td>
      <td><a href="https://github.com/user123projekt"><img src="https://avatars.githubusercontent.com/u/149078858?v=4&s=100" width="60" height="60" alt="User123projekt" title="User123projekt"></a></td>
      <td><a href="https://github.com/LuminousLynx"><img src="https://avatars.githubusercontent.com/u/148456911?v=4&s=100" width="60" height="60" alt="LuminousLynx" title="LuminousLynx"></a></td>
      <td><a href="https://github.com/koljarinne"><img src="https://avatars.githubusercontent.com/u/167416691?v=4&s=100" width="60" height="60" alt="koljarinne" title="koljarinne"></a></td>
    </tr>
    <tr>
      <td><a href="https://github.com/k-schnickmann"><img src="https://avatars.githubusercontent.com/u/168131195?v=4&s=100" width="60" height="60" alt="Karl Schnickmann" title="Karl Schnickmann"></a></td>
      <td><a href="https://github.com/edensarrival"><img src="https://avatars.githubusercontent.com/u/42614229?v=4&s=100" width="60" height="60" alt="edensarrival" title="edensarrival"></a></td>
      <td><a href="https://github.com/U1TIM4T3"><img src="https://avatars.githubusercontent.com/u/167421727?v=4&s=100" width="60" height="60" alt="U1TIM4T3" title="U1TIM4T3"></a></td>
      <td><a href="https://github.com/annaglr"><img src="https://avatars.githubusercontent.com/u/76491696?v=4&s=100" width="60" height="60" alt="Anna Geßler" title="Anna Geßler"></a></td>
      <td><a href="https://github.com/0xmtyset"><img src="https://avatars.githubusercontent.com/u/160525679?v=4&s=100" width="60" height="60" alt="0xmtyset" title="0xmtyset"></a></td>
      <td><a href="https://github.com/tobiaspffl"><img src="https://avatars.githubusercontent.com/u/134608287?v=4&s=100" width="60" height="60" alt="tobiaspffl" title="tobiaspffl"></a></td>
      <td><a href="https://github.com/CelinaSchwarz"><img src="https://avatars.githubusercontent.com/u/71493743?v=4&s=100" width="60" height="60" alt="CelinaSchwarz" title="CelinaSchwarz"></a></td>
    </tr>
    <tr>
      <td><a href="https://github.com/QuynhMaiNguyen"><img src="https://avatars.githubusercontent.com/u/167417535?v=4&s=100" width="60" height="60" alt="QuynhMaiNguyen" title="QuynhMaiNguyen"></a></td>
      <td><a href="https://github.com/pmao0907"><img src="https://avatars.githubusercontent.com/u/167312265?v=4&s=100" width="60" height="60" alt="pmao0907" title="pmao0907"></a></td>
      <td><a href="https://github.com/MingxinJiang"><img src="https://avatars.githubusercontent.com/u/132772605?v=4&s=100" width="60" height="60" alt="MingxinJiang" title="MingxinJiang"></a></td>
      <td><a href="https://github.com/JohannesDiel"><img src="https://avatars.githubusercontent.com/u/167763043?v=4&s=100" width="60" height="60" alt="JohannesDiel" title="JohannesDiel"></a></td>
      <td><a href="https://github.com/julialopezmarti"><img src="https://avatars.githubusercontent.com/u/185966942?v=4&s=100" width="60" height="60" alt="julialopezmarti" title="julialopezmarti"></a></td>
      <td><a href="https://github.com/olgagirona"><img src="https://avatars.githubusercontent.com/u/185909829?v=4&s=100" width="60" height="60" alt="olgagirona" title="olgagirona"></a></td>
      <td><a href="https://github.com/komashevska"><img src="https://avatars.githubusercontent.com/u/191916936?v=4&s=100" width="60" height="60" alt="komashevska" title="komashevska"></a></td>
    </tr>
    <tr>
      <td><a href="https://github.com/trathienphuc-tran"><img src="https://avatars.githubusercontent.com/u/185779015?v=4&s=100" width="60" height="60" alt="trathienphuc-tran" title="trathienphuc-tran"></a></td>
      <td><a href="https://github.com/ammar-uni"><img src="https://avatars.githubusercontent.com/u/185945385?v=4&s=100" width="60" height="60" alt="ammar-uni" title="ammar-uni"></a></td>
      <td><a href="https://github.com/Lea-Chaoui"><img src="https://avatars.githubusercontent.com/u/148755227?v=4&s=100" width="60" height="60" alt="Lea-Chaoui" title="Lea-Chaoui"></a></td>
      <td><a href="https://github.com/ChloeT17"><img src="https://avatars.githubusercontent.com/u/209974918?v=4&s=100" width="60" height="60" alt="ChloeT17" title="ChloeT17"></a></td>
    </tr>
  </tbody>
</table>

<hr>

## License

This project is distributed under the [MIT License](LICENSE) the documentation is distributed under the [CC-0](https://creativecommons.org/publicdomain/zero/1.0/) license.
If you contribute to the project, you agree to share your contribution following these licenses.

## Citing CoLRev

Please cite the project as follows:

Wagner, G. and Prester, J. (2026) CoLRev - An open-source environment for Collaborative Literature Reviews. Available at <https://github.com/CoLRev-Environment/colrev>. doi:[10.5281/zenodo.11668338](https://dx.doi.org/10.5281/zenodo.11668338)
