## Summary

## prescreen

This package uses a predefined scope to apply prescreening decisions automatically. For example, papers can be excluded based on the date of publication or their language. There are two use main use cases:

1. The Scope Prescreen runs before a manual prescreen. In this case, papers are either marked as `rev_prescreen_excluded`, or remain `md_processed`. Afterwards, all papers in `md_processed` are prescreened manually based on their topic.
2. The Scope Prescreen is the only prescreen package activated in the settings. In this case, papers are marked as `rev_prescreen_excluded` or `rev_prescreen_included`. Fully automated prescreening may not be appropriate for all types of reviews.

The Scope Prescreen can be added as follows:

```
colrev prescreen -a colrev.scope_prescreen -p "TimeScopeFrom=2010"
```

**Prerequesite**: The endpoint colrev.add_journal_ranking in the settings of prep must be installed.
"colrev prep" must have been executed and journal_ranking must be included in metadata.

**Description**: Use case: User is able to decide whether journals, which are not included in any ranking, will be marked as "rev_prescreen_included" or as "rev_prescreen_excluded".
