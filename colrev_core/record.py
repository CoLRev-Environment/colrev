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
                        self.data["colrev_id"] = (
                            self.data["colrev_id"] + ";" + colrev_id
                        )

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

    def update_field(self, *, key: str, value, source: str, comment: str = "") -> None:
        if key in self.data:
            if self.data[key] == value:
                return
        self.data[key] = value
        if key in self.identifying_field_keys:
            self.add_masterdata_provenance(key=key, source=source, hint=comment)
        else:
            self.add_data_provenance(key=key, source=source, hint=comment)
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

    def change_ENTRYTYPE(self, *, ENTRYTYPE, NEW_ENTRYTYPE):

        # TODO : reapply field requirements

        return

    def remove_field(self, *, key: str) -> None:
        if key in self.data:
            del self.data[key]
            if key in self.identifying_field_keys:
                if key in self.data["colrev_masterdata_provenance"]:
                    del self.data["colrev_masterdata_provenance"][key]
            else:
                if key in self.data["colrev_data_provenance"]:
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
                if "missing" in note:
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

    def reset_pdf_provenance_hints(self) -> None:
        if "colrev_data_provenance" not in self.data:
            self.add_data_provenance_hint(key="file", hint="")
        if "file" in self.data["colrev_data_provenance"]:
            # TODO : check note and remove hints selectively
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
                    pass
                else:
                    self.update_field(key=key, value=str(val), source=source)

        return

    def fuse_best_field(self, *, MERGING_RECORD, key, val, source) -> None:
        # Note : the assumption is that we need masterdata_provenance hints
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
                if "quality_defect" in record_a_prov["author"].get("hint", ""):
                    return MERGING_RECORD.data["author"]
                # Prefer complete version
                if "incomplete" in record_a_prov["author"].get("hint", ""):
                    return MERGING_RECORD.data["author"]
            elif "author" in record_a_prov and "author" in merging_record_a_prov:
                # Prefer non-defect version
                if "quality_defect" in record_a_prov["author"].get(
                    "hint", ""
                ) and "quality_defect" not in merging_record_a_prov["author"].get(
                    "hint", ""
                ):
                    return MERGING_RECORD.data["author"]

                # Prefer complete version
                if "incomplete" in record_a_prov["author"].get(
                    "hint", ""
                ) and "incomplete" not in merging_record_a_prov["author"].get(
                    "hint", ""
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

    def add_masterdata_provenance_hint(self, *, key, hint):
        if "colrev_masterdata_provenance" not in self.data:
            self.data["colrev_masterdata_provenance"] = {}
        if key in self.data["colrev_masterdata_provenance"]:
            if hint not in self.data["colrev_masterdata_provenance"][key]["note"]:
                self.data["colrev_masterdata_provenance"][key]["note"] += f",{hint}"
        else:
            self.data["colrev_masterdata_provenance"][key] = {
                "source": "ORIGINAL",
                "note": hint,
            }
        return

    def add_data_provenance_hint(self, *, key, hint):
        if "colrev_data_provenance" not in self.data:
            self.data["colrev_data_provenance"] = {}
        if key in self.data["colrev_data_provenance"]:
            if hint not in self.data["colrev_data_provenance"][key]["note"]:
                self.data["colrev_data_provenance"][key]["note"] += f",{hint}"
        else:
            print(hint)
            self.data["colrev_data_provenance"][key] = {
                "source": "ORIGINAL",
                "note": hint,
            }
        return

    def add_masterdata_provenance(self, *, key, source, hint: str = ""):
        md_p_dict = self.data.get("colrev_masterdata_provenance", {})

        if key in md_p_dict:
            if "" != hint:
                md_p_dict[key]["note"] += f",{hint}"
            else:
                md_p_dict[key]["note"] = ""
            md_p_dict[key]["source"] = source
        else:
            md_p_dict[key] = {"source": source, "note": f"{hint}"}
        return

    def add_provenance_all(self, *, source):
        md_p_dict = self.data.get("colrev_masterdata_provenance", {})
        d_p_dict = self.data.get("colrev_data_provenance", {})
        for key in self.data.keys():
            if key in self.identifying_field_keys:
                md_p_dict[key] = {"source": source, "note": ""}
            else:
                d_p_dict[key] = {"source": source, "note": ""}
        return

    def add_data_provenance(self, *, key, source, hint: str = ""):
        md_p_dict = self.data.get("colrev_data_provenance", {})
        if key in md_p_dict:
            if "" != hint:
                md_p_dict[key]["note"] += f",{hint}"
            else:
                md_p_dict[key]["note"] = ""
            md_p_dict[key]["source"] = source
        else:
            md_p_dict[key] = {"source": source, "note": f"{hint}"}
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
                    self.add_masterdata_provenance(key=key, source=source_info, hint="")
            else:
                self.add_data_provenance(key=key, source=source_info, hint="")

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
                # Note : patterns like "I N T R O D U C T I O N"
                # that may result from grobid imports
                if re.search(r"[A-Z] [A-Z] [A-Z] [A-Z]", self.data[key]):
                    defect_field_keys.append(key)
                if len(self.data[key]) < 5:
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

    def prescreen_exclude(self, *, reason) -> None:
        self.data["colrev_status"] = RecordState.rev_prescreen_excluded
        self.data["prescreen_exclusion"] = reason

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
            self.add_data_provenance_hint(key="file", hint="pdf_reader_error")
            self.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)
            pass
        except PDFTextExtractionNotAllowed:
            # msg = f'{record["file"]}'.ljust(PAD, " ") + "PDF reader error: protection"
            # self.REVIEW_MANAGER.report_logger.error(msg)
            # self.REVIEW_MANAGER.logger.error(msg)
            self.add_data_provenance_hint(key="file", hint="pdf_protected")
            self.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)
            pass
        except PDFSyntaxError:
            # msg = f'{record["file"]}'.ljust(PAD, " ") + "PDFSyntaxError"
            # self.REVIEW_MANAGER.report_logger.error(msg)
            # self.REVIEW_MANAGER.logger.error(msg)
            self.add_data_provenance_hint(key="file", hint="pdf_syntax_error")
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
