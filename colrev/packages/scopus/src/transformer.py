#! /usr/bin/env python
"""Scopus record transformer."""

from __future__ import annotations

import typing

from colrev.constants import ENTRYTYPES
from colrev.constants import Fields


def _to_int(x: typing.Any, default: int = 0) -> int:
    try:
        return int(str(x).strip())
    except (ValueError, AttributeError):
        return default


def _year_from_coverdate(entry: typing.Dict[str, typing.Any]) -> str:
    cd = entry.get("prism:coverDate") or entry.get("coverDate") or ""
    return cd[:4] if isinstance(cd, str) and len(cd) >= 4 else ""


def _scopus_id(entry: typing.Dict[str, typing.Any]) -> str:
    """Return the plain Scopus ID (digits only)."""
    dcid = entry.get("dc:identifier", "")
    if isinstance(dcid, str) and dcid.startswith("SCOPUS_ID:"):
        return dcid.replace("SCOPUS_ID:", "").strip()

    eid = entry.get("eid", "")
    if isinstance(eid, str) and "-" in eid:
        # e.g., 2-s2.0-85217243503 -> 85217243503
        parts = eid.split("-")
        if parts:
            return parts[-1].strip()

    # fallback: extract scp= from links
    for lk in entry.get("link", []) or []:
        href = lk.get("@href") or lk.get("href") or ""
        if "scp=" in href:
            return href.split("scp=")[-1].split("&")[0].strip()
    return ""


def _eid(entry: typing.Dict[str, typing.Any]) -> str:
    eid = entry.get("eid", "")
    if isinstance(eid, str) and eid:
        return eid
    sid = _scopus_id(entry)
    return f"2-s2.0-{sid}" if sid else ""


def _open_access(entry: typing.Dict[str, typing.Any]) -> bool:
    flag = entry.get("openaccessFlag")
    if isinstance(flag, bool):
        return flag
    return str(entry.get("openaccess", "")).strip() in {"1", "true", "True"}


def _normalize_pages(entry: typing.Dict[str, typing.Any]) -> typing.Optional[str]:
    pages = entry.get("prism:pageRange") or ""
    if not isinstance(pages, str) or not pages.strip():
        return None
    return pages.replace("-", "--")


def _parse_authors(entry: typing.Dict[str, typing.Any]) -> str:
    """Return compact author string like 'Surname, G.; Second, H.'.
    Handles Scopus variants:
      - dc:creator (string)
      - author (list[dict] or dict)
      - authors.author (list[dict]).
    """
    authors = _get_raw_authors(entry=entry)
    if not authors:
        return _get_dc_creator(entry=entry)

    return "; ".join(n for n in (_normalize_author(author=a) for a in authors) if n)


def _get_raw_authors(entry: typing.Dict[str, typing.Any]) -> typing.List[typing.Any]:
    if isinstance(entry.get("author"), list):
        return entry["author"]
    if isinstance(entry.get("author"), dict):
        maybe = entry["author"]
        if isinstance(maybe.get("author"), list):
            return maybe["author"]
        return [maybe]
    if isinstance(entry.get("authors"), dict) and isinstance(
        entry["authors"].get("author"), list
    ):
        return entry["authors"]["author"]
    return []


def _get_dc_creator(entry: typing.Dict[str, typing.Any]) -> str:
    dc_creator = entry.get("dc:creator")
    if isinstance(dc_creator, str) and dc_creator.strip():
        return dc_creator.strip()
    return ""


def _normalize_author(author: typing.Any) -> str:
    if isinstance(author, str):
        return author.strip()
    if not isinstance(author, dict):
        return ""

    indexed = author.get("ce:indexed-name") or author.get("indexed-name")
    if isinstance(indexed, str) and indexed.strip():
        return indexed.strip()
    return _format_author_from_parts(author=author)


def _format_author_from_parts(author: typing.Dict[str, typing.Any]) -> str:
    surname = (author.get("surname") or author.get("ce:surname") or "").strip()
    given = (author.get("given-name") or author.get("ce:given-name") or "").strip()
    initials = (author.get("initials") or author.get("ce:initials") or "").strip()

    if surname and (given or initials):
        given_part = initials if initials else given
        return f"{surname}, {given_part}"
    if surname:
        return surname
    return _fallback_author_name(author=author)


def _fallback_author_name(author: typing.Dict[str, typing.Any]) -> str:
    for key in ("preferred-name", "authname"):
        value = author.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


_SUBTYPE_MAP: typing.Dict[str, typing.Dict[str, str]] = {
    # subtype -> {label, entrytype}
    "cp": {"label": "conference-paper", "entrytype": ENTRYTYPES.INPROCEEDINGS},
    "cr": {"label": "conference-review", "entrytype": ENTRYTYPES.PROCEEDINGS},
    "ar": {"label": "journal-article", "entrytype": ENTRYTYPES.ARTICLE},
    "re": {"label": "review-article", "entrytype": ENTRYTYPES.ARTICLE},
    "ip": {"label": "article-in-press", "entrytype": ENTRYTYPES.ARTICLE},
    "ed": {"label": "editorial", "entrytype": ENTRYTYPES.ARTICLE},
    "le": {"label": "letter", "entrytype": ENTRYTYPES.ARTICLE},
    "no": {"label": "note", "entrytype": ENTRYTYPES.ARTICLE},
    "dp": {"label": "data-paper", "entrytype": ENTRYTYPES.ARTICLE},
    "ch": {"label": "book-chapter", "entrytype": ENTRYTYPES.INCOLLECTION},
    "bk": {"label": "book", "entrytype": ENTRYTYPES.BOOK},
    # extend as needed
}


def _clean_isbn_value(v: typing.Any) -> typing.Optional[str]:
    """Scopus often returns prism:isbn as [{'@_fa':'true', '$':'[978...]}]."""
    if isinstance(v, str):
        return v.strip("[] ").strip() or None
    if isinstance(v, dict):
        s = v.get("$") or v.get("#text") or ""
        s = str(s)
        return s.strip("[] ").strip() or None
    return None


def _extract_isbn_list(entry: typing.Dict[str, typing.Any]) -> typing.List[str]:
    v = entry.get("prism:isbn")
    if not v:
        return []
    if isinstance(v, list):
        out = [x for x in (_clean_isbn_value(i) for i in v) if x]
        return out
    one = _clean_isbn_value(v)
    return [one] if one else []


def _classify_scopus(
    entry: typing.Dict[str, typing.Any],
) -> typing.Dict[str, typing.Optional[str]]:
    """Return label/entrytype based on subtype (primary) and aggregationType (fallback)."""
    subtype = (entry.get("subtype") or "").strip().lower()
    agg = (
        entry.get("prism:aggregationType") or ""
    ).strip()  # e.g., Journal / Book Series / Conference Proceeding

    if subtype in _SUBTYPE_MAP:
        d = _SUBTYPE_MAP[subtype]
        return {
            "label": d["label"],
            "entrytype": d["entrytype"],
            "subtype": subtype or None,
            "subtypeDescription": entry.get("subtypeDescription"),
            "aggregationType": agg or None,
        }

    # Fallback: use container + identifiers
    has_issn = bool(entry.get("prism:issn") or entry.get("prism:eIssn"))
    has_isbn = bool(entry.get("prism:isbn"))

    if agg == "Journal" or (has_issn and not has_isbn):
        label, et = "journal-article", "article"
    elif agg in {"Conference Proceeding", "Book Series"} or has_isbn:
        label, et = "conference-paper", "inproceedings"
    elif agg == "Book":
        label, et = "book", "book"
    else:
        label, et = ("journal-article" if has_issn else "misc"), (
            "article" if has_issn else "misc"
        )

    return {
        "label": label,
        "entrytype": et,
        "subtype": subtype or None,
        "subtypeDescription": entry.get("subtypeDescription"),
        "aggregationType": agg or None,
    }


def _apply_container_fields(
    rec: typing.Dict[str, typing.Any],
    entry: typing.Dict[str, typing.Any],
    entrytype: str,
) -> None:
    """Set container-specific fields:
    - article -> journal, volume, number
    - inproceedings -> booktitle (+ series if recognizable)
    - proceedings -> title already holds proceedings title; add series
    - incollection -> booktitle (+ series)
    - book -> (title already set), add series if it is a book series.
    """
    # pylint: disable=too-many-branches

    pubname = entry.get("prism:publicationName", "") or ""
    volume = entry.get("prism:volume", "") or ""
    number = entry.get("prism:issueIdentifier", "") or ""
    agg = entry.get("prism:aggregationType", "")
    isbns = _extract_isbn_list(entry)

    if entrytype == "article":
        rec[Fields.JOURNAL] = pubname
        rec[Fields.VOLUME] = volume
        rec[Fields.NUMBER] = number
        # keep DOI/pages elsewhere
    elif entrytype == ENTRYTYPES.INPROCEEDINGS:
        # Scopus often only exposes the *series* (e.g., LNBIP/LNCS) in publicationName.
        # Use it as a best-effort booktitle and also as 'series' if it looks like a series.
        rec[Fields.BOOKTITLE] = pubname or rec.get("booktitle", "")
        # If aggregationType suggests a series, also store as series
        if agg in {"Book Series", "Conference Proceeding"} and pubname:
            rec[Fields.SERIES] = pubname
        rec[Fields.VOLUME] = volume
        # 'number' usually not meaningful here; omit
        if isbns:
            rec[Fields.ISBN] = " ".join(isbns)
    elif entrytype == ENTRYTYPES.PROCEEDINGS:
        # Proceedings record: title is already the proceedings title (often the conference name)
        rec.pop("journal", None)
        # Store the LN* container as series if available
        if pubname:
            rec[Fields.SERIES] = pubname
        rec[Fields.VOLUME] = volume
        if isbns:
            rec[Fields.ISBN] = " ".join(isbns)
    elif entrytype == ENTRYTYPES.INCOLLECTION:
        rec[Fields.BOOKTITLE] = pubname or rec.get("booktitle", "")
        if agg in {"Book Series"} and pubname:
            rec[Fields.SERIES] = pubname
        rec[Fields.VOLUME] = volume
        if isbns:
            rec[Fields.ISBN] = " ".join(isbns)
    elif entrytype == ENTRYTYPES.BOOK:
        # Title already set; add series if the book is in a series
        if agg in {"Book Series"} and pubname:
            rec[Fields.SERIES] = pubname
        rec[Fields.VOLUME] = volume
        if isbns:
            rec[Fields.ISBN] = " ".join(isbns)
    else:
        # misc/unknown: fall back to journal-like fields if ISSN available
        rec[Fields.JOURNAL] = pubname
        rec[Fields.VOLUME] = volume
        rec[Fields.NUMBER] = number


def transform_record(entry: dict) -> dict:
    """Transform a raw Scopus record into a ColRev record."""
    scopus_id = _scopus_id(entry)
    eid = _eid(entry)

    # Classify type first
    klass = _classify_scopus(entry)
    entrytype = klass["entrytype"] or "article"

    record_dict: typing.Dict[str, typing.Any] = {
        Fields.ID: scopus_id,
        Fields.TITLE: entry.get("dc:title", "") or entry.get("title", ""),
        Fields.AUTHOR: _parse_authors(entry),
        Fields.YEAR: _year_from_coverdate(entry),
        Fields.DOI: entry.get("prism:doi", ""),
        Fields.ENTRYTYPE: entrytype,
        "scopus.eid": eid,
        "scopus.citedby": _to_int(entry.get("citedby-count", 0)),
        "scopus.source_id": entry.get("source-id", ""),
        "scopus.open_access": _open_access(entry),
        "scopus.subtype": klass.get("subtype"),
        "scopus.subtype_description": klass.get("subtypeDescription"),
        "scopus.aggregation_type": klass.get("aggregationType"),
    }

    # Container-specific fields
    _apply_container_fields(record_dict, entry, entrytype)

    # Pages (if available)
    pages = _normalize_pages(entry)
    if pages:
        record_dict[Fields.PAGES] = pages

    return record_dict
