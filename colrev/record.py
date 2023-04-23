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
from typing import Set

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
import colrev.qm.colrev_id
import colrev.qm.colrev_pdf_id
import colrev.ui_cli.cli_colors as colors

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.review_manager

# pylint: disable=too-many-lines
# pylint: disable=too-many-public-methods


class Record:
    """The Record class provides a range of basic convenience functions"""

    identifying_field_keys = [
        "title",
        "author",
        "year",
        "journal",
        "booktitle",
        "chapter",
        "publisher",
        "volume",
        "number",
        "pages",
    ]
    """Keys of identifying fields considered for masterdata provenance"""

    # Based on https://en.wikipedia.org/wiki/BibTeX
    record_field_requirements = {
        "article": ["author", "title", "journal", "year", "volume", "number"],
        "inproceedings": ["author", "title", "booktitle", "year"],
        "incollection": ["author", "title", "booktitle", "publisher", "year"],
        "inbook": ["author", "title", "chapter", "publisher", "year"],
        "proceedings": ["booktitle", "editor"],
        "book": ["author", "title", "publisher", "year"],
        "phdthesis": ["author", "title", "school", "year"],
        "masterthesis": ["author", "title", "school", "year"],
        "techreport": ["author", "title", "institution", "year"],
        "unpublished": ["title", "author", "year"],
        "misc": ["author", "title", "year"],
        "software": ["author", "title", "url"],
        "other": ["author", "title", "year"],
    }
    """Fields requirements for respective ENTRYTYPE"""

    # book, inbook: author <- editor

    record_field_inconsistencies: dict[str, list[str]] = {
        "article": ["booktitle"],
        "inproceedings": ["issue", "number", "journal"],
        "incollection": [],
        "inbook": ["journal"],
        "book": ["volume", "issue", "number", "journal"],
        "phdthesis": ["volume", "issue", "number", "journal", "booktitle"],
        "masterthesis": ["volume", "issue", "number", "journal", "booktitle"],
        "techreport": ["volume", "issue", "number", "journal", "booktitle"],
        "unpublished": ["volume", "issue", "number", "journal", "booktitle"],
    }
    """Fields considered inconsistent with the respective ENTRYTYPE"""

    provenance_keys = [
        "colrev_masterdata_provenance",
        "colrev_origin",
        "colrev_status",
        "colrev_data_provenance",
        "colrev_pdf_id",
        "MOVED_DUPE_ID",
    ]

    preferred_sources = ["https://api.crossref.org/works/", "citeas.org"]

    # Fields that are stored as lists (items separated by newlines)
    list_fields_keys = [
        "colrev_origin",
        # "colrev_pdf_id",
        # "screening_criteria",
    ]
    dict_fields_keys = [
        "colrev_masterdata_provenance",
        "colrev_data_provenance",
    ]

    time_variant_fields = ["cited_by"]

    pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)

    def __init__(self, *, data: dict) -> None:
        self.data = data
        """Dictionary containing the record data"""
        # Note : avoid parsing upon Record instantiation as much as possible
        # to maintain high performance and ensure pickle-abiligy (in multiprocessing)

    def __repr__(self) -> str:  # pragma: no cover
        return self.pp.pformat(self.data)

    def __str__(self) -> str:
        identifying_keys_order = ["ID", "ENTRYTYPE"] + [
            k for k in self.identifying_field_keys if k in self.data
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
                    if selected_tuple[1] in self.identifying_field_keys:
                        diff.append(selected_tuple)
                if selected_tuple[0] == "add":
                    addition_list: typing.Tuple = ("add", "", [])
                    for addition_item in selected_tuple[2]:
                        if addition_item[0] in self.identifying_field_keys:
                            addition_list[2].append(addition_item)
                    if addition_list[2]:
                        diff.append(addition_list)
                if selected_tuple[0] == "remove":
                    removal_list: typing.Tuple = ("remove", "", [])
                    for removal_item in selected_tuple[2]:
                        if removal_item[0] in self.identifying_field_keys:
                            removal_list[2].append(removal_item)
                    if removal_list[2]:
                        diff.append(removal_list)
        else:
            diff = list(dictdiffer.diff(self.get_data(), other_record.get_data()))

        return diff

    def format_bib_style(self) -> str:
        """Simple formatter for bibliography-style output"""
        bib_formatted = (
            self.data.get("author", "")
            + " ("
            + self.data.get("year", "")
            + ") "
            + self.data.get("title", "")
            + ". "
            + self.data.get("journal", "")
            + self.data.get("booktitle", "")
            + ", ("
            + self.data.get("volume", "")
            + ") "
            + self.data.get("number", "")
        )
        return bib_formatted

    def __save_field_dict(self, *, input_dict: dict, input_key: str) -> list:
        list_to_return = []
        assert input_key in ["colrev_masterdata_provenance", "colrev_data_provenance"]
        if input_key == "colrev_masterdata_provenance":
            for key, value in input_dict.items():
                if isinstance(value, dict):
                    formated_node = ",".join(
                        sorted(e for e in value["note"].split(",") if "" != e)
                    )
                    list_to_return.append(f"{key}:{value['source']};{formated_node};")

        elif input_key == "colrev_data_provenance":
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
                    if key in ["colrev_origin"]:
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

        if not isinstance(self.data.get("colrev_origin", []), list):
            self.data["colrev_origin"] = (
                self.data["colrev_origin"].rstrip(";").split(";")
            )
        assert isinstance(self.data.get("colrev_origin", []), list)

        if stringify:
            return __get_stringified_record()

        return self.data

    def masterdata_is_curated(self) -> bool:
        """Check whether the record masterdata is curated"""
        return "CURATED" in self.data.get("colrev_masterdata_provenance", {})

    def set_status(self, *, target_state: RecordState) -> None:
        """Set the record status"""
        if RecordState.md_prepared == target_state:
            # Note : must be after import provenance
            # masterdata_is_complete() relies on "missing" notes/"UNKNOWN" fields
            if not self.masterdata_is_complete():
                target_state = RecordState.md_needs_manual_preparation
            if self.has_quality_defects():
                target_state = RecordState.md_needs_manual_preparation
        # pylint: disable=direct-status-assign
        self.data["colrev_status"] = target_state

    def shares_origins(self, *, other_record: Record) -> bool:
        """Check at least one origin is shared with the other record"""
        return any(
            x in other_record.data.get("colrev_origin", [])
            for x in self.data.get("colrev_origin", [])
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
        if "colrev_id" in self.data:
            if isinstance(self.data["colrev_id"], str):
                colrev_id = [cid.lstrip() for cid in self.data["colrev_id"].split(";")]
            elif isinstance(self.data["colrev_id"], list):
                colrev_id = self.data["colrev_id"]
        return [c for c in colrev_id if len(c) > 20]

    def has_overlapping_colrev_id(self, *, record: Record) -> bool:
        """Check if a record has an overlapping colrev_id with the other record"""
        own_colrev_ids = self.get_colrev_id()
        other_colrev_ids = record.get_colrev_id()
        if len(own_colrev_ids) > 0 and len(other_colrev_ids) > 0:
            if any(cid in own_colrev_ids for cid in other_colrev_ids):
                return True
        return False

    def update_field(
        self,
        *,
        key: str,
        value: str,
        source: str,
        note: str = "",
        keep_source_if_equal: bool = False,
        append_edit: bool = True,
    ) -> None:
        """Update a record field (including provenance information)"""
        if keep_source_if_equal:
            if key in self.data:
                if self.data[key] == value:
                    return

        if key in self.identifying_field_keys:
            if not self.masterdata_is_curated():
                if append_edit and key in self.data:
                    if key in self.data.get("colrev_masterdata_provenance", {}):
                        source = (
                            self.data["colrev_masterdata_provenance"][key]["source"]
                            + "|"
                            + source
                        )
                    else:
                        source = "original|" + source
                self.add_masterdata_provenance(key=key, source=source, note=note)
        else:
            if append_edit and key in self.data:
                if key in self.data.get("colrev_data_provenance", {}):
                    source = (
                        self.data["colrev_data_provenance"][key]["source"]
                        + "|"
                        + source
                    )
                else:
                    source = "original|" + source
            self.add_data_provenance(key=key, source=source, note=note)
        self.data[key] = value

    def rename_field(self, *, key: str, new_key: str) -> None:
        """Rename a field"""
        value = self.data[key]
        self.data[new_key] = value

        if key in self.identifying_field_keys:
            value_provenance = self.data["colrev_masterdata_provenance"][key]
            if "source" in value_provenance:
                value_provenance["source"] += f"|rename-from:{key}"
            self.data["colrev_masterdata_provenance"][new_key] = value_provenance
        else:
            value_provenance = self.data["colrev_data_provenance"][key]
            if "source" in value_provenance:
                value_provenance["source"] += f"|rename-from:{key}"
            self.data["colrev_data_provenance"][new_key] = value_provenance

        self.remove_field(key=key)

    def change_entrytype(self, *, new_entrytype: str) -> None:
        """Change the ENTRYTYPE"""
        for value in self.data.get("colrev_masterdata_provenance", {}).values():
            if "inconsistent with entrytype" in value["note"]:
                value["note"] = ""
        self.data["ENTRYTYPE"] = new_entrytype
        if new_entrytype in ["inproceedings", "proceedings"]:
            if self.data.get("volume", "") == "UNKNOWN":
                self.remove_field(key="volume")
            if self.data.get("number", "") == "UNKNOWN":
                self.remove_field(key="number")
            if "journal" in self.data and "booktitle" not in self.data:
                self.rename_field(key="journal", new_key="booktitle")
        elif new_entrytype == "article":
            if "booktitle" in self.data:
                self.rename_field(key="booktitle", new_key="journal")
        else:
            raise colrev_exceptions.MissingRecordQualityRuleSpecification(
                f"No ENTRYTYPE specification ({new_entrytype})"
            )

        self.apply_fields_keys_requirements()
        missing_fields = set()
        # Note: MissingRecordQualityRuleSpecification already raised before.
        missing_fields = self.get_missing_fields()

        if self.has_quality_defects() or missing_fields:
            self.set_status(
                target_state=colrev.record.RecordState.md_needs_manual_preparation
            )

    def remove_field(
        self, *, key: str, not_missing_note: bool = False, source: str = ""
    ) -> None:
        """Remove a field"""

        if key in self.data:
            del self.data[key]

        if not_missing_note and key in self.identifying_field_keys:
            # Example: journal without number
            # we should keep that information that a particular masterdata
            # field is not required
            if key not in self.data["colrev_masterdata_provenance"]:
                self.data["colrev_masterdata_provenance"][key] = {}
            self.data["colrev_masterdata_provenance"][key]["note"] = "not_missing"
            if source != "":
                self.data["colrev_masterdata_provenance"][key]["source"] = source
        else:
            if key in self.identifying_field_keys:
                if key in self.data.get("colrev_masterdata_provenance", ""):
                    del self.data["colrev_masterdata_provenance"][key]
            else:
                if key in self.data.get("colrev_data_provenance", ""):
                    del self.data["colrev_data_provenance"][key]

    def masterdata_is_complete(self) -> bool:
        """Check if the masterdata is complete"""
        if self.masterdata_is_curated():
            return True

        if not any(
            v == "UNKNOWN"
            for k, v in self.data.items()
            if k in self.identifying_field_keys
        ):
            for k in self.identifying_field_keys:
                if k in self.data.get("colrev_masterdata_provenance", {}):
                    if (
                        "not_missing"
                        in self.data["colrev_masterdata_provenance"][k]["note"]
                    ):
                        continue
                    if (
                        "missing"
                        in self.data["colrev_masterdata_provenance"][k]["note"]
                    ):
                        return False
            return True

        return False

    def set_masterdata_complete(
        self, *, source: str, replace_source: bool = True
    ) -> None:
        """Set the masterdata to complete"""
        # pylint: disable=too-many-branches
        if self.masterdata_is_curated():
            return

        if "colrev_masterdata_provenance" not in self.data:
            self.data["colrev_masterdata_provenance"] = {}
        md_p_dict = self.data["colrev_masterdata_provenance"]

        for identifying_field_key in self.identifying_field_keys:
            if identifying_field_key in ["author", "title", "year"]:
                continue
            if self.data.get(identifying_field_key, "NA") == "UNKNOWN":
                del self.data[identifying_field_key]
            if identifying_field_key in md_p_dict:
                note = md_p_dict[identifying_field_key]["note"]
                if "missing" in note and "not_missing" not in note:
                    md_p_dict[identifying_field_key]["note"] = note.replace(
                        "missing", ""
                    )

        if self.data["ENTRYTYPE"] == "article":
            if "volume" not in self.data:
                if "volume" in self.data["colrev_masterdata_provenance"]:
                    self.data["colrev_masterdata_provenance"]["volume"][
                        "note"
                    ] = "not_missing"
                    if replace_source:
                        self.data["colrev_masterdata_provenance"]["volume"][
                            "source"
                        ] = source
                else:
                    self.data["colrev_masterdata_provenance"]["volume"] = {
                        "source": source,
                        "note": "not_missing",
                    }

            if "number" not in self.data:
                if "number" in self.data["colrev_masterdata_provenance"]:
                    self.data["colrev_masterdata_provenance"]["number"][
                        "note"
                    ] = "not_missing"
                    if replace_source:
                        self.data["colrev_masterdata_provenance"]["number"][
                            "source"
                        ] = source
                else:
                    self.data["colrev_masterdata_provenance"]["number"] = {
                        "source": source,
                        "note": "not_missing",
                    }

    def set_masterdata_consistent(self) -> None:
        """Set the masterdata to consistent"""
        if "colrev_masterdata_provenance" not in self.data:
            self.data["colrev_masterdata_provenance"] = {}
        md_p_dict = self.data["colrev_masterdata_provenance"]

        for identifying_field_key in self.identifying_field_keys:
            if identifying_field_key in md_p_dict:
                note = md_p_dict[identifying_field_key]["note"]
                if "inconsistent with ENTRYTYPE" in note:
                    md_p_dict[identifying_field_key]["note"] = note.replace(
                        "inconsistent with ENTRYTYPE", ""
                    )

    def set_fields_complete(self) -> None:
        """Set fields to complete"""
        for identifying_field_key in self.identifying_field_keys:
            if identifying_field_key in self.data.get(
                "colrev_masterdata_provenance", {}
            ):
                note = self.data["colrev_masterdata_provenance"][identifying_field_key][
                    "note"
                ]
                if (
                    "incomplete"
                    in self.data["colrev_masterdata_provenance"][identifying_field_key][
                        "note"
                    ]
                ):
                    self.data["colrev_masterdata_provenance"][identifying_field_key][
                        "note"
                    ] = note.replace("incomplete", "")

    def reset_pdf_provenance_notes(self) -> None:
        """Reset the PDF (file) provenance notes"""
        if "colrev_data_provenance" not in self.data:
            self.add_data_provenance_note(key="file", note="")
        else:
            if "file" in self.data["colrev_data_provenance"]:
                self.data["colrev_data_provenance"]["file"]["note"] = ""
            else:
                self.data["colrev_data_provenance"]["file"] = {
                    "source": "NA",
                    "note": "",
                }

    def get_missing_fields(self) -> set:
        """Get the missing fields"""
        missing_field_keys = set()
        if self.data["ENTRYTYPE"] in Record.record_field_requirements:
            reqs = Record.record_field_requirements[self.data["ENTRYTYPE"]]
            missing_field_keys = {
                x
                for x in reqs
                if x not in self.data.keys()
                or "" == self.data[x]
                or "UNKNOWN" == self.data[x]
            }
            return missing_field_keys
        raise colrev_exceptions.MissingRecordQualityRuleSpecification(
            msg=f"Missing record_field_requirements for {self.data['ENTRYTYPE']}"
        )

    def get_inconsistencies(self) -> set:
        """Get inconsistencies (between fields)"""
        inconsistent_field_keys = set()
        if self.data["ENTRYTYPE"] in Record.record_field_inconsistencies:
            incons_fields = Record.record_field_inconsistencies[self.data["ENTRYTYPE"]]
            inconsistent_field_keys = {x for x in incons_fields if x in self.data}
        # Note: a thesis should be single-authored
        if "thesis" in self.data["ENTRYTYPE"] and " and " in self.data.get(
            "author", ""
        ):
            inconsistent_field_keys.add("author")
        return inconsistent_field_keys

    def has_inconsistent_fields(self) -> bool:
        """Check whether the record has inconsistent fields"""
        found_inconsistencies = False
        if self.data["ENTRYTYPE"] in Record.record_field_inconsistencies:
            inconsistencies = self.get_inconsistencies()
            if inconsistencies:
                found_inconsistencies = True
        return found_inconsistencies

    def has_incomplete_fields(self) -> bool:
        """Check whether the record has incomplete fields"""
        if len(self.get_incomplete_fields()) > 0:
            return True
        return False

    def __merge_origins(self, *, merging_record: Record) -> None:
        """Merge the origins with those of the merging_record"""

        if "colrev_origin" in merging_record.data:
            origins = self.data["colrev_origin"] + merging_record.data["colrev_origin"]
            self.data["colrev_origin"] = sorted(list(set(origins)))

    def __merge_status(self, *, merging_record: Record) -> None:
        """Merge the status with the merging_record"""

        if "colrev_status" in merging_record.data:
            # Set both status to the latter in the state model
            if self.data["colrev_status"] < merging_record.data["colrev_status"]:
                self.set_status(target_state=merging_record.data["colrev_status"])
            else:
                merging_record.set_status(target_state=self.data["colrev_status"])

    def __get_merging_val(self, *, merging_record: Record, key: str) -> str:
        val = merging_record.data.get(key, "")

        if val == "":
            return ""
        if not val:
            return ""

        # do not override provenance, ID, ... fields
        if key in [
            "ID",
            "colrev_masterdata_provenance",
            "colrev_data_provenance",
            "colrev_id",
            "colrev_status",
            "colrev_origin",
            "MOVED_DUPE_ID",
        ]:
            return ""

        return val

    def __prevent_invalid_merges(self, *, merging_record: Record) -> None:
        """Prevents invalid merges like ... part 1 / ... part 2"""

        lower_title_a = self.data.get("title", "").lower()
        lower_title_b = merging_record.data.get("title", "").lower()

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
                for origin in merging_record.data["colrev_origin"]
            ):
                merging_record_preferred = True

        self.__prevent_invalid_merges(merging_record=merging_record)
        self.__merge_origins(merging_record=merging_record)
        self.__merge_status(merging_record=merging_record)

        if not self.masterdata_is_curated() and merging_record.masterdata_is_curated():
            self.data["colrev_masterdata_provenance"] = merging_record.data[
                "colrev_masterdata_provenance"
            ]
            # Note : remove all masterdata fields
            # because the curated record may have fewer masterdata fields
            # and we iterate over the curated record (merging_record) in the next step
            for k in list(self.data.keys()):
                if k in Record.identifying_field_keys and k != "pages":
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
                if key not in Record.identifying_field_keys + ["ENTRYTYPE"]:
                    self.add_data_provenance(key=key, source=source, note=note)

            # Do not change if MERGING_RECORD is not curated
            elif (
                self.masterdata_is_curated()
                and not merging_record.masterdata_is_curated()
            ):
                continue

            # Part 1: identifying fields
            if key in Record.identifying_field_keys:
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
                        note=note,
                    )

            # Part 2: other fields
            else:
                # keep existing values per default
                self.update_field(
                    key=key,
                    value=str(val),
                    source=source,
                    note=note,
                    keep_source_if_equal=True,
                    append_edit=False,
                )

    @classmethod
    def __select_best_author(
        cls, *, record: Record, merging_record: Record, preferred_sources: list
    ) -> str:
        # pylint: disable=too-many-return-statements
        if "colrev_masterdata_provenance" not in record.data:
            record.data["colrev_masterdata_provenance"] = {}
        record_a_prov = record.data["colrev_masterdata_provenance"]

        if "colrev_masterdata_provenance" not in merging_record.data:
            merging_record.data["colrev_masterdata_provenance"] = {}
        merging_record_a_prov = merging_record.data["colrev_masterdata_provenance"]

        if "author" in record_a_prov and "author" not in merging_record_a_prov:
            # Prefer non-defect version
            if "quality_defect" in record_a_prov["author"].get("note", ""):
                return merging_record.data["author"]
            # Prefer complete version
            if "incomplete" in record_a_prov["author"].get("note", ""):
                return merging_record.data["author"]
        elif "author" in record_a_prov and "author" in merging_record_a_prov:
            # Prefer non-defect version
            if "quality_defect" in record_a_prov["author"].get(
                "note", ""
            ) and "quality_defect" not in merging_record_a_prov["author"].get(
                "note", ""
            ):
                return merging_record.data["author"]

            # Prefer complete version
            if "incomplete" in record_a_prov["author"].get(
                "note", ""
            ) and "incomplete" not in merging_record_a_prov["author"].get("note", ""):
                return merging_record.data["author"]

        if len(record.data["author"]) > 0 and len(merging_record.data["author"]) > 0:
            default_mostly_upper = (
                colrev.env.utils.percent_upper_chars(record.data["author"]) > 0.8
            )
            candidate_mostly_upper = (
                colrev.env.utils.percent_upper_chars(merging_record.data["author"])
                > 0.8
            )

            # Prefer title case (not all-caps)
            if default_mostly_upper and not candidate_mostly_upper:
                return merging_record.data["author"]

        # Prefer sources
        if "author" in merging_record_a_prov:
            if any(
                x in merging_record_a_prov["author"]["source"]
                for x in preferred_sources
            ):
                return merging_record.data["author"]
        return record.data["author"]

    @classmethod
    def __select_best_pages(
        cls,
        *,
        record: Record,
        merging_record: Record,
        preferred_sources: list,  # pylint: disable=unused-argument
    ) -> str:
        best_pages = record.data["pages"]
        if "--" in merging_record.data["pages"] and "--" not in record.data["pages"]:
            best_pages = merging_record.data["pages"]
        return best_pages

    @classmethod
    def __select_best_title(
        cls,
        *,
        record: Record,
        merging_record: Record,
        preferred_sources: list,  # pylint: disable=unused-argument
    ) -> str:
        default = record.data["title"]
        candidate = merging_record.data["title"]
        best_title = record.data["title"]

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
        preferred_sources: list,  # pylint: disable=unused-argument
    ) -> str:
        return cls.__select_best_container_title(
            default=record.data["journal"], candidate=merging_record.data["journal"]
        )

    @classmethod
    def __select_best_booktitle(
        cls,
        *,
        record: Record,
        merging_record: Record,
        preferred_sources: list,  # pylint: disable=unused-argument
    ) -> str:
        return cls.__select_best_container_title(
            default=record.data["booktitle"], candidate=merging_record.data["booktitle"]
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
        note: str,  # pylint: disable=unused-argument
    ) -> None:
        # Note : the assumption is that we need masterdata_provenance notes
        # only for authors

        custom_field_selectors = {
            "author": self.__select_best_author,
            "pages": self.__select_best_pages,
            "title": self.__select_best_title,
            "journal": self.__select_best_journal,
            "booktitle": self.__select_best_booktitle,
        }

        if key in custom_field_selectors:
            if key in self.data:
                best_value = custom_field_selectors[key](
                    record=self,
                    merging_record=merging_record,
                    preferred_sources=self.preferred_sources,
                )
                if self.data[key] != best_value:
                    self.update_field(
                        key=key, value=best_value, source=source, append_edit=False
                    )
            else:
                self.update_field(key=key, value=val, source=source, append_edit=False)

        elif key == "file":
            if key in self.data:
                self.data[key] = self.data[key] + ";" + merging_record.data.get(key, "")
            else:
                self.data[key] = merging_record.data[key]
        elif key in ["url", "link"]:
            if (
                key in self.data
                and self.data[key].rstrip("/") != merging_record.data[key].rstrip("/")
                and "https" not in self.data[key]
            ):
                self.update_field(key=key, value=val, source=source, append_edit=False)

        elif "UNKNOWN" == self.data.get(
            key, ""
        ) and "UNKNOWN" != merging_record.data.get(key, ""):
            self.data[key] = merging_record.data[key]
            if key in self.identifying_field_keys:
                self.add_masterdata_provenance(key=key, source=source)
            else:
                self.add_data_provenance(key=key, source=source)

        # elif merging_record.data.get(key, "UNKNOWN") == "UNKNOWN":
        #     pass
        # Note : the following is deactivated to avoid frequent changes in merged records
        # else:
        #     try:
        #         if key in self.identifying_field_keys:
        #             source = merging_record.data["colrev_masterdata_provenance"][key][
        #                 "source"
        #             ]
        #         else:
        #             source = merging_record.data["colrev_data_provenance"][key][
        #                 "source"
        #             ]
        #     except KeyError:
        #         pass
        # if val != str(merging_record.data[key]):
        #     self.update_field(
        #         key=key,
        #         value=str(merging_record.data[key]),
        #         source=source,
        #         note=note,
        #     )
        # self.update_field(key=key, value=val, source=source, note=note)

    @classmethod
    def get_record_change_score(cls, *, record_a: Record, record_b: Record) -> float:
        """Determine how much records changed

        This method is less sensitive than get_record_similarity, especially when
        fields are missing. For example, if the journal field is missing in both
        records, get_similarity will return a value > 1.0. The get_record_changes
        will return 0.0 (if all other fields are equal)."""

        # At some point, this may become more sensitive to major changes
        str_a = (
            f"{record_a.data.get('author', '')} ({record_a.data.get('year', '')}) "
            + f"{record_a.data.get('title', '')}. "
            + f"{record_a.data.get('journal', '')}{record_a.data.get('booktitle', '')}, "
            + f"{record_a.data.get('volume', '')} ({record_a.data.get('number', '')})"
        )
        str_b = (
            f"{record_b.data.get('author', '')} ({record_b.data.get('year', '')}) "
            + f"{record_b.data.get('title', '')}. "
            + f"{record_b.data.get('journal', '')}{record_b.data.get('booktitle', '')}, "
            + f"{record_b.data.get('volume', '')} ({record_b.data.get('number', '')})"
        )
        return 1 - fuzz.ratio(str_a.lower(), str_b.lower()) / 100

    @classmethod
    def get_record_similarity(cls, *, record_a: Record, record_b: Record) -> float:
        """Determine the similarity between two records (their masterdata)"""
        record_a_dict = record_a.copy().get_data()
        record_b_dict = record_b.copy().get_data()

        mandatory_fields = [
            "title",
            "author",
            "year",
            "journal",
            "volume",
            "number",
            "pages",
            "booktitle",
        ]

        for mandatory_field in mandatory_fields:
            if record_a_dict.get(mandatory_field, "UNKNOWN") == "UNKNOWN":
                record_a_dict[mandatory_field] = ""
            if record_b_dict.get(mandatory_field, "UNKNOWN") == "UNKNOWN":
                record_b_dict[mandatory_field] = ""

        if "container_title" not in record_a_dict:
            record_a_dict["container_title"] = (
                record_a_dict.get("journal", "")
                + record_a_dict.get("booktitle", "")
                + record_a_dict.get("series", "")
            )

        if "container_title" not in record_b_dict:
            record_b_dict["container_title"] = (
                record_b_dict.get("journal", "")
                + record_b_dict.get("booktitle", "")
                + record_b_dict.get("series", "")
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
            author_similarity = fuzz.ratio(record_a["author"], record_b["author"]) / 100

            title_similarity = (
                fuzz.ratio(
                    record_a["title"].lower().replace(":", "").replace("-", ""),
                    record_b["title"].lower().replace(":", "").replace("-", ""),
                )
                / 100
            )

            # partial ratio (catching 2010-10 or 2001-2002)
            year_similarity = (
                fuzz.ratio(str(record_a["year"]), str(record_b["year"])) / 100
            )

            outlet_similarity = 0.0
            if record_b["container_title"] and record_a["container_title"]:
                outlet_similarity = (
                    fuzz.ratio(record_a["container_title"], record_b["container_title"])
                    / 100
                )

            if str(record_a["journal"]) != "nan":
                # Note: for journals papers, we expect more details
                volume_similarity = (
                    1 if (record_a["volume"] == record_b["volume"]) else 0
                )

                number_similarity = (
                    1 if (record_a["number"] == record_b["number"]) else 0
                )

                # page similarity is not considered at the moment.
                #
                # sometimes, only the first page is provided.
                # if str(record_a["pages"]) == "nan" or str(record_b["pages"]) == "nan":
                #     pages_similarity = 1
                # else:
                #     if record_a["pages"] == record_b["pages"]:
                #         pages_similarity = 1
                #     else:
                #         if record_a["pages"].split("-")[0] == record_b["pages"].split("-")[0]:
                #             pages_similarity = 1
                #         else:
                #            pages_similarity = 0

                # Put more weight on other fields if the title is very common
                # ie., non-distinctive
                # The list is based on a large export of distinct papers, tabulated
                # according to titles and sorted by frequency
                if [record_a["title"], record_b["title"]] in [
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
                    "authors",
                    "title",
                    "year",
                    "outlet",
                    "volume",
                    "number",
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
                    "author",
                    "title",
                    "year",
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
        if key in self.identifying_field_keys:
            if "colrev_masterdata_provenance" in self.data:
                if key in self.data.get("colrev_masterdata_provenance", {}):
                    if "source" in self.data["colrev_masterdata_provenance"][key]:
                        source = self.data["colrev_masterdata_provenance"][key][
                            "source"
                        ]
                    if "note" in self.data["colrev_masterdata_provenance"][key]:
                        note = self.data["colrev_masterdata_provenance"][key]["note"]
        else:
            if "colrev_data_provenance" in self.data:
                if key in self.data["colrev_data_provenance"]:
                    if "source" in self.data["colrev_data_provenance"][key]:
                        source = self.data["colrev_data_provenance"][key]["source"]
                    if "note" in self.data["colrev_data_provenance"][key]:
                        note = self.data["colrev_data_provenance"][key]["note"]

        return {"source": source, "note": note}

    def add_masterdata_provenance_note(self, *, key: str, note: str) -> None:
        """Add a masterdata provenance note (based on a key)"""
        if "colrev_masterdata_provenance" not in self.data:
            self.data["colrev_masterdata_provenance"] = {}
        if key in self.data.get("colrev_masterdata_provenance", {}):
            if (
                "" == self.data["colrev_masterdata_provenance"][key]["note"]
                or "" == note
            ):
                self.data["colrev_masterdata_provenance"][key]["note"] = note
            elif note not in self.data["colrev_masterdata_provenance"][key][
                "note"
            ].split(","):
                self.data["colrev_masterdata_provenance"][key]["note"] += f",{note}"
        else:
            self.data["colrev_masterdata_provenance"][key] = {
                "source": "ORIGINAL",
                "note": note,
            }

        existing_note = self.data["colrev_masterdata_provenance"][key]["note"]
        if "quality_defect" in existing_note and any(
            x in existing_note for x in ["missing", "disagreement"]
        ):
            self.data["colrev_masterdata_provenance"][key]["note"] = (
                existing_note.replace("quality_defect", "").rstrip(",").lstrip(",")
            )

    def add_data_provenance_note(self, *, key: str, note: str) -> None:
        """Add a data provenance note (based on a key)"""
        if "colrev_data_provenance" not in self.data:
            self.data["colrev_data_provenance"] = {}
        if key in self.data["colrev_data_provenance"]:
            if self.data["colrev_data_provenance"][key]["note"] == "":
                self.data["colrev_data_provenance"][key]["note"] = note
            elif note not in self.data["colrev_data_provenance"][key]["note"].split(
                ","
            ):
                self.data["colrev_data_provenance"][key]["note"] += f",{note}"
        else:
            self.data["colrev_data_provenance"][key] = {
                "source": "ORIGINAL",
                "note": note,
            }

    def add_masterdata_provenance(
        self, *, key: str, source: str, note: str = ""
    ) -> None:
        """Add a masterdata provenance, including source and note (based on a key)"""
        if "colrev_masterdata_provenance" not in self.data:
            self.data["colrev_masterdata_provenance"] = {}
        md_p_dict = self.data["colrev_masterdata_provenance"]

        if key in md_p_dict:
            if md_p_dict[key]["note"] == "" or "" == note:
                md_p_dict[key]["note"] = note
            elif "missing" == note and "not_missing" in md_p_dict[key]["note"].split(
                ","
            ):
                md_p_dict[key]["note"] = "missing"
            elif note not in md_p_dict[key]["note"].split(","):
                md_p_dict[key]["note"] += f",{note}"
            md_p_dict[key]["source"] = source
        else:
            md_p_dict[key] = {"source": source, "note": f"{note}"}

    def add_provenance_all(self, *, source: str) -> None:
        """Add a data provenance (source) to all fields"""
        if "colrev_masterdata_provenance" not in self.data:
            self.data["colrev_masterdata_provenance"] = {}
        if "colrev_data_provenance" not in self.data:
            self.data["colrev_data_provenance"] = {}

        md_p_dict = self.data["colrev_masterdata_provenance"]
        d_p_dict = self.data["colrev_data_provenance"]
        for key in self.data.keys():
            if key in [
                "ENTRYTYPE",
                "colrev_data_provenance",
                "colrev_masterdata_provenance",
                "colrev_status",
                "colrev_id",
            ]:
                continue
            if (
                key in self.identifying_field_keys
                and "CURATED" not in self.data["colrev_masterdata_provenance"]
            ):
                md_p_dict[key] = {"source": source, "note": ""}
            else:
                d_p_dict[key] = {"source": source, "note": ""}

    def add_data_provenance(self, *, key: str, source: str, note: str = "") -> None:
        """Add a data provenance, including source and note (based on a key)"""
        if "colrev_data_provenance" not in self.data:
            self.data["colrev_data_provenance"] = {}
        md_p_dict = self.data["colrev_data_provenance"]
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
                    "colrev_id",
                    "ENTRYTYPE",
                    "ID",
                    "metadata_source_repository_paths",
                    "local_curated_metadata",
                ]
                + self.provenance_keys
            ):
                continue

            if key in self.identifying_field_keys:
                if not self.masterdata_is_curated():
                    self.add_masterdata_provenance(key=key, source=source_info, note="")
            else:
                self.add_data_provenance(key=key, source=source_info, note="")

        return True

    def get_incomplete_fields(self) -> set:
        """Get the list of incomplete fields"""
        incomplete_field_keys = set()
        for key in self.data.keys():
            if key in ["title", "journal", "booktitle", "author"]:
                if self.data[key].endswith("...") or self.data[key].endswith("…"):
                    incomplete_field_keys.add(key)

            if key == "author":
                if (
                    self.data[key].endswith("and others")
                    or self.data[key].endswith("et al.")
                    # heuristics for missing first names:
                    or ", and " in self.data[key]
                    or self.data[key].rstrip().endswith(",")
                ):
                    incomplete_field_keys.add(key)

        return incomplete_field_keys

    def get_quality_defects(self) -> list:
        """Get the fields (keys) with quality defects"""

        def get_author_quality_defects(*, defect_field_keys: list) -> None:
            sanitized_authors = re.sub(
                "[^a-zA-Z, ;1]+",
                "",
                colrev.env.utils.remove_accents(input_str=self.data["author"]),
            ).split(" and ")
            if not all(
                re.findall(
                    r"^[\w .'’-]*, [\w .'’-]*$",
                    sanitized_author,
                    re.UNICODE,
                )
                for sanitized_author in sanitized_authors
            ):
                defect_field_keys.append("author")
            # At least two capital letters per name
            elif not all(
                re.findall(
                    r"[A-Z]+",
                    author_part,
                    re.UNICODE,
                )
                for sanitized_author in sanitized_authors
                for author_part in sanitized_author.split(",")
            ):
                defect_field_keys.append("author")

            # Note : patterns like "I N T R O D U C T I O N"
            # that may result from grobid imports
            elif re.search(r"[A-Z] [A-Z] [A-Z] [A-Z]", self.data["author"]):
                defect_field_keys.append("author")
            elif len(self.data["author"]) < 5:
                defect_field_keys.append("author")
            elif any(
                x in str(self.data["author"]) for x in ["�", "http", "University", "™"]
            ):
                defect_field_keys.append("author")

        def get_title_quality_defects(*, defect_field_keys: list) -> None:
            # Note : titles that have no space and special characters
            # like _ . or digits.
            if " " not in self.data["title"] and (
                any(x in self.data["title"] for x in ["_", "."])
                or any(char.isdigit() for char in self.data["title"])
            ):
                defect_field_keys.append("title")
            if "�" in str(self.data["title"]):
                defect_field_keys.append("title")

        def get_general_quality_defects(*, key: str, defect_field_keys: list) -> None:
            if key in ["title", "author", "journal", "booktitle"]:
                if colrev.env.utils.percent_upper_chars(self.data[key]) > 0.8:
                    defect_field_keys.append(key)
                if "�" in str(self.data[key]):
                    defect_field_keys.append(key)

        defect_field_keys: typing.List[str] = []
        for key in self.data.keys():
            if self.data[key] == "UNKNOWN":
                continue

            if key == "author":
                get_author_quality_defects(defect_field_keys=defect_field_keys)

            if key == "title":
                get_title_quality_defects(defect_field_keys=defect_field_keys)

            get_general_quality_defects(key=key, defect_field_keys=defect_field_keys)

        if "colrev_masterdata_provenance" in self.data:
            for field, provenance in self.data["colrev_masterdata_provenance"].items():
                if any(x in provenance["note"] for x in ["disagreement", "missing"]):
                    defect_field_keys.append(field)

        return list(set(defect_field_keys))

    def has_quality_defects(self) -> bool:
        """Check whether a record has quality defects"""
        return len(self.get_quality_defects()) > 0

    def remove_quality_defect_notes(self) -> None:
        """Remove the quality defect notes"""
        for key in self.data.keys():
            if key in self.data.get("colrev_masterdata_provenance", {}):
                note = self.data["colrev_masterdata_provenance"][key]["note"]
                if "quality_defect" in note:
                    self.data["colrev_masterdata_provenance"][key][
                        "note"
                    ] = note.replace("quality_defect", "")

    def get_container_title(self) -> str:
        """Get the record's container title (journal name, booktitle, etc.)"""
        container_title = "NA"
        if "ENTRYTYPE" not in self.data:
            container_title = self.data.get("journal", self.data.get("booktitle", "NA"))
        else:
            if self.data["ENTRYTYPE"] == "article":
                container_title = self.data.get("journal", "NA")
            if self.data["ENTRYTYPE"] == "inproceedings":
                container_title = self.data.get("booktitle", "NA")
            if self.data["ENTRYTYPE"] == "book":
                container_title = self.data.get("title", "NA")
            if self.data["ENTRYTYPE"] == "inbook":
                container_title = self.data.get("booktitle", "NA")
        return container_title

    def create_colrev_id(
        self,
        *,
        also_known_as_record: Optional[dict] = None,
        assume_complete: bool = False,
    ) -> str:
        """Returns the colrev_id of the Record.
        If a also_known_as_record is provided, it returns the colrev_id of the
        also_known_as_record (using the Record as the reference to decide whether
        required fields are missing)"""
        if also_known_as_record is None:
            also_known_as_record = {}

        return colrev.qm.colrev_id.create_colrev_id(
            record=self,
            also_known_as_record=also_known_as_record,
            assume_complete=assume_complete,
        )

    def prescreen_exclude(self, *, reason: str, print_warning: bool = False) -> None:
        """Prescreen-exclude a record"""
        # Warn when setting rev_synthesized/rev_included to prescreen_excluded
        # Especially in cases in which the prescreen-exclusion decision
        # is revised (e.g., because a paper was retracted)
        # In these cases, the paper may already be in the data extraction/synthesis
        if self.data.get("colrev_status", "NA") in [
            RecordState.rev_synthesized,
            RecordState.rev_included,
        ]:
            print(
                f"\n{colors.RED}Warning: setting paper to prescreen_excluded. Please check and "
                f"remove from synthesis: {self.data['ID']}{colors.END}\n"
            )

        self.set_status(target_state=RecordState.rev_prescreen_excluded)

        if (
            "retracted" not in self.data.get("prescreen_exclusion", "")
            and "retracted" == reason
            and print_warning
        ):
            print(
                f"\n{colors.RED}Paper retracted and prescreen "
                f"excluded: {self.data['ID']}{colors.END}\n"
            )

        self.data["prescreen_exclusion"] = reason

        # Note: when records are prescreen-excluded during prep:
        to_drop = []
        for key, value in self.data.items():
            if value == "UNKNOWN":
                to_drop.append(key)
        for key in to_drop:
            self.remove_field(key=key)

    def extract_text_by_page(
        self, *, pages: Optional[list] = None, project_path: Path
    ) -> str:
        """Extract the text from the PDF for a given number of pages"""
        text_list: list = []
        pdf_path = project_path / Path(self.data["file"])

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

    def set_pages_in_pdf(self, *, project_path: Path) -> None:
        """Set the pages_in_file field based on the PDF"""
        pdf_path = project_path / Path(self.data["file"])
        with open(pdf_path, "rb") as file:
            parser = PDFParser(file)
            document = PDFDocument(parser)
            pages_in_file = resolve1(document.catalog["Pages"])["Count"]
        self.data["pages_in_file"] = pages_in_file

    def set_text_from_pdf(self, *, project_path: Path) -> None:
        """Set the text_from_pdf field based on the PDF"""
        self.data["text_from_pdf"] = ""
        try:
            self.set_pages_in_pdf(project_path=project_path)
            text = self.extract_text_by_page(pages=[0, 1, 2], project_path=project_path)
            self.data["text_from_pdf"] = text

        except PDFSyntaxError:  # pragma: no cover
            self.add_data_provenance_note(key="file", note="pdf_reader_error")
            self.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)
        except PDFTextExtractionNotAllowed:  # pragma: no cover
            self.add_data_provenance_note(key="file", note="pdf_protected")
            self.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)

    def extract_pages(
        self, *, pages: list, project_path: Path, save_to_path: Optional[Path] = None
    ) -> None:  # pragma: no cover
        """Extract pages from the PDF (saveing them to the save_to_path)"""
        pdf_path = project_path / Path(self.data["file"])
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

    def apply_fields_keys_requirements(self) -> None:
        """Apply the field key requirements"""

        required_fields_keys = self.record_field_requirements["other"]
        if self.data["ENTRYTYPE"] in self.record_field_requirements:
            required_fields_keys = self.record_field_requirements[
                self.data["ENTRYTYPE"]
            ]
        for required_fields_key in required_fields_keys:
            if self.data.get(required_fields_key, "UNKNOWN") == "UNKNOWN":
                self.update_field(
                    key=required_fields_key,
                    value="UNKNOWN",
                    source="generic_field_requirements",
                    note="missing",
                    append_edit=False,
                )

    def get_toc_key(self) -> str:
        """Get the record's toc-key"""

        try:
            if self.data["ENTRYTYPE"] == "article":
                toc_key = (
                    self.data["journal"]
                    .replace(" ", "-")
                    .replace("\\", "")
                    .replace("&", "and")
                    .lower()
                )
                toc_key += (
                    f"|{self.data['volume']}"
                    if ("UNKNOWN" != self.data.get("volume", "UNKNOWN"))
                    else "|-"
                )
                toc_key += (
                    f"|{self.data['number']}"
                    if ("UNKNOWN" != self.data.get("number", "UNKNOWN"))
                    else "|-"
                )

            elif self.data["ENTRYTYPE"] == "inproceedings":
                toc_key = (
                    self.data["booktitle"]
                    .replace(" ", "-")
                    .replace("\\", "")
                    .replace("&", "and")
                    .lower()
                    + f"|{self.data.get('year', '')}"
                )
            else:
                msg = (
                    f"ENTRYTYPE {self.data['ENTRYTYPE']} "
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
            f"{self.data.get('author', '')} ({self.data.get('year', '')}) "
            + f"{self.data.get('title', '')}. "
            + f"{self.data.get('journal', '')}{self.data.get('booktitle', '')}, "
            + f"{self.data.get('volume', '')} ({self.data.get('number', '')})"
        )
        print(formatted_ref)

    def get_tei_filename(self) -> Path:
        """Get the TEI filename associated with the file (PDF)"""
        tei_filename = Path(f'.tei/{self.data["ID"]}.tei.xml')
        if "file" in self.data:
            tei_filename = Path(
                self.data["file"].replace("pdfs/", ".tei/")
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
                    letters[i] = f"{colors.RED}" + letters[i][-1] + f"{colors.END}"
                elif letter.startswith("- "):
                    letters[i] = f"{colors.GREEN}" + letters[i][-1] + f"{colors.END}"
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
                        "volume",
                        "number",
                        "year",
                    ]:
                        line = f"{colors.RED}{rec.get(key, '')}{colors.END}"
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

    def apply_restrictions(self, *, restrictions: dict) -> None:
        """Apply masterdata restrictions to the record"""

        for required_field in ["author", "title", "year"]:
            if required_field in self.data:
                continue
            self.set_status(
                target_state=colrev.record.RecordState.md_needs_manual_preparation
            )
            colrev.record.Record(data=self.data).add_masterdata_provenance(
                key=required_field,
                source="colrev_curation.masterdata_restrictions",
                note="missing",
            )

        for exact_match in ["ENTRYTYPE", "journal", "booktitle"]:
            if exact_match in restrictions:
                if restrictions[exact_match] != self.data.get(exact_match, ""):
                    self.data[exact_match] = restrictions[exact_match]

        if "volume" in restrictions:
            if restrictions["volume"] and "volume" not in self.data:
                self.set_status(
                    target_state=colrev.record.RecordState.md_needs_manual_preparation
                )
                colrev.record.Record(data=self.data).add_masterdata_provenance(
                    key="volume",
                    source="colrev_curation.masterdata_restrictions",
                    note="missing",
                )

        if "number" in restrictions:
            if restrictions["number"] and "number" not in self.data:
                self.set_status(
                    target_state=colrev.record.RecordState.md_needs_manual_preparation
                )
                colrev.record.Record(data=self.data).add_masterdata_provenance(
                    key="number",
                    source="colrev_curation.masterdata_restrictions",
                    note="missing",
                )
            elif "number" in self.data:
                self.remove_field(
                    key="number",
                    not_missing_note=True,
                    source="colrev_curation.masterdata_restrictions",
                )

    def update_masterdata_provenance(
        self, *, masterdata_restrictions: Optional[dict] = None
    ) -> None:
        """Update the masterdata provenance"""
        # pylint: disable=too-many-branches

        if masterdata_restrictions is None:
            masterdata_restrictions = {}

        if not self.masterdata_is_curated():
            if "colrev_masterdata_provenance" not in self.data:
                self.data["colrev_masterdata_provenance"] = {}
            missing_fields: Set[str] = set()
            try:
                missing_fields = self.get_missing_fields()
                not_missing_fields = []
                for missing_field in missing_fields:
                    if missing_field in self.data["colrev_masterdata_provenance"]:
                        if (
                            "not_missing"
                            in self.data["colrev_masterdata_provenance"][missing_field][
                                "note"
                            ]
                        ):
                            not_missing_fields.append(missing_field)
                            continue
                    self.add_masterdata_provenance_note(
                        key=missing_field, note="missing"
                    )

                for not_missing_field in not_missing_fields:
                    missing_fields.remove(not_missing_field)
            except colrev_exceptions.MissingRecordQualityRuleSpecification:
                pass

            if masterdata_restrictions:
                self.apply_restrictions(restrictions=masterdata_restrictions)

            if self.data.get("year", "") == "forthcoming":
                source = "NA"
                if "year" in self.data["colrev_masterdata_provenance"]:
                    source = self.data["colrev_masterdata_provenance"]["year"]["source"]
                if "volume" in missing_fields:
                    missing_fields.remove("volume")
                    self.data["colrev_masterdata_provenance"]["volume"] = {
                        "source": source,
                        "note": "not_missing",
                    }
                if "number" in missing_fields:
                    missing_fields.remove("number")
                    self.data["colrev_masterdata_provenance"]["number"] = {
                        "source": source,
                        "note": "not_missing",
                    }

            if not missing_fields:
                self.set_masterdata_complete(
                    source="update_masterdata_provenance",
                    replace_source=False,
                )

            inconsistencies = self.get_inconsistencies()
            if inconsistencies:
                for inconsistency in inconsistencies:
                    self.add_masterdata_provenance_note(
                        key=inconsistency,
                        note="inconsistent with ENTRYTYPE",
                    )
            else:
                self.set_masterdata_consistent()

            incomplete_fields = self.get_incomplete_fields()
            if incomplete_fields:
                for incomplete_field in incomplete_fields:
                    self.add_masterdata_provenance_note(
                        key=incomplete_field, note="incomplete"
                    )
            else:
                self.set_fields_complete()

            defect_fields = self.get_quality_defects()
            if defect_fields:
                for defect_field in defect_fields:
                    self.add_masterdata_provenance_note(
                        key=defect_field, note="quality_defect"
                    )
            else:
                self.remove_quality_defect_notes()

            if missing_fields or inconsistencies or incomplete_fields or defect_fields:
                self.set_status(target_state=RecordState.md_needs_manual_preparation)

    def check_potential_retracts(self) -> bool:
        """Check for potential retracts"""
        # Note : we retrieved metadata in get_masterdata_from_crossref()
        if self.data.get("crossmark", "") == "True":
            self.prescreen_exclude(reason="retracted", print_warning=True)
            self.remove_field(key="crossmark")
            return True
        if self.data.get("warning", "") == "Withdrawn (according to DBLP)":
            self.prescreen_exclude(reason="retracted", print_warning=True)
            self.remove_field(key="warning")
            return True
        return False

    def print_prescreen_record(self) -> None:
        """Print the record for prescreen operations"""

        ret_str = f"  ID: {self.data['ID']} ({self.data['ENTRYTYPE']})"
        ret_str += (
            f"\n  {colors.GREEN}{self.data.get('title', 'no title')}{colors.END}"
            f"\n  {self.data.get('author', 'no-author')}"
        )
        if self.data["ENTRYTYPE"] == "article":
            ret_str += (
                f"\n  {self.data.get('journal', 'no-journal')} "
                f"({self.data.get('year', 'no-year')}) "
                f"{self.data.get('volume', 'no-volume')}"
                f"({self.data.get('number', '')})"
            )
        elif self.data["ENTRYTYPE"] == "inproceedings":
            ret_str += f"\n  {self.data.get('booktitle', 'no-booktitle')}"
        if "abstract" in self.data:
            lines = textwrap.wrap(self.data["abstract"], 100, break_long_words=False)
            if lines:
                ret_str += f"\n  Abstract: {lines.pop(0)}\n"
                ret_str += "\n  ".join(lines) + ""

        if "url" in self.data:
            ret_str += f"\n  url: {self.data['url']}"

        if "file" in self.data:
            ret_str += f"\n  file: {self.data['file']}"

        print(ret_str)

    def print_pdf_prep_man(self) -> None:
        """Print the record for pdf-prep-man operations"""
        # pylint: disable=too-many-branches
        ret_str = ""
        if "file" in self.data:
            ret_str += f"\nfile: {colors.ORANGE}{self.data['file']}{colors.END}\n\n"

        pdf_prep_note = self.get_field_provenance(key="file")

        if "author_not_in_first_pages" in pdf_prep_note["note"]:
            ret_str += (
                f"{colors.RED}{self.data.get('author', 'no-author')}{colors.END}\n"
            )
        else:
            ret_str += (
                f"{colors.GREEN}{self.data.get('author', 'no-author')}{colors.END}\n"
            )

        if "title_not_in_first_pages" in pdf_prep_note["note"]:
            ret_str += f"{colors.RED}{self.data.get('title', 'no title')}{colors.END}\n"
        else:
            ret_str += (
                f"{colors.GREEN}{self.data.get('title', 'no title')}{colors.END}\n"
            )

        if self.data["ENTRYTYPE"] == "article":
            ret_str += (
                f"{self.data.get('journal', 'no-journal')} "
                f"({self.data.get('year', 'no-year')}) "
                f"{self.data.get('volume', 'no-volume')}"
                f"({self.data.get('number', '')})"
            )
            if "pages" in self.data:
                if "nr_pages_not_matching" in pdf_prep_note["note"]:
                    ret_str += f", {colors.RED}pp.{self.data['pages']}{colors.END}\n"
                else:
                    ret_str += f", pp.{colors.GREEN}{self.data['pages']}{colors.END}\n"
            else:
                ret_str += "\n"
        elif self.data["ENTRYTYPE"] == "inproceedings":
            ret_str += f"{self.data.get('booktitle', 'no-booktitle')}\n"
        if "abstract" in self.data:
            lines = textwrap.wrap(self.data["abstract"], 100, break_long_words=False)
            ret_str += f"\nAbstract: {lines.pop(0)}\n"
            ret_str += "\n".join(lines) + "\n"

        if "url" in self.data:
            ret_str += f"\nurl: {self.data['url']}\n"

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
        if "author" not in record.data:
            return
        authors = record.data["author"]
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
        record.data["author"] = authors_string

    def container_is_abbreviated(self) -> bool:
        """Check whether the container title is abbreviated"""
        if "journal" in self.data:
            if self.data["journal"].count(".") > 2:
                return True
            if self.data["journal"].isupper():
                return True
        if "booktitle" in self.data:
            if self.data["booktitle"].count(".") > 2:
                return True
            if self.data["booktitle"].isupper():
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
            if "journal" in record.data:
                record.data["journal"] = " ".join(
                    [x[:min_len] for x in record.data["journal"].split(" ")]
                )

        def get_abbrev_container_min_len(*, record: colrev.record.Record) -> int:
            min_len = -1
            if "journal" in record.data:
                min_len = min(
                    len(x) for x in record.data["journal"].replace(".", "").split(" ")
                )
            if "booktitle" in record.data:
                min_len = min(
                    len(x) for x in record.data["booktitle"].replace(".", "").split(" ")
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

        if "title" in record.data:
            record.data["title"] = record.data["title"][:90]
        if "title" in retrieved_record.data:
            retrieved_record.data["title"] = retrieved_record.data["title"][:90]

        if "author" in record.data:
            cls.__format_authors_string_for_comparison(record=record)
            record.data["author"] = record.data["author"][:45]
        if "author" in retrieved_record.data:
            cls.__format_authors_string_for_comparison(record=retrieved_record)
            retrieved_record.data["author"] = retrieved_record.data["author"][:45]
        if not ("volume" in record.data and "volume" in retrieved_record.data):
            record.data["volume"] = "nan"
            retrieved_record.data["volume"] = "nan"
        if not ("number" in record.data and "number" in retrieved_record.data):
            record.data["number"] = "nan"
            retrieved_record.data["number"] = "nan"
        if not ("pages" in record.data and "pages" in retrieved_record.data):
            record.data["pages"] = "nan"
            retrieved_record.data["pages"] = "nan"
        # Sometimes, the number of pages is provided (not the range)
        elif not (
            "--" in record.data["pages"] and "--" in retrieved_record.data["pages"]
        ):
            record.data["pages"] = "nan"
            retrieved_record.data["pages"] = "nan"

        if "year" in record.data and "year" in retrieved_record.data:
            if record.data["year"] == "forthcoming":
                record.data["year"] = retrieved_record.data["year"]
            if retrieved_record.data["year"] == "forthcoming":
                retrieved_record.data["year"] = record.data["year"]

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
                "ENTRYTYPE", "a"
            ) != retrieved_record_original.data.get("ENTRYTYPE", "b"):
                return 0.0

        record = record_original.copy_prep_rec()
        retrieved_record = retrieved_record_original.copy_prep_rec()

        cls.__prep_records_for_similarity(
            record=record, retrieved_record=retrieved_record
        )

        if "editorial" in record.data.get("title", "NA").lower():
            if not all(x in record.data for x in ["volume", "number"]):
                return 0.0

        similarity = Record.get_record_similarity(
            record_a=record, record_b=retrieved_record
        )

        return similarity

    def format_if_mostly_upper(self, *, key: str, case: str = "capitalize") -> None:
        """Format the field if it is mostly in upper case"""
        # if not re.match(r"^[a-zA-Z\"\{\} ]+$", self.data[key]):
        #     return

        self.data[key] = self.data[key].replace("\n", " ")

        if colrev.env.utils.percent_upper_chars(self.data[key]) > 0.8:
            if case == "capitalize":
                self.data[key] = self.data[key].capitalize()
            if case == "title":
                self.data[key] = (
                    self.data[key]
                    .title()
                    .replace(" Of ", " of ")
                    .replace(" For ", " for ")
                    .replace(" The ", " the ")
                    .replace("Ieee", "IEEE")
                    .replace("Acm", "ACM")
                    .replace(" And ", " and ")
                )

            if key in self.data.get("colrev_masterdata_provenance", {}):
                note = self.data["colrev_masterdata_provenance"][key]["note"]
                if "quality_defect" in note:
                    self.data["colrev_masterdata_provenance"][key][
                        "note"
                    ] = note.replace("quality_defect", "")

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
        if "pages" not in self.data:
            return
        if not isinstance(self.data["pages"], str):
            return
        if 1 == self.data["pages"].count("-"):
            self.data["pages"] = self.data["pages"].replace("-", "--")
        self.data["pages"] = (
            self.data["pages"]
            .replace("–", "--")
            .replace("----", "--")
            .replace(" -- ", "--")
            .rstrip(".")
        )

    def preparation_save_condition(self) -> bool:
        """Check whether the save condition for the prep operation is given"""

        if self.data.get("colrev_status", "NA") in [
            RecordState.rev_prescreen_excluded,
            RecordState.md_prepared,
        ]:
            return True

        if any(
            "disagreement with " in x["note"]
            for x in self.data.get("colrev_masterdata_provenance", {}).values()
        ) or any(
            "record_not_in_toc" in x["note"]
            for x in self.data.get("colrev_masterdata_provenance", {}).values()
        ):
            return True

        return False

    def preparation_break_condition(self) -> bool:
        """Check whether the break condition for the prep operation is given"""
        if any(
            "disagreement with " in x["note"]
            for x in self.data.get("colrev_masterdata_provenance", {}).values()
        ) or any(
            "record_not_in_toc" in x["note"]
            for x in self.data.get("colrev_masterdata_provenance", {}).values()
        ):
            return True

        if self.data.get("colrev_status", "NA") in [
            RecordState.rev_prescreen_excluded,
        ]:
            return True
        return False

    def status_to_prepare(self) -> bool:
        """Check whether the record needs to be prepared"""
        return self.data.get("colrev_status", "NA") in [
            RecordState.md_needs_manual_preparation,
            RecordState.md_imported,
            RecordState.md_prepared,
        ]

    def update_metadata_status(
        self,
    ) -> None:
        """Update the metadata status (retracts, incompleteness, inconsistencies, etc.)
        and setting the status accordingly"""

        self.check_potential_retracts()

        if (
            colrev.record.RecordState.rev_prescreen_excluded
            == self.data["colrev_status"]
        ):
            return

        if self.masterdata_is_curated():
            self.set_status(target_state=RecordState.md_prepared)
            return

        if (
            self.masterdata_is_complete()
            and not self.has_incomplete_fields()
            and not self.has_inconsistent_fields()
            and not self.has_quality_defects()
        ):
            self.set_status(target_state=RecordState.md_prepared)
        else:
            self.set_status(target_state=RecordState.md_needs_manual_preparation)


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
            "trigger": "load",
            "source": RecordState.md_retrieved,
            "dest": RecordState.md_imported,
        },
        {
            "trigger": "prep",
            "source": RecordState.md_imported,
            "dest": RecordState.md_needs_manual_preparation,
        },
        {
            "trigger": "prep",
            "source": RecordState.md_imported,
            "dest": RecordState.md_prepared,
        },
        {
            "trigger": "prep_man",
            "source": RecordState.md_needs_manual_preparation,
            "dest": RecordState.md_prepared,
        },
        {
            "trigger": "dedupe",
            "source": RecordState.md_prepared,
            "dest": RecordState.md_processed,
        },
        {
            "trigger": "prescreen",
            "source": RecordState.md_processed,
            "dest": RecordState.rev_prescreen_excluded,
        },
        {
            "trigger": "prescreen",
            "source": RecordState.md_processed,
            "dest": RecordState.rev_prescreen_included,
        },
        {
            "trigger": "pdf_get",
            "source": RecordState.rev_prescreen_included,
            "dest": RecordState.pdf_imported,
        },
        {
            "trigger": "pdf_get",
            "source": RecordState.rev_prescreen_included,
            "dest": RecordState.pdf_needs_manual_retrieval,
        },
        {
            "trigger": "pdf_get_man",
            "source": RecordState.pdf_needs_manual_retrieval,
            "dest": RecordState.pdf_not_available,
        },
        {
            "trigger": "pdf_get_man",
            "source": RecordState.pdf_needs_manual_retrieval,
            "dest": RecordState.pdf_imported,
        },
        {
            "trigger": "pdf_prep",
            "source": RecordState.pdf_imported,
            "dest": RecordState.pdf_needs_manual_preparation,
        },
        {
            "trigger": "pdf_prep",
            "source": RecordState.pdf_imported,
            "dest": RecordState.pdf_prepared,
        },
        {
            "trigger": "pdf_prep_man",
            "source": RecordState.pdf_needs_manual_preparation,
            "dest": RecordState.pdf_prepared,
        },
        {
            "trigger": "screen",
            "source": RecordState.pdf_prepared,
            "dest": RecordState.rev_excluded,
        },
        {
            "trigger": "screen",
            "source": RecordState.pdf_prepared,
            "dest": RecordState.rev_included,
        },
        {
            "trigger": "data",
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

            return {el["colrev_status"] for el in record_header_list}

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


if __name__ == "__main__":
    pass
