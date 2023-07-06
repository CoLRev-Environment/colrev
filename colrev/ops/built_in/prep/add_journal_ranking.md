# Prep: "endpoint": "colrev.add_journal_ranking"

Prerequisite:
Initial ranking data is extracted from ranking.csv into SQLite Database sqlite_index.db with 'colrev env -i'.

The function is added to the 'colrev prep' method

Description:
The add_journal_ranking extension allows the user to add a ranking to the records metadata for additional automated prescreen options. While iterating through the records, this class calls the search_in_database method to access the sqlite_index.db to compare if a journal_name is in one or more of the saved rankings. These rankings are being saved in the records metadata.

Example:
journal_ranking = {Senior Scholars' List of Premier Journals}, or
journal_ranking = {not included in a ranking},

Should the journal be in the Beall's Predatory Journal list, then the record will be marked as "Predatory Journal: Do not include!" and be predestined to be excluded in the scope_prescreen process.

Example:
journal_ranking = {Predatory Journal: Do not include!},

The journal ranking will also be used in the colrev prescreen method and allows the user to decide if the record should be marked as 'exclude' or 'include'.

For further information see:

## colrev/ops/built_in/prescreen/scope_prescreen.md