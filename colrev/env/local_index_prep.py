#! /usr/bin/env python
"""Prep for LocalIndex."""
from __future__ import annotations

import hashlib
from pathlib import Path

import colrev.env.environment_manager
import colrev.env.local_index_sqlite
import colrev.env.resources
import colrev.env.tei_parser
import colrev.exceptions as colrev_exceptions
import colrev.ops.check
import colrev.record.record
import colrev.review_manager
from colrev.constants import Fields
from colrev.constants import FieldSet
from colrev.constants import LocalIndexFields
from colrev.constants import RecordState


def _apply_status_requirements(record_dict: dict) -> None:
    if Fields.STATUS not in record_dict:
        raise colrev_exceptions.RecordNotIndexableException()

    # It is important to exclude md_prepared if the LocalIndex
    # is used to dissociate duplicates
    if record_dict[Fields.STATUS] in RecordState.get_non_processed_states():
        raise colrev_exceptions.RecordNotIndexableException()

    # Some prescreen_excluded records are not prepared
    if record_dict[Fields.STATUS] == RecordState.rev_prescreen_excluded:
        raise colrev_exceptions.RecordNotIndexableException()


def _remove_fields(record_dict: dict) -> None:
    # Do not cover deprecated fields
    for deprecated_field in ["pdf_hash"]:
        if deprecated_field in record_dict:
            print(f"Removing deprecated field: {deprecated_field}")
            del record_dict[deprecated_field]

    for field in ["note", "link"]:
        record_dict.pop(field, None)

    if Fields.SCREENING_CRITERIA in record_dict:
        del record_dict[Fields.SCREENING_CRITERIA]
    # Note: if the colrev_pdf_id has not been checked,
    # we cannot use it for retrieval or preparation.
    post_pdf_prepared_states = RecordState.get_post_x_states(
        state=RecordState.pdf_prepared
    )
    if record_dict[Fields.STATUS] not in post_pdf_prepared_states:
        record_dict.pop(Fields.PDF_ID, None)

    # Note : numbers of citations change regularly.
    # They should be retrieved from sources like crossref/doi.org
    record_dict.pop(Fields.CITED_BY, None)
    if record_dict.get(Fields.YEAR, "NA").isdigit():
        record_dict[Fields.YEAR] = int(record_dict[Fields.YEAR])
    else:
        raise colrev_exceptions.RecordNotIndexableException()

    if Fields.LANGUAGE in record_dict and len(record_dict[Fields.LANGUAGE]) != 3:
        print(f"Language not in ISO 639-3 format: {record_dict[Fields.LANGUAGE]}")
        del record_dict[Fields.LANGUAGE]


def _adjust_provenance_for_indexing(record_dict: dict) -> None:
    # Provenance should point to the original repository path.
    # If the provenance/source was example.bib (and the record is amended during indexing)
    # we wouldn't know where the example.bib belongs to.
    record = colrev.record.record.Record(record_dict)
    # Make sure that we don't add provenance information without corresponding fields
    record.align_provenance()
    for key in list(record.data.keys()):
        if not record.masterdata_is_curated():
            record.add_field_provenance(
                key=key, source=record_dict[Fields.METADATA_SOURCE_REPOSITORY_PATHS]
            )
        elif key not in FieldSet.IDENTIFYING_FIELD_KEYS + FieldSet.PROVENANCE_KEYS + [
            Fields.ID,
            Fields.ENTRYTYPE,
            Fields.METADATA_SOURCE_REPOSITORY_PATHS,
        ]:
            record.add_field_provenance(
                key=key,
                source=record_dict[Fields.METADATA_SOURCE_REPOSITORY_PATHS],
            )

    record.remove_field(key=Fields.METADATA_SOURCE_REPOSITORY_PATHS)
    record_dict = record.get_data()


def _prep_fields_for_indexing(record_dict: dict) -> None:
    # Note : file paths should be absolute when added to the LocalIndex
    if Fields.FILE in record_dict:
        pdf_path = Path(record_dict[Fields.FILE])
        if pdf_path.is_file():
            record_dict[Fields.FILE] = str(pdf_path)
        else:
            del record_dict[Fields.FILE]

    record_dict.pop(Fields.ORIGIN, None)


def _get_record_hash(record_dict: dict) -> str:
    # Note : may raise NotEnoughDataToIdentifyException
    string_to_hash = colrev.record.record.Record(record_dict).get_colrev_id()
    return hashlib.sha256(string_to_hash.encode("utf-8")).hexdigest()


def prepare_record_for_indexing(record_dict: dict) -> dict:
    """Prepare record for LocalIndex."""
    try:
        _apply_status_requirements(record_dict)
        _remove_fields(record_dict)
        _prep_fields_for_indexing(record_dict)
        _adjust_provenance_for_indexing(record_dict)
        cid_to_index = colrev.record.record.Record(record_dict).get_colrev_id()
        record_dict[Fields.COLREV_ID] = cid_to_index
        record_dict[LocalIndexFields.CITATION_KEY] = record_dict[Fields.ID]
        record_dict[LocalIndexFields.ID] = _get_record_hash(record_dict)

    except (
        colrev_exceptions.NotEnoughDataToIdentifyException
    ) as exc:  # pragma: no cover
        missing_key = ""
        if exc.missing_fields is not None:
            missing_key = ",".join(exc.missing_fields)
        raise colrev_exceptions.RecordNotIndexableException(
            missing_key=missing_key
        ) from exc

    return record_dict
