## Summary

The colrev-sync package imports references from CoLRev projects (through local_index) into non-CoLRev paper projects that use Markdown and BibTeX.
If BibTeX citations keys are used in the paper project, the following command retrieves the corresponding bibliographical details and adds them to the BibTeX file:

```
colrev-sync
```

CoLRev sync can also be used through pre-commit hooks, when the following is included in the `.pre-commit-config.yaml`:

```
-   repo: local
    hooks:
    -   id: colrev-hooks-update
        name: "CoLRev ReviewManager: update"
        entry: colrev-hooks-update
        language: python
        stages: [commit]
        files: 'records.bib|paper.md'
```
