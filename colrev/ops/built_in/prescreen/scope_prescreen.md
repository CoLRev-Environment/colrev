# Prescreen: endpoint: colrev.scope_prescreen

# Method: __conditional_presecreen_not_in_ranking()

Prerequesite:

The endpoint colrev.add_journal_ranking in the settings of prep must be installed.
"colrev prep" must have been executed and journal_ranking must be included in metadata.

Description:
Use case: User is able to decide whether journals, which are not included in any ranking, will be marked as "rev_prescreen_included" or as "rev_prescreen_excluded".
This will lead to an exclusion in prescreen.
Example: "colrev_status = {rev_prescreen_excluded}" leads to exclusion in prescreen process


## Links
