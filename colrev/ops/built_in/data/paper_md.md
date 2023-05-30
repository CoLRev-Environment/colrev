# Data: paper_md

<!--
Note: This document is currently under development. It will contain the following elements.

- description
- example
-->

The paper-md endpoint can be used to create a review protocol or a manuscript based on [pandoc](https://pandoc.org/) and [csl citation styles](https://citationstyles.org/).

Pandoc can use different template files to generate word, pdf, or latex outputs (among others).

The `data/data/paper.md` file may serve as a review protocol at the beginning and evolve into the final manuscript.

The citation style can be change in the `data/data/paper.md` header. The template can be changed in the `settings.json` (`data/data_package_endpoints/colrev.paper_md/word_template`).

Upon running the paper-md (as part of `colrev data`), new records are added after the following marker (as a to-do list):

```
# Coding and synthesis

_Records to synthesize_:<!-- NEW_RECORD_SOURCE -->

- @Smith2010
- @Webster2020

```
Once record citations are moved from the to-do list to other parts of the manuscript, they are considered synthesized and are set to `rev_synthesized` upon running `colrev data`.

## Links
