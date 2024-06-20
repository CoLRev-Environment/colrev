#! /usr/bin/env python
"""Functionality to determine similarity betwen records."""
from __future__ import annotations

import typing

import colrev.env.utils
from colrev.constants import DefectCodes
from colrev.constants import Fields
from colrev.constants import FieldSet
from colrev.constants import FieldValues

if typing.TYPE_CHECKING:  # pragma: no cover
    import colrev.record.record


def _get_merging_triple(
    merging_record: colrev.record.record.Record, *, key: str, default_source: str
) -> typing.Tuple[
    str,
    str,
    str,
]:
    val = merging_record.data.get(key, "")

    # do not override provenance, ID, ... fields
    if key in [
        Fields.ID,
        Fields.MD_PROV,
        Fields.D_PROV,
        Fields.COLREV_ID,
        Fields.STATUS,
        Fields.ORIGIN,
        "MOVED_DUPE_ID",
    ]:
        val = ""

    field_provenance = merging_record.get_field_provenance(
        key=key, default_source=default_source
    )
    source = field_provenance["source"]
    note = field_provenance["note"]
    return val, source, note


def _merge_origins(
    main_record: colrev.record.record.Record,
    merging_record: colrev.record.record.Record,
) -> None:
    """Merge the origins with those of the merging_record"""

    if Fields.ORIGIN in merging_record.data:
        origins = main_record.data[Fields.ORIGIN] + merging_record.data[Fields.ORIGIN]
        main_record.data[Fields.ORIGIN] = sorted(list(set(origins)))


def _merge_status(
    main_record: colrev.record.record.Record,
    merging_record: colrev.record.record.Record,
) -> None:
    """Merge the status with the merging_record"""

    if Fields.STATUS in merging_record.data:
        # Set both status to the latter in the state model
        if main_record.data[Fields.STATUS] < merging_record.data[Fields.STATUS]:
            main_record.set_status(merging_record.data[Fields.STATUS])
        else:
            merging_record.set_status(main_record.data[Fields.STATUS])


def _select_author(
    record: colrev.record.record.Record, merging_record: colrev.record.record.Record
) -> str:
    if not record.has_quality_defects(
        key=Fields.AUTHOR
    ) and merging_record.has_quality_defects(key=Fields.AUTHOR):
        return record.data[Fields.AUTHOR]
    if record.has_quality_defects(
        key=Fields.AUTHOR
    ) and not merging_record.has_quality_defects(key=Fields.AUTHOR):
        return merging_record.data[Fields.AUTHOR]
    return record.data[Fields.AUTHOR]


def _select_pages(
    record: colrev.record.record.Record,
    merging_record: colrev.record.record.Record,
) -> str:
    best_pages = record.data[Fields.PAGES]
    if (
        "--" in merging_record.data[Fields.PAGES]
        and "--" not in record.data[Fields.PAGES]
    ):
        best_pages = merging_record.data[Fields.PAGES]
    return best_pages


def _select_title(
    record: colrev.record.record.Record,
    merging_record: colrev.record.record.Record,
) -> str:
    default = record.data[Fields.TITLE]
    candidate = merging_record.data[Fields.TITLE]
    best_title = record.data[Fields.TITLE]

    # Note : avoid switching titles
    if default.replace(" - ", ": ") == candidate.replace(" - ", ": "):
        return default

    default_upper = colrev.env.utils.percent_upper_chars(default)
    candidate_upper = colrev.env.utils.percent_upper_chars(candidate)

    if candidate[-1] not in ["*", "1", "2"]:
        # Relatively simple rule...
        # catches cases when default is all upper or title case
        if default_upper > candidate_upper:
            best_title = candidate
    return best_title


def _select_journal(
    record: colrev.record.record.Record,
    merging_record: colrev.record.record.Record,
) -> str:
    return _select_container_title(
        record.data[Fields.JOURNAL],
        merging_record.data[Fields.JOURNAL],
    )


def _select_booktitle(
    record: colrev.record.record.Record,
    merging_record: colrev.record.record.Record,
) -> str:
    return _select_container_title(
        record.data[Fields.BOOKTITLE],
        merging_record.data[Fields.BOOKTITLE],
    )


def _select_container_title(default: str, candidate: str) -> str:
    best_journal = default

    default_upper = colrev.env.utils.percent_upper_chars(default)
    candidate_upper = colrev.env.utils.percent_upper_chars(candidate)

    # Simple heuristic to avoid abbreviations
    if "." in default and "." not in candidate:
        best_journal = candidate
    # Relatively simple rule...
    # catches cases when default is all upper or title case
    if default_upper > candidate_upper:
        best_journal = candidate
    return best_journal


CUSTOM_FIELD_SELECTORS = {
    Fields.AUTHOR: _select_author,
    Fields.PAGES: _select_pages,
    Fields.TITLE: _select_title,
    Fields.JOURNAL: _select_journal,
    Fields.BOOKTITLE: _select_booktitle,
}


def _fuse_fields(
    main_record: colrev.record.record.Record,
    *,
    merging_record: colrev.record.record.Record,
    key: str,
) -> None:
    # Note : the assumption is that we need masterdata_provenance notes
    # only for authors

    quality_model = colrev.record.qm.quality_model.QualityModel(
        defects_to_ignore=[
            DefectCodes.MISSING,
            DefectCodes.RECORD_NOT_IN_TOC,
            DefectCodes.INCONSISTENT_WITH_DOI_METADATA,
            DefectCodes.CONTAINER_TITLE_ABBREVIATED,
            DefectCodes.INCONSISTENT_WITH_DOI_METADATA,
        ]
    )
    quality_model.run(record=main_record)
    quality_model.run(record=merging_record)

    if key in CUSTOM_FIELD_SELECTORS:
        if key in main_record.data:
            best_value = CUSTOM_FIELD_SELECTORS[key](
                main_record,
                merging_record,
            )
            if main_record.data[key] != best_value:
                main_record.update_field(
                    key=key,
                    value=best_value,
                    source=merging_record.get_field_provenance_source(key),
                    append_edit=False,
                )
        else:
            main_record.update_field(
                key=key,
                value=merging_record.data[key],
                source=merging_record.get_field_provenance_source(key),
                append_edit=False,
            )

    elif key == Fields.FILE:
        if key in main_record.data:
            main_record.data[key] = (
                main_record.data[key] + ";" + merging_record.data.get(key, "")
            )
        else:
            main_record.data[key] = merging_record.data[key]
    elif key in [Fields.URL]:
        if (
            key in main_record.data
            and main_record.data[key].rstrip("/")
            != merging_record.data[key].rstrip("/")
            and "https" not in main_record.data[key]
        ):
            main_record.update_field(
                key=key,
                value=merging_record.data[key],
                source=merging_record.get_field_provenance_source(key),
                append_edit=False,
            )

    elif main_record.data.get(key, "") in [
        "",
        FieldValues.UNKNOWN,
    ] and merging_record.data.get(key, "") not in ["", FieldValues.UNKNOWN]:
        if _preserve_ignore_missing(main_record, key=key):
            return
        main_record.update_field(
            key=key,
            value=merging_record.data[key],
            source=merging_record.get_field_provenance_source(key),
            append_edit=False,
        )


def _preserve_ignore_missing(
    main_record: colrev.record.record.Record, *, key: str
) -> bool:
    if main_record.ignored_defect(key=key, defect=DefectCodes.MISSING):
        return True
    return False


def _merging_record_preferred(
    merging_record: colrev.record.record.Record,
    *,
    preferred_masterdata_source_prefixes: list,
) -> bool:
    if Fields.ORIGIN not in merging_record.data:
        return False
    merging_record_preferred = False
    if any(
        any(ps in origin for ps in preferred_masterdata_source_prefixes)
        for origin in merging_record.data[Fields.ORIGIN]
    ):
        merging_record_preferred = True
    return merging_record_preferred


def _prep_incoming_masterdata_merge(
    main_record: colrev.record.record.Record,
    merging_record: colrev.record.record.Record,
) -> None:
    if (
        not main_record.masterdata_is_curated()
        and merging_record.masterdata_is_curated()
    ):
        main_record.data[Fields.MD_PROV] = merging_record.data[Fields.MD_PROV]
        # Note : remove all masterdata fields
        # because the curated record may have fewer masterdata fields
        # and we iterate over the curated record (merging_record) in the next step
        for k in list(main_record.data.keys()):
            if k in FieldSet.IDENTIFYING_FIELD_KEYS and k != Fields.PAGES:
                del main_record.data[k]


def merge(
    main_record: colrev.record.record.Record,
    merging_record: colrev.record.record.Record,
    *,
    default_source: str,
    preferred_masterdata_source_prefixes: list,
) -> None:
    """General-purpose record merging
    for preparation, curated/non-curated records and records with origins


    Apply heuristics to create a fusion of the best fields based on
    quality heuristics"""

    merging_record_preferred = _merging_record_preferred(
        merging_record,
        preferred_masterdata_source_prefixes=preferred_masterdata_source_prefixes,
    )

    _merge_origins(main_record, merging_record)
    _merge_status(main_record, merging_record)

    _prep_incoming_masterdata_merge(main_record, merging_record)

    for key in list(merging_record.data.keys()):
        val, source, note = _get_merging_triple(
            merging_record, key=key, default_source=default_source
        )
        if val == "":
            continue

        # Do not change if MERGING_RECORD is not curated and main_record is curated
        if (
            main_record.masterdata_is_curated()
            and not merging_record.masterdata_is_curated()
        ):
            continue

        # Always update from curated merging_records if it is curated
        if merging_record.masterdata_is_curated():
            main_record.data[key] = merging_record.data[key]
            if key not in FieldSet.IDENTIFYING_FIELD_KEYS + [Fields.ENTRYTYPE]:
                main_record.add_field_provenance(key=key, source=source, note=note)

        # Part 1: identifying fields
        if key in FieldSet.IDENTIFYING_FIELD_KEYS:
            if merging_record_preferred:
                main_record.update_field(
                    key=key, value=str(val), source=source, append_edit=False
                )

            # Fuse best fields if none is curated
            else:
                _fuse_fields(
                    main_record,
                    merging_record=merging_record,
                    key=key,
                )

        # Part 2: other fields
        else:
            # keep existing values per default
            if key in main_record.data:
                continue
            main_record.update_field(
                key=key,
                value=str(val),
                source=source,
                note=note,
                keep_source_if_equal=True,
                append_edit=False,
            )
