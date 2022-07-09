#! /usr/bin/env python
import pprint
import re
import typing
import unicodedata
from copy import deepcopy
from enum import auto
from enum import Enum
from pathlib import Path

import pandas as pd
from nameparser import HumanName
from thefuzz import fuzz


class Record:

    identifying_field_keys = [
        "title",
        "author",
        "year",
        "journal",
        "booktitle",
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
    }
    """Fields requirements for respective ENTRYTYPE"""

    # book, inbook: author <- editor

    record_field_inconsistencies: typing.Dict[str, typing.List[str]] = {
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
        "colrev_id",
        "colrev_data_provenance",
        "colrev_pdf_id",
        "MOVED_DUPE",
    ]

    preferred_sources = ["https://api.crossref.org/works/"]

    pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)

    def __init__(self, *, data: dict):
        self.data = data
        """Dictionary containing the record data"""
        # Note : avoid parsing upon Record instantiation as much as possible
        # to maintain high performance and ensure pickle-abiligy (in multiprocessing)

    def __repr__(self) -> str:
        return self.pp.pformat(self.data)

    def __str__(self) -> str:

        self.identifying_keys_order = ["ID", "ENTRYTYPE"] + [
            k for k in self.identifying_field_keys if k in self.data
        ]
        complementary_keys_order = [
            k for k, v in self.data.items() if k not in self.identifying_keys_order
        ]

        ik_sorted = {
            k: v for k, v in self.data.items() if k in self.identifying_keys_order
        }
        ck_sorted = {
            k: v for k, v in self.data.items() if k in complementary_keys_order
        }
        ret_str = (
            self.pp.pformat(ik_sorted)[:-1] + "\n" + self.pp.pformat(ck_sorted)[1:]
        )

        return ret_str

    def copy(self):
        return Record(data=deepcopy(self.data))

    def copy_prep_rec(self):
        return PrepRecord(data=deepcopy(self.data))

    def update_by_record(self, *, UPDATE):
        self.data = UPDATE.copy_prep_rec().get_data()
        return

    def get_diff(self, *, OTHER_RECORD) -> list:
        import dictdiffer

        diff = list(dictdiffer.diff(self.get_data(), OTHER_RECORD.get_data()))
        return diff

    def format_bib_style(self) -> str:
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

    def get_data(self, *, stringify=False) -> dict:
        from colrev_core.review_dataset import ReviewDataset

        def save_field_dict(*, input_dict: dict, key: str) -> list:
            list_to_return = []
            if "colrev_masterdata_provenance" == key:
                for k, v in input_dict.items():
                    list_to_return.append(f"{k}:{v['source']};{v['note']};")

            elif "colrev_data_provenance" == key:
                for k, v in input_dict.items():
                    list_to_return.append(f"{k}:{v['source']};{v['note']};")

            else:
                print(f"error in to_string of dict_field: {key}")

            return list_to_return

        def list_to_str(*, val: list) -> str:
            return ("\n" + " " * 36).join([f.rstrip() for f in val])

        if stringify:

            # separated by \n
            for key in ReviewDataset.list_fields_keys:
                if key in self.data:
                    if isinstance(self.data[key], str):
                        self.data[key] = [
                            element.lstrip().rstrip()
                            for element in self.data[key].split(";")
                        ]
                    if "colrev_id" == key:
                        self.data[key] = sorted(list(set(self.data[key])))
                    for ind, val in enumerate(self.data[key]):
                        if len(val) > 0:
                            if ";" != val[-1]:
                                self.data[key][ind] = val + ";"
                    self.data[key] = list_to_str(val=self.data[key])

            for key in ReviewDataset.dict_fields_keys:
                if key in self.data:
                    if isinstance(self.data[key], dict):
                        self.data[key] = save_field_dict(
                            input_dict=self.data[key], key=key
                        )
                    if isinstance(self.data[key], list):
                        self.data[key] = list_to_str(val=self.data[key])

        return self.data

    def masterdata_is_curated(self) -> bool:
        return "CURATED" in self.data.get("colrev_masterdata_provenance", {})

    def set_status(self, *, target_state) -> None:
        from colrev_core.record import RecordState

        if RecordState.md_prepared == target_state:
            if self.masterdata_is_complete():
                try:
                    colrev_id = self.create_colrev_id()
                    if "colrev_id" not in self.data:
                        self.data["colrev_id"] = colrev_id
                    elif colrev_id not in self.data["colrev_id"]:
                        self.data["colrev_id"] += ";" + colrev_id

                    # else should not happen because colrev_ids should only be
                    # created once records are prepared (complete)
                except NotEnoughDataToIdentifyException:
                    pass
            else:
                target_state = RecordState.md_needs_manual_preparation

        self.data["colrev_status"] = target_state

    def get_origins(self) -> list:
        if "colrev_origin" in self.data:
            origins = self.data["colrev_origin"].split(";")
        else:
            origins = []

        # Note : to cover legacy key:
        if "origin" in self.data:
            origins = self.data["origin"].split(";")

        return origins

    def shares_origins(self, *, other_record) -> bool:
        return any(x in other_record.get_origins() for x in self.get_origins())

    def get_source_repo(self) -> str:
        # priority: return source_link first (then check for source_path)
        if "source_link" in self.data:
            if self.data["source_link"] is not None:
                if "http" in self.data["source_link"]:
                    return self.data["source_link"]
            else:
                print("source_link: none")
        if "source_path" in self.data:
            return self.data["source_path"]
        return "NO_SOURCE_INFO"

    def get_value(self, *, key: str, default=None):
        if default is not None:
            try:
                ret = self.data[key]
                return ret
            except KeyError:
                pass
                return default
        else:
            return self.data[key]

    def get_colrev_id(self) -> list:
        # Note : do not automatically create colrev_ids
        # or at least keep in mind that this will not be possible for some records
        colrev_id = []
        if "colrev_id" in self.data:
            if isinstance(self.data["colrev_id"], str):
                colrev_id = [cid.lstrip() for cid in self.data["colrev_id"].split(";")]
            elif isinstance(self.data["colrev_id"], list):
                colrev_id = self.data["colrev_id"]
        return colrev_id

    def update_field(
        self,
        *,
        key: str,
        value,
        source: str,
        comment: str = "",
        keep_source_if_equal: bool = False,
    ) -> None:
        if keep_source_if_equal:
            if key in self.data:
                if self.data[key] == value:
                    return
        self.data[key] = value
        if key in self.identifying_field_keys:
            self.add_masterdata_provenance(key=key, source=source, note=comment)
        else:
            self.add_data_provenance(key=key, source=source, note=comment)
        return

    def rename_field(self, *, key: str, new_key: str) -> None:
        value = self.data[key]
        self.data[new_key] = value

        if key in self.identifying_field_keys:
            value_provenance = self.data["colrev_masterdata_provenance"][key]
            self.data["colrev_masterdata_provenance"][new_key] = value_provenance
        else:
            value_provenance = self.data["colrev_data_provenance"][key]
            self.data["colrev_data_provenance"][new_key] = value_provenance

        self.remove_field(key=key)

        return

    def change_ENTRYTYPE(self, *, NEW_ENTRYTYPE):

        self.data["ENTRYTYPE"] = NEW_ENTRYTYPE

        # TODO : reapply field requirements

        return

    def remove_field(
        self, *, key: str, not_missing_note: bool = False, source=""
    ) -> None:
        if key in self.data:
            del self.data[key]
            if not_missing_note:
                if key in self.identifying_field_keys:
                    # Example: journal without number
                    # we should keep that information that a particular masterdata
                    # field is not required
                    if key in self.data["colrev_masterdata_provenance"]:
                        self.data["colrev_masterdata_provenance"][key][
                            "note"
                        ] = "not_missing"
                        self.data["colrev_masterdata_provenance"][key][
                            "source"
                        ] = source

            else:
                if key in self.identifying_field_keys:
                    if key in self.data.get("colrev_masterdata_provenance", ""):
                        del self.data["colrev_masterdata_provenance"][key]
                else:
                    if key in self.data.get("colrev_data_provenance", ""):
                        del self.data["colrev_data_provenance"][key]

        return

    def add_colrev_ids(self, *, records: typing.List[dict]) -> None:
        if "colrev_id" in self.data:
            if isinstance(self.data["colrev_id"], str):
                print(f'Problem: colrev_id is str not list: {self.data["colrev_id"]}')
                self.data["colrev_id"] = self.data["colrev_id"].split(";")
        for r in records:
            try:
                colrev_id = self.create_colrev_id(alsoKnownAsRecord=r)
                if "colrev_id" not in self.data:
                    self.data["colrev_id"] = colrev_id
                elif colrev_id not in self.data["colrev_id"]:
                    self.data["colrev_id"].append(colrev_id)
            except NotEnoughDataToIdentifyException:
                pass
        return

    def masterdata_is_complete(self) -> bool:
        if self.masterdata_is_curated():
            return True
        if not any(
            v == "UNKNOWN"
            for k, v in self.data.items()
            if k in self.identifying_field_keys
        ):
            return True
        return False

    def set_masterdata_complete(self) -> None:
        md_p_dict = self.data.get("colrev_masterdata_provenance", {})

        for identifying_field_key in self.identifying_field_keys:
            if "UNKNOWN" == self.data.get(identifying_field_key, "NA"):
                del self.data[identifying_field_key]
            if identifying_field_key in md_p_dict:
                note = md_p_dict[identifying_field_key]["note"]
                if "missing" in note and "not_missing" not in note:
                    md_p_dict[identifying_field_key]["note"] = note.replace(
                        "missing", ""
                    )
        return

    def set_masterdata_consistent(self) -> None:
        md_p_dict = self.data.get("colrev_masterdata_provenance", {})
        for identifying_field_key in self.identifying_field_keys:
            if identifying_field_key in md_p_dict:
                note = md_p_dict[identifying_field_key]["note"]
                if "inconsistent with ENTRYTYPE" in note:
                    md_p_dict[identifying_field_key]["note"] = note.replace(
                        "inconsistent with ENTRYTYPE", ""
                    )
        return

    def set_fields_complete(self) -> None:
        for identifying_field_key in self.identifying_field_keys:
            if identifying_field_key in self.data["colrev_masterdata_provenance"]:
                note = self.data["colrev_masterdata_provenance"][identifying_field_key][
                    "note"
                ]
                if "incomplete" in self.data["colrev_masterdata_provenance"]:
                    self.data["colrev_masterdata_provenance"][identifying_field_key][
                        "note"
                    ] = note.replace("incomplete", "")
        return

    def reset_pdf_provenance_notes(self) -> None:
        if "colrev_data_provenance" not in self.data:
            self.add_data_provenance_note(key="file", note="")
        if "file" in self.data["colrev_data_provenance"]:
            # TODO : check note and remove notes selectively
            # note = d_p_dict['file']['note']
            self.data["colrev_data_provenance"]["file"]["note"] = ""
        return

    def missing_fields(self) -> list:
        missing_field_keys = []
        if self.data["ENTRYTYPE"] in Record.record_field_requirements.keys():
            reqs = Record.record_field_requirements[self.data["ENTRYTYPE"]]
            missing_field_keys = [
                x
                for x in reqs
                if x not in self.data.keys()
                or "" == self.data[x]
                or "UNKNOWN" == self.data[x]
            ]
        else:
            missing_field_keys = ["no field requirements defined"]
        return missing_field_keys

    def get_inconsistencies(self) -> list:
        inconsistent_field_keys = []
        if self.data["ENTRYTYPE"] in Record.record_field_inconsistencies.keys():
            incons_fields = Record.record_field_inconsistencies[self.data["ENTRYTYPE"]]
            inconsistent_field_keys = [x for x in incons_fields if x in self.data]
        # Note: a thesis should be single-authored
        if "thesis" in self.data["ENTRYTYPE"] and " and " in self.data.get(
            "author", ""
        ):
            inconsistent_field_keys.append("author")
        return inconsistent_field_keys

    def has_inconsistent_fields(self) -> bool:
        found_inconsistencies = False
        if self.data["ENTRYTYPE"] in Record.record_field_inconsistencies.keys():
            inconsistencies = self.get_inconsistencies()
            if inconsistencies:
                found_inconsistencies = True
        return found_inconsistencies

    def has_incomplete_fields(self) -> bool:
        if len(self.get_incomplete_fields()) > 0:
            return True
        return False

    def merge(self, *, MERGING_RECORD, default_source: str) -> None:
        """General-purpose record merging
        for preparation, curated/non-curated records and records with origins


        Apply heuristics to create a fusion of the best fields based on
        quality heuristics"""

        # self.REVIEW_MANAGER.logger.debug(
        #     "Fuse retrieved record " "(select fields with the highest quality)"
        # )
        # self.REVIEW_MANAGER.logger.debug(MERGING_RECORD)

        # NOTE : the following block was originally dedupe-merge-records
        # TODO : consider fuse_best_fields... (if not curated)

        if "colrev_origin" in MERGING_RECORD.data:
            origins = self.data["colrev_origin"].split(";") + MERGING_RECORD.data[
                "colrev_origin"
            ].split(";")
            self.data["colrev_origin"] = ";".join(list(set(origins)))

        # if not self.masterdata_is_curated():
        #     for k in self.identifying_field_keys:
        #         if k in MERGING_RECORD.data and k not in self.data:
        #             self.data[k] = MERGING_RECORD.data[k]

        # if "pages" in MERGING_RECORD.data and "pages" not in self.data:
        #     self.data["pages"] = MERGING_RECORD.data["pages"]

        # Note : no need to check "not self.masterdata_is_curated()":
        # this should enable updates of curated metadata
        if MERGING_RECORD.masterdata_is_curated() and not self.masterdata_is_curated():
            self.data["colrev_masterdata_provenance"] = MERGING_RECORD.data[
                "colrev_masterdata_provenance"
            ]

            for k in list(self.data.keys()):
                if k in Record.identifying_field_keys and k != "pages":
                    del self.data[k]

        # TODO : TBD: merge colrev_ids?

        for key, val in MERGING_RECORD.data.items():
            if "" == val:
                continue
            if not val:
                continue

            # do not override provenance, ID, ... fields
            if key in [
                "ID",
                "colrev_masterdata_provenance",
                "colrev_data_provenance",
                "colrev_id",
                "colrev_status",
                "colrev_origin",
                "MOVED_DUPE",
            ]:
                continue

            source = MERGING_RECORD.get_provenance_field_source(
                key=key, default=default_source
            )

            # Part 1: identifying fields
            if key in Record.identifying_field_keys:

                # Always update from curated MERGING_RECORDs
                if MERGING_RECORD.masterdata_is_curated():
                    self.data[key] = MERGING_RECORD.data[key]

                # Do not change if MERGING_RECORD is not curated
                elif (
                    self.masterdata_is_curated()
                    and not MERGING_RECORD.masterdata_is_curated()
                ):
                    continue

                # Fuse best fields if none is curated
                else:
                    self.fuse_best_field(
                        MERGING_RECORD=MERGING_RECORD, key=key, val=val, source=source
                    )

            # Part 2: other fields
            else:
                # keep existing values per default
                if key in self.data:
                    # except for those that should be updated regularly
                    if key in ["cited_by"]:
                        self.update_field(key=key, value=str(val), source=source)
                else:
                    self.update_field(key=key, value=str(val), source=source)

        return

    def fuse_best_field(self, *, MERGING_RECORD, key, val, source) -> None:
        # Note : the assumption is that we need masterdata_provenance notes
        # only for authors

        def percent_upper_chars(input_string: str) -> float:
            return sum(map(str.isupper, input_string)) / len(input_string)

        def select_best_author(RECORD: Record, MERGING_RECORD: Record) -> str:
            record_a_prov = RECORD.data.get("colrev_masterdata_provenance", {})
            merging_record_a_prov = MERGING_RECORD.data.get(
                "colrev_masterdata_provenance", {}
            )

            if "author" in record_a_prov and "author" not in merging_record_a_prov:
                # Prefer non-defect version
                if "quality_defect" in record_a_prov["author"].get("note", ""):
                    return MERGING_RECORD.data["author"]
                # Prefer complete version
                if "incomplete" in record_a_prov["author"].get("note", ""):
                    return MERGING_RECORD.data["author"]
            elif "author" in record_a_prov and "author" in merging_record_a_prov:
                # Prefer non-defect version
                if "quality_defect" in record_a_prov["author"].get(
                    "note", ""
                ) and "quality_defect" not in merging_record_a_prov["author"].get(
                    "note", ""
                ):
                    return MERGING_RECORD.data["author"]

                # Prefer complete version
                if "incomplete" in record_a_prov["author"].get(
                    "note", ""
                ) and "incomplete" not in merging_record_a_prov["author"].get(
                    "note", ""
                ):
                    return MERGING_RECORD.data["author"]

            if (
                len(RECORD.data["author"]) > 0
                and len(MERGING_RECORD.data["author"]) > 0
            ):
                default_mostly_upper = percent_upper_chars(RECORD.data["author"]) > 0.8
                candidate_mostly_upper = (
                    percent_upper_chars(MERGING_RECORD.data["author"]) > 0.8
                )

                # Prefer title case (not all-caps)
                if default_mostly_upper and not candidate_mostly_upper:
                    return MERGING_RECORD.data["author"]

            # Prefer sources
            if "author" in merging_record_a_prov:
                if any(
                    x in merging_record_a_prov["author"]["source"]
                    for x in self.preferred_sources
                ):
                    return MERGING_RECORD.data["author"]

            # self.REVIEW_MANAGER.logger.debug(
            #     f"best_author({default}, \n"
            #     f"                                      {candidate}) = \n"
            #     f"                                      {best_author}"
            # )
            return RECORD.data["author"]

        def select_best_pages(*, default: str, candidate: str) -> str:
            best_pages = default
            if "--" in candidate and "--" not in default:
                best_pages = candidate

            # self.REVIEW_MANAGER.logger.debug(
            #     f"best_pages({default}, {candidate}) = {best_pages}"
            # )

            return best_pages

        def select_best_title(*, default: str, candidate: str) -> str:
            best_title = default

            default_upper = percent_upper_chars(default)
            candidate_upper = percent_upper_chars(candidate)

            # Relatively simple rule...
            # catches cases when default is all upper or title case
            if default_upper > candidate_upper:
                best_title = candidate

            # self.REVIEW_MANAGER.logger.debug(
            #     f"best_title({default},\n"
            #     f"                                      {candidate}) = \n"
            #     f"                                      {best_title}"
            # )

            return best_title

        def select_best_journal(*, default: str, candidate: str) -> str:

            best_journal = default

            default_upper = percent_upper_chars(default)
            candidate_upper = percent_upper_chars(candidate)

            # Simple heuristic to avoid abbreviations
            if "." in default and "." not in candidate:
                best_journal = candidate
            # Relatively simple rule...
            # catches cases when default is all upper or title case
            if default_upper > candidate_upper:
                best_journal = candidate

            # self.REVIEW_MANAGER.logger.debug(
            #     f"best_journal({default}, \n"
            #     f"                                      {candidate}) = \n"
            #     f"                                      {best_journal}"
            # )

            return best_journal

        if "author" == key:
            if "author" in self.data:
                best_author = select_best_author(self, MERGING_RECORD)
                if self.data["author"] != best_author:
                    self.update_field(key="author", value=best_author, source=source)
            else:
                self.update_field(key="author", value=str(val), source=source)

        elif "pages" == key:
            if "pages" in self.data:
                best_pages = select_best_pages(
                    default=self.data["pages"], candidate=MERGING_RECORD.data["pages"]
                )
                if self.data["pages"] != best_pages:
                    self.update_field(key="pages", value=best_pages, source=source)

            else:
                self.update_field(key="pages", value=str(val), source=source)

        elif "title" == key:
            if "title" in self.data:
                best_title = select_best_title(
                    default=self.data["title"], candidate=MERGING_RECORD.data["title"]
                )
                self.update_field(key="title", value=best_title, source=source)

            else:
                self.update_field(key="title", value=str(val), source=source)

        elif "journal" == key:
            if "journal" in self.data:
                best_journal = select_best_journal(
                    default=self.data["journal"],
                    candidate=MERGING_RECORD.data["journal"],
                )
                self.update_field(key="journal", value=best_journal, source=source)
            else:
                self.update_field(key="journal", value=str(val), source=source)

        elif "booktitle" == key:
            if "booktitle" in self.data:
                best_booktitle = select_best_journal(
                    default=self.data["booktitle"],
                    candidate=MERGING_RECORD.data["booktitle"],
                )
                # TBD: custom select_best_booktitle?
                self.update_field(key="booktitle", value=best_booktitle, source=source)

            else:
                self.update_field(key="booktitle", value=str(val), source=source)

        elif "file" == key:
            if "file" in self.data:
                self.data["file"] = (
                    self.data["file"] + ";" + MERGING_RECORD.data.get("file", "")
                )
            else:
                self.data["file"] = MERGING_RECORD.data["file"]
        else:
            self.update_field(key=key, value=str(val), source=source)
        return

    @classmethod
    def get_record_similarity(cls, *, RECORD_A, RECORD_B) -> float:
        record_a = deepcopy(RECORD_A.get_data())
        record_b = deepcopy(RECORD_B.get_data())

        if "title" not in record_a:
            record_a["title"] = ""
        if "author" not in record_a:
            record_a["author"] = ""
        if "year" not in record_a:
            record_a["year"] = ""
        if "journal" not in record_a:
            record_a["journal"] = ""
        if "volume" not in record_a:
            record_a["volume"] = ""
        if "number" not in record_a:
            record_a["number"] = ""
        if "pages" not in record_a:
            record_a["pages"] = ""
        if "booktitle" not in record_a:
            record_a["booktitle"] = ""
        if "title" not in record_b:
            record_b["title"] = ""
        if "author" not in record_b:
            record_b["author"] = ""
        if "year" not in record_b:
            record_b["year"] = ""
        if "journal" not in record_b:
            record_b["journal"] = ""
        if "volume" not in record_b:
            record_b["volume"] = ""
        if "number" not in record_b:
            record_b["number"] = ""
        if "pages" not in record_b:
            record_b["pages"] = ""
        if "booktitle" not in record_b:
            record_b["booktitle"] = ""

        if "container_title" not in record_a:
            record_a["container_title"] = (
                record_a.get("journal", "")
                + record_a.get("booktitle", "")
                + record_a.get("series", "")
            )

        if "container_title" not in record_b:
            record_b["container_title"] = (
                record_b.get("journal", "")
                + record_b.get("booktitle", "")
                + record_b.get("series", "")
            )

        df_a = pd.DataFrame.from_dict([record_a])
        df_b = pd.DataFrame.from_dict([record_b])

        return Record.get_similarity(df_a=df_a.iloc[0], df_b=df_b.iloc[0])

    @classmethod
    def get_similarity(cls, *, df_a: pd.DataFrame, df_b: pd.DataFrame) -> float:
        details = Record.get_similarity_detailed(df_a=df_a, df_b=df_b)
        return details["score"]

    @classmethod
    def get_similarity_detailed(cls, *, df_a: pd.DataFrame, df_b: pd.DataFrame) -> dict:

        try:
            author_similarity = fuzz.ratio(df_a["author"], df_b["author"]) / 100

            title_similarity = (
                fuzz.ratio(df_a["title"].lower(), df_b["title"].lower()) / 100
            )

            # partial ratio (catching 2010-10 or 2001-2002)
            year_similarity = fuzz.ratio(df_a["year"], df_b["year"]) / 100

            outlet_similarity = (
                fuzz.ratio(df_a["container_title"], df_b["container_title"]) / 100
            )

            if str(df_a["journal"]) != "nan":
                # Note: for journals papers, we expect more details
                if df_a["volume"] == df_b["volume"]:
                    volume_similarity = 1
                else:
                    volume_similarity = 0
                if df_a["number"] == df_b["number"]:
                    number_similarity = 1
                else:
                    number_similarity = 0

                # page similarity is not considered at the moment.
                #
                # sometimes, only the first page is provided.
                # if str(df_a["pages"]) == "nan" or str(df_b["pages"]) == "nan":
                #     pages_similarity = 1
                # else:
                #     if df_a["pages"] == df_b["pages"]:
                #         pages_similarity = 1
                #     else:
                #         if df_a["pages"].split("-")[0] == df_b["pages"].split("-")[0]:
                #             pages_similarity = 1
                #         else:
                #            pages_similarity = 0

                # Put more weight on other fields if the title is very common
                # ie., non-distinctive
                # The list is based on a large export of distinct papers, tabulated
                # according to titles and sorted by frequency
                if [df_a["title"], df_b["title"]] in [
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
            pass
        return {"score": similarity_score, "details": details}

    def get_provenance_field_source(self, *, key, default="ORIGINAL") -> str:
        if key in self.identifying_field_keys:
            if "colrev_masterdata_provenance" in self.data:
                if key in self.data["colrev_masterdata_provenance"]:
                    if "source" in self.data["colrev_masterdata_provenance"][key]:
                        return self.data["colrev_masterdata_provenance"][key]["source"]
        else:
            if "colrev_data_provenance" in self.data:
                if key in self.data["colrev_data_provenance"]:
                    if "source" in self.data["colrev_data_provenance"][key]:
                        return self.data["colrev_data_provenance"][key]["source"]

        return default

    def add_masterdata_provenance_note(self, *, key, note):
        if "colrev_masterdata_provenance" not in self.data:
            self.data["colrev_masterdata_provenance"] = {}
        if key in self.data["colrev_masterdata_provenance"]:
            if note not in self.data["colrev_masterdata_provenance"][key]["note"]:
                if "" == self.data["colrev_masterdata_provenance"][key]["note"]:
                    self.data["colrev_masterdata_provenance"][key]["note"] += f"{note}"
                else:
                    self.data["colrev_masterdata_provenance"][key]["note"] += f",{note}"
        else:
            self.data["colrev_masterdata_provenance"][key] = {
                "source": "ORIGINAL",
                "note": note,
            }
        return

    def add_data_provenance_note(self, *, key, note):
        if "colrev_data_provenance" not in self.data:
            self.data["colrev_data_provenance"] = {}
        if key in self.data["colrev_data_provenance"]:
            if note not in self.data["colrev_data_provenance"][key]["note"]:
                self.data["colrev_data_provenance"][key]["note"] += f",{note}"
        else:
            self.data["colrev_data_provenance"][key] = {
                "source": "ORIGINAL",
                "note": note,
            }
        return

    def add_masterdata_provenance(self, *, key, source, note: str = ""):
        md_p_dict = self.data.get("colrev_masterdata_provenance", {})

        if key in md_p_dict:
            if "" != note:
                md_p_dict[key]["note"] += f",{note}"
            else:
                md_p_dict[key]["note"] = ""
            md_p_dict[key]["source"] = source
        else:
            md_p_dict[key] = {"source": source, "note": f"{note}"}
        return

    def add_provenance_all(self, *, source):
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
            elif key in self.identifying_field_keys:
                md_p_dict[key] = {"source": source, "note": ""}
            else:
                d_p_dict[key] = {"source": source, "note": ""}
        return

    def add_data_provenance(self, *, key, source, note: str = ""):
        if "colrev_data_provenance" not in self.data:
            self.data["colrev_data_provenance"] = {}
        md_p_dict = self.data["colrev_data_provenance"]
        if key in md_p_dict:
            if "" != note:
                md_p_dict[key]["note"] += f",{note}"
            else:
                md_p_dict[key]["note"] = ""
            md_p_dict[key]["source"] = source
        else:
            md_p_dict[key] = {"source": source, "note": f"{note}"}
        return

    def complete_provenance(self, *, source_info) -> bool:
        """Complete provenance information for LocalIndex"""

        for key in list(self.data.keys()):

            if key in [
                "source_link",
                "source_url",
                "colrev_id",
                "colrev_status",
                "ENTRYTYPE",
                "ID",
                "source_path",
                "local_curated_metadata",
            ]:
                continue

            if key in self.identifying_field_keys:
                if not self.masterdata_is_curated:
                    self.add_masterdata_provenance(key=key, source=source_info, note="")
            else:
                self.add_data_provenance(key=key, source=source_info, note="")

        return True

    def get_incomplete_fields(self) -> list:
        incomplete_field_keys = []
        for key in self.data.keys():
            if key in ["title", "journal", "booktitle", "author"]:
                if self.data[key].endswith("...") or self.data[key].endswith("…"):
                    incomplete_field_keys.append(key)

            if "author" == key:
                if (
                    self.data[key].endswith("and others")
                    or self.data[key].endswith("et al.")
                    # heuristics for missing first names:
                    or ", and " in self.data[key]
                    or self.data[key].rstrip().endswith(",")
                ):
                    incomplete_field_keys.append(key)

        return incomplete_field_keys

    def get_quality_defects(self) -> list:
        defect_field_keys = []
        for key in self.data.keys():
            if "author" == key:
                if "UNKNOWN" == self.data[key]:
                    continue
                # Note : patterns like "I N T R O D U C T I O N"
                # that may result from grobid imports
                if re.search(r"[A-Z] [A-Z] [A-Z] [A-Z]", self.data[key]):
                    defect_field_keys.append(key)
                if len(self.data[key]) < 5:
                    defect_field_keys.append(key)

                if str(self.data[key]).count(" ") > (
                    4 * str(self.data[key]).count(",")
                ):
                    defect_field_keys.append(key)

                if str(self.data[key]).count(" and ") != (
                    str(self.data[key]).count(",") - 1
                ):
                    defect_field_keys.append(key)

            if "title" == key:
                # Note : titles that have no space and special characters
                # like _ . or digits.
                if " " not in self.data[key] and (
                    any(x in self.data[key] for x in ["_", "."])
                    or any(char.isdigit() for char in self.data[key])
                ):
                    defect_field_keys.append(key)

        return defect_field_keys

    def remove_quality_defect_notes(self) -> None:

        for key in self.data.keys():
            if key in self.data["colrev_masterdata_provenance"]:
                note = self.data["colrev_masterdata_provenance"][key]["note"]
                if "quality_defect" in note:
                    self.data["colrev_masterdata_provenance"][key][
                        "note"
                    ] = note.replace("quality_defect", "")
        return

    @classmethod
    def remove_accents(cls, *, input_str: str) -> str:
        def rmdiacritics(char):
            """
            Return the base character of char, by "removing" any
            diacritics like accents or curls and strokes and the like.
            """
            try:
                desc = unicodedata.name(char)
                cutoff = desc.find(" WITH ")
                if cutoff != -1:
                    desc = desc[:cutoff]
                    char = unicodedata.lookup(desc)
            except (KeyError, ValueError):
                pass  # removing "WITH ..." produced an invalid name
            return char

        try:
            nfkd_form = unicodedata.normalize("NFKD", input_str)
            wo_ac_list = [
                rmdiacritics(c) for c in nfkd_form if not unicodedata.combining(c)
            ]
            wo_ac = "".join(wo_ac_list)
        except ValueError:
            wo_ac = input_str
            pass
        return wo_ac

    def get_container_title(self) -> str:
        container_title = "NA"
        if "ENTRYTYPE" not in self.data:
            container_title = self.data.get("journal", self.data.get("booktitle", "NA"))
        else:
            if "article" == self.data["ENTRYTYPE"]:
                container_title = self.data.get("journal", "NA")
            if "inproceedings" == self.data["ENTRYTYPE"]:
                container_title = self.data.get("booktitle", "NA")
            if "book" == self.data["ENTRYTYPE"]:
                container_title = self.data.get("title", "NA")
            if "inbook" == self.data["ENTRYTYPE"]:
                container_title = self.data.get("booktitle", "NA")
        return container_title

    def create_colrev_id(
        self, *, alsoKnownAsRecord: dict = {}, assume_complete=False
    ) -> str:
        """Returns the colrev_id of the Record.
        If a alsoKnownAsRecord is provided, it returns the colrev_id of the
        alsoKnownAsRecord (using the Record as the reference to decide whether
        required fields are missing)"""

        def format_author_field(input_string: str) -> str:
            input_string = input_string.replace("\n", " ").replace("'", "")
            names = input_string.replace("; ", " and ").split(" and ")
            author_list = []
            for name in names:

                if "," == name.rstrip()[-1:]:
                    # if last-names only (eg, "Webster, and Watson, ")
                    if len(name[:-2]) > 1:
                        author_list.append(str(name.rstrip()[:-1]))
                else:
                    parsed_name = HumanName(name)
                    # Note: do not set parsed_name.string_format as a global constant
                    # to preserve consistent creation of identifiers
                    parsed_name.string_format = "{last} "
                    if len(parsed_name.middle) > 0:
                        parsed_name.middle = parsed_name.middle[:1]
                    if len(parsed_name.first) > 0:
                        parsed_name.first = parsed_name.first[:1]
                    if len(parsed_name.nickname) > 0:
                        parsed_name.nickname = ""

                    if len(str(parsed_name)) > 1:
                        author_list.append(str(parsed_name))

            return " ".join(author_list)

        def get_container_title(*, record: dict) -> str:
            # Note: custom get_container_title for the colrev_id

            # school as the container title for theses
            if record["ENTRYTYPE"] in ["phdthesis", "masterthesis"]:
                container_title = record["school"]
            # for technical reports
            elif "techreport" == record["ENTRYTYPE"]:
                container_title = record["institution"]
            elif "inproceedings" == record["ENTRYTYPE"]:
                container_title = record["booktitle"]
            elif "article" == record["ENTRYTYPE"]:
                container_title = record["journal"]
            else:
                raise KeyError
            # TODO : TBD how to deal with the other ENTRYTYPES
            # if "series" in record:
            #     container_title += record["series"]
            # if "url" in record and not any(
            #     x in record for x in ["journal", "series", "booktitle"]
            # ):
            #     container_title += record["url"]

            return container_title

        def robust_append(*, input_string: str, to_append: str) -> str:
            input_string = str(input_string)
            to_append = str(to_append).replace("\n", " ").replace("/", " ")
            to_append = to_append.rstrip().lstrip().replace("–", " ")
            to_append = to_append.replace("emph{", "")
            to_append = to_append.replace("&amp;", "and")
            to_append = to_append.replace(" & ", " and ")
            to_append = Record.remove_accents(input_str=to_append)
            to_append = re.sub("[^0-9a-zA-Z -]+", "", to_append)
            to_append = re.sub(r"\s+", "-", to_append)
            to_append = re.sub(r"-+", "-", to_append)
            to_append = to_append.lower()
            if len(to_append) > 1:
                to_append = to_append.rstrip("-")
            input_string = input_string + "|" + to_append
            return input_string

        if not assume_complete:
            if self.data["colrev_status"] in [
                RecordState.md_imported,
                RecordState.md_needs_manual_preparation,
            ]:
                if len(alsoKnownAsRecord) != 0:
                    raise NotEnoughDataToIdentifyException(
                        "cannot determine field requirements "
                        "(e.g., volume/number for journal articles)"
                    )

        if len(alsoKnownAsRecord) == 0:
            record = self.data
        else:
            # TODO : need a better design for selecting required fields
            required_fields_keys = [
                k
                for k in self.data.keys()
                if k
                in [
                    "author",
                    "title",
                    "year",
                    "journal",
                    "volume",
                    "number",
                    "pages",
                    "booktitle",
                    # chapter, school, ...
                ]
            ]

            missing_field_keys = [
                f for f in required_fields_keys if f not in alsoKnownAsRecord
            ]
            if len(missing_field_keys) > 0:
                raise NotEnoughDataToIdentifyException(",".join(missing_field_keys))
            record = alsoKnownAsRecord

        try:

            # Including the version of the identifier prevents cases
            # in which almost all identifiers are identical
            # (and very few identifiers change)
            # when updating the identifier function function
            # (this may look like an anomaly and be hard to identify)
            srep = "colrev_id1:"
            if "article" == record["ENTRYTYPE"].lower():
                srep = robust_append(input_string=srep, to_append="a")
            elif "inproceedings" == record["ENTRYTYPE"].lower():
                srep = robust_append(input_string=srep, to_append="p")
            else:
                srep = robust_append(
                    input_string=srep, to_append=record["ENTRYTYPE"].lower()
                )
            srep = robust_append(
                input_string=srep, to_append=get_container_title(record=record)
            )
            if "article" == record["ENTRYTYPE"]:
                # Note: volume/number may not be required.
                # TODO : how do we make sure that colrev_ids are not generated when
                # volume/number are required?
                srep = robust_append(
                    input_string=srep, to_append=record.get("volume", "-")
                )
                srep = robust_append(
                    input_string=srep, to_append=record.get("number", "-")
                )
            srep = robust_append(input_string=srep, to_append=record["year"])
            author = format_author_field(record["author"])
            if "" == author.replace("-", ""):
                raise NotEnoughDataToIdentifyException("author field format error")
            srep = robust_append(input_string=srep, to_append=author)
            srep = robust_append(input_string=srep, to_append=record["title"])

            # Note : pages not needed.
            # pages = record.get("pages", "")
            # srep = robust_append(srep, pages)
        except KeyError as e:
            raise NotEnoughDataToIdentifyException(str(e))

        srep = srep.replace(";", "")  # ";" is the separator in colrev_id list

        return srep

    def prescreen_exclude(self, *, reason, print_warning: bool = False) -> None:
        self.data["colrev_status"] = RecordState.rev_prescreen_excluded

        if (
            "retracted" not in self.data.get("prescreen_exclusion", "")
            and "retracted" == reason
            and print_warning
        ):
            red = "\033[91m"
            end = "\033[0m"
            print(
                f"\n{red}Paper retracted and prescreen "
                f"excluded: {self.data['ID']}{end}\n"
            )

        self.data["prescreen_exclusion"] = reason

        # TODO : warn/remove from data extraction/synthesis?

        to_drop = []
        for k, v in self.data.items():
            if "UNKNOWN" == v:
                to_drop.append(k)
        for k in to_drop:
            self.remove_field(key=k)

        return

    def extract_text_by_page(self, *, pages: list = None, project_path) -> str:
        from pdfminer.pdfpage import PDFPage
        from pdfminer.pdfinterp import PDFResourceManager
        from pdfminer.converter import TextConverter
        import io
        from pdfminer.pdfinterp import PDFPageInterpreter

        text_list: list = []
        pdf_path = project_path / Path(self.data["file"])
        with open(pdf_path, "rb") as fh:
            try:
                for page in PDFPage.get_pages(
                    fh,
                    pagenos=pages,  # note: maybe skip potential cover pages?
                    caching=True,
                    check_extractable=True,
                ):
                    resource_manager = PDFResourceManager()
                    fake_file_handle = io.StringIO()
                    converter = TextConverter(resource_manager, fake_file_handle)
                    page_interpreter = PDFPageInterpreter(resource_manager, converter)
                    page_interpreter.process_page(page)

                    text = fake_file_handle.getvalue()
                    text_list += text

                    # close open handles
                    converter.close()
                    fake_file_handle.close()
            except TypeError:
                pass
        return "".join(text_list)

    def get_pages_in_pdf(self, *, project_path: Path):
        from pdfminer.pdfparser import PDFParser
        from pdfminer.pdfinterp import resolve1
        from pdfminer.pdfdocument import PDFDocument

        pdf_path = project_path / Path(self.data["file"])
        with open(pdf_path, "rb") as file:
            parser = PDFParser(file)
            document = PDFDocument(parser)
            pages_in_file = resolve1(document.catalog["Pages"])["Count"]
        self.data["pages_in_file"] = pages_in_file
        return

    def get_text_from_pdf(self, *, project_path: Path):
        from pdfminer.pdfparser import PDFSyntaxError
        from pdfminer.pdfdocument import PDFTextExtractionNotAllowed

        self.data["text_from_pdf"] = ""
        try:
            self.get_pages_in_pdf(project_path=project_path)
            text = self.extract_text_by_page(pages=[0, 1, 2], project_path=project_path)
            self.data["text_from_pdf"] = text

        except PDFSyntaxError:
            # msg = (
            #     f'{record["file"]}'.ljust(PAD, " ")
            #     + "PDF reader error: check whether is a pdf"
            # )
            # self.REVIEW_MANAGER.report_logger.error(msg)
            # self.REVIEW_MANAGER.logger.error(msg)
            self.add_data_provenance_note(key="file", note="pdf_reader_error")
            self.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)
            pass
        except PDFTextExtractionNotAllowed:
            # msg = f'{record["file"]}'.ljust(PAD, " ") + "PDF reader error: protection"
            # self.REVIEW_MANAGER.report_logger.error(msg)
            # self.REVIEW_MANAGER.logger.error(msg)
            self.add_data_provenance_note(key="file", note="pdf_protected")
            self.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)
            pass
        except PDFSyntaxError:
            # msg = f'{record["file"]}'.ljust(PAD, " ") + "PDFSyntaxError"
            # self.REVIEW_MANAGER.report_logger.error(msg)
            # self.REVIEW_MANAGER.logger.error(msg)
            self.add_data_provenance_note(key="file", note="pdf_syntax_error")
            self.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)
            pass
        return

    def extract_pages(
        self, *, pages: list, type: str, project_path: Path, save_to_path: Path
    ) -> None:
        from PyPDF2 import PdfFileReader
        from PyPDF2 import PdfFileWriter

        pdf_path = project_path / Path(self.data["file"])
        pdfReader = PdfFileReader(pdf_path, strict=False)
        writer = PdfFileWriter()
        for i in range(0, pdfReader.getNumPages()):
            if i in pages:
                continue
            writer.addPage(pdfReader.getPage(i))
        with open(pdf_path, "wb") as outfile:
            writer.write(outfile)

        if save_to_path:
            writer_cp = PdfFileWriter()
            writer_cp.addPage(pdfReader.getPage(0))
            filepath = Path(pdf_path)
            with open(save_to_path / filepath.name, "wb") as outfile:
                writer_cp.write(outfile)
        return

    def get_colrev_pdf_id(self, *, path: Path) -> str:
        from pdf2image import convert_from_path
        import imagehash

        cpid1 = "cpid1:" + str(
            imagehash.average_hash(
                convert_from_path(path, first_page=1, last_page=1)[0],
                hash_size=32,
            )
        )
        return cpid1

    def import_provenance(self, *, source_identifier: str) -> None:
        def percent_upper_chars(input_string: str) -> float:
            return sum(map(str.isupper, input_string)) / len(input_string)

        # Initialize colrev_masterdata_provenance
        colrev_masterdata_provenance = {}
        colrev_data_provenance = {}
        marker = re.search(r"\{\{(.*)\}\}", source_identifier)
        source_identifier_string = source_identifier
        if marker:
            marker_string = marker.group(0)
            key = marker_string[2:-2]

            try:
                marker_replacement = self.data[key]
                source_identifier_string = source_identifier.replace(
                    marker_string, marker_replacement
                )
            except KeyError as e:
                print(e)
                pass

        for key in self.data.keys():
            if key in Record.identifying_field_keys:
                if key not in colrev_masterdata_provenance:
                    colrev_masterdata_provenance[key] = {
                        "source": source_identifier_string,
                        "note": "",
                    }
            elif key not in Record.provenance_keys and key not in [
                "colrev_source_identifier",
                "ID",
                "ENTRYTYPE",
                "source_url",
            ]:
                colrev_data_provenance[key] = {
                    "source": source_identifier_string,
                    "note": "",
                }

        self.data["colrev_data_provenance"] = colrev_data_provenance
        self.data["colrev_masterdata_provenance"] = colrev_masterdata_provenance

        if not self.masterdata_is_curated():
            if self.data["ENTRYTYPE"] in self.record_field_requirements:
                required_fields = self.record_field_requirements[self.data["ENTRYTYPE"]]
                for required_field in required_fields:
                    if required_field in self.data:
                        if percent_upper_chars(self.data[required_field]) > 0.8:
                            self.add_masterdata_provenance_note(
                                key=required_field, note="mostly upper case"
                            )
                    else:
                        # self.data[required_field] = "UNKNOWN"
                        self.update_field(
                            key=required_field,
                            value="UNKNOWN",
                            source="LOADER.import_provenance",
                            comment="missing",
                        )
            # TODO : how to handle cases where we do not have field_requirements?

        if self.data["ENTRYTYPE"] in self.record_field_inconsistencies:
            inconsistent_fields = self.record_field_inconsistencies[
                self.data["ENTRYTYPE"]
            ]
            for inconsistent_field in inconsistent_fields:
                if inconsistent_field in self.data:
                    inconsistency_note = (
                        f"inconsistent with entrytype ({self.data['ENTRYTYPE']})"
                    )
                    self.add_masterdata_provenance_note(
                        key=inconsistent_field, note=inconsistency_note
                    )

        incomplete_fields = self.get_incomplete_fields()
        for incomplete_field in incomplete_fields:
            self.add_masterdata_provenance_note(key=incomplete_field, note="incomplete")

        defect_fields = self.get_quality_defects()
        if defect_fields:
            for defect_field in defect_fields:
                self.add_masterdata_provenance_note(
                    key=defect_field, note="quality_defect"
                )

        return


class PrepRecord(Record):
    # Note: add methods that are called multiple times
    # TODO : or includ all functionality?
    # distinguish:
    # 1. independent processing operation (format, ...)
    # 2. processing operation using curated data
    # 3. processing operation using external, non-curated data
    #  (-> merge/fuse_best_field)

    def __init__(self, *, data: dict):
        super().__init__(data=data)

    @classmethod
    def format_author_field(cls, *, input_string: str) -> str:
        def mostly_upper_case(input_string: str) -> bool:
            if not re.match(r"[a-zA-Z]+", input_string):
                return False
            input_string = input_string.replace(".", "").replace(",", "")
            words = input_string.split()
            return sum(word.isupper() for word in words) / len(words) > 0.8

        input_string = input_string.replace("\n", " ")
        # DBLP appends identifiers to non-unique authors
        input_string = str(re.sub(r"[0-9]{4}", "", input_string))

        names = input_string.split(" and ")
        author_string = ""
        for name in names:
            # Note: https://github.com/derek73/python-nameparser
            # is very effective (maybe not perfect)

            parsed_name = HumanName(name)
            if mostly_upper_case(input_string.replace(" and ", "").replace("Jr", "")):
                parsed_name.capitalize(force=True)

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
    def get_retrieval_similarity(
        cls, *, RECORD_ORIGINAL: Record, RETRIEVED_RECORD_ORIGINAL: Record
    ) -> float:
        def format_authors_string_for_comparison(REC_IN):
            if "author" not in REC_IN.data:
                return
            authors = REC_IN.data["author"]
            authors = str(authors).lower()
            authors_string = ""
            authors = Record.remove_accents(input_str=authors)

            # abbreviate first names
            # "Webster, Jane" -> "Webster, J"
            # also remove all special characters and do not include separators (and)
            for author in authors.split(" and "):
                if "," in author:
                    last_names = [
                        word[0]
                        for word in author.split(",")[1].split(" ")
                        if len(word) > 0
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
            REC_IN.data["author"] = authors_string
            return

        RECORD = PrepRecord(data=deepcopy(RECORD_ORIGINAL.get_data()))
        RETRIEVED_RECORD = PrepRecord(
            data=deepcopy(RETRIEVED_RECORD_ORIGINAL.get_data())
        )
        if RECORD.container_is_abbreviated():
            min_len = RECORD.get_abbrev_container_min_len()
            RETRIEVED_RECORD.abbreviate_container(min_len=min_len)
            RECORD.abbreviate_container(min_len=min_len)
        if RETRIEVED_RECORD.container_is_abbreviated():
            min_len = RETRIEVED_RECORD.get_abbrev_container_min_len()
            RECORD.abbreviate_container(min_len=min_len)
            RETRIEVED_RECORD.abbreviate_container(min_len=min_len)

        if "title" in RECORD.data:
            RECORD.data["title"] = RECORD.data["title"][:90]
        if "title" in RETRIEVED_RECORD.data:
            RETRIEVED_RECORD.data["title"] = RETRIEVED_RECORD.data["title"][:90]

        if "author" in RECORD.data:
            format_authors_string_for_comparison(RECORD)
            RECORD.data["author"] = RECORD.data["author"][:45]
        if "author" in RETRIEVED_RECORD.data:
            format_authors_string_for_comparison(RETRIEVED_RECORD)
            RETRIEVED_RECORD.data["author"] = RETRIEVED_RECORD.data["author"][:45]
        if not ("volume" in RECORD.data and "volume" in RETRIEVED_RECORD.data):
            RECORD.data["volume"] = "nan"
            RETRIEVED_RECORD.data["volume"] = "nan"
        if not ("number" in RECORD.data and "number" in RETRIEVED_RECORD.data):
            RECORD.data["number"] = "nan"
            RETRIEVED_RECORD.data["number"] = "nan"
        if not ("pages" in RECORD.data and "pages" in RETRIEVED_RECORD.data):
            RECORD.data["pages"] = "nan"
            RETRIEVED_RECORD.data["pages"] = "nan"
        # Sometimes, the number of pages is provided (not the range)
        elif not (
            "--" in RECORD.data["pages"] and "--" in RETRIEVED_RECORD.data["pages"]
        ):
            RECORD.data["pages"] = "nan"
            RETRIEVED_RECORD.data["pages"] = "nan"

        if "year" in RECORD.data and "year" in RETRIEVED_RECORD.data:
            if "forthcoming" == RECORD.data["year"]:
                RECORD.data["year"] = RETRIEVED_RECORD.data["year"]
            if "forthcoming" == RETRIEVED_RECORD.data["year"]:
                RETRIEVED_RECORD.data["year"] = RECORD.data["year"]

        if "editorial" in RECORD.data.get("title", "NA").lower():
            if not all(x in RECORD.data for x in ["volume", "number"]):
                return 0
        # print(RECORD)
        # print(RETRIEVED_RECORD)
        similarity = Record.get_record_similarity(
            RECORD_A=RECORD, RECORD_B=RETRIEVED_RECORD
        )

        return similarity

    def format_if_mostly_upper(self, *, key: str, case: str = "capitalize") -> None:
        def percent_upper_chars(input_string: str) -> float:
            return sum(map(str.isupper, input_string)) / len(input_string)

        if not re.match(r"[a-zA-Z]+", self.data[key]):
            return

        self.data[key] = self.data[key].replace("\n", " ")

        if percent_upper_chars(self.data[key]) > 0.8:
            if "capitalize" == case:
                self.data[key] = self.data[key].capitalize()
            if "title" == case:
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
                return
        return

    def container_is_abbreviated(self) -> bool:
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

    def abbreviate_container(self, *, min_len: int):
        if "journal" in self.data:
            self.data["journal"] = " ".join(
                [x[:min_len] for x in self.data["journal"].split(" ")]
            )
        return

    def get_abbrev_container_min_len(self) -> int:
        min_len = -1
        if "journal" in self.data:
            min_len = min(
                len(x) for x in self.data["journal"].replace(".", "").split(" ")
            )
        if "booktitle" in self.data:
            min_len = min(
                len(x) for x in self.data["booktitle"].replace(".", "").split(" ")
            )
        return min_len

    def check_potential_retracts(self) -> None:
        # Note : we retrieved metadata in get_masterdata_from_crossref()
        if self.data.get("crossmark", "") == "True":
            self.data["colrev_status"] = RecordState.md_needs_manual_preparation
            if "note" in self.data:
                self.data["note"] += ", crossmark_restriction_potential_retract"
            else:
                self.data["note"] = "crossmark_restriction_potential_retract"
        if self.data.get("warning", "") == "Withdrawn (according to DBLP)":
            self.data["colrev_status"] = RecordState.md_needs_manual_preparation
            if "note" in self.data:
                self.data["note"] += ", withdrawn (according to DBLP)"
            else:
                self.data["note"] = "withdrawn (according to DBLP)"
        return

    def unify_pages_field(self) -> None:
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
        return

    def drop_fields(self, PREPARATION) -> None:
        from colrev_core.environment import LocalIndex

        for key in list(self.data.keys()):
            if key not in PREPARATION.fields_to_keep:
                self.remove_field(key=key)
                PREPARATION.REVIEW_MANAGER.report_logger.info(f"Dropped {key} field")

            # for key in list(RECORD.data.keys()):
            #     if key in PREPARATION.fields_to_keep:
            #         continue
            elif self.data[key] in ["", "NA"]:
                self.remove_field(key=key)

        if self.data.get("publisher", "") in ["researchgate.net"]:
            self.remove_field(key="publisher")

        if "volume" in self.data.keys() and "number" in self.data.keys():
            # Note : cannot use LOCAL_INDEX as an attribute of PrepProcess
            # because it creates problems with multiprocessing
            LOCAL_INDEX = LocalIndex()

            fields_to_remove = LOCAL_INDEX.get_fields_to_remove(record=self.get_data())
            for field_to_remove in fields_to_remove:
                if field_to_remove in self.data:
                    # TODO : maybe use set_masterdata_complete()?
                    self.remove_field(
                        key=field_to_remove, not_missing_note=True, source="local_index"
                    )
                    # TODO : we need to keep track of the information
                    # that a certain field is not required
        return

    def preparation_save_condition(self) -> bool:

        if self.data["colrev_status"] in [
            RecordState.rev_prescreen_excluded,
            RecordState.md_prepared,
        ]:
            return True
        if "disagreement with " in self.data.get("colrev_masterdata_provenance", ""):
            return True

        return False

    def preparation_break_condition(self) -> bool:
        if "disagreement with " in self.data.get("colrev_masterdata_provenance", ""):
            return True

        if self.data["colrev_status"] in [
            RecordState.rev_prescreen_excluded,
        ]:
            return True
        return False

    def status_to_prepare(self) -> bool:
        return self.data["colrev_status"] in [
            RecordState.md_needs_manual_preparation,
            RecordState.md_imported,
        ]

    def update_metadata_status(self, *, REVIEW_MANAGER):

        self.check_potential_retracts()

        if "crossmark" in self.data:
            return
        if self.masterdata_is_curated():
            self.set_status(target_state=RecordState.md_prepared)
            return

        REVIEW_MANAGER.logger.debug(
            f'is_incomplete({self.data["ID"]}): {not self.masterdata_is_complete()}'
        )

        REVIEW_MANAGER.logger.debug(
            f'has_inconsistent_fields({self.data["ID"]}): '
            f"{self.has_inconsistent_fields()}"
        )
        REVIEW_MANAGER.logger.debug(
            f'has_incomplete_fields({self.data["ID"]}): '
            f"{self.has_incomplete_fields()}"
        )

        if (
            not self.masterdata_is_complete()
            or self.has_incomplete_fields()
            or self.has_inconsistent_fields()
        ):
            self.set_status(target_state=RecordState.md_needs_manual_preparation)
        else:
            self.set_status(target_state=RecordState.md_prepared)

        return

    def update_masterdata_provenance(
        self, *, UNPREPARED_RECORD, REVIEW_MANAGER
    ) -> None:

        if not self.masterdata_is_curated():

            missing_fields = self.missing_fields()
            not_missing_fields = []
            if missing_fields:
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
                missing_fields.remove(missing_field)

            if not missing_fields:
                self.set_masterdata_complete()

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

        change = 1 - Record.get_record_similarity(
            RECORD_A=self, RECORD_B=UNPREPARED_RECORD
        )
        if change > 0.1:
            REVIEW_MANAGER.report_logger.info(
                f' {self.data["ID"]}' + f"Change score: {round(change, 2)}"
            )

        return


class PrescreenRecord(Record):
    def __init__(self, *, data: dict):
        super().__init__(data=data)

    def __str__(self) -> str:

        self.identifying_keys_order = ["ID", "ENTRYTYPE"] + [
            k for k in self.identifying_field_keys if k in self.data
        ]
        complementary_keys_order = [
            k for k, v in self.data.items() if k not in self.identifying_keys_order
        ]

        ik_sorted = {
            k: v for k, v in self.data.items() if k in self.identifying_keys_order
        }
        ck_sorted = {
            k: v
            for k, v in self.data.items()
            if k in complementary_keys_order and k not in self.provenance_keys
        }
        ret_str = (
            self.pp.pformat(ik_sorted)[:-1] + "\n" + self.pp.pformat(ck_sorted)[1:]
        )

        return ret_str


class ScreenRecord(PrescreenRecord):

    # Note : currently still identical with PrescreenRecord
    def __init__(self, data: dict):
        super().__init__(data=data)


class RecordState(Enum):
    # without the md_retrieved state, we could not display the load transition
    md_retrieved = auto()
    """Record is retrieved and stored in the ./search directory"""
    md_imported = auto()
    """Record is imported into the MAIN_REFERENCES"""
    md_needs_manual_preparation = auto()
    """Record requires manual preparation
    (colrev_masterdata_provenance provides hints)"""
    md_prepared = auto()
    """Record is prepared (no missing or incomplete fields, inconsistencies checked)"""
    md_processed = auto()
    """Record has been checked for duplicate associations
    with any record in RecordState md_processed or later"""
    rev_prescreen_excluded = auto()
    """Record was excluded in the prescreen (based on titles/abstracts)"""
    rev_prescreen_included = auto()
    """Record was included in the prescreen (based on titles/abstracts)"""
    pdf_needs_manual_retrieval = auto()
    """Record marked for manual PDF retrieval"""
    pdf_imported = auto()
    """PDF imported and marked for preparation"""
    pdf_not_available = auto()
    """PDF is not available"""
    pdf_needs_manual_preparation = auto()
    """PDF marked for manual preparation"""
    pdf_prepared = auto()
    """PDF prepared"""
    rev_excluded = auto()
    """Record excluded in screen (full-text)"""
    rev_included = auto()
    """Record included in screen (full-text)"""
    rev_synthesized = auto()
    """Record synthesized"""
    # Note : TBD: rev_coded

    def __str__(self):
        return f"{self.name}"


class NotEnoughDataToIdentifyException(Exception):
    def __init__(self, msg: str = None):
        self.message = msg
        super().__init__(self.message)


if __name__ == "__main__":
    pass
