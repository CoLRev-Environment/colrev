## Summary

[GitHub](https://github.com/) hosts repositories for code, datasets, and documentation.

## search

### API search

ℹ️ Restriction: API searches require an GitHub access token to retrieve all the relevant meta data.

In your GitHub account, a classic [personal access tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) can be created. It is not necessary to select any scopes.

Keywords are entered after the search command is executed. The user can chose to search repositories by title, readme files, or both.

```
colrev search --add colrev.github
```

Format of the search-history file (interactive API search):

```json
{
    "search_string": {
        "query": "microsourcing",
        "scope": "title,readme"
    },
    "platform": "colrev.github",
    "search_results_path": "data/search/github.bib",
    "search_type": "API",
    "version": "0.1.0"
}
```

Format of the search-history file (URL-based API search):

```json
{
    "search_string": "",
    "platform": "colrev.github",
    "search_results_path": "data/search/github_search.bib",
    "search_type": "API",
    "search_parameters": {
        "query": "topic:microsourcing"
    },
    "version": "0.1.0"
}
```

## prep

GitHub can be used to provide meta data for linking and updating existing records.

```
colrev prep --add colrev.github
```
