## Summary

## prep

**Prerequisite** Initial ranking data is extracted from ranking.csv into SQLite Database sqlite_index.db with 'colrev env -i'.

**Description**

The add_journal_ranking package allows the user to add a ranking to the records metadata for additional automated prescreen options. While iterating through the records, this class calls the get_journal_rankings method to access the sqlite_index.db to compare if a journal_name is in one or more of the saved rankings. These rankings are being saved in the records metadata.

Example:

```
journal_ranking = {Senior Scholars' List of Premier Journals}, or
journal_ranking = {not included in a ranking},
```

Should the journal be in the Beall's Predatory Journal list, then the record will be marked as "Predatory Journal: Do not include!" and be predestined to be excluded in the scope_prescreen process.

Example:

```
journal_ranking = {Predatory Journal: Do not include!},
```

The journal ranking will also be used in the colrev prescreen method and allows the user to decide if the record should be marked as 'rev_prescreen_excluded' or 'rev_prescreen_included'.

For further information see [scope_prescreen](https://github.com/CoLRev-Environment/colrev/blob/main/colrev/packages/prescreen/scope_prescreen.md).
