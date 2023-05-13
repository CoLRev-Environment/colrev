# Quality model

<!--
CHECK SYSTEMATICALLY:
Resources: https://github.com/Kingsford-Group/biblint

- search sources/provenance
- identification (reducing manual/error-prone processes)
- quality rules: fit for purposes: dedupe/reporting/citing the sample
- dedupe: prepare, dedupe, dedupe-special-cases, validate, undo
- use ontology to capture the "research history"/relations

- Introduce quality defect rules with id s like pylint (and add examples)
- Use in provenance and allow users to disable or add custom rules.
- Extract the rules to a separate script

TBD: separately
- check for compliance with rules
- apply prep package endpoints to fix defets

TBD: General errors category? (quality_defect)
Should the following simply be corrected?
- associated-entity (???): correction, update, ... (-> RESEARCH-HISTORY)
- non-entity (??): editorial board, cover page, back-matter (-> RESEARCH-HISTORY)

TBD: should it be possible to override all rules? how? how do we make sure that follow-up operations do not re-apply the requirements?
TBD: language: add missing (always required) - BUT: language is not a masterdata item (missing only applies to masterdata...)

Timeliness:
- outdated (?)
- up-to-date (status: retracted? volatile fields like citations, completeness)

Error, Warning, Convention (https://pylint.readthedocs.io/en/latest/user_guide/messages/message_control.html)

-->

## Quality defects

The check and fix should be separated.

At some point, the quality defect analysis may be extracted as a standalone bibtex-linter

### Completeness

- [x] missing-field: a mandatory masterdata field does not have a value (based on requirements for the respective ENTRYTYPE)
- [ ] not-missing: not an error code!? (TBD. implicitly/without note?)

### Semantic consistency (between fields and linked records)

- [x] inconsistent-with-entrytype : e.g., journal with booktitle
- [x] identical-values-between-title-and-container: e.g., title = Information Systems Journal, journal=Information Systems Journal, titlexjournal,titlexbooktitle (typical error in GROBID extracts)
- [x] inconsistent-content: e.g., journal field with "conference" or booktitle field with "journal"
TBD: the following is only discovered after prep/linking of masterdata (but the checker should run again after prep...):
- [ ] record-not-in-toc: the record was not found in the tables of contents of the journal
- [ ] inconsistent-with-linked-record: e.g., metadata associated with doi is not similar to metadata of the record (global-id-conflict)

### Format

- [x] mostly-all-caps : applies to title, author, journal, booktitle, ...
- [x] name-format-separators : applies to author, editor, ... (should be " and " and comma between first/last name)
- [x] name-format-titles : author fields should not contain titles (MD, Dr, PhD, Prof, Dipl Ing)
- [x] year-format: 4 digits
- [x] container-title-abbreviated: e.g., ICIS (container-title-abbreviated: preferred to mostly-all-caps)
- [x] name-abbreviated: e.g., and others/et al/...
- [x] language-format-error : language fields should match ISO 639-3
- [x] doi-not-matching-pattern: dois should match a regex pattern
- [ ] name-format-particles: propper escaping of particles ({vom Brocke}) Basis: CSL / https://docs.citationstyles.org/en/stable/specification.html?highlight=von#names
- [ ] pages-format: applies to pages
- [ ] page-range: x < y
- [ ] latex-char : applies to title, author, journal, booktitle
- [ ] html-char : applies to title, author, journal, booktitle
- [ ] unprotected-terms: applies to title, booktitle, journal (capitalized terms/acronyms should be protected)
- [ ] title-suffix: e.g., *, \textdagger (warning?)
