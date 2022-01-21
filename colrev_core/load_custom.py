import pprint
import typing
from pathlib import Path

pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)


def apply_field_mapping(records: typing.List[dict], mapping: dict) -> typing.List[dict]:

    mapping = {k.lower(): v.lower() for k, v in mapping.items()}
    for record in records:
        prior_keys = list(record.keys())
        # Note : warning: do not create a new dict.
        for key in prior_keys:
            if key.lower() in mapping:
                record[mapping[key.lower()]] = record[key]
                del record[key]

    return records


def drop_fields(records: typing.List[dict], drop: list) -> typing.List[dict]:
    records = [{k: v for k, v in r.items() if k not in drop} for r in records]
    return records


# AIS eLibrary ------------------------------------------------


def ais_heuristic(filename: Path, data: str) -> bool:
    if "https://aisel.aisnet.org/" in data:
        return True
    return False


def load_ais_source(records: typing.List[dict]) -> typing.List[dict]:
    ais_mapping: typing.Dict = {}
    records = apply_field_mapping(records, ais_mapping)

    for record in records:

        # Note : simple heuristic
        # but at the moment, AISeLibrary only indexes articles and conference papers
        if "volume" in record or "number" in record:
            record["ENTRYTYPE"] = "article"
            if "journal" not in record and "booktitle" in record:
                record["journal"] = record["booktitle"]
                del record["booktitle"]
            if "journal" not in record and "title" in record and "chapter" in record:
                record["journal"] = record["title"]
                record["title"] = record["chapter"]
                del record["chapter"]
        else:
            record["ENTRYTYPE"] = "inproceedings"
            if "booktitle" not in record and "title" in record and "chapter" in record:
                record["booktitle"] = record["title"]
                record["title"] = record["chapter"]
                del record["chapter"]
            if "journal" in record and "booktitle" not in record:
                record["booktitle"] = record["journal"]
                del record["journal"]

        if "abstract" in record:
            if "N/A" == record["abstract"]:
                del record["abstract"]
        if "author" in record:
            record["author"] = record["author"].replace("\n", " ")

    return records


# GoogleScholar ------------------------------------------------


def gs_heuristic(filename: Path, data: str) -> bool:
    if "related = {https://scholar.google.com/scholar?q=relat" in data:
        return True
    return False


def load_gs_source(records: typing.List[dict]) -> typing.List[dict]:

    return records


# Web of Science ------------------------------------------------


def wos_heuristic(filename: Path, data: str) -> bool:
    if "UT_(Unique_WOS_ID) = {WOS:" in data:
        return True
    if "@article{ WOS:" in data:
        return True
    return False


def load_wos_source(records: typing.List[dict]) -> typing.List[dict]:

    mapping = {
        "unique-id": "wos_accession_number",
        "UT_(Unique_WOS_ID)": "wos_accession_number",
        "Article_Title": "title",
        "Publication_Year": "year",
        "Author_Full_Names": "author",
    }
    records = apply_field_mapping(records, mapping)

    drop = ["Authors"]
    records = drop_fields(records, drop)

    for record in records:
        if "Publication_Type" in record:
            if "J" == record["Publication_Type"]:
                record["ENTRYTYPE"] = "article"
            if "C" == record["Publication_Type"]:
                record["ENTRYTYPE"] = "inproceedings"
            del record["Publication_Type"]

        if "Start_Page" in record and "End_Page" in record:
            if record["Start_Page"] != "nan" and record["End_Page"] != "nan":
                record["pages"] = record["Start_Page"] + "--" + record["End_Page"]
                record["pages"] = record["pages"].replace(".0", "")
                del record["Start_Page"]
                del record["End_Page"]

        if "author" in record:
            record["author"] = record["author"].replace("; ", " and ")

    return records


# DBLP ------------------------------------------------


def dblp_heuristic(filename: Path, data: str) -> bool:
    if "bibsource = {dblp computer scienc" in data:
        return True
    return False


scripts: typing.List[typing.Dict[str, typing.Any]] = [
    {
        "source_name": "AISeLibrary",
        "source_url": "https://aisel.aisnet.org/",
        "heuristic": ais_heuristic,
        "load_script": load_ais_source,
    },
    {
        "source_name": "GoogleScholar",
        "source_url": "googlescholar.com",
        "heuristic": gs_heuristic,
        "load_script": load_gs_source,
    },
    {
        "source_name": "WebOfScience",
        "source_url": "www.webofscience.com",
        "heuristic": wos_heuristic,
        "load_script": load_wos_source,
    },
]

if __name__ == "__main__":
    pass
