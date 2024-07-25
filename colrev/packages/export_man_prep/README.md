## Summary

## prep-man

This package provides functionality aimed at
- exporting records that need to be prepared,
- fixing the errors manually (with the relevant error codes and explanations)
- importing the prepared records

1. Export the md_needs_manual_preparation cases

```
colrev prep-man
```

Exports the `records_prep_man.bib` (containing the records) and the `records_prep_man_info.csv` (containing the error codes).

2. Manually fix the errors

Manually change the bib file (based on error codes in csv file)
Error code descriptions are available [here](https://colrev.readthedocs.io/en/latest/resources/quality_model.html).

3. (Re) import the records

```
colrev prep-man
```

Notes:

- There is no need to change the colrev_status fields (it will be reevaluated upon import)
- The colrev_status field can be used to override error codes
- It can also be set to rev_prescreen_excluded (or the entry can be deleted)
- When ENTRYTYPEs need to be corrected, change the ENTRYTYPE, and run `colrev prep-man` twice (remove the BIB and CSV file before the second run). This will reapply the field requirements for the new ENTRYTYPE. For example, if a record needs to switch from `article` to `inproceedings`, reapplying the field requirements will create the `booktitle` field and indicate that the `journal`, `volume`, and `number` fields are no longer needed.

## Links
