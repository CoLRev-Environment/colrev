## Summary

BibDedupe is an open-source Python library for deduplication of bibliographic records, tailored for literature reviews. Unlike traditional deduplication methods, BibDedupe focuses on entity resolution, linking duplicate records instead of simply deleting them.

[![status](https://joss.theoj.org/papers/b954027d06d602c106430e275fe72130/status.svg)](https://joss.theoj.org/papers/b954027d06d602c106430e275fe72130)

**Features**

- Automated Duplicate Linking with Zero False Positives: BibDedupe automates the duplicate linking process with a focus on eliminating false positives.
- Preprocessing Approach: BibDedupe uses a preprocessing approach that reflects the unique error generation process in academic databases, such as author re-formatting, journal abbreviation or translations.
- Entity Resolution: BibDedupe does not simply delete duplicates, but it links duplicates to resolve the entitity and integrates the data. This allows for validation, and undo operations.
- Programmatic Access: BibDedupe is designed for seamless integration into existing research workflows, providing programmatic access for easy incorporation into scripts and applications.
- Transparent and Reproducible Rules: BibDedupe's blocking and matching rules are transparent and easily reproducible to promote reproducibility in deduplication processes.
- Continuous Benchmarking: Continuous integration tests running on GitHub Actions ensure ongoing benchmarking, maintaining the library's reliability and performance across datasets.
- Efficient and Parallel Computation: BibDedupe implements computations efficiently and in parallel, using appropriate data structures and functions for optimal performance.

## dedupe

The [bib-dedupe](https://github.com/CoLRev-Environment/bib-dedupe) package is the default deduplication module for CoLRev.
It is activated by default and is responsible for removing duplicate entries in the data.

## Cite

```
@article{Wagner_BibDedupe_An_Open-Source_2024,
        author  = {Wagner, Gerit},
        doi     = {10.21105/joss.06318},
        journal = {Journal of Open Source Software},
        month   = may,
        number  = {97},
        pages   = {6318},
        title   = {{BibDedupe: An Open-Source Python Library for Bibliographic Record Deduplication}},
        url     = {https://joss.theoj.org/papers/10.21105/joss.06318},
        volume  = {9},
        year    = {2024}
        }
```

## Links

- [bib-dedupe](https://github.com/CoLRev-Environment/bib-dedupe)
- [Documentation](https://colrev-environment.github.io/bib-dedupe/)
- [Evaluation](https://colrev-environment.github.io/bib-dedupe/evaluation.html)
