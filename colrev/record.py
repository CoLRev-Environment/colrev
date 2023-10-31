#! /usr/bin/env python
"""Functionality for individual records."""
from __future__ import annotations

import difflib
import io
import logging
import pprint
import re
import textwrap
import typing
from copy import deepcopy
from enum import Enum
from pathlib import Path
from typing import Optional
from typing import TYPE_CHECKING

import dictdiffer
import pandas as pd
import pdfminer
from nameparser import HumanName
from pdfminer.converter import TextConverter
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfdocument import PDFTextExtractionNotAllowed
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import resolve1
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfparser import PDFSyntaxError
from PyPDF2 import PdfFileReader
from PyPDF2 import PdfFileWriter
from thefuzz import fuzz

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.prep.utils as prep_utils
import colrev.qm.colrev_id
import colrev.qm.colrev_pdf_id
from colrev.constants import Colors
from colrev.constants import DefectCodes
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import FieldSet
from colrev.constants import FieldValues
from colrev.constants import Operations

if TYPE_CHECKING:
    import colrev.review_manager
    import colrev.qm.quality_model

# pylint: disable=too-many-lines
# pylint: disable=too-many-public-methods


class Record:
    """The Record class provides a range of basic convenience functions"""

    # Fields that are stored as lists (items separated by newlines)
    list_fields_keys = [
        Fields.ORIGIN,
        # "colrev_pdf_id",
        # Fields.SCREENING_CRITERIA,
    ]
    dict_fields_keys = [Fields.MD_PROV, Fields.D_PROV]

    pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)

    def __init__(self, *, data: dict) -> None:
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

    def copy(self) -> Record:
        """Copy the record object"""
        return Record(data=deepcopy(self.data))

    def copy_prep_rec(self) -> PrepRecord:
        """Copy the record object (as a PrepRecord)"""
        return PrepRecord(data=deepcopy(self.data))

    def update_by_record(self, *, update_record: Record) -> None:
        """Update all data of a record object based on another record"""
        self.data = update_record.copy_prep_rec().get_data()

    def get_diff(
        self, *, other_record: Record, identifying_fields_only: bool = True
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

    def __save_field_dict(self, *, input_dict: dict, input_key: str) -> list:
        list_to_return = []
        assert input_key in [Fields.MD_PROV, Fields.D_PROV]
        if input_key == Fields.MD_PROV:
            for key, value in input_dict.items():
                if isinstance(value, dict):
                    formated_node = ",".join(
                        sorted(e for e in value["note"].split(",") if "" != e)
                    )
                    list_to_return.append(f"{key}:{value['source']};{formated_node};")

        elif input_key == Fields.D_PROV:
            for key, value in input_dict.items():
                if isinstance(value, dict):
                    list_to_return.append(f"{key}:{value['source']};{value['note']};")

        return list_to_return

    def get_data(self, *, stringify: bool = False) -> dict:
        """Get the record data (optionally: in stringified version, i.e., without lists/dicts)"""

        def __get_stringified_record() -> dict:
            data_copy = deepcopy(self.data)

            def list_to_str(*, val: list) -> str:
                return ("\n" + " " * 36).join([f.rstrip() for f in val])

            for key in self.list_fields_keys:
                if key in data_copy:
                    if key in [Fields.ORIGIN]:
                        data_copy[key] = sorted(list(set(data_copy[key])))
                    for ind, val in enumerate(data_copy[key]):
                        if len(val) > 0:
                            if val[-1] != ";":
                                data_copy[key][ind] = val + ";"
                    data_copy[key] = list_to_str(val=data_copy[key])

            for key in self.dict_fields_keys:
                if key in data_copy:
                    if isinstance(data_copy[key], dict):
                        data_copy[key] = self.__save_field_dict(
                            input_dict=data_copy[key], input_key=key
                        )
                    if isinstance(data_copy[key], list):
                        data_copy[key] = list_to_str(val=data_copy[key])

            return data_copy

        if not isinstance(self.data.get(Fields.ORIGIN, []), list):
            self.data[Fields.ORIGIN] = self.data[Fields.ORIGIN].rstrip(";").split(";")
        assert isinstance(self.data.get(Fields.ORIGIN, []), list)

        if stringify:
            return __get_stringified_record()

        return self.data

    def masterdata_is_curated(self) -> bool:
        """Check whether the record masterdata is curated"""
        return FieldValues.CURATED in self.data.get(Fields.MD_PROV, {})

    def set_status(self, *, target_state: RecordState, force: bool = False) -> None:
        """Set the record status"""

        if RecordState.md_prepared == target_state and not force:
            if self.has_quality_defects():
                target_state = RecordState.md_needs_manual_preparation
        # pylint: disable=colrev-direct-status-assign
        self.data[Fields.STATUS] = target_state

    def prefix_non_standardized_field_keys(self, *, prefix: str) -> None:
        """Prefix non-standardized field keys"""
        for key in list(self.data.keys()):
            if key in FieldSet.STANDARDIZED_FIELD_KEYS:
                continue
            if key.startswith("colrev."):
                continue
            self.data[f"{prefix}.{key}"] = self.data.pop(key)

    def shares_origins(self, *, other_record: Record) -> bool:
        """Check at least one origin is shared with the other record"""
        return any(
            x in other_record.data.get(Fields.ORIGIN, [])
            for x in self.data.get(Fields.ORIGIN, [])
        )

    def get_value(self, *, key: str, default: Optional[str] = None) -> str:
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

    def has_overlapping_colrev_id(self, *, record: Record) -> bool:
        """Check if a record has an overlapping colrev_id with the other record"""
        own_colrev_ids = self.get_colrev_id()
        other_colrev_ids = record.get_colrev_id()
        if len(own_colrev_ids) > 0 and len(other_colrev_ids) > 0:
            if any(cid in own_colrev_ids for cid in other_colrev_ids):
                return True
        return False

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

    def change_entrytype(
        self,
        *,
        new_entrytype: str,
        qm: colrev.qm.quality_model.QualityModel,
    ) -> None:
        """Change the ENTRYTYPE"""
        for value in self.data.get(Fields.MD_PROV, {}).values():
            if DefectCodes.INCONSISTENT_WITH_ENTRYTYPE in value["note"]:
                value["note"] = ""
            if DefectCodes.MISSING in value["note"]:
                value["note"] = ""
        missing_fields = [k for k, v in self.data.items() if v == FieldValues.UNKNOWN]
        for missing_field in missing_fields:
            self.remove_field(key=missing_field)

        self.data[Fields.ENTRYTYPE] = new_entrytype
        if new_entrytype in [ENTRYTYPES.INPROCEEDINGS, ENTRYTYPES.PROCEEDINGS]:
            if self.data.get(Fields.VOLUME, "") == FieldValues.UNKNOWN:
                self.remove_field(key=Fields.VOLUME)
            if self.data.get(Fields.NUMBER, "") == FieldValues.UNKNOWN:
                self.remove_field(key=Fields.NUMBER)
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
                self.data[Fields.MD_PROV][key] = {}
            self.data[Fields.MD_PROV][key]["note"] = DefectCodes.NOT_MISSING
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
                if DefectCodes.MISSING in note and DefectCodes.NOT_MISSING not in note:
                    md_p_dict[identifying_field_key]["note"] = note.replace(
                        DefectCodes.MISSING, ""
                    )

        if self.data[Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE:
            if Fields.VOLUME not in self.data:
                if Fields.VOLUME in self.data[Fields.MD_PROV]:
                    self.data[Fields.MD_PROV][Fields.VOLUME][
                        "note"
                    ] = DefectCodes.NOT_MISSING
                    if replace_source:
                        self.data[Fields.MD_PROV][Fields.VOLUME]["source"] = source
                else:
                    self.data[Fields.MD_PROV][Fields.VOLUME] = {
                        "source": source,
                        "note": DefectCodes.NOT_MISSING,
                    }

            if Fields.NUMBER not in self.data:
                if Fields.NUMBER in self.data[Fields.MD_PROV]:
                    self.data[Fields.MD_PROV][Fields.NUMBER][
                        "note"
                    ] = DefectCodes.NOT_MISSING
                    if replace_source:
                        self.data[Fields.MD_PROV][Fields.NUMBER]["source"] = source
                else:
                    self.data[Fields.MD_PROV][Fields.NUMBER] = {
                        "source": source,
                        "note": DefectCodes.NOT_MISSING,
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

    def __merge_origins(self, *, merging_record: Record) -> None:
        """Merge the origins with those of the merging_record"""

        if Fields.ORIGIN in merging_record.data:
            origins = self.data[Fields.ORIGIN] + merging_record.data[Fields.ORIGIN]
            self.data[Fields.ORIGIN] = sorted(list(set(origins)))

    def __merge_status(self, *, merging_record: Record) -> None:
        """Merge the status with the merging_record"""

        if Fields.STATUS in merging_record.data:
            # Set both status to the latter in the state model
            if self.data[Fields.STATUS] < merging_record.data[Fields.STATUS]:
                self.set_status(target_state=merging_record.data[Fields.STATUS])
            else:
                merging_record.set_status(target_state=self.data[Fields.STATUS])

    def __get_merging_val(self, *, merging_record: Record, key: str) -> str:
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

    def __prevent_invalid_merges(self, *, merging_record: Record) -> None:
        """Prevents invalid merges like ... part 1 / ... part 2"""

        lower_title_a = self.data.get(Fields.TITLE, "").lower()
        lower_title_b = merging_record.data.get(Fields.TITLE, "").lower()

        part_match_a = re.findall(r"part [A-Za-z0-9]+$", lower_title_a)
        part_match_b = re.findall(r"part [A-Za-z0-9]+$", lower_title_b)

        if part_match_a != part_match_b:
            raise colrev_exceptions.InvalidMerge(record_a=self, record_b=merging_record)

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
            raise colrev_exceptions.InvalidMerge(record_a=self, record_b=merging_record)

    def merge(
        self,
        *,
        merging_record: Record,
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

        self.__prevent_invalid_merges(merging_record=merging_record)
        self.__merge_origins(merging_record=merging_record)
        self.__merge_status(merging_record=merging_record)

        if not self.masterdata_is_curated() and merging_record.masterdata_is_curated():
            self.data[Fields.MD_PROV] = merging_record.data[Fields.MD_PROV]
            # Note : remove all masterdata fields
            # because the curated record may have fewer masterdata fields
            # and we iterate over the curated record (merging_record) in the next step
            for k in list(self.data.keys()):
                if k in FieldSet.IDENTIFYING_FIELD_KEYS and k != Fields.PAGES:
                    del self.data[k]

        for key in list(merging_record.data.keys()):
            val = self.__get_merging_val(merging_record=merging_record, key=key)
            if val == "":
                continue

            field_provenance = merging_record.get_field_provenance(
                key=key, default_source=default_source
            )
            source = field_provenance["source"]
            note = field_provenance["note"]

            # Always update from curated merging_records
            if merging_record.masterdata_is_curated():
                self.data[key] = merging_record.data[key]
                if key not in FieldSet.IDENTIFYING_FIELD_KEYS + [Fields.ENTRYTYPE]:
                    self.add_data_provenance(key=key, source=source, note=note)

            # Do not change if MERGING_RECORD is not curated
            elif (
                self.masterdata_is_curated()
                and not merging_record.masterdata_is_curated()
            ):
                continue

            # Part 1: identifying fields
            if key in FieldSet.IDENTIFYING_FIELD_KEYS:
                if preferred_masterdata_source_prefixes:
                    if merging_record_preferred:
                        self.update_field(
                            key=key, value=str(val), source=source, append_edit=False
                        )

                # Fuse best fields if none is curated
                else:
                    self.__fuse_best_field(
                        merging_record=merging_record,
                        key=key,
                        val=str(val),
                        source=source,
                    )

            # Part 2: other fields
            else:
                # keep existing values per default
                if key in self.data:
                    continue
                self.update_field(
                    key=key,
                    value=str(val),
                    source=source,
                    note=note,
                    keep_source_if_equal=True,
                    append_edit=False,
                )

    @classmethod
    def __select_best_author(cls, *, record: Record, merging_record: Record) -> str:
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

    @classmethod
    def __select_best_pages(
        cls,
        *,
        record: Record,
        merging_record: Record,
    ) -> str:
        best_pages = record.data[Fields.PAGES]
        if (
            "--" in merging_record.data[Fields.PAGES]
            and "--" not in record.data[Fields.PAGES]
        ):
            best_pages = merging_record.data[Fields.PAGES]
        return best_pages

    @classmethod
    def __select_best_title(
        cls,
        *,
        record: Record,
        merging_record: Record,
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

    @classmethod
    def __select_best_journal(
        cls,
        *,
        record: Record,
        merging_record: Record,
    ) -> str:
        return cls.__select_best_container_title(
            default=record.data[Fields.JOURNAL],
            candidate=merging_record.data[Fields.JOURNAL],
        )

    @classmethod
    def __select_best_booktitle(
        cls,
        *,
        record: Record,
        merging_record: Record,
    ) -> str:
        return cls.__select_best_container_title(
            default=record.data[Fields.BOOKTITLE],
            candidate=merging_record.data[Fields.BOOKTITLE],
        )

    @classmethod
    def __select_best_container_title(cls, *, default: str, candidate: str) -> str:
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

    def __fuse_best_field(
        self,
        *,
        merging_record: Record,
        key: str,
        val: str,
        source: str,
    ) -> None:
        # Note : the assumption is that we need masterdata_provenance notes
        # only for authors

        custom_field_selectors = {
            Fields.AUTHOR: self.__select_best_author,
            Fields.PAGES: self.__select_best_pages,
            Fields.TITLE: self.__select_best_title,
            Fields.JOURNAL: self.__select_best_journal,
            Fields.BOOKTITLE: self.__select_best_booktitle,
        }

        if key in custom_field_selectors:
            if key in self.data:
                best_value = custom_field_selectors[key](
                    record=self,
                    merging_record=merging_record,
                )
                if self.data[key] != best_value:
                    self.update_field(
                        key=key, value=best_value, source=source, append_edit=False
                    )
            else:
                self.update_field(key=key, value=val, source=source, append_edit=False)

        elif key == Fields.FILE:
            if key in self.data:
                self.data[key] = self.data[key] + ";" + merging_record.data.get(key, "")
            else:
                self.data[key] = merging_record.data[key]
        elif key in [Fields.URL]:
            if (
                key in self.data
                and self.data[key].rstrip("/") != merging_record.data[key].rstrip("/")
                and "https" not in self.data[key]
            ):
                self.update_field(key=key, value=val, source=source, append_edit=False)

        elif FieldValues.UNKNOWN == self.data.get(
            key, ""
        ) and FieldValues.UNKNOWN != merging_record.data.get(key, ""):
            self.data[key] = merging_record.data[key]
            if key in FieldSet.IDENTIFYING_FIELD_KEYS:
                self.add_masterdata_provenance(key=key, source=source)
            else:
                self.add_data_provenance(key=key, source=source)

    @classmethod
    def get_record_change_score(cls, *, record_a: Record, record_b: Record) -> float:
        """Determine how much records changed

        This method is less sensitive than get_record_similarity, especially when
        fields are missing. For example, if the journal field is missing in both
        records, get_similarity will return a value > 1.0. The get_record_changes
        will return 0.0 (if all other fields are equal)."""

        # At some point, this may become more sensitive to major changes
        str_a = (
            f"{record_a.data.get(Fields.AUTHOR, '')} ({record_a.data.get(Fields.YEAR, '')}) "
            + f"{record_a.data.get(Fields.TITLE, '')}. "
            + f"{record_a.data.get(Fields.JOURNAL, '')}{record_a.data.get(Fields.BOOKTITLE, '')}, "
            + f"{record_a.data.get(Fields.VOLUME, '')} ({record_a.data.get(Fields.NUMBER, '')})"
        )
        str_b = (
            f"{record_b.data.get(Fields.AUTHOR, '')} ({record_b.data.get(Fields.YEAR, '')}) "
            + f"{record_b.data.get(Fields.TITLE, '')}. "
            + f"{record_b.data.get(Fields.JOURNAL, '')}{record_b.data.get(Fields.BOOKTITLE, '')}, "
            + f"{record_b.data.get(Fields.VOLUME, '')} ({record_b.data.get(Fields.NUMBER, '')})"
        )
        return 1 - fuzz.ratio(str_a.lower(), str_b.lower()) / 100

    @classmethod
    def get_record_similarity(cls, *, record_a: Record, record_b: Record) -> float:
        """Determine the similarity between two records (their masterdata)"""
        record_a_dict = record_a.copy().get_data()
        record_b_dict = record_b.copy().get_data()

        mandatory_fields = [
            Fields.TITLE,
            Fields.AUTHOR,
            Fields.YEAR,
            Fields.JOURNAL,
            Fields.VOLUME,
            Fields.NUMBER,
            Fields.PAGES,
            Fields.BOOKTITLE,
        ]

        for mandatory_field in mandatory_fields:
            if (
                record_a_dict.get(mandatory_field, FieldValues.UNKNOWN)
                == FieldValues.UNKNOWN
            ):
                record_a_dict[mandatory_field] = ""
            if (
                record_b_dict.get(mandatory_field, FieldValues.UNKNOWN)
                == FieldValues.UNKNOWN
            ):
                record_b_dict[mandatory_field] = ""

        if "container_title" not in record_a_dict:
            record_a_dict["container_title"] = (
                record_a_dict.get(Fields.JOURNAL, "")
                + record_a_dict.get(Fields.BOOKTITLE, "")
                + record_a_dict.get(Fields.SERIES, "")
            )

        if "container_title" not in record_b_dict:
            record_b_dict["container_title"] = (
                record_b_dict.get(Fields.JOURNAL, "")
                + record_b_dict.get(Fields.BOOKTITLE, "")
                + record_b_dict.get(Fields.SERIES, "")
            )

        df_a = pd.DataFrame.from_dict([record_a_dict])  # type: ignore
        df_b = pd.DataFrame.from_dict([record_b_dict])  # type: ignore

        return Record.get_similarity(df_a=df_a.iloc[0], df_b=df_b.iloc[0])

    @classmethod
    def get_similarity(cls, *, df_a: dict, df_b: dict) -> float:
        """Determine the similarity between two records"""

        details = Record.get_similarity_detailed(record_a=df_a, record_b=df_b)
        return details["score"]

    @classmethod
    def get_similarity_detailed(cls, *, record_a: dict, record_b: dict) -> dict:
        """Determine the detailed similarities between records"""
        try:
            author_similarity = (
                fuzz.ratio(record_a[Fields.AUTHOR], record_b[Fields.AUTHOR]) / 100
            )

            title_similarity = (
                fuzz.ratio(
                    record_a[Fields.TITLE].lower().replace(":", "").replace("-", ""),
                    record_b[Fields.TITLE].lower().replace(":", "").replace("-", ""),
                )
                / 100
            )

            # partial ratio (catching 2010-10 or 2001-2002)
            year_similarity = (
                fuzz.ratio(str(record_a[Fields.YEAR]), str(record_b[Fields.YEAR])) / 100
            )

            outlet_similarity = 0.0
            if record_b["container_title"] and record_a["container_title"]:
                outlet_similarity = (
                    fuzz.ratio(record_a["container_title"], record_b["container_title"])
                    / 100
                )

            if str(record_a[Fields.JOURNAL]) != "nan":
                # Note: for journals papers, we expect more details
                volume_similarity = (
                    1 if (record_a[Fields.VOLUME] == record_b[Fields.VOLUME]) else 0
                )

                number_similarity = (
                    1 if (record_a[Fields.NUMBER] == record_b[Fields.NUMBER]) else 0
                )

                # page similarity is not considered at the moment.
                #
                # sometimes, only the first page is provided.
                # if str(record_a[Fields.PAGES]) == "nan" or str(record_b[Fields.PAGES]) == "nan":
                #     pages_similarity = 1
                # else:
                #     if record_a[Fields.PAGES] == record_b[Fields.PAGES]:
                #         pages_similarity = 1
                #     else:
                #         if record_a[Fields.PAGES].split("-")[0] ==
                #               record_b[Fields.PAGES].split("-")[0]:
                #             pages_similarity = 1
                #         else:
                #            pages_similarity = 0

                # Put more weight on other fields if the title is very common
                # ie., non-distinctive
                # The list is based on a large export of distinct papers, tabulated
                # according to titles and sorted by frequency
                if [record_a[Fields.TITLE], record_b[Fields.TITLE]] in [
                    ["editorial", "editorial"],
                    ["editorial introduction", "editorial introduction"],
                    ["editorial notes", "editorial notes"],
                    ["editor's comments", "editor's comments"],
                    ["book reviews", "book reviews"],
                    ["editorial note", "editorial note"],
                    ["reviewer ackowledgment", "reviewer ackowledgment"],
                ]:
                    weights = [0.175, 0, 0.175, 0.175, 0.275, 0.2]
                else:
                    weights = [0.2, 0.25, 0.13, 0.2, 0.12, 0.1]

                sim_names = [
                    Fields.AUTHOR,
                    Fields.TITLE,
                    Fields.YEAR,
                    "outlet",
                    Fields.VOLUME,
                    Fields.NUMBER,
                ]
                similarities = [
                    author_similarity,
                    title_similarity,
                    year_similarity,
                    outlet_similarity,
                    volume_similarity,
                    number_similarity,
                ]

            else:
                weights = [0.15, 0.75, 0.05, 0.05]
                sim_names = [
                    Fields.AUTHOR,
                    Fields.TITLE,
                    Fields.YEAR,
                    "outlet",
                ]
                similarities = [
                    author_similarity,
                    title_similarity,
                    year_similarity,
                    outlet_similarity,
                ]

            weighted_average = sum(
                similarities[g] * weights[g] for g in range(len(similarities))
            )

            details = (
                "["
                + ",".join([sim_names[g] for g in range(len(similarities))])
                + "]"
                + "*weights_vecor^T = "
                + "["
                + ",".join([str(similarities[g]) for g in range(len(similarities))])
                + "]*"
                + "["
                + ",".join([str(weights[g]) for g in range(len(similarities))])
                + "]^T"
            )
            similarity_score = round(weighted_average, 4)
        except AttributeError:
            similarity_score = 0
            details = ""
        return {"score": similarity_score, "details": details}

    def get_field_provenance(
        self, *, key: str, default_source: str = "ORIGINAL"
    ) -> dict:
        """Get the provenance for a selected field (key)"""
        default_note = ""
        note = default_note
        source = default_source
        if key in FieldSet.IDENTIFYING_FIELD_KEYS:
            if Fields.MD_PROV in self.data:
                if key in self.data.get(Fields.MD_PROV, {}):
                    if "source" in self.data[Fields.MD_PROV][key]:
                        source = self.data[Fields.MD_PROV][key]["source"]
                    if "note" in self.data[Fields.MD_PROV][key]:
                        note = self.data[Fields.MD_PROV][key]["note"]
        else:
            if Fields.D_PROV in self.data:
                if key in self.data[Fields.D_PROV]:
                    if "source" in self.data[Fields.D_PROV][key]:
                        source = self.data[Fields.D_PROV][key]["source"]
                    if "note" in self.data[Fields.D_PROV][key]:
                        note = self.data[Fields.D_PROV][key]["note"]

        return {"source": source, "note": note}

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
            elif DefectCodes.MISSING == note and DefectCodes.NOT_MISSING in md_p_dict[
                key
            ]["note"].split(","):
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

    def has_quality_defects(self, *, field: str = "") -> bool:
        """Check whether a record has quality defects"""
        if field != "":
            if field in self.data.get(Fields.MD_PROV, {}):
                note = self.data[Fields.MD_PROV][field]["note"]
                notes = note.split(",")
                notes = [n for n in notes if n != DefectCodes.NOT_MISSING]
                return len(notes) == 0
            if field in self.data.get(Fields.D_PROV, {}):
                note = self.data[Fields.D_PROV][field]["note"]
                notes = note.split(",")
                notes = [n for n in notes if n != DefectCodes.NOT_MISSING]
                return len(notes) == 0
            return False

        return any(
            x["note"] != ""
            for x in self.data.get(Fields.MD_PROV, {}).values()
            if not any(y == x["note"] for y in [DefectCodes.NOT_MISSING])
        )

    def get_container_title(self) -> str:
        """Get the record's container title (journal name, booktitle, etc.)"""
        container_title = "NA"
        if Fields.ENTRYTYPE not in self.data:
            container_title = self.data.get(
                Fields.JOURNAL, self.data.get(Fields.BOOKTITLE, "NA")
            )
        else:
            if self.data[Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE:
                container_title = self.data.get(Fields.JOURNAL, "NA")
            if self.data[Fields.ENTRYTYPE] == ENTRYTYPES.INPROCEEDINGS:
                container_title = self.data.get(Fields.BOOKTITLE, "NA")
            if self.data[Fields.ENTRYTYPE] == ENTRYTYPES.BOOK:
                container_title = self.data.get(Fields.TITLE, "NA")
            if self.data[Fields.ENTRYTYPE] == ENTRYTYPES.INBOOK:
                container_title = self.data.get(Fields.BOOKTITLE, "NA")
        return container_title

    def create_colrev_id(
        self,
        *,
        assume_complete: bool = False,
    ) -> str:
        """Returns the colrev_id of the Record."""

        return colrev.qm.colrev_id.create_colrev_id(
            record=self,
            assume_complete=assume_complete,
        )

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

        self.set_status(target_state=RecordState.rev_prescreen_excluded)

        if (
            FieldValues.RETRACTED not in self.data.get(Fields.PRESCREEN_EXCLUSION, "")
            and FieldValues.RETRACTED == reason
            and print_warning
        ):
            print(
                f"\n{Colors.RED}Paper retracted and prescreen "
                f"excluded: {self.data['ID']}{Colors.END}\n"
            )

        self.data[Fields.PRESCREEN_EXCLUSION] = reason

        # Note: when records are prescreen-excluded during prep:
        to_drop = []
        for key, value in self.data.items():
            if value == FieldValues.UNKNOWN:
                to_drop.append(key)
        for key in to_drop:
            self.remove_field(key=key)

    def extract_text_by_page(
        self,
        *,
        pages: Optional[list] = None,
    ) -> str:
        """Extract the text from the PDF for a given number of pages"""
        text_list: list = []
        pdf_path = Path(self.data[Fields.FILE]).absolute()

        # https://stackoverflow.com/questions/49457443/python-pdfminer-converts-pdf-file-into-one-chunk-of-string-with-no-spaces-betwee
        laparams = pdfminer.layout.LAParams()
        setattr(laparams, "all_texts", True)

        with open(pdf_path, "rb") as pdf_file:
            try:
                for page in PDFPage.get_pages(
                    pdf_file,
                    pagenos=pages,  # note: maybe skip potential cover pages?
                    caching=True,
                    check_extractable=True,
                ):
                    resource_manager = PDFResourceManager()
                    fake_file_handle = io.StringIO()
                    converter = TextConverter(
                        resource_manager, fake_file_handle, laparams=laparams
                    )
                    page_interpreter = PDFPageInterpreter(resource_manager, converter)
                    page_interpreter.process_page(page)

                    text = fake_file_handle.getvalue()
                    text_list += text

                    # close open handles
                    converter.close()
                    fake_file_handle.close()
            except (TypeError, KeyError):  # pragma: no cover
                pass
        return "".join(text_list)

    def set_pages_in_pdf(self) -> None:
        """Set the pages_in_file field based on the PDF"""
        pdf_path = Path(self.data[Fields.FILE]).absolute()
        with open(pdf_path, "rb") as file:
            parser = PDFParser(file)
            document = PDFDocument(parser)
            pages_in_file = resolve1(document.catalog["Pages"])["Count"]
        self.data["pages_in_file"] = pages_in_file

    def set_text_from_pdf(self) -> None:
        """Set the text_from_pdf field based on the PDF"""
        self.data["text_from_pdf"] = ""
        try:
            self.set_pages_in_pdf()
            text = self.extract_text_by_page(pages=[0, 1, 2])
            self.data["text_from_pdf"] = text.replace("\n", " ").replace("\x0c", "")

        except PDFSyntaxError:  # pragma: no cover
            self.add_data_provenance_note(key=Fields.FILE, note="pdf_reader_error")
            self.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)
        except PDFTextExtractionNotAllowed:  # pragma: no cover
            self.add_data_provenance_note(key=Fields.FILE, note="pdf_protected")
            self.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)

    def extract_pages(
        self, *, pages: list, project_path: Path, save_to_path: Optional[Path] = None
    ) -> None:  # pragma: no cover
        """Extract pages from the PDF (saveing them to the save_to_path)"""
        pdf_path = project_path / Path(self.data[Fields.FILE])
        pdf_reader = PdfFileReader(str(pdf_path), strict=False)
        writer = PdfFileWriter()
        for i in range(0, len(pdf_reader.pages)):
            if i in pages:
                continue
            writer.addPage(pdf_reader.getPage(i))
        with open(pdf_path, "wb") as outfile:
            writer.write(outfile)

        if save_to_path:
            writer_cp = PdfFileWriter()
            for page in pages:
                writer_cp.addPage(pdf_reader.getPage(page))
            filepath = Path(pdf_path)
            with open(save_to_path / filepath.name, "wb") as outfile:
                writer_cp.write(outfile)

    @classmethod
    def get_colrev_pdf_id(
        cls,
        *,
        pdf_path: Path,
    ) -> str:  # pragma: no cover
        """Generate the colrev_pdf_id"""

        return colrev.qm.colrev_pdf_id.create_colrev_pdf_id(pdf_path=pdf_path)

    def get_toc_key(self) -> str:
        """Get the record's toc-key"""

        try:
            if self.data[Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE:
                toc_key = (
                    self.data[Fields.JOURNAL]
                    .replace(" ", "-")
                    .replace("\\", "")
                    .replace("&", "and")
                    .lower()
                )
                toc_key += (
                    f"|{self.data[Fields.VOLUME]}"
                    if (
                        FieldValues.UNKNOWN
                        != self.data.get(Fields.VOLUME, FieldValues.UNKNOWN)
                    )
                    else "|-"
                )
                toc_key += (
                    f"|{self.data[Fields.NUMBER]}"
                    if (
                        FieldValues.UNKNOWN
                        != self.data.get(Fields.NUMBER, FieldValues.UNKNOWN)
                    )
                    else "|-"
                )

            elif self.data[Fields.ENTRYTYPE] == ENTRYTYPES.INPROCEEDINGS:
                toc_key = (
                    self.data[Fields.BOOKTITLE]
                    .replace(" ", "-")
                    .replace("\\", "")
                    .replace("&", "and")
                    .lower()
                    + f"|{self.data.get(Fields.YEAR, '')}"
                )
            else:
                msg = (
                    f"ENTRYTYPE {self.data[Fields.ENTRYTYPE]} "
                    + f"({self.data['ID']}) not toc-identifiable"
                )
                raise colrev_exceptions.NotTOCIdentifiableException(msg)
        except KeyError as exc:
            raise colrev_exceptions.NotTOCIdentifiableException(
                f"missing key {exc}"
            ) from exc

        return toc_key

    def print_citation_format(self) -> None:
        """Print the record as a citation"""
        formatted_ref = (
            f"{self.data.get(Fields.AUTHOR, '')} ({self.data.get(Fields.YEAR, '')}) "
            + f"{self.data.get(Fields.TITLE, '')}. "
            + f"{self.data.get(Fields.JOURNAL, '')}{self.data.get(Fields.BOOKTITLE, '')}, "
            + f"{self.data.get(Fields.VOLUME, '')} ({self.data.get(Fields.NUMBER, '')})"
        )
        print(formatted_ref)

    def get_tei_filename(self) -> Path:
        """Get the TEI filename associated with the file (PDF)"""
        tei_filename = Path(f".tei/{self.data[Fields.ID]}.tei.xml")
        if Fields.FILE in self.data:
            tei_filename = Path(
                self.data[Fields.FILE].replace("pdfs/", ".tei/")
            ).with_suffix(".tei.xml")
        return tei_filename

    @classmethod
    def print_diff_pair(cls, *, record_pair: list, keys: list) -> None:
        """Print the diff between two records"""

        def print_diff(change: tuple) -> str:
            diff = difflib.Differ()
            letters = list(diff.compare(change[1], change[0]))
            for i, letter in enumerate(letters):
                if letter.startswith("  "):
                    letters[i] = letters[i][-1]
                elif letter.startswith("+ "):
                    letters[i] = f"{Colors.RED}" + letters[i][-1] + f"{Colors.END}"
                elif letter.startswith("- "):
                    letters[i] = f"{Colors.GREEN}" + letters[i][-1] + f"{Colors.END}"
            res = "".join(letters).replace("\n", " ")
            return res

        for key in keys:
            prev_val = "_FIRST_VAL"
            for rec in record_pair:
                if prev_val == rec.get(key, "") or prev_val == "_FIRST_VAL":
                    line = f"{rec.get(key, '')}"
                else:
                    similarity = 0.0
                    if (
                        prev_val is not None
                        and rec.get(key, "") != ""
                        and prev_val != ""
                        and rec[key] is not None
                    ):
                        similarity = fuzz.partial_ratio(prev_val, rec[key]) / 100
                        # Note : the fuzz.partial_ratio works better for partial substrings
                        # from difflib import SequenceMatcher
                        # similarity = SequenceMatcher(None, prev_val, rec[key]).ratio()
                    if similarity < 0.5 or key in [
                        Fields.VOLUME,
                        Fields.NUMBER,
                        Fields.YEAR,
                    ]:
                        line = f"{Colors.RED}{rec.get(key, '')}{Colors.END}"
                    else:
                        line = print_diff((prev_val, rec.get(key, "")))
                print(f"{key} : {line}")
                prev_val = rec.get(key, "")
            print()

    def cleanup_pdf_processing_fields(self) -> None:
        """Cleanup the PDF processing fiels (text_from_pdf, pages_in_file)"""
        if "text_from_pdf" in self.data:
            del self.data["text_from_pdf"]
        if "pages_in_file" in self.data:
            del self.data["pages_in_file"]

    def run_quality_model(
        self, *, qm: colrev.qm.quality_model.QualityModel, set_prepared: bool = False
    ) -> None:
        """Update the masterdata provenance"""

        if Fields.MD_PROV not in self.data:
            self.data[Fields.MD_PROV] = {}

        self.check_potential_retracts()

        if self.masterdata_is_curated():
            if set_prepared:
                self.set_status(target_state=RecordState.md_prepared)
            return

        # Apply the checkers (including field key requirements etc.)
        qm.run(record=self)

        if (
            Fields.STATUS in self.data
            and self.data[Fields.STATUS] == RecordState.rev_prescreen_excluded
        ):
            return

        if self.has_quality_defects():
            self.set_status(target_state=RecordState.md_needs_manual_preparation)
        elif set_prepared:
            self.set_status(target_state=RecordState.md_prepared)

    def check_potential_retracts(self) -> bool:
        """Check for potential retracts"""
        # Note : we retrieved metadata in get_masterdata_from_crossref()
        if self.data.get("crossmark", "") == "True":
            self.prescreen_exclude(reason=FieldValues.RETRACTED, print_warning=True)
            self.remove_field(key="crossmark")
            return True
        if self.data.get("warning", "") == "Withdrawn (according to DBLP)":
            self.prescreen_exclude(reason=FieldValues.RETRACTED, print_warning=True)
            self.remove_field(key="warning")
            return True
        return False

    def print_prescreen_record(self) -> None:
        """Print the record for prescreen operations"""

        ret_str = f"  ID: {self.data['ID']} ({self.data[Fields.ENTRYTYPE]})"
        ret_str += (
            f"\n  {Colors.GREEN}{self.data.get(Fields.TITLE, 'no title')}{Colors.END}"
            f"\n  {self.data.get(Fields.AUTHOR, 'no-author')}"
        )
        if self.data[Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE:
            ret_str += (
                f"\n  {self.data.get(Fields.JOURNAL, 'no-journal')} "
                f"({self.data.get(Fields.YEAR, 'no-year')}) "
                f"{self.data.get(Fields.VOLUME, 'no-volume')}"
                f"({self.data.get(Fields.NUMBER, '')})"
            )
        elif self.data[Fields.ENTRYTYPE] == ENTRYTYPES.INPROCEEDINGS:
            ret_str += f"\n  {self.data.get(Fields.BOOKTITLE, 'no-booktitle')}"
        if Fields.ABSTRACT in self.data:
            lines = textwrap.wrap(
                self.data[Fields.ABSTRACT], 100, break_long_words=False
            )
            if lines:
                ret_str += f"\n  Abstract: {lines.pop(0)}\n"
                ret_str += "\n  ".join(lines) + ""

        if Fields.URL in self.data:
            ret_str += f"\n  url: {self.data[Fields.URL]}"

        if Fields.FILE in self.data:
            ret_str += f"\n  file: {self.data[Fields.FILE]}"

        print(ret_str)

    def print_pdf_prep_man(self) -> None:
        """Print the record for pdf-prep-man operations"""
        # pylint: disable=too-many-branches
        ret_str = ""
        if Fields.FILE in self.data:
            ret_str += (
                f"\nfile: {Colors.ORANGE}{self.data[Fields.FILE]}{Colors.END}\n\n"
            )

        pdf_prep_note = self.get_field_provenance(key=Fields.FILE)

        if "author_not_in_first_pages" in pdf_prep_note["note"]:
            ret_str += (
                f"{Colors.RED}{self.data.get(Fields.AUTHOR, 'no-author')}{Colors.END}\n"
            )
        else:
            ret_str += f"{Colors.GREEN}{self.data.get(Fields.AUTHOR, 'no-author')}{Colors.END}\n"

        if "title_not_in_first_pages" in pdf_prep_note["note"]:
            ret_str += (
                f"{Colors.RED}{self.data.get(Fields.TITLE, 'no title')}{Colors.END}\n"
            )
        else:
            ret_str += (
                f"{Colors.GREEN}{self.data.get(Fields.TITLE, 'no title')}{Colors.END}\n"
            )

        if self.data[Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE:
            ret_str += (
                f"{self.data.get(Fields.JOURNAL, 'no-journal')} "
                f"({self.data.get(Fields.YEAR, 'no-year')}) "
                f"{self.data.get(Fields.VOLUME, 'no-volume')}"
                f"({self.data.get(Fields.NUMBER, '')})"
            )
            if Fields.PAGES in self.data:
                if "nr_pages_not_matching" in pdf_prep_note["note"]:
                    ret_str += (
                        f", {Colors.RED}pp.{self.data[Fields.PAGES]}{Colors.END}\n"
                    )
                else:
                    ret_str += (
                        f", pp.{Colors.GREEN}{self.data[Fields.PAGES]}{Colors.END}\n"
                    )
            else:
                ret_str += "\n"
        elif self.data[Fields.ENTRYTYPE] == ENTRYTYPES.INPROCEEDINGS:
            ret_str += f"{self.data.get(Fields.BOOKTITLE, 'no-booktitle')}\n"
        if Fields.ABSTRACT in self.data:
            lines = textwrap.wrap(
                self.data[Fields.ABSTRACT], 100, break_long_words=False
            )
            ret_str += f"\nAbstract: {lines.pop(0)}\n"
            ret_str += "\n".join(lines) + "\n"

        if Fields.URL in self.data:
            ret_str += f"\nurl: {self.data[Fields.URL]}\n"

        print(ret_str)


class PrepRecord(Record):
    """The PrepRecord class provides a range of convenience functions for record preparation"""

    @classmethod
    def format_author_field(cls, *, input_string: str) -> str:
        """Format the author field (recognizing first/last names based on HumanName parser)"""

        def mostly_upper_case(input_string: str) -> bool:
            if not re.match(r"[a-zA-Z]+", input_string):
                return False
            input_string = input_string.replace(".", "").replace(",", "")
            words = input_string.split()
            return sum(word.isupper() for word in words) / len(words) > 0.8

        input_string = input_string.replace("\n", " ")
        # DBLP appends identifiers to non-unique authors
        input_string = str(re.sub(r"[0-9]{4}", "", input_string))

        if " and " in input_string:
            names = input_string.split(" and ")
        elif input_string.count(",") > 1:
            names = input_string.split(", ")
        else:
            names = [input_string]
        author_string = ""
        for name in names:
            # Note: https://github.com/derek73/python-nameparser
            # is very effective (maybe not perfect)

            parsed_name = HumanName(name)
            if mostly_upper_case(input_string.replace(" and ", "").replace("Jr", "")):
                parsed_name.capitalize(force=True)

            # Fix typical parser error
            if parsed_name.last == "" and parsed_name.title != "":
                parsed_name.last = parsed_name.title

            # pylint: disable=chained-comparison
            # Fix: when first names are abbreviated, nameparser creates errors:
            if (
                len(parsed_name.last) <= 3
                and parsed_name.last.isupper()
                and len(parsed_name.first) > 3
                and not parsed_name.first.isupper()
            ):
                # in these casees, first and last names are confused
                author_name_string = parsed_name.first + ", " + parsed_name.last
            else:
                parsed_name.string_format = "{last} {suffix}, {first} {middle}"
                # '{last} {suffix}, {first} ({nickname}) {middle}'
                author_name_string = str(parsed_name).replace(" , ", ", ")
                # Note: there are errors for the following author:
                # JR Cromwell and HK Gardner
                # The JR is probably recognized as Junior.
                # Check whether this is fixed in the Grobid name parser

            if author_string == "":
                author_string = author_name_string
            else:
                author_string = author_string + " and " + author_name_string

        return author_string

    @classmethod
    def __format_authors_string_for_comparison(cls, *, record: Record) -> None:
        if Fields.AUTHOR not in record.data:
            return
        authors = record.data[Fields.AUTHOR]
        authors = str(authors).lower()
        authors_string = ""
        authors = colrev.env.utils.remove_accents(input_str=authors)

        # abbreviate first names
        # "Webster, Jane" -> "Webster, J"
        # also remove all special characters and do not include separators (and)
        for author in authors.split(" and "):
            if "," in author:
                last_names = [
                    word[0] for word in author.split(",")[1].split(" ") if len(word) > 0
                ]
                authors_string = (
                    authors_string
                    + author.split(",")[0]
                    + " "
                    + " ".join(last_names)
                    + " "
                )
            else:
                authors_string = authors_string + author + " "
        authors_string = re.sub(r"[^A-Za-z0-9, ]+", "", authors_string.rstrip())
        record.data[Fields.AUTHOR] = authors_string

    def container_is_abbreviated(self) -> bool:
        """Check whether the container title is abbreviated"""
        if Fields.JOURNAL in self.data:
            if self.data[Fields.JOURNAL].count(".") > 2:
                return True
            if self.data[Fields.JOURNAL].isupper():
                return True
        if Fields.BOOKTITLE in self.data:
            if self.data[Fields.BOOKTITLE].count(".") > 2:
                return True
            if self.data[Fields.BOOKTITLE].isupper():
                return True
        # add heuristics? (e.g., Hawaii Int Conf Syst Sci)
        return False

    @classmethod
    def __abbreviate_container_titles(
        cls,
        *,
        record: colrev.record.PrepRecord,
        retrieved_record: colrev.record.PrepRecord,
    ) -> None:
        def abbreviate_container(*, record: colrev.record.Record, min_len: int) -> None:
            if Fields.JOURNAL in record.data:
                record.data[Fields.JOURNAL] = " ".join(
                    [x[:min_len] for x in record.data[Fields.JOURNAL].split(" ")]
                )

        def get_abbrev_container_min_len(*, record: colrev.record.Record) -> int:
            min_len = -1
            if Fields.JOURNAL in record.data:
                min_len = min(
                    len(x)
                    for x in record.data[Fields.JOURNAL].replace(".", "").split(" ")
                )
            if Fields.BOOKTITLE in record.data:
                min_len = min(
                    len(x)
                    for x in record.data[Fields.BOOKTITLE].replace(".", "").split(" ")
                )
            return min_len

        if record.container_is_abbreviated():
            min_len = get_abbrev_container_min_len(record=record)
            abbreviate_container(record=retrieved_record, min_len=min_len)
            abbreviate_container(record=record, min_len=min_len)
        if retrieved_record.container_is_abbreviated():
            min_len = get_abbrev_container_min_len(record=retrieved_record)
            abbreviate_container(record=record, min_len=min_len)
            abbreviate_container(record=retrieved_record, min_len=min_len)

    @classmethod
    def __prep_records_for_similarity(
        cls,
        *,
        record: colrev.record.PrepRecord,
        retrieved_record: colrev.record.PrepRecord,
    ) -> None:
        cls.__abbreviate_container_titles(
            record=record, retrieved_record=retrieved_record
        )

        if Fields.TITLE in record.data:
            record.data[Fields.TITLE] = record.data[Fields.TITLE][:90]
        if Fields.TITLE in retrieved_record.data:
            retrieved_record.data[Fields.TITLE] = retrieved_record.data[Fields.TITLE][
                :90
            ]

        if Fields.AUTHOR in record.data:
            cls.__format_authors_string_for_comparison(record=record)
            record.data[Fields.AUTHOR] = record.data[Fields.AUTHOR][:45]
        if Fields.AUTHOR in retrieved_record.data:
            cls.__format_authors_string_for_comparison(record=retrieved_record)
            retrieved_record.data[Fields.AUTHOR] = retrieved_record.data[Fields.AUTHOR][
                :45
            ]
        if not (
            Fields.VOLUME in record.data and Fields.VOLUME in retrieved_record.data
        ):
            record.data[Fields.VOLUME] = "nan"
            retrieved_record.data[Fields.VOLUME] = "nan"
        if not (
            Fields.NUMBER in record.data and Fields.NUMBER in retrieved_record.data
        ):
            record.data[Fields.NUMBER] = "nan"
            retrieved_record.data[Fields.NUMBER] = "nan"
        if not (Fields.PAGES in record.data and Fields.PAGES in retrieved_record.data):
            record.data[Fields.PAGES] = "nan"
            retrieved_record.data[Fields.PAGES] = "nan"
        # Sometimes, the number of pages is provided (not the range)
        elif not (
            "--" in record.data[Fields.PAGES]
            and "--" in retrieved_record.data[Fields.PAGES]
        ):
            record.data[Fields.PAGES] = "nan"
            retrieved_record.data[Fields.PAGES] = "nan"

        if Fields.YEAR in record.data and Fields.YEAR in retrieved_record.data:
            if record.data[Fields.YEAR] == FieldValues.FORTHCOMING:
                record.data[Fields.YEAR] = retrieved_record.data[Fields.YEAR]
            if retrieved_record.data[Fields.YEAR] == FieldValues.FORTHCOMING:
                retrieved_record.data[Fields.YEAR] = record.data[Fields.YEAR]

    @classmethod
    def get_retrieval_similarity(
        cls,
        *,
        record_original: Record,
        retrieved_record_original: Record,
        same_record_type_required: bool = True,
    ) -> float:
        """Get the retrieval similarity between the record and a retrieved record"""

        if same_record_type_required:
            if record_original.data.get(
                Fields.ENTRYTYPE, "a"
            ) != retrieved_record_original.data.get(Fields.ENTRYTYPE, "b"):
                return 0.0

        record = record_original.copy_prep_rec()
        retrieved_record = retrieved_record_original.copy_prep_rec()

        cls.__prep_records_for_similarity(
            record=record, retrieved_record=retrieved_record
        )

        if "editorial" in record.data.get(Fields.TITLE, "NA").lower():
            if not all(x in record.data for x in [Fields.VOLUME, Fields.NUMBER]):
                return 0.0

        similarity = Record.get_record_similarity(
            record_a=record, record_b=retrieved_record
        )
        return similarity

    def format_if_mostly_upper(self, *, key: str, case: str = "sentence") -> None:
        """Format the field if it is mostly in upper case"""

        if key not in self.data or self.data[key] == FieldValues.UNKNOWN:
            return

        if colrev.env.utils.percent_upper_chars(self.data[key]) < 0.6:
            return

        # Note: the truecase package is not very reliable (yet)

        self.data[key] = self.data[key].replace("\n", " ")

        if case == "sentence":
            self.data[key] = self.data[key].capitalize()
        elif case == "title":
            self.data[key] = self.data[key].title()
        else:
            raise colrev_exceptions.ParameterError(
                parameter="case", value=case, options=["sentence", "title"]
            )

        self.data[key] = prep_utils.capitalize_entities(self.data[key])

    def rename_fields_based_on_mapping(self, *, mapping: dict) -> None:
        """Convenience function for the prep scripts (to rename fields)"""

        mapping = {k.lower(): v.lower() for k, v in mapping.items()}
        prior_keys = list(self.data.keys())
        # Note : warning: do not create a new dict.
        for key in prior_keys:
            if key.lower() in mapping:
                self.rename_field(key=key, new_key=mapping[key.lower()])

    def unify_pages_field(self) -> None:
        """Unify the format of the page field"""
        if Fields.PAGES not in self.data:
            return
        if not isinstance(self.data[Fields.PAGES], str):
            return
        if 1 == self.data[Fields.PAGES].count("-"):
            self.data[Fields.PAGES] = self.data[Fields.PAGES].replace("-", "--")
        self.data[Fields.PAGES] = (
            self.data[Fields.PAGES]
            .replace("–", "--")
            .replace("----", "--")
            .replace(" -- ", "--")
            .rstrip(".")
        )
        if re.match(r"^\d+\-\-\d+$", self.data[Fields.PAGES]):
            from_page, to_page = re.findall(r"(\d+)", self.data[Fields.PAGES])
            if int(from_page) > int(to_page) and len(from_page) > len(to_page):
                self.data[
                    Fields.PAGES
                ] = f"{from_page}--{from_page[:-len(to_page)]}{to_page}"

    def fix_name_particles(self) -> None:
        """Fix the name particles in the author field"""
        if Fields.AUTHOR not in self.data:
            return
        names = self.data[Fields.AUTHOR].split(" and ")
        for ind, name in enumerate(names):
            for prefix in [
                "van den",
                "von den",
                "van der",
                "von der",
                "vom",
                "van",
                "von",
            ]:
                if name.startswith(f"{prefix} "):
                    if "," in name:
                        name = "{" + name.replace(", ", "}, ")
                    else:
                        name = "{" + name + "}"
                if name.endswith(f" {prefix}"):
                    if "," in name:
                        name = (
                            "{"
                            + prefix
                            + " "
                            + name[: -len(prefix)].replace(", ", "}, ")
                        )
                    else:
                        name = "{" + prefix + " " + name[: -len(prefix)] + "}"

                names[ind] = name
        self.data[Fields.AUTHOR] = " and ".join(names)

    def preparation_save_condition(self) -> bool:
        """Check whether the save condition for the prep operation is given"""

        if self.data.get(Fields.STATUS, "NA") in [
            RecordState.rev_prescreen_excluded,
            RecordState.md_prepared,
        ]:
            return True

        if any(
            DefectCodes.RECORD_NOT_IN_TOC in x["note"]
            for x in self.data.get(Fields.MD_PROV, {}).values()
        ):
            return True

        return False

    def preparation_break_condition(self) -> bool:
        """Check whether the break condition for the prep operation is given"""
        if any(
            DefectCodes.RECORD_NOT_IN_TOC in x["note"]
            for x in self.data.get(Fields.MD_PROV, {}).values()
        ):
            return True

        if self.data.get(Fields.STATUS, "NA") in [
            RecordState.rev_prescreen_excluded,
        ]:
            return True
        return False

    def status_to_prepare(self) -> bool:
        """Check whether the record needs to be prepared"""
        return self.data.get(Fields.STATUS, "NA") in [
            RecordState.md_needs_manual_preparation,
            RecordState.md_imported,
            RecordState.md_prepared,
        ]


class RecordState(Enum):
    """The possible RecordStates stored in the colrev_status field
    (corresponding to the RecordStateModel)"""

    # pylint: disable=invalid-name

    # without the md_retrieved state, we could not display the load transition
    md_retrieved = 1
    """Record is retrieved and stored in the ./search directory"""
    md_imported = 2
    """Record is imported into the RECORDS_FILE"""
    md_needs_manual_preparation = 3
    """Record requires manual preparation
    (colrev_masterdata_provenance provides hints)"""
    md_prepared = 4
    """Record is prepared (no missing or incomplete fields, inconsistencies checked)"""
    md_processed = 5
    """Record has been checked for duplicate associations
    with any record in RecordState md_processed or later"""
    rev_prescreen_excluded = 6
    """Record was excluded in the prescreen (based on titles/abstracts)"""
    rev_prescreen_included = 7
    """Record was included in the prescreen (based on titles/abstracts)"""
    pdf_needs_manual_retrieval = 8
    """Record marked for manual PDF retrieval"""
    pdf_imported = 9
    """PDF imported and marked for preparation"""
    pdf_not_available = 10
    """PDF is not available"""
    pdf_needs_manual_preparation = 11
    """PDF marked for manual preparation"""
    pdf_prepared = 12
    """PDF prepared"""
    rev_excluded = 13
    """Record excluded in screen (full-text)"""
    rev_included = 14
    """Record included in screen (full-text)"""
    rev_synthesized = 15
    """Record synthesized"""
    # Note : TBD: rev_coded

    def __str__(self) -> str:
        return f"{self.name}"

    def __lt__(self, other) -> bool:  # type: ignore
        if self.__class__ == RecordState and other.__class__ == RecordState:
            return self.value < other.value
        raise NotImplementedError

    @classmethod
    def get_non_processed_states(cls) -> list:
        """Get the states that correspond to not-yet-processed"""
        return [
            colrev.record.RecordState.md_retrieved,
            colrev.record.RecordState.md_imported,
            colrev.record.RecordState.md_prepared,
            colrev.record.RecordState.md_needs_manual_preparation,
        ]

    @classmethod
    def get_post_x_states(cls, *, state: RecordState) -> typing.Set[RecordState]:
        """Get the states after state x (passed as a parameter)"""
        if state == RecordState.md_prepared:
            return {
                RecordState.md_prepared,
                RecordState.md_processed,
                RecordState.rev_prescreen_included,
                RecordState.rev_prescreen_excluded,
                RecordState.pdf_needs_manual_retrieval,
                RecordState.pdf_imported,
                RecordState.pdf_not_available,
                RecordState.pdf_needs_manual_preparation,
                RecordState.pdf_prepared,
                RecordState.rev_excluded,
                RecordState.rev_included,
                RecordState.rev_synthesized,
            }
        if state == RecordState.md_processed:
            return {
                RecordState.md_processed,
                RecordState.rev_prescreen_included,
                RecordState.rev_prescreen_excluded,
                RecordState.pdf_needs_manual_retrieval,
                RecordState.pdf_imported,
                RecordState.pdf_not_available,
                RecordState.pdf_needs_manual_preparation,
                RecordState.pdf_prepared,
                RecordState.rev_excluded,
                RecordState.rev_included,
                RecordState.rev_synthesized,
            }
        if state == RecordState.rev_prescreen_included:
            return {
                RecordState.rev_prescreen_included,
                RecordState.rev_prescreen_excluded,
                RecordState.pdf_needs_manual_retrieval,
                RecordState.pdf_imported,
                RecordState.pdf_not_available,
                RecordState.pdf_needs_manual_preparation,
                RecordState.pdf_prepared,
                RecordState.rev_excluded,
                RecordState.rev_included,
                RecordState.rev_synthesized,
            }
        if state == RecordState.pdf_prepared:
            return {
                RecordState.pdf_prepared,
                RecordState.rev_excluded,
                RecordState.rev_included,
                RecordState.rev_synthesized,
            }

        if state == RecordState.rev_included:
            return {
                RecordState.rev_excluded,
                RecordState.rev_included,
                RecordState.rev_synthesized,
            }

        # pylint: disable=no-member
        raise colrev_exceptions.ParameterError(
            parameter="state", value="state", options=cls._member_names_
        )


non_processing_transitions = [
    [
        {
            "trigger": "format",
            "source": state,
            "dest": state,
        },
        {
            "trigger": "explore",
            "source": state,
            "dest": state,
        },
        {
            "trigger": "check",
            "source": state,
            "dest": state,
        },
    ]
    for state in list(RecordState)
]


class RecordStateModel:
    """The RecordStateModel describes transitions between RecordStates"""

    transitions = [
        {
            "trigger": Operations.LOAD,
            "source": RecordState.md_retrieved,
            "dest": RecordState.md_imported,
        },
        {
            "trigger": Operations.PREP,
            "source": RecordState.md_imported,
            "dest": RecordState.md_needs_manual_preparation,
        },
        {
            "trigger": Operations.PREP,
            "source": RecordState.md_imported,
            "dest": RecordState.md_prepared,
        },
        {
            "trigger": Operations.PREP_MAN,
            "source": RecordState.md_needs_manual_preparation,
            "dest": RecordState.md_prepared,
        },
        {
            "trigger": Operations.DEDUPE,
            "source": RecordState.md_prepared,
            "dest": RecordState.md_processed,
        },
        {
            "trigger": Operations.PRESCREEN,
            "source": RecordState.md_processed,
            "dest": RecordState.rev_prescreen_excluded,
        },
        {
            "trigger": Operations.PRESCREEN,
            "source": RecordState.md_processed,
            "dest": RecordState.rev_prescreen_included,
        },
        {
            "trigger": Operations.PDF_GET,
            "source": RecordState.rev_prescreen_included,
            "dest": RecordState.pdf_imported,
        },
        {
            "trigger": Operations.PDF_GET,
            "source": RecordState.rev_prescreen_included,
            "dest": RecordState.pdf_needs_manual_retrieval,
        },
        {
            "trigger": Operations.PDF_GET_MAN,
            "source": RecordState.pdf_needs_manual_retrieval,
            "dest": RecordState.pdf_not_available,
        },
        {
            "trigger": Operations.PDF_GET_MAN,
            "source": RecordState.pdf_needs_manual_retrieval,
            "dest": RecordState.pdf_imported,
        },
        {
            "trigger": Operations.PDF_PREP,
            "source": RecordState.pdf_imported,
            "dest": RecordState.pdf_needs_manual_preparation,
        },
        {
            "trigger": Operations.PDF_PREP,
            "source": RecordState.pdf_imported,
            "dest": RecordState.pdf_prepared,
        },
        {
            "trigger": Operations.PDF_PREP_MAN,
            "source": RecordState.pdf_needs_manual_preparation,
            "dest": RecordState.pdf_prepared,
        },
        {
            "trigger": Operations.SCREEN,
            "source": RecordState.pdf_prepared,
            "dest": RecordState.rev_excluded,
        },
        {
            "trigger": Operations.SCREEN,
            "source": RecordState.pdf_prepared,
            "dest": RecordState.rev_included,
        },
        {
            "trigger": Operations.DATA,
            "source": RecordState.rev_included,
            "dest": RecordState.rev_synthesized,
        },
    ]

    transitions_non_processing = [
        item for sublist in non_processing_transitions for item in sublist
    ]

    # from transitions import Machine
    # def __init__(
    #     self,
    #     *,
    #     state: RecordState,
    # ) -> None:
    #     self.state = state

    #     self.machine = Machine(
    #         model=self,
    #         states=RecordState,
    #         transitions=self.transitions + self.transitions_non_processing,
    #         initial=self.state,
    #     )

    @classmethod
    def get_valid_transitions(cls, *, state: RecordState) -> set:
        """Get the list of valid transitions"""
        logging.getLogger("transitions").setLevel(logging.WARNING)
        return set({x["trigger"] for x in cls.transitions if x["source"] == state})

    @classmethod
    def get_preceding_states(cls, *, state: RecordState) -> set:
        """Get the states preceding the state that is given as a parameter"""

        logging.getLogger("transitions").setLevel(logging.WARNING)
        preceding_states: set[RecordState] = set()
        added = True
        while added:
            preceding_states_size = len(preceding_states)
            for transition in RecordStateModel.transitions:
                if (
                    transition["dest"] in preceding_states
                    or state == transition["dest"]
                ):
                    preceding_states.add(transition["source"])  # type: ignore
            if preceding_states_size == len(preceding_states):
                added = False
        return preceding_states

    @classmethod
    def check_operation_precondition(
        cls, *, operation: colrev.operation.Operation
    ) -> None:
        """Check the preconditions for an operation"""

        def get_states_set() -> set:
            if not operation.review_manager.dataset.records_file.is_file():
                return set()
            records_headers = operation.review_manager.dataset.load_records_dict(
                header_only=True
            )
            record_header_list = list(records_headers.values())

            return {el[Fields.STATUS] for el in record_header_list}

        if operation.review_manager.settings.project.delay_automated_processing:
            start_states: list[str] = [
                str(x["source"])
                for x in colrev.record.RecordStateModel.transitions
                if str(operation.type) == x["trigger"]
            ]
            state = colrev.record.RecordState[start_states[0]]

            cur_state_list = get_states_set()
            # self.review_manager.logger.debug(f"cur_state_list: {cur_state_list}")
            # self.review_manager.logger.debug(f"precondition: {self.state}")
            required_absent = cls.get_preceding_states(state=state)
            # self.review_manager.logger.debug(f"required_absent: {required_absent}")
            intersection = cur_state_list.intersection(required_absent)
            if (
                len(cur_state_list) == 0
                and not operation.type.name == "load"  # type: ignore
            ):
                raise colrev_exceptions.NoRecordsError()
            if len(intersection) != 0:
                raise colrev_exceptions.ProcessOrderViolation(
                    operation.type.name, str(state), list(intersection)
                )
