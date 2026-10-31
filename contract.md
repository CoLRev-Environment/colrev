# `bibliography-io` API Contract — v0.2

**Purpose:** Describe the public record-loading and writing interfaces exposed by `bibliography-io`, including format support, normalization behavior, optional dependencies, and CoLRev integration.

## 1. Ownership and dependencies

- `bibliography-io` provides the public APIs, generic format dispatch, record normalization, and package-defined I/O exceptions. Its core import and non-optional format APIs work without importing CoLRev or optional dependencies.
- CoLRev owns workflow rules such as status and provenance semantics, record lifecycle, and CoLRev-specific identifier and entry-type policies. CoLRev can adapt records at its integration boundary.
- Excel and DataFrame APIs require the `excel` optional dependency extra (`pandas`, `openpyxl`, and `xlrd` as applicable).
- Markdown reference-list loading first discovers an optional backend through the `bibliography_io.backends` entry-point group, with the name `markdown`. If no registered backend handles the request, the current built-in implementation uses `requests` and CoLRev's `GrobidService`; the `markdown` extra installs CoLRev. A running GROBID service is required.
- Markdown table output is implemented in core and does not require the Markdown parsing backend.

## 2. Public API

The package exports the following principal functions from `bibliography_io`:

```python
records = bibliography_io.load_raw("references.bib")
records = bibliography_io.loads_raw(bibtex_text, format="bib")

primary_records = bibliography_io.load_primary("references.bib")
primary_records = bibliography_io.loads_primary(bibtex_text, format="bib")

bibliography_io.write(records, path="references.ris")
text = bibliography_io.to_string(records, format="bib")
```

### Loading raw records

```python
load_raw(
    path: str | Path,
    *,
    format: str | None = None,
    normalize: bool = True,
    mapping_fields=(),
    list_fields=(),
) -> list[dict[str, Any]]

loads_raw(
    text: str,
    *,
    format: str,
    normalize: bool = True,
    mapping_fields=(),
    list_fields=(),
) -> list[dict[str, Any]]
```

- File APIs infer the format from the filename suffix unless `format` is supplied. String APIs require `format`.
- Format names are case-insensitive; a leading dot is accepted. Aliases include `bibtex` for `bib`, `markdown` for `md`, `excel` for `xlsx`, and `endnote` for `enl`.
- Raw loaders return an ordered list of record dictionaries. They do not index records by ID or reject duplicate IDs.
- `normalize=True` (the default) normalizes field names and provides convenient scalar values. For example, repeated authors are joined with ` and `, repeated keywords with `; `, and conflicting scalar values with `; ` in source order. `normalize=False` retains parser-level values.
- For BibTeX only, `mapping_fields` and `list_fields` identify fields using `bibliography-io`'s structured-value encoding/decoding. Declared field names use lowercased BibTeX field names. A field cannot be declared both ways. Supplying either option for another format raises `UnsupportedFormatError`.
- File reads use UTF-8 (accepting a UTF-8 byte-order mark). A missing file raises `FileNotFoundError`.
- `load_raw_df(path, *, format=None, normalize=True, mapping_fields=(), list_fields=())` returns a pandas DataFrame with source order as rows. `get_nr_records(filename)` returns the number of raw records in a file.

### Loading primary records

```python
load_primary(
    path: str | Path,
    *,
    format: str | None = None,
    header_only: bool = False,
    mapping_fields=(),
    list_fields=(),
) -> dict[str, dict[str, Any]]

loads_primary(
    text: str,
    *,
    format: str,
    mapping_fields=(),
    list_fields=(),
) -> dict[str, dict[str, Any]]
```

- Primary loaders return records indexed by their `ID`, preserving input order.
- Each record must have a non-empty string `ID` and non-empty string `ENTRYTYPE`; duplicate IDs raise `DuplicateRecordIDError`, and a missing or invalid ID raises `MissingRecordIDError`.
- `header_only=True` is supported only for BibTeX and returns each record's `ID` and `ENTRYTYPE` without parsing its fields.
- `load_primary_df(...)` provides the same file-loading options as `load_primary` and returns a pandas DataFrame indexed by record ID.

### Writing records

```python
write(
    records,
    *,
    path: str | Path,
    format: str | None = None,
    mapping_fields=(),
    list_fields=(),
    primary: bool = False,
) -> None

to_string(
    records,
    *,
    format: str,
    mapping_fields=(),
    list_fields=(),
) -> str
```

- `write` requires `path` as a keyword-only argument. It infers format from the suffix unless `format` is supplied, writes UTF-8, and replaces an existing destination.
- `to_string` requires an explicit `format`. Excel is a file format and cannot be written as a string.
- Writers accept a list of record dictionaries or a mapping of IDs to record dictionaries. They normalize output records, lowercase `ENTRYTYPE`, default a missing entry type to `misc`, and assign sequential IDs to records lacking one. For lists, duplicate IDs are disambiguated in the normalized mapping keys with `#2`, `#3`, and so on; duplicate IDs in an input mapping raise `DuplicateRecordIDError`.
- `primary=True` is available on `write` for mappings. It validates record IDs and entry types and restricts output to BibTeX.
- BibTeX `mapping_fields` and `list_fields` options are supported as for loading. Unknown or incompatible options are errors rather than silently ignored.
- `write` supports `.bib`, `.ris`, `.csv`, `.xlsx`, and `.md`. Excel writing and DataFrame APIs require the `excel` extra. Markdown output is a table.

## 3. Record shape, fields, IDs, and entry types

- Records are dictionaries with string field names. Normalized records use reserved `ID` and `ENTRYTYPE` keys. Primary records are returned in a mapping whose key is the record's `ID`.
- The package exposes generic `Fields` and `ENTRYTYPES` constants in `bibliography_io.constants`. Common fields include `title`, `author`, `editor`, `year`, `date`, `journal`, `booktitle`, `container_title`, `publisher`, `volume`, `number`, `pages`, `doi`, `url`, `abstract`, and `keywords`.
- Format-specific aliases are normalized where the loaders define them. Unknown fields are retained as record data; field values can be structured parser values when `normalize=False` or structured BibTeX options are used.
- `ENTRYTYPE` is an open vocabulary. Common values are exposed by `ENTRYTYPES.get_all()`. Values are lowercased when normalized, and unrecognized non-empty values are not mapped to `misc`.
- IDs found in loaded source data are retained. Raw loading does not assign IDs solely to make every record addressable; primary loading requires an ID. Writing assigns IDs to records without IDs as described in §2.
- CoLRev-specific fields are payload data; the generic API does not apply CoLRev workflow semantics to them.

## 4. Supported formats

| Format | File read | String read | File write | String write |
| --- | --- | --- | --- | --- |
| BibTeX (`.bib`) | Yes | Yes | Yes | Yes |
| RIS (`.ris`) | Yes | Yes | Yes | Yes |
| CSV (`.csv`) | Yes | Yes | Yes | Yes |
| Excel (`.xls`, `.xlsx`) | Yes | No | `.xlsx` only | No |
| ENL / EndNote (`.enl`) | Yes | Yes | No | No |
| NBIB (`.nbib`) | Yes | Yes | No | No |
| Tagged text (`.txt`) | Yes | Yes | No | No |
| JSON (`.json`) | Yes | Yes | No | No |
| Markdown (`.md`) | Yes, via reference-list parser | Yes, via reference-list parser | Yes, table output | Yes, table output |

Excel reading/writing depends on the `excel` extra. Markdown reference-list input requires an available backend/GROBID support; it is distinct from Markdown table writing and is not promised to round-trip with it.

## 5. Optional dependencies and Markdown backend

- Importing `bibliography_io` does not require optional dependencies.
- Calling DataFrame APIs or reading/writing Excel files without the necessary dependencies raises `OptionalBackendUnavailableError` and includes an installation hint for `bibliography-io[excel]`.
- Markdown parsing discovers entry points in group `bibliography_io.backends`, selecting the `markdown` name. A loaded backend may expose `loads(text, source=...)` or be a callable accepting those arguments. Its result may be a list of record dictionaries or a mapping of IDs to record dictionaries.
- Without a registered backend, the built-in implementation uses the Markdown text and source path with CoLRev's GROBID service integration. Install `bibliography-io[markdown]` and ensure the service is available. Missing optional dependencies raise `OptionalBackendUnavailableError`; parsing or backend failures raise `BackendExecutionError`.

## 6. Exceptions and CoLRev integration

All package-defined exceptions derive from `BibliographyIOError`:

- `UnsupportedFormatError`
- `ParseError`
- `RecordValidationError`, including `MissingRecordIDError` and `DuplicateRecordIDError`
- `SerializationError`
- `OptionalBackendUnavailableError`
- `BackendExecutionError`

Standard filesystem exceptions, including `FileNotFoundError` and `PermissionError`, remain standard Python exceptions. Parser and backend errors preserve the original exception as their cause where wrapped. Invalid argument types may also raise standard `TypeError`.

The public package API does not expose the proposed `load_records`, `loads`, `write_records`, `dumps`, or `write_file` names. CoLRev's existing loader/writer paths may serve as integration or compatibility facades and can translate `bibliography-io` exceptions at the adapter boundary.

## 7. Verification criteria

- Tests cover raw and primary loading, file and string APIs, normalization options, source IDs, missing and duplicate IDs, supported format dispatch, and writer behavior.
- Optional-dependency tests cover missing Excel and Markdown dependencies and backend failures; Markdown success tests exercise the registered backend or GROBID service path.
- CoLRev tests cover adapter-specific IDs, fields, entry types, exception translation, and any retained compatibility paths.
- Validate using built package artifacts as well as a local checkout.
