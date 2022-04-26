#! /usr/bin/env python
import pprint
import re
import typing
import unicodedata
from enum import auto
from enum import Enum

import pandas as pd
from nameparser import HumanName
from thefuzz import fuzz


class Record:

    identifying_fields = [
        "title",
        "author",
        "year",
        "journal",
        "booktitle",
        "volume",
        "number",
        "pages",
    ]
    """Identifying fields considered for masterdata provenance"""

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
        "colrev_masterdata",
        "colrev_masterdata_provenance",
        "colrev_origin",
        "colrev_status",
        "colrev_id",
        "colrev_data_provenance",
        "colrev_pdf_id",
        "MOVED_DUPE",
    ]

    pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)

    def __init__(self, data: dict):
        self.data = data
        """Dictionary containing the record data"""
        # Note : avoid parsing upon Record instantiation as much as possible
        # to maintain high performance and ensure pickle-abiligy (in multiprocessing)

    def __repr__(self) -> str:
        return self.pp.pformat(self.data)

    def __str__(self) -> str:

        self.identifying_keys_order = ["ID", "ENTRYTYPE"] + [
            k for k in self.identifying_fields if k in self.data
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

    def get_data(self) -> dict:
        return self.data

    def masterdata_is_curated(self) -> bool:
        return "CURATED" in self.data.get("colrev_masterdata", "")

    def set_status(self, target_state) -> None:
        from colrev_core.record import RecordState

        if RecordState.md_prepared == target_state:
            if self.masterdata_is_complete():
                try:
                    colrev_id = self.create_colrev_id()
                    if "colrev_id" not in self.data:
                        self.data["colrev_id"] = colrev_id
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

        # Note : to cover legacy fieldname:
        if "origin" in self.data:
            origins = self.data["origin"].split(";")

        return origins

    def shares_origins(self, other_record) -> bool:
        return any(x in other_record.get_origins() for x in self.get_origins())

    def get_source_repo(self) -> str:
        # priority: return source_link first (then check for source_path)
        if "source_link" in self.data:
            if "http" in self.data["source_link"]:
                return self.data["source_link"]
        if "source_path" in self.data:
            return self.data["source_path"]
        return "NO_SOURCE_INFO"

    def get_field(self, field_key: str, default=None):
        if default is not None:
            try:
                ret = self.data[field_key]
                return ret
            except KeyError:
                pass
                return default
        else:
            return self.data[field_key]

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

    def update_field(self, field: str, value, source: str, comment: str = "") -> None:
        self.data[field] = value
        if field in self.identifying_fields:
            self.add_masterdata_provenance(field, source, comment)
        else:
            self.add_data_provenance(field, source, comment)
        return

    def add_colrev_ids(self, records: typing.List[dict]) -> None:
        if "colrev_id" in self.data:
            if isinstance(self.data["colrev_id"], list):
                self.data["colrev_id"] = ";".join(self.data["colrev_id"])
        for r in records:
            try:
                colrev_id = self.create_colrev_id(alsoKnownAsRecord=r)
                if "colrev_id" not in self.data:
                    self.data["colrev_id"] = colrev_id
                elif colrev_id not in self.data["colrev_id"]:
                    cids = self.data["colrev_id"].split(";")
                    if colrev_id not in cids:
                        self.data["colrev_id"] = (
                            self.data["colrev_id"] + ";" + colrev_id
                        )
            except NotEnoughDataToIdentifyException:
                pass
        return

    def masterdata_is_complete(self) -> bool:
        if self.masterdata_is_curated():
            return True
        if not any(
            v == "UNKNOWN" for k, v in self.data.items() if k in self.identifying_fields
        ):
            return True
        return False

    def set_masterdata_complete(self) -> None:
        md_p_dict = self.load_masterdata_provenance()

        for identifying_field in self.identifying_fields:
            if "UNKNOWN" == self.data.get(identifying_field, "NA"):
                del self.data[identifying_field]
            if identifying_field in md_p_dict:
                note = md_p_dict[identifying_field]["note"]
                if "missing" in note:
                    md_p_dict[identifying_field]["note"] = note.replace("missing", "")
                    self.set_masterdata_provenance(md_p_dict)
        return

    def set_masterdata_consistent(self) -> None:
        md_p_dict = self.load_masterdata_provenance()
        for identifying_field in self.identifying_fields:
            if identifying_field in md_p_dict:
                note = md_p_dict[identifying_field]["note"]
                if "inconsistent with ENTRYTYPE" in note:
                    md_p_dict[identifying_field]["note"] = note.replace(
                        "inconsistent with ENTRYTYPE", ""
                    )
                    self.set_masterdata_provenance(md_p_dict)
        return

    def set_fields_complete(self) -> None:
        md_p_dict = self.load_masterdata_provenance()
        for identifying_field in self.identifying_fields:
            if identifying_field in md_p_dict:
                note = md_p_dict[identifying_field]["note"]
                if "incomplete" in note:
                    md_p_dict[identifying_field]["note"] = note.replace(
                        "incomplete", ""
                    )
                    self.set_masterdata_provenance(md_p_dict)
        return

    def reset_pdf_provenance_hints(self) -> None:
        d_p_dict = self.load_data_provenance()
        if "file" in d_p_dict:
            # TODO : check note and remove hints selectively
            # note = d_p_dict['file']['note']
            d_p_dict["file"]["note"] = ""
            self.set_data_provenance(d_p_dict)
        return

    def missing_fields(self) -> list:
        missing_fields = []
        if self.data["ENTRYTYPE"] in Record.record_field_requirements.keys():
            reqs = Record.record_field_requirements[self.data["ENTRYTYPE"]]
            missing_fields = [
                x
                for x in reqs
                if x not in self.data.keys()
                or "" == self.data[x]
                or "UNKNOWN" == self.data[x]
            ]
        else:
            missing_fields = ["no field requirements defined"]
        return missing_fields

    def get_inconsistencies(self) -> list:
        inconsistent_fields = []
        if self.data["ENTRYTYPE"] in Record.record_field_inconsistencies.keys():
            incons_fields = Record.record_field_inconsistencies[self.data["ENTRYTYPE"]]
            inconsistent_fields = [x for x in incons_fields if x in self.data]
        # Note: a thesis should be single-authored
        if "thesis" in self.data["ENTRYTYPE"] and " and " in self.data.get(
            "author", ""
        ):
            inconsistent_fields.append("author")
        return inconsistent_fields

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

    def merge(self, MERGING_RECORD, default_source: str) -> None:
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
        #     for k in self.identifying_fields:
        #         if k in MERGING_RECORD.data and k not in self.data:
        #             self.data[k] = MERGING_RECORD.data[k]

        # if "pages" in MERGING_RECORD.data and "pages" not in self.data:
        #     self.data["pages"] = MERGING_RECORD.data["pages"]

        # Note : no need to check "not self.masterdata_is_curated()":
        # this should enable updates of curated metadata
        if MERGING_RECORD.masterdata_is_curated() and not self.masterdata_is_curated():
            self.data["colrev_masterdata"] = MERGING_RECORD.data["colrev_masterdata"]
            if "colrev_masterdata_provenance" in self.data:
                del self.data["colrev_masterdata_provenance"]

            for k in list(self.data.keys()):
                if k in Record.identifying_fields:
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
            ]:
                continue

            source = MERGING_RECORD.get_provenance_field_source(
                key, default=default_source
            )

            # Part 1: identifying fields
            if key in Record.identifying_fields:

                # Always update from curated MERGING_RECORDs
                if MERGING_RECORD.masterdata_is_curated():
                    self.data[key] = MERGING_RECORD.data[key]

                # Do not change if MERGING_RECORD is not curated
                elif (
                    self.masterdata_is_curated
                    and not MERGING_RECORD.masterdata_is_curated()
                ):
                    continue

                # Fuse best fields if none is curated
                else:
                    self.fuse_best_field(MERGING_RECORD, key, val, source)

            # Part 2: other fields
            else:
                # keep existing values per default
                if key in self.data:
                    pass
                else:
                    self.update_field(key, str(val), source)

        return

    def fuse_best_field(self, MERGING_RECORD, key, val, source) -> None:
        def percent_upper_chars(input_string: str) -> float:
            return sum(map(str.isupper, input_string)) / len(input_string)

        def select_best_author(default: str, candidate: str) -> str:
            best_author = default

            # Prefer complete version
            if (
                "and others" in default.lower()
                and "and others" not in candidate.lower()
            ):
                return candidate
            if "et al" in default.lower() and "et al" not in candidate.lower():
                return candidate

            default_mostly_upper = percent_upper_chars(default) > 0.8
            candidate_mostly_upper = percent_upper_chars(candidate) > 0.8

            if default_mostly_upper and not candidate_mostly_upper:
                best_author = candidate

            # Heuristics for missing first names (e.g., in doi.org/crossref metadata)
            if ", and " in default and ", and " not in candidate:
                return candidate
            if "," == default.rstrip()[-1:] and "," != candidate.rstrip()[-1:]:
                best_author = candidate

            # self.REVIEW_MANAGER.logger.debug(
            #     f"best_author({default}, \n"
            #     f"                                      {candidate}) = \n"
            #     f"                                      {best_author}"
            # )
            return best_author

        def select_best_pages(default: str, candidate: str) -> str:
            best_pages = default
            if "--" in candidate and "--" not in default:
                best_pages = candidate

            # self.REVIEW_MANAGER.logger.debug(
            #     f"best_pages({default}, {candidate}) = {best_pages}"
            # )

            return best_pages

        def select_best_title(default: str, candidate: str) -> str:
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

        def select_best_journal(default: str, candidate: str) -> str:

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
                best_author = select_best_author(
                    self.data["author"], MERGING_RECORD.data["author"]
                )
                if self.data["author"] != best_author:
                    self.update_field("author", best_author, source)
            else:
                self.update_field("author", str(val), source)

        elif "pages" == key:
            if "pages" in self.data:
                best_pages = select_best_pages(
                    self.data["pages"], MERGING_RECORD.data["pages"]
                )
                if self.data["pages"] != best_pages:
                    self.update_field("pages", best_pages, source)

            else:
                self.update_field("pages", str(val), source)

        elif "title" == key:
            if "title" in self.data:
                best_title = select_best_title(
                    self.data["title"], MERGING_RECORD.data["title"]
                )
                if self.data["title"] != best_title:
                    self.update_field("title", best_title, source)

            else:
                self.update_field("title", str(val), source)

        elif "journal" == key:
            if "journal" in self.data:
                best_journal = select_best_journal(
                    self.data["journal"], MERGING_RECORD.data["journal"]
                )
                if self.data["journal"] != best_journal:
                    self.update_field("journal", best_journal, source)
            else:
                self.update_field("journal", str(val), source)

        elif "booktitle" == key:
            if "booktitle" in self.data:
                best_booktitle = select_best_journal(
                    self.data["booktitle"], MERGING_RECORD.data["booktitle"]
                )
                if self.data["booktitle"] != best_booktitle:
                    # TBD: custom select_best_booktitle?
                    self.update_field("booktitle", best_booktitle, source)

            else:
                self.update_field("booktitle", str(val), source)

        elif "file" == key:
            if "file" in self.data:
                self.data["file"] = (
                    self.data["file"] + ";" + MERGING_RECORD.data.get("file", "")
                )
            else:
                self.data["file"] = MERGING_RECORD.data["file"]
        return

    @classmethod
    def get_record_similarity(cls, RECORD_A, RECORD_B) -> float:
        record_a = RECORD_A.data.copy()
        record_b = RECORD_B.data.copy()

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

        return Record.get_similarity(df_a.iloc[0], df_b.iloc[0])

    @classmethod
    def get_similarity(cls, df_a: pd.DataFrame, df_b: pd.DataFrame) -> float:
        details = Record.get_similarity_detailed(df_a, df_b)
        return details["score"]

    @classmethod
    def get_similarity_detailed(cls, df_a: pd.DataFrame, df_b: pd.DataFrame) -> dict:

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

            # Put more weithe on other fields if the title is very common
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
        return {"score": similarity_score, "details": details}

    def load_masterdata_provenance(self) -> dict:
        colrev_masterdata_provenance_dict = {}
        if "colrev_masterdata_provenance" in self.data:
            if "" == self.data["colrev_masterdata_provenance"]:
                return {}
            for item in self.data["colrev_masterdata_provenance"].split("\n"):
                key_source = item[: item[:-1].rfind(";")]
                note = item[item[:-1].rfind(";") + 1 : -1]
                key, source = key_source.split(":", 1)
                colrev_masterdata_provenance_dict[key] = {
                    "source": source,
                    "note": note,
                }
                # else:
                #     print(f"problem with masterdata_provenance_item {item}")
        return colrev_masterdata_provenance_dict

    def get_provenance_field_source(self, field, default="ORIGINAL") -> str:

        if field in self.identifying_fields:
            md_p_dict = self.load_masterdata_provenance()
            if field in md_p_dict:
                if "source" in md_p_dict[field]:
                    return md_p_dict[field]["source"]
        else:
            d_p_dict = self.load_data_provenance()
            if field in d_p_dict:
                if "source" in d_p_dict[field]:
                    return d_p_dict[field]["source"]

        return default

    def set_masterdata_provenance(self, md_p_dict: dict):
        parsed = ""
        for k, v in md_p_dict.items():
            v["note"] = (
                v["note"].replace(";", ",").replace(",,", ",").rstrip(",").lstrip(",")
            )
            parsed += (
                f"{k.replace(';', ',')}:"
                + f"{v['source']};"  # Note : some dois have semicolons...
                + f"{v['note']};\n"
            )
        self.data["colrev_masterdata_provenance"] = parsed.rstrip("\n")
        return

    def add_masterdata_provenance_hint(self, field, hint):
        md_p_dict = self.load_masterdata_provenance()
        if field in md_p_dict:
            if hint not in md_p_dict[field]["note"]:
                md_p_dict[field]["note"] += f",{hint}"
        else:
            md_p_dict[field] = {"source": "ORIGINAL", "note": f"{hint}"}
        self.set_masterdata_provenance(md_p_dict)
        return

    def add_masterdata_provenance(self, field, source, hint: str = ""):
        md_p_dict = self.load_masterdata_provenance()
        if field in md_p_dict:
            if "" != hint:
                md_p_dict[field]["note"] += f",{hint}"
            else:
                md_p_dict[field]["note"] = ""
            md_p_dict[field]["source"] = source
        else:
            md_p_dict[field] = {"source": source, "note": f"{hint}"}
        self.set_masterdata_provenance(md_p_dict)
        return

    def load_data_provenance(self) -> dict:
        colrev_data_provenance_dict = {}
        if "colrev_data_provenance" in self.data:
            if "" == self.data["colrev_data_provenance"]:
                return {}
            for item in self.data["colrev_data_provenance"].split("\n"):
                key_source = item[: item[:-1].rfind(";")]
                note = item[item[:-1].rfind(";") + 1 : -1]
                key, source = key_source.split(":", 1)
                colrev_data_provenance_dict[key] = {
                    "source": source,
                    "note": note,
                }

                # else:
                #     print(f"problem with data_provenance_item {item}")
        return colrev_data_provenance_dict

    def set_data_provenance(self, md_p_dict: dict):
        # TODO: test this!
        parsed = ""
        for k, v in md_p_dict.items():
            parsed += (
                f"{k.replace(';', ',')}:"
                + f"{v['source']};"  # Note : some dois have semicolons...
                + f"{v['note'].replace(';', ',')};\n"
            )
        self.data["colrev_data_provenance"] = parsed.rstrip("\n")
        return

    def add_data_provenance(self, field, source, hint: str = ""):
        md_p_dict = self.load_data_provenance()
        if field in md_p_dict:
            if "" != hint:
                md_p_dict[field]["note"] += f",{hint}"
            else:
                md_p_dict[field]["note"] = ""
            md_p_dict[field]["source"] = source
        else:
            md_p_dict[field] = {"source": source, "note": f"{hint}"}
        self.set_data_provenance(md_p_dict)
        return

    def complete_provenance(self, source_info) -> bool:
        """Complete provenance information for LocalIndex"""

        for key in list(self.data.keys()):

            if key in [
                "source_link",
                "source_url",
                "colrev_id",
                "colrev_masterdata",
                "colrev_status",
                "ENTRYTYPE",
                "ID",
                "source_path",
                "local_curated_metadata",
            ]:
                continue

            if key in self.identifying_fields:
                if not self.masterdata_is_curated:
                    self.add_masterdata_provenance(key, source_info, "")
            else:
                self.add_data_provenance(key, source_info, "")

        return True

    def get_incomplete_fields(self) -> list:
        incomplete_fields = []
        for key in self.data.keys():
            if key in ["title", "journal", "booktitle", "author"]:
                if self.data[key].endswith("...") or self.data[key].endswith("…"):
                    incomplete_fields.append(key)
        if self.data.get("author", "").endswith("and others"):
            incomplete_fields.append("author")
        return incomplete_fields

    @classmethod
    def remove_accents(cls, input_str: str) -> str:
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
        self, alsoKnownAsRecord: dict = {}, assume_complete=False
    ) -> str:
        """Returns the colrev_id of the Record.
        If a alsoKnownAsRecord is provided, it returns the colrev_id of the
        alsoKnownAsRecord (using the Record as the reference to decide whether
        required fields are missing)"""

        def format_author_field(input_string: str) -> str:
            input_string = input_string.replace("\n", " ").replace("'", "")
            names = (
                Record.remove_accents(input_string)
                .replace("; ", " and ")
                .split(" and ")
            )
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

            return "-".join(author_list)

        def get_container_title(record: dict) -> str:
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

        def robust_append(input_string: str, to_append: str) -> str:
            input_string = str(input_string)
            to_append = str(to_append).replace("\n", " ")
            to_append = to_append.rstrip().lstrip().replace("–", " ")
            to_append = re.sub(r"[\.\:“”’]", "", to_append)
            to_append = re.sub(r"\s+", "-", to_append)
            to_append = to_append.lower()
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
            required_fields = [
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

            missing_fields = [f for f in required_fields if f not in alsoKnownAsRecord]
            if len(missing_fields) > 0:
                raise NotEnoughDataToIdentifyException(",".join(missing_fields))
            record = alsoKnownAsRecord

        try:

            # Including the version of the identifier prevents cases
            # in which almost all identifiers are identical
            # (and very few identifiers change)
            # when updating the identifier function function
            # (this may look like an anomaly and be hard to identify)
            srep = "colrev_id1:"
            if "article" == record["ENTRYTYPE"].lower():
                srep = robust_append(srep, "a")
            elif "inproceedings" == record["ENTRYTYPE"].lower():
                srep = robust_append(srep, "p")
            else:
                srep = robust_append(srep, record["ENTRYTYPE"].lower())
            srep = robust_append(srep, get_container_title(record))
            if "article" == record["ENTRYTYPE"]:
                # Note: volume/number may not be required.
                # TODO : how do we make sure that colrev_ids are not generated when
                # volume/number are required?
                srep = robust_append(srep, record.get("volume", "-"))
                srep = robust_append(srep, record.get("number", "-"))
            srep = robust_append(srep, record["year"])
            author = format_author_field(record["author"])
            if "" == author.replace("-", ""):
                raise NotEnoughDataToIdentifyException("author field format error")
            srep = robust_append(srep, author)
            title_str = re.sub("[^0-9a-zA-Z]+", " ", record["title"])
            srep = robust_append(srep, title_str)
            srep = srep.replace("&", "and")

            # Note : pages not needed.
            # pages = record.get("pages", "")
            # srep = robust_append(srep, pages)
        except KeyError as e:
            raise NotEnoughDataToIdentifyException(str(e))
        return srep


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
