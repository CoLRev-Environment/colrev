# Quality model

<!--
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

### Completeness

- missing: a mandatory field does not have a value (based on requirements for the respective ENTRYTYPE)

### Semantic consistency (between fields and linked records)

- inconsistent-with-entrytype : e.g., journal with booktitle
- inconsistent-with-linked-record: e.g., metadata associated with doi is not similar to metadata of the record (global-id-conflict)
- identical-values-between-fields: e.g., title = Information Systems Journal, journal=Information Systems Journal (typical error in GROBID extracts)
- inconsistent-content: e.g., journal field with "conference" or booktitle field with "journal"
- not-in-toc: the record was not found in the tables of contents of the journal

### Format

- mostly-all-caps : applies to title, author, journal, booktitle, ...
- name-format-separators : applies to author, editor, ... (should be " and " and comma between first/last name)
- name-format-titles : author fields should not contain titles (MD, Dr, PhD, Prof, Dipl Ing)
- name-format-particles: propper escaping of particles ({vom Brocke}) Basis: CSL / https://docs.citationstyles.org/en/stable/specification.html?highlight=von#names
- field-abbreviated: e.g., and others/et al/...
- pages-format: applies to pages
- latex-char : applies to title, author, journal, booktitle
- html-char : applies to title, author, journal, booktitle
- language-format-error : language fields should match ISO 639-3
- doi-not-matching-pattern: dois should match a regex pattern
- unprotected-terms: applies to title, booktitle, journal (capitalized terms/acronyms should be protected)
- title-suffix: e.g., *, \textdagger (warning?)
