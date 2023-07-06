# Prescreen: Scope Prescreen

This package uses a predefined scope to apply prescreening decisions automatically. For example, papers can be excluded based on the date of publication or their language. There are two use main use cases:

1. The Scope Prescreen runs before a manual prescreen. In this case, papers are either marked as `rev_prescreen_excluded`, or remain `md_processed`. Afterwards, all papers in `md_processed` are prescreened manually based on their topic.
2. The Scope Prescreen is the only prescreen package activated in the settings. In this case, papers are marked as `rev_prescreen_excluded` or `rev_prescreen_included`. Fully automated prescreening may not be appropriate for all types of reviews.

The Scope Prescreen can be added as follows:

```
colrev prescreen --add colrev.scope_prescreen:"TimeScopeFrom=2010"
```
