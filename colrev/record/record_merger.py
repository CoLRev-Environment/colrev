#! /usr/bin/env python
"""Functionality to determine similarity betwen records."""
from __future__ import annotations

import re
from typing import Optional
from typing import TYPE_CHECKING

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
from colrev.constants import Fields
from colrev.constants import FieldSet
from colrev.constants import FieldValues

if TYPE_CHECKING:
    import colrev.record.record


def _prevent_invalid_merges(
    main_record: colrev.record.record.Record,
    merging_record: colrev.record.record.Record,
) -> None:
    """Prevents invalid merges like ... part 1 / ... part 2"""

    lower_title_a = main_record.data.get(Fields.TITLE, "").lower()
    lower_title_b = merging_record.data.get(Fields.TITLE, "").lower()

    part_match_a = re.findall(r"part [A-Za-z0-9]+$", lower_title_a)
    part_match_b = re.findall(r"part [A-Za-z0-9]+$", lower_title_b)

    if part_match_a != part_match_b:
        raise colrev_exceptions.InvalidMerge(
            record_a=main_record, record_b=merging_record
        )

    terms_required_to_match = [
        "erratum",
        "correction",
        "corrigendum",
        "comment",
        "commentary",
        "response",
    ]
    terms_in_a = [t for t in terms_required_to_match if t in lower_title_a]
    terms_in_b = [t for t in terms_required_to_match if t in lower_title_b]

    if terms_in_a != terms_in_b:
        raise colrev_exceptions.InvalidMerge(
            record_a=main_record, record_b=merging_record
        )


def _get_merging_val(merging_record: colrev.record.record.Record, *, key: str) -> str:
    val = merging_record.data.get(key, "")

    if val == "":
        return ""
    if not val:
        return ""

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
        return ""

    return val


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


def merge(
    main_record: colrev.record.record.Record,
    merging_record: colrev.record.record.Record,
    *,
    default_source: str,
    preferred_masterdata_source_prefixes: Optional[list] = None,
) -> None:
    """General-purpose record merging
    for preparation, curated/non-curated records and records with origins


    Apply heuristics to create a fusion of the best fields based on
    quality heuristics"""

    # pylint: disable=too-many-branches

    merging_record_preferred = False
    if preferred_masterdata_source_prefixes:
        if any(
            any(ps in origin for ps in preferred_masterdata_source_prefixes)
            for origin in merging_record.data[Fields.ORIGIN]
        ):
            merging_record_preferred = True

    _prevent_invalid_merges(main_record, merging_record)
    _merge_origins(main_record, merging_record)
    _merge_status(main_record, merging_record)

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

    for key in list(merging_record.data.keys()):
        val = _get_merging_val(merging_record, key=key)
        if val == "":
            continue

        field_provenance = merging_record.get_field_provenance(
            key=key, default_source=default_source
        )
        source = field_provenance["source"]
        note = field_provenance["note"]

        # Always update from curated merging_records
        if merging_record.masterdata_is_curated():
            main_record.data[key] = merging_record.data[key]
            if key not in FieldSet.IDENTIFYING_FIELD_KEYS + [Fields.ENTRYTYPE]:
                main_record.add_data_provenance(key=key, source=source, note=note)

        # Do not change if MERGING_RECORD is not curated
        elif (
            main_record.masterdata_is_curated()
            and not merging_record.masterdata_is_curated()
        ):
            continue

        # Part 1: identifying fields
        if key in FieldSet.IDENTIFYING_FIELD_KEYS:
            if preferred_masterdata_source_prefixes:
                if merging_record_preferred:
                    main_record.update_field(
                        key=key, value=str(val), source=source, append_edit=False
                    )

            # Fuse best fields if none is curated
            else:
                _fuse_best_field(
                    main_record,
                    merging_record=merging_record,
                    key=key,
                    val=str(val),
                    source=source,
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


def _select_best_author(
    record: colrev.record.record.Record, merging_record: colrev.record.record.Record
) -> str:
    if not record.has_quality_defects(
        field=Fields.AUTHOR
    ) and merging_record.has_quality_defects(field=Fields.AUTHOR):
        return record.data[Fields.AUTHOR]
    if record.has_quality_defects(
        field=Fields.AUTHOR
    ) and not merging_record.has_quality_defects(field=Fields.AUTHOR):
        return merging_record.data[Fields.AUTHOR]

    if (
        len(record.data[Fields.AUTHOR]) > 0
        and len(merging_record.data[Fields.AUTHOR]) > 0
    ):
        default_mostly_upper = (
            colrev.env.utils.percent_upper_chars(record.data[Fields.AUTHOR]) > 0.8
        )
        candidate_mostly_upper = (
            colrev.env.utils.percent_upper_chars(merging_record.data[Fields.AUTHOR])
            > 0.8
        )

        # Prefer title case (not all-caps)
        if default_mostly_upper and not candidate_mostly_upper:
            return merging_record.data[Fields.AUTHOR]

    return record.data[Fields.AUTHOR]


def _select_best_pages(
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


def _select_best_title(
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


def _select_best_journal(
    record: colrev.record.record.Record,
    merging_record: colrev.record.record.Record,
) -> str:
    return _select_best_container_title(
        record.data[Fields.JOURNAL],
        merging_record.data[Fields.JOURNAL],
    )


def _select_best_booktitle(
    record: colrev.record.record.Record,
    merging_record: colrev.record.record.Record,
) -> str:
    return _select_best_container_title(
        record.data[Fields.BOOKTITLE],
        merging_record.data[Fields.BOOKTITLE],
    )


def _select_best_container_title(default: str, candidate: str) -> str:
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


def _fuse_best_field(
    main_record: colrev.record.record.Record,
    *,
    merging_record: colrev.record.record.Record,
    key: str,
    val: str,
    source: str,
) -> None:
    # Note : the assumption is that we need masterdata_provenance notes
    # only for authors

    custom_field_selectors = {
        Fields.AUTHOR: _select_best_author,
        Fields.PAGES: _select_best_pages,
        Fields.TITLE: _select_best_title,
        Fields.JOURNAL: _select_best_journal,
        Fields.BOOKTITLE: _select_best_booktitle,
    }

    if key in custom_field_selectors:
        if key in main_record.data:
            best_value = custom_field_selectors[key](
                main_record,
                merging_record,
            )
            if main_record.data[key] != best_value:
                main_record.update_field(
                    key=key, value=best_value, source=source, append_edit=False
                )
        else:
            main_record.update_field(
                key=key, value=val, source=source, append_edit=False
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
                key=key, value=val, source=source, append_edit=False
            )

    elif FieldValues.UNKNOWN == main_record.data.get(
        key, ""
    ) and FieldValues.UNKNOWN != merging_record.data.get(key, ""):
        main_record.data[key] = merging_record.data[key]
        if key in FieldSet.IDENTIFYING_FIELD_KEYS:
            main_record.add_masterdata_provenance(key=key, source=source)
        else:
            main_record.add_data_provenance(key=key, source=source)
