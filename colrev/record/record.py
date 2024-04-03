#! /usr/bin/env python
"""Functionality for individual records."""
from __future__ import annotations

import pprint
import typing
from copy import deepcopy
from pathlib import Path
from typing import Optional
from typing import TYPE_CHECKING

import dictdiffer

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.record.record_identifier
import colrev.record.record_merger
import colrev.record.record_similarity
from colrev.constants import Colors
from colrev.constants import DefectCodes
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import FieldSet
from colrev.constants import FieldValues
from colrev.constants import RecordState

if TYPE_CHECKING:  # pragma: no cover
    import colrev.review_manager
    import colrev.record.qm.quality_model

# pylint: disable=too-many-public-methods


class Record:
    """The Record class provides a range of basic convenience functions"""

    # Fields that are stored as lists (items separated by newlines)
    list_fields_keys = [
        Fields.ORIGIN,
        # "colrev_pdf_id",
        # Fields.SCREENING_CRITERIA,
    ]

    pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)

    def __init__(self, data: dict) -> None:
        self.data = data
        """Dictionary containing the record data"""
        # Note : avoid parsing upon Record instantiation as much as possible
        # to maintain high performance and ensure pickle-abiligy (in multiprocessing)

    def __repr__(self) -> str:  # pragma: no cover
        return self.pp.pformat(self.data)

    def __str__(self) -> str:
        identifying_keys_order = [Fields.ID, Fields.ENTRYTYPE] + [
            k for k in FieldSet.IDENTIFYING_FIELD_KEYS if k in self.data
        ]
        complementary_keys_order = [
            k for k, v in self.data.items() if k not in identifying_keys_order
        ]

        ik_sorted = {k: v for k, v in self.data.items() if k in identifying_keys_order}
        ck_sorted = {
            k: v for k, v in self.data.items() if k in complementary_keys_order
        }
        ret_str = (
            self.pp.pformat(ik_sorted)[:-1] + "\n" + self.pp.pformat(ck_sorted)[1:]
        )

        return ret_str

    def __eq__(self, other: object) -> bool:
        return self.__dict__ == other.__dict__

    def print_citation_format(self) -> None:
        """Print the record as a citation"""
        formatted_ref = (
            f"{self.data.get(Fields.AUTHOR, '')} ({self.data.get(Fields.YEAR, '')}) "
            + f"{self.data.get(Fields.TITLE, '')}. "
            + f"{self.data.get(Fields.JOURNAL, '')}{self.data.get(Fields.BOOKTITLE, '')}, "
            + f"{self.data.get(Fields.VOLUME, '')} ({self.data.get(Fields.NUMBER, '')})"
        )
        print(formatted_ref)

    def copy(self) -> Record:
        """Copy the record object"""
        return Record(deepcopy(self.data))

    def copy_prep_rec(self) -> colrev.record.record_prep.PrepRecord:
        """Copy the record object (as a PrepRecord)"""
        return colrev.record.record_prep.PrepRecord(deepcopy(self.data))

    def update_by_record(self, update_record: Record) -> None:
        """Update all data of a record object based on another record"""
        self.data = update_record.copy_prep_rec().get_data()

    def get_diff(
        self, other_record: Record, *, identifying_fields_only: bool = True
    ) -> list:
        """Get diff between record objects"""

        # pylint: disable=too-many-branches

        diff = []
        if identifying_fields_only:
            for selected_tuple in list(
                dictdiffer.diff(self.get_data(), other_record.get_data())
            ):
                if selected_tuple[0] == "change":
                    if selected_tuple[1] in FieldSet.IDENTIFYING_FIELD_KEYS:
                        diff.append(selected_tuple)
                if selected_tuple[0] == "add":
                    addition_list: typing.Tuple = ("add", "", [])
                    for addition_item in selected_tuple[2]:
                        if addition_item[0] in FieldSet.IDENTIFYING_FIELD_KEYS:
                            addition_list[2].append(addition_item)
                    if addition_list[2]:
                        diff.append(addition_list)
                if selected_tuple[0] == "remove":
                    removal_list: typing.Tuple = ("remove", "", [])
                    for removal_item in selected_tuple[2]:
                        if removal_item[0] in FieldSet.IDENTIFYING_FIELD_KEYS:
                            removal_list[2].append(removal_item)
                    if removal_list[2]:
                        diff.append(removal_list)
        else:
            diff = list(dictdiffer.diff(self.get_data(), other_record.get_data()))

        return diff

    def format_bib_style(self) -> str:
        """Simple formatter for bibliography-style output"""
        bib_formatted = (
            self.data.get(Fields.AUTHOR, "")
            + " ("
            + self.data.get(Fields.YEAR, "")
            + ") "
            + self.data.get(Fields.TITLE, "")
            + ". "
            + self.data.get(Fields.JOURNAL, "")
            + self.data.get(Fields.BOOKTITLE, "")
            + ", ("
            + self.data.get(Fields.VOLUME, "")
            + ") "
            + self.data.get(Fields.NUMBER, "")
        )
        return bib_formatted

    def get_data(self) -> dict:
        """Get the record data"""

        if not isinstance(self.data.get(Fields.ORIGIN, []), list):
            self.data[Fields.ORIGIN] = self.data[Fields.ORIGIN].rstrip(";").split(";")
        assert isinstance(self.data.get(Fields.ORIGIN, []), list)

        return self.data

    def set_masterdata_curated(self, source: str) -> None:
        """Set record masterdata to curated"""
        self.data[Fields.MD_PROV] = {
            FieldValues.CURATED: {"source": source, "note": ""}
        }

    def masterdata_is_curated(self) -> bool:
        """Check whether the record masterdata is curated"""
        return FieldValues.CURATED in self.data.get(Fields.MD_PROV, {})

    def set_status(self, target_state: RecordState, *, force: bool = False) -> None:
        """Set the record status"""

        if RecordState.md_prepared == target_state and not force:
            if self.has_quality_defects():
                target_state = RecordState.md_needs_manual_preparation
        # pylint: disable=colrev-direct-status-assign
        self.data[Fields.STATUS] = target_state

    def get_value(self, key: str, *, default: Optional[str] = None) -> str:
        """Get a record value (based on the key parameter)"""
        if default is not None:
            try:
                ret = self.data[key]
                return ret
            except KeyError:
                return default
        else:
            return self.data[key]

    def get_colrev_id(self) -> list:
        """Get the colrev_id of a record"""
        # Note : do not automatically create colrev_ids
        # or at least keep in mind that this will not be possible for some records
        colrev_id = []
        if Fields.COLREV_ID in self.data:
            if isinstance(self.data[Fields.COLREV_ID], str):
                colrev_id = [
                    cid.lstrip() for cid in self.data[Fields.COLREV_ID].split(";")
                ]
            elif isinstance(self.data[Fields.COLREV_ID], list):
                colrev_id = self.data[Fields.COLREV_ID]
        return [c for c in colrev_id if len(c) > 20]

    # pylint: disable=too-many-arguments
    def update_field(
        self,
        *,
        key: str,
        value: str,
        source: str,
        note: str = "",
        keep_source_if_equal: bool = True,
        append_edit: bool = True,
    ) -> None:
        """Update a record field (including provenance information)"""
        if keep_source_if_equal:
            if key in self.data:
                if self.data[key] == value:
                    return

        if key in FieldSet.IDENTIFYING_FIELD_KEYS:
            if not self.masterdata_is_curated():
                if append_edit and key in self.data:
                    if key in self.data.get(Fields.MD_PROV, {}):
                        source = self.data[Fields.MD_PROV][key]["source"] + "|" + source
                    else:
                        source = "original|" + source
                self.add_masterdata_provenance(key=key, source=source, note=note)
        else:
            if append_edit and key in self.data:
                if key in self.data.get(Fields.D_PROV, {}):
                    source = self.data[Fields.D_PROV][key]["source"] + "|" + source
                else:
                    source = "original|" + source
            self.add_data_provenance(key=key, source=source, note=note)
        self.data[key] = value

    def rename_field(self, *, key: str, new_key: str) -> None:
        """Rename a field"""
        if key not in self.data:
            return
        value = self.data[key]
        self.data[new_key] = value

        if key in FieldSet.IDENTIFYING_FIELD_KEYS:
            if Fields.MD_PROV not in self.data:
                self.data[Fields.MD_PROV] = {}
            if key in self.data[Fields.MD_PROV]:
                value_provenance = self.data[Fields.MD_PROV][key]
                if "source" in value_provenance:
                    value_provenance["source"] += f"|rename-from:{key}"
            else:
                value_provenance = {
                    "source": f"|rename-from:{key}",
                    "note": "",
                }
            self.data[Fields.MD_PROV][new_key] = value_provenance
        else:
            if Fields.D_PROV not in self.data:
                self.data[Fields.D_PROV] = {}
            if key in self.data[Fields.D_PROV]:
                value_provenance = self.data[Fields.D_PROV][key]
                if "source" in value_provenance:
                    value_provenance["source"] += f"|rename-from:{key}"
            else:
                value_provenance = {"source": f"|rename-from:{key}", "note": ""}
            self.data[Fields.D_PROV][new_key] = value_provenance

        self.remove_field(key=key)

    def align_provenance(self) -> None:
        """Remove unnecessary provenance information and add missing provenance information"""
        if Fields.MD_PROV not in self.data:
            self.data[Fields.MD_PROV] = {}
        if Fields.D_PROV not in self.data:
            self.data[Fields.D_PROV] = {}
        for key in list(self.data[Fields.MD_PROV].keys()):
            if (
                key not in self.data
                and key != FieldValues.CURATED
                and "IGNORE:missing" not in self.get_masterdata_provenance_notes(key)
            ):
                del self.data[Fields.MD_PROV][key]
        for key in list(self.data[Fields.D_PROV].keys()):
            if (
                key not in self.data
                and "IGNORE:missing" not in self.get_data_provenance_notes(key)
            ):
                del self.data[Fields.D_PROV][key]

        for non_prov_key in [Fields.ENTRYTYPE, Fields.ID] + FieldSet.PROVENANCE_KEYS:
            self.data[Fields.MD_PROV].pop(non_prov_key, None)
            self.data[Fields.D_PROV].pop(non_prov_key, None)

        for key in self.data.keys():
            if key in FieldSet.PROVENANCE_KEYS + [Fields.ID, Fields.ENTRYTYPE]:
                continue
            if key in FieldSet.IDENTIFYING_FIELD_KEYS:
                if (
                    not self.masterdata_is_curated()
                    and key not in self.data[Fields.MD_PROV]
                ):
                    self.data[Fields.MD_PROV][key] = {"source": "manual", "note": ""}
            elif key not in self.data[Fields.D_PROV]:
                self.data[Fields.D_PROV][key] = {"source": "manual", "note": ""}

    # pylint: disable=too-many-branches
    def change_entrytype(
        self,
        new_entrytype: str,
        *,
        qm: colrev.record.qm.quality_model.QualityModel,
    ) -> None:
        """Change the ENTRYTYPE"""
        for value in self.data.get(Fields.MD_PROV, {}).values():
            if any(
                x in value["note"]
                for x in [DefectCodes.INCONSISTENT_WITH_ENTRYTYPE, DefectCodes.MISSING]
            ):
                value["note"] = ""
        missing_fields = [k for k, v in self.data.items() if v == FieldValues.UNKNOWN]
        for missing_field in missing_fields:
            self.remove_field(key=missing_field)

        self.align_provenance()

        self.data[Fields.ENTRYTYPE] = new_entrytype
        if new_entrytype in [ENTRYTYPES.INPROCEEDINGS, ENTRYTYPES.PROCEEDINGS]:
            if Fields.JOURNAL in self.data and Fields.BOOKTITLE not in self.data:
                self.rename_field(key=Fields.JOURNAL, new_key=Fields.BOOKTITLE)
        elif new_entrytype == ENTRYTYPES.ARTICLE:
            if Fields.BOOKTITLE in self.data:
                self.rename_field(key=Fields.BOOKTITLE, new_key=Fields.JOURNAL)
        elif new_entrytype in [
            ENTRYTYPES.INBOOK,
            ENTRYTYPES.BOOK,
            ENTRYTYPES.INCOLLECTION,
            ENTRYTYPES.PHDTHESIS,
            ENTRYTYPES.THESIS,
            ENTRYTYPES.MASTERSTHESIS,
            ENTRYTYPES.BACHELORTHESIS,
            ENTRYTYPES.TECHREPORT,
            ENTRYTYPES.UNPUBLISHED,
            ENTRYTYPES.MISC,
            ENTRYTYPES.SOFTWARE,
            ENTRYTYPES.ONLINE,
            ENTRYTYPES.CONFERENCE,
        ]:
            pass
        else:
            raise colrev_exceptions.MissingRecordQualityRuleSpecification(
                f"No ENTRYTYPE specification ({new_entrytype})"
            )

        self.run_quality_model(qm=qm)

    def remove_field(
        self, *, key: str, not_missing_note: bool = False, source: str = ""
    ) -> None:
        """Remove a field"""

        if key in self.data:
            del self.data[key]

        if Fields.MD_PROV not in self.data:
            self.data[Fields.MD_PROV] = {}

        if not_missing_note and key in FieldSet.IDENTIFYING_FIELD_KEYS:
            # Example: journal without number
            # we should keep that information that a particular masterdata
            # field is not required
            if key not in self.data[Fields.MD_PROV]:
                self.data[Fields.MD_PROV][key] = {"source": "manual", "note": ""}
            self.data[Fields.MD_PROV][key]["note"] = f"IGNORE:{DefectCodes.MISSING}"
            if source != "":
                self.data[Fields.MD_PROV][key]["source"] = source
        else:
            if key in self.data.get(Fields.MD_PROV, {}):
                del self.data[Fields.MD_PROV][key]
            if key in self.data.get(Fields.D_PROV, {}):
                del self.data[Fields.D_PROV][key]

    def set_masterdata_complete(
        self, *, source: str, masterdata_repository: bool, replace_source: bool = True
    ) -> None:
        """Set the masterdata to complete"""
        # pylint: disable=too-many-branches
        if self.masterdata_is_curated() or masterdata_repository:
            return

        if Fields.MD_PROV not in self.data:
            self.data[Fields.MD_PROV] = {}
        md_p_dict = self.data[Fields.MD_PROV]

        for identifying_field_key in FieldSet.IDENTIFYING_FIELD_KEYS:
            if identifying_field_key in [Fields.AUTHOR, Fields.TITLE, Fields.YEAR]:
                continue
            if self.data.get(identifying_field_key, "NA") == FieldValues.UNKNOWN:
                del self.data[identifying_field_key]
            if identifying_field_key in md_p_dict:
                note = md_p_dict[identifying_field_key]["note"]
                if (
                    DefectCodes.MISSING in note
                    and f"IGNORE:{DefectCodes.MISSING}" not in note
                ):
                    md_p_dict[identifying_field_key]["note"] = note.replace(
                        DefectCodes.MISSING, ""
                    )

        if self.data[Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE:
            if Fields.VOLUME not in self.data:
                if Fields.VOLUME in self.data[Fields.MD_PROV]:
                    self.data[Fields.MD_PROV][Fields.VOLUME][
                        "note"
                    ] = f"IGNORE:{DefectCodes.MISSING}"
                    if replace_source:
                        self.data[Fields.MD_PROV][Fields.VOLUME]["source"] = source
                else:
                    self.data[Fields.MD_PROV][Fields.VOLUME] = {
                        "source": source,
                        "note": f"IGNORE:{DefectCodes.MISSING}",
                    }

            if Fields.NUMBER not in self.data:
                if Fields.NUMBER in self.data[Fields.MD_PROV]:
                    self.data[Fields.MD_PROV][Fields.NUMBER][
                        "note"
                    ] = f"IGNORE:{DefectCodes.MISSING}"
                    if replace_source:
                        self.data[Fields.MD_PROV][Fields.NUMBER]["source"] = source
                else:
                    self.data[Fields.MD_PROV][Fields.NUMBER] = {
                        "source": source,
                        "note": f"IGNORE:{DefectCodes.MISSING}",
                    }

    def set_masterdata_consistent(self) -> None:
        """Set the masterdata to consistent"""
        if Fields.MD_PROV not in self.data:
            self.data[Fields.MD_PROV] = {}
        md_p_dict = self.data[Fields.MD_PROV]

        for identifying_field_key in FieldSet.IDENTIFYING_FIELD_KEYS:
            if identifying_field_key in md_p_dict:
                note = md_p_dict[identifying_field_key]["note"]
                if DefectCodes.INCONSISTENT_WITH_ENTRYTYPE in note:
                    md_p_dict[identifying_field_key]["note"] = note.replace(
                        DefectCodes.INCONSISTENT_WITH_ENTRYTYPE, ""
                    )

    def reset_pdf_provenance_notes(self) -> None:
        """Reset the PDF (file) provenance notes"""
        if Fields.D_PROV not in self.data:
            self.add_data_provenance_note(key=Fields.FILE, note="")
        else:
            if Fields.FILE in self.data[Fields.D_PROV]:
                self.data[Fields.D_PROV][Fields.FILE]["note"] = ""
            else:
                self.data[Fields.D_PROV][Fields.FILE] = {
                    "source": "NA",
                    "note": "",
                }

    @classmethod
    def get_record_change_score(cls, record_a: Record, record_b: Record) -> float:
        """Determine how much records changed

        This method is less sensitive than get_record_similarity, especially when
        fields are missing. For example, if the journal field is missing in both
        records, get_similarity will return a value > 1.0. The get_record_changes
        will return 0.0 (if all other fields are equal)."""

        return colrev.record.record_similarity.get_record_change_score(
            record_a, record_b
        )

    @classmethod
    def get_record_similarity(cls, record_a: Record, record_b: Record) -> float:
        """Determine the similarity between two records (their masterdata)"""

        return colrev.record.record_similarity.get_record_similarity(record_a, record_b)

    def get_field_provenance(
        self, *, key: str, default_source: str = "ORIGINAL"
    ) -> dict:
        """Get the provenance for a selected field (key)"""
        default_note = ""
        note = default_note
        source = default_source
        if key in FieldSet.IDENTIFYING_FIELD_KEYS:
            if Fields.MD_PROV in self.data and key in self.data[Fields.MD_PROV]:
                if "source" in self.data[Fields.MD_PROV][key]:
                    source = self.data[Fields.MD_PROV][key]["source"]
                if "note" in self.data[Fields.MD_PROV][key]:
                    note = self.data[Fields.MD_PROV][key]["note"]
        else:
            if Fields.D_PROV in self.data and key in self.data[Fields.D_PROV]:
                if "source" in self.data[Fields.D_PROV][key]:
                    source = self.data[Fields.D_PROV][key]["source"]
                if "note" in self.data[Fields.D_PROV][key]:
                    note = self.data[Fields.D_PROV][key]["note"]

        return {"source": source, "note": note}

    def get_masterdata_provenance_notes(self, key: str) -> list:
        """Get a masterdata provenance note based on a key"""
        if Fields.MD_PROV not in self.data:
            return []
        if key not in self.data[Fields.MD_PROV]:
            return []
        notes = self.data[Fields.MD_PROV][key]["note"].split(",")
        return [note for note in notes if note]

    def get_masterdata_provenance_source(self, key: str) -> str:
        """Get a masterdata provenance source based on a key"""
        if Fields.MD_PROV not in self.data:
            return ""
        if key not in self.data[Fields.MD_PROV]:
            return ""
        return self.data[Fields.MD_PROV][key]["source"]

    def get_data_provenance_source(self, key: str) -> str:
        """Get a data provenance source based on a key"""
        if Fields.D_PROV not in self.data:
            return ""
        if key not in self.data[Fields.D_PROV]:
            return ""
        return self.data[Fields.D_PROV][key]["source"]

    def remove_masterdata_provenance_note(self, *, key: str, note: str) -> None:
        """Remove a masterdata provenance note"""
        if Fields.MD_PROV not in self.data:
            return
        if key not in self.data[Fields.MD_PROV]:
            return
        notes = self.data[Fields.MD_PROV][key]["note"].split(",")
        if note not in notes:
            return
        self.data[Fields.MD_PROV][key]["note"] = ",".join(n for n in notes if n != note)

    def add_masterdata_provenance_note(self, *, key: str, note: str) -> None:
        """Add a masterdata provenance note (based on a key)"""
        if Fields.MD_PROV not in self.data:
            self.data[Fields.MD_PROV] = {}
        if key in self.data.get(Fields.MD_PROV, {}):
            if "" == self.data[Fields.MD_PROV][key]["note"] or "" == note:
                self.data[Fields.MD_PROV][key]["note"] = note
            elif note not in self.data[Fields.MD_PROV][key]["note"].split(","):
                self.data[Fields.MD_PROV][key]["note"] += f",{note}"
        else:
            self.data[Fields.MD_PROV][key] = {
                "source": "ORIGINAL",
                "note": note,
            }

    def get_data_provenance_notes(self, key: str) -> list:
        """Get a data provenance note based on a key"""
        if Fields.D_PROV not in self.data:
            return []
        if key not in self.data[Fields.D_PROV]:
            return []
        notes = self.data[Fields.D_PROV][key]["note"].split(",")
        return [note.strip() for note in notes if note]

    def add_data_provenance_note(self, *, key: str, note: str) -> None:
        """Add a data provenance note (based on a key)"""
        if Fields.D_PROV not in self.data:
            self.data[Fields.D_PROV] = {}
        if key in self.data[Fields.D_PROV]:
            if self.data[Fields.D_PROV][key]["note"] == "":
                self.data[Fields.D_PROV][key]["note"] = note
            elif note not in self.data[Fields.D_PROV][key]["note"].split(","):
                self.data[Fields.D_PROV][key]["note"] += f",{note}"
        else:
            self.data[Fields.D_PROV][key] = {
                "source": "ORIGINAL",
                "note": note,
            }

    def remove_data_provenance_note(self, *, key: str, note: str) -> None:
        """Remove a masterdata provenance note"""
        if Fields.D_PROV not in self.data:
            return
        if key not in self.data[Fields.D_PROV]:
            return
        notes = self.data[Fields.D_PROV][key]["note"].split(",")
        if note not in notes:
            return
        self.data[Fields.D_PROV][key]["note"] = ",".join(n for n in notes if n != note)

    def add_masterdata_provenance(
        self, *, key: str, source: str, note: str = ""
    ) -> None:
        """Add a masterdata provenance, including source and note (based on a key)"""
        if Fields.MD_PROV not in self.data:
            self.data[Fields.MD_PROV] = {}
        md_p_dict = self.data[Fields.MD_PROV]

        if key in md_p_dict:
            if md_p_dict[key]["note"] == "" or "" == note:
                md_p_dict[key]["note"] = note
            elif (
                DefectCodes.MISSING == note
                and f"IGNORE:{DefectCodes.MISSING}" in md_p_dict[key]["note"].split(",")
            ):
                md_p_dict[key]["note"] = DefectCodes.MISSING
            elif note not in md_p_dict[key]["note"].split(","):
                md_p_dict[key]["note"] += f",{note}"
            md_p_dict[key]["source"] = source
        else:
            md_p_dict[key] = {"source": source, "note": f"{note}"}

    def add_provenance_all(self, *, source: str) -> None:
        """Add a data provenance (source) to all fields"""
        if Fields.MD_PROV not in self.data:
            self.data[Fields.MD_PROV] = {}
        if Fields.D_PROV not in self.data:
            self.data[Fields.D_PROV] = {}

        md_p_dict = self.data[Fields.MD_PROV]
        d_p_dict = self.data[Fields.D_PROV]
        for key in self.data.keys():
            if key in [
                Fields.ENTRYTYPE,
                Fields.D_PROV,
                Fields.MD_PROV,
                Fields.STATUS,
                Fields.COLREV_ID,
            ]:
                continue
            if (
                key in FieldSet.IDENTIFYING_FIELD_KEYS
                and FieldValues.CURATED not in self.data[Fields.MD_PROV]
            ):
                md_p_dict[key] = {"source": source, "note": ""}
            else:
                d_p_dict[key] = {"source": source, "note": ""}

    def add_data_provenance(self, *, key: str, source: str, note: str = "") -> None:
        """Add a data provenance, including source and note (based on a key)"""
        if Fields.D_PROV not in self.data:
            self.data[Fields.D_PROV] = {}
        md_p_dict = self.data[Fields.D_PROV]
        if key in md_p_dict:
            if note != "":
                md_p_dict[key]["note"] += f",{note}"
            else:
                md_p_dict[key]["note"] = ""
            md_p_dict[key]["source"] = source
        else:
            md_p_dict[key] = {"source": source, "note": f"{note}"}

    def complete_provenance(self, *, source_info: str) -> bool:
        """Complete provenance information for indexing"""

        for key in list(self.data.keys()):
            if (
                key
                in [
                    Fields.COLREV_ID,
                    Fields.ENTRYTYPE,
                    Fields.ID,
                    Fields.METADATA_SOURCE_REPOSITORY_PATHS,
                    Fields.LOCAL_CURATED_METADATA,
                ]
                + FieldSet.PROVENANCE_KEYS
            ):
                continue

            if key in FieldSet.IDENTIFYING_FIELD_KEYS:
                if not self.masterdata_is_curated():
                    self.add_masterdata_provenance(key=key, source=source_info, note="")
            else:
                self.add_data_provenance(key=key, source=source_info, note="")

        return True

    def defects(self, field: str) -> typing.List[str]:
        """Get a list of defects for a field"""
        if field in self.data[Fields.MD_PROV]:
            return self.data[Fields.MD_PROV][field]["note"].split(",")
        if field in self.data[Fields.D_PROV]:
            return self.data[Fields.D_PROV][field]["note"].split(",")
        return []

    def ignore_defect(self, *, field: str, defect: str) -> None:
        """Ignore a defect for a field"""
        ignore_code = f"IGNORE:{defect}"

        if field in FieldSet.IDENTIFYING_FIELD_KEYS + [
            Fields.DOI,
            Fields.PUBMED_ID,
            Fields.ISBN,
        ]:
            if (
                Fields.MD_PROV not in self.data
                or field not in self.data[Fields.MD_PROV]
            ):
                self.add_masterdata_provenance_note(key=field, note=ignore_code)
            else:
                notes = self.data[Fields.MD_PROV][field]["note"].split(",")
                if defect in notes:
                    notes.remove(defect)
                if ignore_code not in notes:
                    notes.append(ignore_code)
                self.data[Fields.MD_PROV][field]["note"] = ",".join(notes)
        else:
            if Fields.D_PROV not in self.data or field not in self.data[Fields.D_PROV]:
                self.add_data_provenance_note(key=field, note=ignore_code)
            else:
                notes = self.data[Fields.D_PROV][field]["note"].split(",")
                if defect in notes:
                    notes.remove(defect)
                if ignore_code not in notes:
                    notes.append(ignore_code)
                self.data[Fields.D_PROV][field]["note"] = ",".join(notes)

    def ignored_defect(self, *, field: str, defect: str) -> bool:
        """Get a list of ignored defects for a record"""
        ignore_code = f"IGNORE:{defect}"
        if Fields.MD_PROV in self.data and field in self.data[Fields.MD_PROV]:
            notes = self.data[Fields.MD_PROV][field]["note"].split(",")
            return ignore_code in notes
        if Fields.D_PROV in self.data and field in self.data[Fields.D_PROV]:
            notes = self.data[Fields.D_PROV][field]["note"].split(",")
            return ignore_code in notes
        return False

    def has_pdf_defects(self) -> bool:
        """Check whether the PDF has quality defects"""

        if (
            Fields.D_PROV not in self.data
            or Fields.FILE not in self.data[Fields.D_PROV]
        ):
            return False

        return bool(
            [
                n
                for n in self.data[Fields.D_PROV][Fields.FILE]["note"].split(",")
                if not n.startswith("IGNORE:") and n != ""
            ]
        )

    def has_quality_defects(self, *, field: str = "") -> bool:
        """Check whether a record has quality defects"""
        if field != "":
            if field in self.data.get(Fields.MD_PROV, {}):
                note = self.data[Fields.MD_PROV][field]["note"]
                notes = note.split(",")
                notes = [n for n in notes if not n.startswith("IGNORE:")]
                return len(notes) == 0
            if field in self.data.get(Fields.D_PROV, {}):
                note = self.data[Fields.D_PROV][field]["note"]
                notes = note.split(",")
                notes = [n for n in notes if not n.startswith("IGNORE:")]
                return len(notes) == 0
            return False
        defect_codes = [
            n
            for x in self.data.get(Fields.MD_PROV, {}).values()
            for n in x["note"].split(",")
            if not n.startswith("IGNORE:") and n != ""
        ]
        return bool(defect_codes)

    def get_container_title(self, *, na_string: str = "NA") -> str:
        """Get the record's container title (journal name, booktitle, etc.)"""

        if Fields.ENTRYTYPE not in self.data:
            return self.data.get(
                Fields.JOURNAL, self.data.get(Fields.BOOKTITLE, na_string)
            )
        if self.data[Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE:
            return self.data.get(Fields.JOURNAL, na_string)
        if self.data[Fields.ENTRYTYPE] in [
            ENTRYTYPES.INPROCEEDINGS,
            ENTRYTYPES.PROCEEDINGS,
            ENTRYTYPES.INBOOK,
        ]:
            return self.data.get(Fields.BOOKTITLE, na_string)
        if self.data[Fields.ENTRYTYPE] == ENTRYTYPES.BOOK:
            return self.data.get(Fields.TITLE, na_string)
        return na_string

    def create_colrev_id(
        self,
        *,
        assume_complete: bool = False,
    ) -> str:
        """Returns the colrev_id of the Record."""

        return colrev.record.record_identifier.create_colrev_id(
            record=self,
            assume_complete=assume_complete,
        )

    @classmethod
    def get_colrev_pdf_id(
        cls,
        pdf_path: Path,
    ) -> str:  # pragma: no cover
        """Generate the colrev_pdf_id"""

        return colrev.record.record_identifier.create_colrev_pdf_id(pdf_path=pdf_path)

    def get_toc_key(self) -> str:
        """Get the record's toc-key"""
        return colrev.record.record_identifier.get_toc_key(self)

    def prescreen_exclude(self, *, reason: str, print_warning: bool = False) -> None:
        """Prescreen-exclude a record"""
        # Warn when setting rev_synthesized/rev_included to prescreen_excluded
        # Especially in cases in which the prescreen-exclusion decision
        # is revised (e.g., because a paper was retracted)
        # In these cases, the paper may already be in the data extraction/synthesis
        if self.data.get(Fields.STATUS, "NA") in [
            RecordState.rev_synthesized,
            RecordState.rev_included,
        ]:
            print(
                f"\n{Colors.RED}Warning: setting paper to prescreen_excluded. Please check and "
                f"remove from synthesis: {self.data['ID']}{Colors.END}\n"
            )

        self.set_status(RecordState.rev_prescreen_excluded)

        if (
            FieldValues.RETRACTED not in self.data.get(Fields.PRESCREEN_EXCLUSION, "")
            and FieldValues.RETRACTED == reason
            and print_warning
        ):
            print(
                f"\n{Colors.RED}Paper retracted and prescreen "
                f"excluded: {self.data['ID']}{Colors.END}\n"
            )
            self.data[Fields.RETRACTED] = FieldValues.RETRACTED

        self.data[Fields.PRESCREEN_EXCLUSION] = reason

        # Note: when records are prescreen-excluded during prep:
        to_drop = []
        for key, value in self.data.items():
            if value == FieldValues.UNKNOWN:
                to_drop.append(key)
        for key in to_drop:
            self.remove_field(key=key)

    def get_tei_filename(self) -> Path:
        """Get the TEI filename associated with the file (PDF)"""
        tei_filename = Path(f".tei/{self.data[Fields.ID]}.tei.xml")
        if Fields.FILE in self.data:
            tei_filename = Path(
                self.data[Fields.FILE].replace("pdfs/", ".tei/")
            ).with_suffix(".tei.xml")
        return tei_filename

    def run_pdf_quality_model(
        self,
        *,
        pdf_qm: colrev.record.qm.quality_model.QualityModel,
        set_prepared: bool = False,
    ) -> None:
        """Run the PDF quality model"""

        pdf_qm.run(record=self)
        if self.has_pdf_defects():
            self.set_status(RecordState.pdf_needs_manual_preparation)
        elif set_prepared:
            self.set_status(RecordState.pdf_prepared)

    def run_quality_model(
        self,
        *,
        qm: colrev.record.qm.quality_model.QualityModel,
        set_prepared: bool = False,
    ) -> None:
        """Update the masterdata provenance"""

        if Fields.MD_PROV not in self.data:
            self.data[Fields.MD_PROV] = {}

        self.is_retracted()

        if self.masterdata_is_curated():
            if set_prepared:
                self.set_status(RecordState.md_prepared)
            return

        # Apply the checkers (including field key requirements etc.)
        qm.run(record=self)

        if (
            Fields.STATUS in self.data
            and self.data[Fields.STATUS] == RecordState.rev_prescreen_excluded
        ):
            return

        if self.has_quality_defects():
            self.set_status(RecordState.md_needs_manual_preparation)
        elif set_prepared:
            self.set_status(RecordState.md_prepared)

    def is_retracted(self) -> bool:
        """Check for potential retracts"""

        if Fields.RETRACTED in self.data:
            self.prescreen_exclude(reason=FieldValues.RETRACTED, print_warning=True)
            return True

        # Legacy
        if (
            self.data.get("crossmark", "") == "True"
            or self.data.get("colrev.crossref.crossmark", "") == "True"
        ):
            self.prescreen_exclude(reason=FieldValues.RETRACTED, print_warning=True)
            self.remove_field(key="crossmark")
            self.remove_field(key="colrev.crossref.crossmark")
            return True
        if self.data.get("warning", "") == "Withdrawn (according to DBLP)":
            self.prescreen_exclude(reason=FieldValues.RETRACTED, print_warning=True)
            self.remove_field(key="warning")
            return True
        return False

    def merge(
        self,
        merging_record: Record,
        *,
        default_source: str,
        preferred_masterdata_source_prefixes: Optional[list] = None,
    ) -> None:
        """General-purpose record merging
        for preparation, curated/non-curated records and records with origins

        Apply heuristics to create a fusion of the best fields based on
        quality heuristics"""

        colrev.record.record_merger.merge(
            self,
            merging_record,
            default_source=default_source,
            preferred_masterdata_source_prefixes=preferred_masterdata_source_prefixes,
        )
