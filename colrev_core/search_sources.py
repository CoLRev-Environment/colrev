from __future__ import annotations

import pprint
import typing
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from colrev_core.prep import PrepRecord

pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)


class SearchSources:
    @classmethod
    def apply_field_mapping(cls, *, RECORD: PrepRecord, mapping: dict) -> PrepRecord:

        mapping = {k.lower(): v.lower() for k, v in mapping.items()}
        prior_keys = list(RECORD.data.keys())
        # Note : warning: do not create a new dict.
        for key in prior_keys:
            if key.lower() in mapping:
                RECORD.rename_field(field=key, new_field=mapping[key.lower()])
                # RECORD.data[mapping[key.lower()]] = RECORD.data[key]
                # del RECORD.data[key]

        return RECORD

    @classmethod
    def drop_fields(cls, *, RECORD: PrepRecord, drop=list) -> PrepRecord:
        # records = [{k: v for k, v in r.items() if k not in drop} for r in records]
        for key_to_drop in drop:
            RECORD.remove_field(field=key_to_drop)
        return RECORD

    # AIS eLibrary ------------------------------------------------

    @classmethod
    def ais_heuristic(cls, *, filename: Path, data: str) -> bool:

        nr_ais_links = data.count("https://aisel.aisnet.org/")
        if nr_ais_links > 0:
            # for the enl file:
            if nr_ais_links == data.count("%T "):
                return True
            # for the bib file:
            if nr_ais_links == data.count("\n}"):
                return True

        return False

    @classmethod
    def prep_ais_source(cls, *, RECORD: PrepRecord) -> PrepRecord:
        ais_mapping: dict = {}
        RECORD = cls.apply_field_mapping(RECORD=RECORD, mapping=ais_mapping)

        if RECORD.data["journal"] in ["Research-in-Progress Papers", "Research Papers"]:
            if "https://aisel.aisnet.org/ecis" in RECORD.data.get("url", ""):
                RECORD.update_field(
                    field="journal", value="ECIS", source="prep_ais_source"
                )

        if RECORD.data["journal"] == "Management Information Systems Quarterly":
            RECORD.update_field(
                field="journal", value="MIS Quarterly", source="prep_ais_source"
            )

        # Note : simple heuristic
        # but at the moment, AISeLibrary only indexes articles and conference papers
        if (
            RECORD.data.get("volume", "UNKNOWN") != "UNKNOWN"
            or RECORD.data.get("number", "UNKNOWN") != "UNKNOWN"
        ) and not any(
            x in RECORD.data.get("journal", "")
            for x in ["HICSS", "ICIS", "ECIS", "AMCIS", "Proceedings"]
        ):
            RECORD.data["ENTRYTYPE"] = "article"
            if "journal" not in RECORD.data and "booktitle" in RECORD.data:
                RECORD.rename_field(field="booktitle", new_field="journal")
            if (
                "journal" not in RECORD.data
                and "title" in RECORD.data
                and "chapter" in RECORD.data
            ):
                RECORD.rename_field(field="title", new_field="journal")
                RECORD.rename_field(field="chapter", new_field="title")

        else:
            RECORD.data["ENTRYTYPE"] = "inproceedings"
            if RECORD.data.get("volume", "") == "UNKNOWN":
                RECORD.remove_field(field="volume")
            if RECORD.data.get("number", "") == "UNKNOWN":
                RECORD.remove_field(field="number")

            if (
                "booktitle" not in RECORD.data
                and "title" in RECORD.data
                and "chapter" in RECORD.data
            ):

                RECORD.rename_field(field="title", new_field="booktitle")
                RECORD.rename_field(field="chapter", new_field="title")

            if "journal" in RECORD.data and "booktitle" not in RECORD.data:
                RECORD.rename_field(field="journal", new_field="booktitle")

            if "ICIS" in RECORD.data["booktitle"]:
                RECORD.update_field(
                    field="booktitle",
                    value="International Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "PACIS" in RECORD.data["booktitle"]:
                RECORD.update_field(
                    field="booktitle",
                    value="Pacific-Asia Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "ECIS" in RECORD.data["booktitle"]:
                RECORD.update_field(
                    field="booktitle",
                    value="European Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "AMCIS" in RECORD.data["booktitle"]:
                RECORD.update_field(
                    field="booktitle",
                    value="Americas Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "HICSS" in RECORD.data["booktitle"]:
                RECORD.update_field(
                    field="booktitle",
                    value="Hawaii International Conference on System Sciences",
                    source="prep_ais_source",
                )

        if "abstract" in RECORD.data:
            if "N/A" == RECORD.data["abstract"]:
                RECORD.remove_field(field="abstract")
        if "author" in RECORD.data:
            RECORD.update_field(
                field="author",
                value=RECORD.data["author"].replace("\n", " "),
                source="prep_ais_source",
            )

        return RECORD

    # GoogleScholar ------------------------------------------------

    @classmethod
    def gs_heuristic(cls, *, filename: Path, data: str) -> bool:
        if "related = {https://scholar.google.com/scholar?q=relat" in data:
            return True
        return False

    @classmethod
    def prep_gs_source(cls, RECORD: PrepRecord) -> PrepRecord:

        return RECORD

    # Web of Science ------------------------------------------------

    @classmethod
    def wos_heuristic(cls, *, filename: Path, data: str) -> bool:
        if "Unique-ID = {WOS:" in data:
            return True
        if "UT_(Unique_WOS_ID) = {WOS:" in data:
            return True
        if "@article{ WOS:" in data:
            return True
        return False

    @classmethod
    def prep_wos_source(cls, *, RECORD: PrepRecord) -> PrepRecord:

        mapping = {
            "unique-id": "wos_accession_number",
            "UT_(Unique_WOS_ID)": "wos_accession_number",
            "Article_Title": "title",
            "Publication_Year": "year",
            "Author_Full_Names": "author",
        }
        RECORD = cls.apply_field_mapping(RECORD=RECORD, mapping=mapping)

        drop = ["Authors"]
        RECORD = cls.drop_fields(RECORD=RECORD, drop=drop)

        if "Publication_Type" in RECORD.data:
            if "J" == RECORD.data["Publication_Type"]:
                RECORD.data["ENTRYTYPE"] = "article"
            if "C" == RECORD.data["Publication_Type"]:
                RECORD.data["ENTRYTYPE"] = "inproceedings"
            RECORD.remove_field(field="Publication_Type")

        if "Start_Page" in RECORD.data and "End_Page" in RECORD.data:
            if RECORD.data["Start_Page"] != "nan" and RECORD.data["End_Page"] != "nan":
                RECORD.data["pages"] = (
                    RECORD.data["Start_Page"] + "--" + RECORD.data["End_Page"]
                )
                RECORD.data["pages"] = RECORD.data["pages"].replace(".0", "")
                RECORD.remove_field(field="Start_Page")
                RECORD.remove_field(field="End_Page")

        if "author" in RECORD.data:
            RECORD.data["author"] = RECORD.data["author"].replace("; ", " and ")

        return RECORD

    # DBLP ------------------------------------------------

    @classmethod
    def dblp_heuristic(cls, *, filename: Path, data: str) -> bool:
        if "bibsource = {dblp computer scienc" in data:
            return True
        return False

    # Scopus ------------------------------------------------

    @classmethod
    def scopus_heuristic(cls, *, filename: Path, data: str) -> bool:
        if "source={Scopus}," in data:
            return True
        return False

    @classmethod
    def prep_scopus_source(cls, *, RECORD: PrepRecord) -> PrepRecord:
        # Scopus:
        if "document_type" in RECORD.data:
            if RECORD.data["document_type"] == "Conference Paper":
                RECORD.data["ENTRYTYPE"] = "inproceedings"
                if "journal" in RECORD.data:
                    RECORD.rename_field(field="journal", new_field="booktitle")
            elif RECORD.data["document_type"] == "Conference Review":
                RECORD.data["ENTRYTYPE"] = "proceedings"
                if "journal" in RECORD.data:
                    RECORD.rename_field(field="journal", new_field="booktitle")

            elif RECORD.data["document_type"] == "Article":
                RECORD.data["ENTRYTYPE"] = "article"

            RECORD.remove_field(field="document_type")

        if "Start_Page" in RECORD.data and "End_Page" in RECORD.data:
            if RECORD.data["Start_Page"] != "nan" and RECORD.data["End_Page"] != "nan":
                RECORD.data["pages"] = (
                    RECORD.data["Start_Page"] + "--" + RECORD.data["End_Page"]
                )
                RECORD.data["pages"] = RECORD.data["pages"].replace(".0", "")
                RECORD.remove_field(field="Start_Page")
                RECORD.remove_field(field="End_Page")

        if "note" in RECORD.data:
            if "cited By " in RECORD.data["note"]:
                RECORD.rename_field(field="note", new_field="cited_by")
                RECORD.data["cited_by"] = RECORD.data["cited_by"].replace(
                    "cited By ", ""
                )

        if "author" in RECORD.data:
            RECORD.data["author"] = RECORD.data["author"].replace("; ", " and ")

        drop = ["source"]
        for field_to_drop in drop:
            RECORD.remove_field(field=field_to_drop)

        return RECORD

    # PDF ------------------------------------------------

    @classmethod
    def pdf_heuristic(cls, *, filename: Path, data: str) -> bool:
        if filename.suffix == ".pdf" and not cls.pdf_backward_search_heuristic(
            filename=filename, data=data
        ):
            return True
        return False

    # PDF backward search ------------------------------------------------

    @classmethod
    def pdf_backward_search_heuristic(cls, *, filename: Path, data: str) -> bool:
        if str(filename).endswith("_ref_list.pdf"):
            return True
        return False

    def __init__(self):
        pass


scripts: list[dict[str, typing.Any]] = [
    {
        "source_name": "ais_library",
        "source_identifier": "https://aisel.aisnet.org/",
        "heuristic": SearchSources.ais_heuristic,
        "prep_script": SearchSources.prep_ais_source,
    },
    {
        "source_name": "google_scholar",
        "source_identifier": "https://scholar.google.com/",
        "heuristic": SearchSources.gs_heuristic,
        "prep_script": SearchSources.prep_gs_source,
    },
    {
        "source_name": "web_of_science",
        "source_identifier": "https://www.webofscience.com/wos/woscc/full-record/"
        + "{{unique-id}}",
        "heuristic": SearchSources.wos_heuristic,
        "prep_script": SearchSources.prep_wos_source,
    },
    {
        "source_name": "scopus",
        "source_identifier": "{{url}}",
        "heuristic": SearchSources.scopus_heuristic,
        "prep_script": SearchSources.prep_scopus_source,
    },
    {
        "source_name": "PDF",
        "source_identifier": "{{file}}",
        "heuristic": SearchSources.pdf_heuristic,
    },
    {
        "source_name": "PDF backward search",
        "source_identifier": "{{cited_by_file}} (references)",
        "heuristic": SearchSources.pdf_backward_search_heuristic,
    },
]


def apply_source_heuristics(*, original: Path) -> list:
    """Apply heuristics to identify source"""

    # TODO : we should consider all records
    # (e.g., the first record with url=ais... may be misleading)
    # TBD: applying heuristics before bibtex-conversion?
    # -> test bibtex conversion before? (otherwise: abort import/warn?)
    data = ""
    # TODO : deal with misleading file extensions.
    try:
        data = original.read_text()
    except UnicodeDecodeError:
        pass

    for source in [x for x in scripts if "heuristic" in x]:
        if source["heuristic"](filename=original, data=data):
            return [
                source["source_name"],
                source["source_identifier"],
            ]

    return ["NA", "NA"]


if __name__ == "__main__":
    pass
