# SearchSource: SYNERGY datasets

<!--
Note: This document is currently under development. It will contain the following elements.

- description
- coverage (disciplines, types of work)
- supported (details): run_search (including updates), load,  prep (including get_masterdata)
-->

## Add the search source

<!-- Download search results and store in `data/search/` directory. API-access not yet available. -->

```
colrev search -a colrev.synergy_datasets -p dataset=Appenzeller-Herzog_2019
```

Note: some datasets are "broken". For example, the [Nagtegaal_2019](https://github.com/asreview/synergy-dataset/blob/master/datasets/Nagtegaal_2019/Nagtegaal_2019_ids.csv) dataset is a broken csv file and does not have any ids (doi/pubmedid/openalex_id).

The percentage of records with missing meatadata (no ids) is shown upon `colrev search`.

## Links

- [SYNERGY Datasets](https://github.com/asreview/synergy-dataset)
