## Summary

## search

### API search

<!-- Download search results and store in `data/search/` directory. API-access not yet available. -->

Navigate to the [SYNERGY Datasets](https://github.com/asreview/synergy-dataset) and copy the name of the directory and csv file (in the datasets directory).
For example, the dataset under `Howard_2016/Wassenaar_2017_ids.csv` can be added as follows:

```
colrev search --add colrev.synergy_datasets -p dataset=Howard_2016/Wassenaar_2017_ids.csv
```

Note: some datasets are "broken". For example, the [Nagtegaal_2019](https://github.com/asreview/synergy-dataset/blob/master/datasets/Nagtegaal_2019/Nagtegaal_2019_ids.csv) dataset is a broken csv file and does not have any ids (doi/pubmedid/openalex_id).

The percentage of records with missing meatadata (no ids) is shown upon `colrev search`.

Format of the search-history file:

```json
{
    "search_string": "",
    "platform": "colrev.synergy_datasets",
    "search_results_path": "data/search/SYNERGY_Bos_2018_Bos_2018.bib",
    "search_type": "API",
    "field": "",
    "version": "0.1.0",
    "search_parameters": {
        "dataset": "Bos_2018/Bos_2018_ids.csv"
    },
}
```

## Links

- [SYNERGY Datasets](https://github.com/asreview/synergy-dataset)
