#! /usr/bin/env python
import collections
import html
import json
import logging
import pprint
import re
import sys
import typing
import urllib
from pathlib import Path

import bibtexparser
import dictdiffer
import git
import pandas as pd
import requests
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from nameparser import HumanName
from thefuzz import fuzz
from tqdm.contrib.concurrent import process_map

from colrev_core import dedupe
from colrev_core.review_manager import RecordState
from colrev_core.review_manager import ReviewManager

pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)
PAD = 0
EMAIL, DEBUG_MODE = "NA", "NA"
RETRIEVAL_SIMILARITY = 0.84
TIMEOUT = 10

report_logger = logging.getLogger("colrev_core_report")
logger = logging.getLogger("colrev_core")


def retrieve_local_JOURNAL_ABBREVIATIONS() -> pd.DataFrame:
    j_abbrev = Path("lexicon/JOURNAL_ABBREVIATIONS.csv")
    if j_abbrev.is_file():
        JOURNAL_ABBREVIATIONS = pd.read_csv("lexicon/JOURNAL_ABBREVIATIONS.csv")
    else:
        JOURNAL_ABBREVIATIONS = pd.DataFrame([], columns=["journal", "abbreviation"])
    return JOURNAL_ABBREVIATIONS


def retrieve_local_JOURNAL_VARIATIONS() -> pd.DataFrame:
    j_var = Path("lexicon/JOURNAL_VARIATIONS.csv")
    if j_var.is_file():
        JOURNAL_VARIATIONS = pd.read_csv("lexicon/JOURNAL_VARIATIONS.csv")
    else:
        JOURNAL_VARIATIONS = pd.DataFrame([], columns=["journal", "variation"])
    return JOURNAL_VARIATIONS


def retrieve_local_CONFERENCE_ABBREVIATIONS() -> pd.DataFrame:
    c_abbrev = Path("lexicon/CONFERENCE_ABBREVIATIONS.csv")
    if c_abbrev.is_file():
        CONFERENCE_ABBREVIATIONS = pd.read_csv("lexicon/CONFERENCE_ABBREVIATIONS.csv")
    else:
        CONFERENCE_ABBREVIATIONS = pd.DataFrame(
            [], columns=["conference", "abbreviation"]
        )
    return CONFERENCE_ABBREVIATIONS


LOCAL_JOURNAL_ABBREVIATIONS = retrieve_local_JOURNAL_ABBREVIATIONS()
LOCAL_JOURNAL_VARIATIONS = retrieve_local_JOURNAL_VARIATIONS()
LOCAL_CONFERENCE_ABBREVIATIONS = retrieve_local_CONFERENCE_ABBREVIATIONS()


conf_strings = []
for i, row in LOCAL_CONFERENCE_ABBREVIATIONS.iterrows():
    conf_strings.append(row["abbreviation"])
    conf_strings.append(row["conference"])


def correct_recordtype(record: dict) -> dict:

    if is_complete(record) and not has_inconsistent_fields(record):
        return record

    # Consistency checks
    if "journal" in record:
        if any(x in record["journal"] for x in conf_strings):
            record.update(booktitle=record["journal"])
            record.update(ENTRYTYPE="inproceedings")
            del record["journal"]
    if "booktitle" in record:
        if any(x in record["booktitle"] for x in conf_strings):
            record.update(ENTRYTYPE="inproceedings")
            if "title" in record and "chapter" in record:
                record["booktitle"] = record["title"]
                record["title"] = record["chapter"]
                del record["chapter"]

    if (
        "dissertation" in record.get("fulltext", "NA").lower()
        and record["ENTRYTYPE"] != "phdthesis"
    ):
        prior_e_type = record["ENTRYTYPE"]
        record.update(ENTRYTYPE="phdthesis")
        report_logger.info(
            f' {record["ID"]}'.ljust(PAD, " ")
            + f"Set from {prior_e_type} to phdthesis "
            '("dissertation" in fulltext link)'
        )

    if (
        "thesis" in record.get("fulltext", "NA").lower()
        and record["ENTRYTYPE"] != "phdthesis"
    ):
        prior_e_type = record["ENTRYTYPE"]
        record.update(ENTRYTYPE="phdthesis")
        report_logger.info(
            f' {record["ID"]}'.ljust(PAD, " ")
            + f"Set from {prior_e_type} to phdthesis "
            '("thesis" in fulltext link)'
        )

    # TODO: create a warning if any conference strings (ecis, icis, ..)
    # as stored in CONFERENCE_ABBREVIATIONS is in an article/book

    # Journal articles should not have booktitles/series set.
    if "article" == record["ENTRYTYPE"]:
        if "booktitle" in record:
            if "journal" not in record:
                record.update(journal=record["booktitle"])
                del record["booktitle"]
        if "series" in record:
            if "journal" not in record:
                record.update(journal=record["series"])
                del record["series"]

    if "book" == record["ENTRYTYPE"]:
        if "series" in record:
            if any(x in record["series"] for x in conf_strings):
                conf_name = record["series"]
                del record["series"]
                record.update(booktitle=conf_name)
                record.update(ENTRYTYPE="inproceedings")

    if "article" == record["ENTRYTYPE"]:
        if "journal" not in record:
            if "series" in record:
                journal_string = record["series"]
                record.update(journal=journal_string)
                del record["series"]

    return record


def format_minor(record: dict) -> dict:

    fields_to_process = [
        "author",
        "year",
        "title",
        "journal",
        "booktitle",
        "series",
        "volume",
        "number",
        "pages",
        "doi",
        "abstract",
    ]
    for field in fields_to_process:
        if field in record:
            record[field] = (
                record[field]
                .replace("\n", " ")
                .rstrip()
                .lstrip()
                .replace("{", "")
                .replace("}", "")
                .rstrip(",")
            )
            record[field] = re.sub(r"\s+", " ", record[field])
    return record


def title_if_mostly_upper(input_string: str) -> str:
    if not re.match(r"[a-zA-Z]+", input_string):
        return input_string
    words = input_string.split()
    if sum(word.isupper() for word in words) / len(words) > 0.8:
        return input_string.capitalize()
    else:
        return input_string


def format(record: dict) -> dict:

    fields_to_process = [
        "author",
        "year",
        "title",
        "journal",
        "booktitle",
        "series",
        "volume",
        "number",
        "pages",
        "doi",
        "abstract",
    ]
    for field in fields_to_process:
        if field in record:
            record[field] = (
                record[field]
                .replace("\n", " ")
                .rstrip()
                .lstrip()
                .replace("{", "")
                .replace("}", "")
            )

    if "author" in record:
        # DBLP appends identifiers to non-unique authors
        record.update(author=str(re.sub(r"[0-9]{4}", "", record["author"])))

        # fix name format
        if (1 == len(record["author"].split(" ")[0])) or (", " not in record["author"]):
            record.update(author=format_author_field(record["author"]))

    if "title" in record:
        record.update(title=re.sub(r"\s+", " ", record["title"]).rstrip("."))
        record.update(title=title_if_mostly_upper(record["title"]))

    if "booktitle" in record:
        record.update(booktitle=title_if_mostly_upper(record["booktitle"]))

        stripped_btitle = re.sub(r"\d{4}", "", record["booktitle"])
        stripped_btitle = re.sub(r"\d{1,2}th", "", stripped_btitle)
        stripped_btitle = re.sub(r"\d{1,2}nd", "", stripped_btitle)
        stripped_btitle = re.sub(r"\d{1,2}rd", "", stripped_btitle)
        stripped_btitle = re.sub(r"\d{1,2}st", "", stripped_btitle)
        stripped_btitle = re.sub(r"\([A-Z]{3,6}\)", "", stripped_btitle)
        stripped_btitle = stripped_btitle.replace("Proceedings of the", "").replace(
            "Proceedings", ""
        )
        stripped_btitle = stripped_btitle.lstrip().rstrip()
        record.update(booktitle=stripped_btitle)

    if "date" in record and "year" not in record:
        year = re.search(r"\d{4}", record["date"])
        if year:
            record["year"] = year.group(0)

    if "journal" in record:
        if len(record["journal"]) > 10:
            record.update(journal=title_if_mostly_upper(record["journal"]))

    if "pages" in record:
        record.update(pages=unify_pages_field(record["pages"]))
        if (
            not re.match(r"^\d*$", record["pages"])
            and not re.match(r"^\d*--\d*$", record["pages"])
            and not re.match(r"^[xivXIV]*--[xivXIV]*$", record["pages"])
        ):
            report_logger.info(
                f' {record["ID"]}:'.ljust(PAD, " ")
                + f'Unusual pages: {record["pages"]}'
            )

    if "doi" in record:
        record.update(doi=record["doi"].replace("http://dx.doi.org/", ""))

    if "number" not in record and "issue" in record:
        record.update(number=record["issue"])
        del record["issue"]

    if "url" in record and "fulltext" in record:
        if record["url"] == record["fulltext"]:
            del record["fulltext"]

    return record


def apply_local_rules(record: dict) -> dict:

    if "journal" in record:
        for i, row in LOCAL_JOURNAL_ABBREVIATIONS.iterrows():
            if row["abbreviation"].lower() == record["journal"].lower():
                record.update(journal=row["journal"])

        for i, row in LOCAL_JOURNAL_VARIATIONS.iterrows():
            if row["variation"].lower() == record["journal"].lower():
                record.update(journal=row["journal"])

    if "booktitle" in record:
        for i, row in LOCAL_CONFERENCE_ABBREVIATIONS.iterrows():
            if row["abbreviation"].lower() == record["booktitle"].lower():
                record.update(booktitle=row["conference"])

    return record


def mostly_upper_case(input_string: str) -> bool:
    if not re.match(r"[a-zA-Z]+", input_string):
        return False
    input_string = input_string.replace(".", "").replace(",", "")
    words = input_string.split()
    return sum(word.isupper() for word in words) / len(words) > 0.8


def format_author_field(input_string: str) -> str:

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


def get_container_title(record: dict) -> str:
    container_title = "NA"
    if "ENTRYTYPE" not in record:
        container_title = record.get("journal", record.get("booktitle", "NA"))
    else:
        if "article" == record["ENTRYTYPE"]:
            container_title = record.get("journal", "NA")
        if "inproceedings" == record["ENTRYTYPE"]:
            container_title = record.get("booktitle", "NA")
        if "book" == record["ENTRYTYPE"]:
            container_title = record.get("title", "NA")
        if "inbook" == record["ENTRYTYPE"]:
            container_title = record.get("booktitle", "NA")
    return container_title


def unify_pages_field(input_string: str) -> str:
    if not isinstance(input_string, str):
        return input_string
    if not re.match(r"^\d*--\d*$", input_string) and "--" not in input_string:
        input_string = (
            input_string.replace("-", "--")
            .replace("–", "--")
            .replace("----", "--")
            .replace(" -- ", "--")
            .rstrip(".")
        )
    return input_string


def get_md_from_doi(record: dict) -> dict:
    if "doi" not in record:
        return record
    record = retrieve_doi_metadata(record)
    record.update(metadata_source="DOI.ORG")
    return record


def crossref_json_to_record(item: dict) -> dict:
    # Note: the format differst between crossref and doi.org
    record: dict = {}

    if "title" in item:
        retrieved_title = item["title"]
        if isinstance(retrieved_title, list):
            retrieved_title = retrieved_title[0]
        retrieved_title = re.sub(r"\s+", " ", str(retrieved_title)).replace("\n", " ")
        record.update(title=retrieved_title)

    container_title = None
    if "container-title" in item:
        container_title = item["container-title"]
        if isinstance(container_title, list):
            if container_title:
                container_title = container_title[0]

    if "type" in item:
        if "journal-article" == item.get("type", "NA"):
            record.update(ENTRYTYPE="article")
            if container_title is not None:
                record.update(journal=container_title)
        if "proceedings-article" == item.get("type", "NA"):
            record.update(ENTRYTYPE="inproceedings")
            if container_title is not None:
                record.update(booktitle=container_title)
        if "book" == item.get("type", "NA"):
            record.update(ENTRYTYPE="book")
            if container_title is not None:
                record.update(series=container_title)

    if "DOI" in item:
        record.update(doi=item["DOI"])

    authors = [
        f'{author["family"]}, {author.get("given", "")}'
        for author in item.get("author", "NA")
        if "family" in author
    ]
    authors_string = " and ".join(authors)
    # authors_string = format_author_field(authors_string)
    record.update(author=authors_string)

    try:
        if "published-print" in item:
            date_parts = item["published-print"]["date-parts"]
            record.update(year=str(date_parts[0][0]))
        elif "published-online" in item:
            date_parts = item["published-online"]["date-parts"]
            record.update(year=str(date_parts[0][0]))
    except KeyError:
        pass

    retrieved_pages = item.get("page", "")
    if retrieved_pages != "":
        # DOI data often has only the first page.
        if (
            not record.get("pages", "no_pages") in retrieved_pages
            and "-" in retrieved_pages
        ):
            record.update(pages=unify_pages_field(str(retrieved_pages)))
    retrieved_volume = item.get("volume", "")
    if not retrieved_volume == "":
        record.update(volume=str(retrieved_volume))

    retrieved_number = item.get("issue", "")
    if "journal-issue" in item:
        if "issue" in item["journal-issue"]:
            retrieved_number = item["journal-issue"]["issue"]
    if not retrieved_number == "":
        record.update(number=str(retrieved_number))

    if "abstract" in item:
        retrieved_abstract = item["abstract"]
        if not retrieved_abstract == "":
            retrieved_abstract = re.sub(r"<\/?jats\:[^>]*>", " ", retrieved_abstract)
            retrieved_abstract = re.sub(r"\s+", " ", retrieved_abstract)
            retrieved_abstract = str(retrieved_abstract).replace("\n", "")
            retrieved_abstract = retrieved_abstract.lstrip().rstrip()
            retrieved_abstract = html.unescape(retrieved_abstract)
            record.update(abstract=retrieved_abstract)
    return record


def crossref_query(
    record: dict, jour_vol_iss_list: bool = False
) -> typing.List[typing.Dict]:
    # https://github.com/CrossRef/rest-api-doc
    api_url = "https://api.crossref.org/works?"

    if not jour_vol_iss_list:
        params = {"rows": "15"}
        bibl = record["title"].replace("-", "_") + " " + record.get("year", "")
        bibl = re.sub(r"[\W]+", "", bibl.replace(" ", "_"))
        params["query.bibliographic"] = bibl.replace("_", " ")

        container_title = get_container_title(record)
        if "." not in container_title:
            container_title = container_title.replace(" ", "_")
            container_title = re.sub(r"[\W]+", "", container_title)
            params["query.container-title"] = container_title.replace("_", " ")

        author_last_names = [
            x.split(",")[0] for x in record.get("author", "").split(" and ")
        ]
        author_string = " ".join(author_last_names)
        author_string = re.sub(r"[\W]+", "", author_string.replace(" ", "_"))
        params["query.author"] = author_string.replace("_", " ")
    else:
        params = {"rows": "25"}
        container_title = re.sub(r"[\W]+", " ", record["journal"])
        params["query.container-title"] = container_title.replace("_", " ")

        query_field = record["volume"] + "+" + record["number"]
        params["query"] = query_field

    url = api_url + urllib.parse.urlencode(params)
    headers = {"user-agent": f"{__name__} (mailto:{EMAIL})"}
    record_list = []
    try:
        logger.debug(url)
        ret = requests.get(url, headers=headers, timeout=TIMEOUT)
        ret.raise_for_status()
        if ret.status_code != 200:
            logger.debug(f"crossref_query failed with status {ret.status_code}")
            return [{}]

        data = json.loads(ret.text)

        items = data["message"]["items"]
        most_similar = 0
        most_similar_record = {}
        for item in items:
            if "title" not in item:
                continue

            retrieved_record = crossref_json_to_record(item)

            title_similarity = fuzz.partial_ratio(
                retrieved_record["title"].lower(),
                record.get("title", "").lower(),
            )
            container_similarity = fuzz.partial_ratio(
                get_container_title(retrieved_record).lower(),
                get_container_title(record).lower(),
            )
            weights = [0.6, 0.4]
            similarities = [title_similarity, container_similarity]

            similarity = sum(
                similarities[g] * weights[g] for g in range(len(similarities))
            )
            # logger.debug(f'record: {pp.pformat(record)}')
            # logger.debug(f'similarities: {similarities}')
            # logger.debug(f'similarity: {similarity}')
            # pp.pprint(retrieved_record)

            if jour_vol_iss_list:
                record_list.append(retrieved_record)
            if most_similar < similarity:
                most_similar = similarity
                most_similar_record = retrieved_record
    except requests.exceptions.ConnectionError:
        logger.error("requests.exceptions.ConnectionError in crossref_query")
        return [{}]

    if jour_vol_iss_list:
        return record_list
    else:
        return [most_similar_record]


def container_is_abbreviated(record: dict) -> bool:
    if "journal" in record:
        if record["journal"].count(".") > 2:
            return True
        if record["journal"].isupper():
            return True
    if "booktitle" in record:
        if record["booktitle"].count(".") > 2:
            return True
        if record["booktitle"].isupper():
            return True
    # add heuristics? (e.g., Hawaii Int Conf Syst Sci)
    return False


def abbreviate_container(record: dict, min_len: int) -> dict:
    if "journal" in record:
        record["journal"] = " ".join(
            [x[:min_len] for x in record["journal"].split(" ")]
        )

    return record


def get_abbrev_container_min_len(record: dict) -> int:
    min_len = -1
    if "journal" in record:
        min_len = min(len(x) for x in record["journal"].replace(".", "").split(" "))
    if "booktitle" in record:
        min_len = min(len(x) for x in record["booktitle"].replace(".", "").split(" "))
    return min_len


def get_retrieval_similarity(record: dict, retrieved_record: dict) -> float:

    # TODO: also replace speicla characters (e.g., &amp;)

    if container_is_abbreviated(record):
        min_len = get_abbrev_container_min_len(record)
        abbreviate_container(retrieved_record, min_len)
        abbreviate_container(record, min_len)
    if container_is_abbreviated(retrieved_record):
        min_len = get_abbrev_container_min_len(retrieved_record)
        abbreviate_container(record, min_len)
        abbreviate_container(retrieved_record, min_len)

    if "title" in record:
        record["title"] = record["title"][:90]
    if "title" in retrieved_record:
        retrieved_record["title"] = retrieved_record["title"][:90]

    if "author" in record:
        record["author"] = dedupe.format_authors_string(record["author"])
        record["author"] = record["author"][:45]
    if "author" in retrieved_record:
        retrieved_record["author"] = dedupe.format_authors_string(
            retrieved_record["author"]
        )
        retrieved_record["author"] = retrieved_record["author"][:45]
    if not ("volume" in record and "volume" in retrieved_record):
        record["volume"] = "nan"
        retrieved_record["volume"] = "nan"
    if not ("number" in record and "number" in retrieved_record):
        record["number"] = "nan"
        retrieved_record["number"] = "nan"
    if not ("pages" in record and "pages" in retrieved_record):
        record["pages"] = "nan"
        retrieved_record["pages"] = "nan"
    # Sometimes, the number of pages is provided (not the range)
    elif not ("--" in record["pages"] and "--" in retrieved_record["pages"]):
        record["pages"] = "nan"
        retrieved_record["pages"] = "nan"

    if "editorial" in record.get("title", "NA").lower():
        if not all(x in record for x in ["volume", "number"]):
            return 0
    # pp.pprint(record)
    # pp.pprint(retrieved_record)
    similarity = dedupe.get_record_similarity(record, retrieved_record)

    return similarity


def get_md_from_crossref(record: dict) -> dict:
    if (
        ("title" not in record)
        or ("doi" in record)
        or is_complete_metadata_source(record)
    ):
        return record

    enrich_only = False
    if is_complete_metadata_source(record):
        enrich_only = True

    # To test the metadata provided for a particular DOI use:
    # https://api.crossref.org/works/DOI

    logger.debug(f'get_md_from_crossref({record["ID"]})')
    MAX_RETRIES_ON_ERROR = 3
    # https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
    if len(record["title"]) > 35:
        try:

            retrieved_record_list = crossref_query(record)
            retrieved_record = retrieved_record_list.pop()
            retries = 0
            while not retrieved_record and retries < MAX_RETRIES_ON_ERROR:
                retries += 1
                retrieved_record_list = crossref_query(record)
                retrieved_record = retrieved_record_list.pop()

            if 0 == len(retrieved_record):
                return record

            similarity = get_retrieval_similarity(
                record.copy(), retrieved_record.copy()
            )
            logger.debug(f"crossref similarity: {similarity}")
            if similarity > RETRIEVAL_SIMILARITY:
                for key, val in retrieved_record.items():
                    # Note: no abstracts in crossref?
                    # if enrich_only and 'abstract' != key:
                    #     continue
                    record[key] = val
                if not enrich_only:
                    record.update(metadata_source="CROSSREF")
        except requests.exceptions.ReadTimeout as e:
            logger.error(f"exception: {e}")
            pass
        except KeyboardInterrupt:
            sys.exit()
    return record


def get_year_from_vol_iss_jour_crossref(record: dict) -> dict:
    # The year depends on journal x volume x issue
    if not (
        ("journal" in record and "volume" in record and "number")
        and "year" not in record
    ):
        return record

    logger.debug(f'get_md_from_crossref({record["ID"]})')
    MAX_RETRIES_ON_ERROR = 3
    try:
        modified_record = record.copy()
        modified_record = {
            k: v
            for k, v in modified_record.items()
            if k in ["journal", "volume", "number"]
        }

        # http://api.crossref.org/works?
        # query.container-title=%22MIS+Quarterly%22&query=%2216+2%22

        retrieved_records_list = crossref_query(record, jour_vol_iss_list=True)
        retries = 0
        while not retrieved_records_list and retries < MAX_RETRIES_ON_ERROR:
            retries += 1
            retrieved_records_list = crossref_query(record, jour_vol_iss_list=True)
        if 0 == len(retrieved_records_list):
            return record

        retrieved_records = [
            r
            for r in retrieved_records_list
            if r.get("volume", "NA") == record["volume"]
            and r.get("journal", "NA") == record["journal"]
            and r.get("number", "NA") == record["number"]
        ]
        years = [r["year"] for r in retrieved_records]
        if len(years) == 0:
            return record
        most_common = max(years, key=years.count)
        logger.debug(most_common)
        logger.debug(years.count(most_common))
        if years.count(most_common) > 3:
            record["year"] = most_common
            record["metadata_source"] = "CROSSREF"

    except KeyboardInterrupt:
        sys.exit()

    return record


def sem_scholar_json_to_record(item: dict, record: dict) -> dict:
    retrieved_record: dict = {}
    if "authors" in item:
        authors_string = " and ".join(
            [author["name"] for author in item["authors"] if "name" in author]
        )
        authors_string = format_author_field(authors_string)
        retrieved_record.update(author=authors_string)
    if "abstract" in item:
        retrieved_record.update(abstract=item["abstract"])
    if "doi" in item:
        retrieved_record.update(doi=item["doi"])
    if "title" in item:
        retrieved_record.update(title=item["title"])
    if "year" in item:
        retrieved_record.update(year=item["year"])
    # Note: semantic scholar does not provide data on the type of venue.
    # we therefore use the original ENTRYTYPE
    if "venue" in item:
        if "journal" in record:
            retrieved_record.update(journal=item["venue"])
        if "booktitle" in record:
            retrieved_record.update(booktitle=item["venue"])
    if "url" in item:
        retrieved_record.update(sem_scholar_id=item["url"])

    keys_to_drop = []
    for key, value in retrieved_record.items():
        retrieved_record[key] = str(value).replace("\n", " ").lstrip().rstrip()
        if value in ["", "None"] or value is None:
            keys_to_drop.append(key)
    for key in keys_to_drop:
        del retrieved_record[key]
    return retrieved_record


def get_md_from_sem_scholar(record: dict) -> dict:
    if is_complete_metadata_source(record) or "abstract" in record:
        return record
    enrich_only = False
    if is_complete_metadata_source(record):
        enrich_only = True

    try:
        search_api_url = "https://api.semanticscholar.org/graph/v1/paper/search?query="
        url = search_api_url + record.get("title", "").replace(" ", "+")
        logger.debug(url)
        headers = {"user-agent": f"{__name__} (mailto:{EMAIL})"}
        ret = requests.get(url, headers=headers, timeout=TIMEOUT)
        ret.raise_for_status()

        data = json.loads(ret.text)
        items = data["data"]
        if len(items) == 0:
            return record
        if "paperId" not in items[0]:
            return record

        paper_id = items[0]["paperId"]
        record_retrieval_url = "https://api.semanticscholar.org/v1/paper/" + paper_id
        logger.debug(record_retrieval_url)
        ret_ent = requests.get(record_retrieval_url, headers=headers, timeout=TIMEOUT)
        ret_ent.raise_for_status()
        item = json.loads(ret_ent.text)
        retrieved_record = sem_scholar_json_to_record(item, record)

        red_record_copy = record.copy()
        for key in ["volume", "number", "number", "pages"]:
            if key in red_record_copy:
                del red_record_copy[key]

        similarity = get_retrieval_similarity(red_record_copy, retrieved_record.copy())
        logger.debug(f"scholar similarity: {similarity}")
        if similarity > RETRIEVAL_SIMILARITY:
            for key, val in retrieved_record.items():
                if enrich_only and "abstract" != key:
                    continue
                record[key] = val
            if not enrich_only:
                record.update(metadata_source="SEMANTIC_SCHOLAR")

    except KeyError:
        pass
    except UnicodeEncodeError:
        logger.error("UnicodeEncodeError - this needs to be fixed at some time")
        pass
    except requests.exceptions.ConnectionError:
        logger.error("requests.exceptions.ConnectionError in get_md_from_sem_scholar")
        pass
    return record


def open_library_json_to_record(item: dict) -> dict:
    retrieved_record: dict = {}

    if "author_name" in item:
        authors_string = " and ".join(
            [format_author_field(author) for author in item["author_name"]]
        )
        retrieved_record.update(author=authors_string)
    if "publisher" in item:
        retrieved_record.update(publisher=str(item["publisher"][0]))
    if "title" in item:
        retrieved_record.update(title=str(item["title"]))
    if "publish_year" in item:
        retrieved_record.update(year=str(item["publish_year"][0]))
    if "edition_count" in item:
        retrieved_record.update(edition=str(item["edition_count"]))
    if "seed" in item:
        if "/books/" in item["seed"][0]:
            retrieved_record.update(ENTRYTYPE="book")
    if "publish_place" in item:
        retrieved_record.update(address=str(item["publish_place"][0]))
    if "isbn" in item:
        retrieved_record.update(isbn=str(item["isbn"][0]))

    return retrieved_record


def get_md_from_open_library(record: dict) -> dict:
    if is_complete_metadata_source(record):
        return record
    # only consider entries that are not journal or conference papers
    if record.get("ENTRYTYPE", "NA") in ["article", "inproceedings"]:
        return record

    try:
        base_url = "https://openlibrary.org/search.json?"
        url = ""
        if record.get("author", "NA").split(",")[0]:
            url = base_url + "&author=" + record.get("author", "NA").split(",")[0]
        if "inbook" == record["ENTRYTYPE"] and "editor" in record:
            if record.get("editor", "NA").split(",")[0]:
                url = base_url + "&author=" + record.get("editor", "NA").split(",")[0]
        if base_url not in url:
            return record

        title = record.get("title", record.get("booktitle", "NA"))
        if len(title) < 10:
            return record
        if ":" in title:
            title = title[: title.find(":")]  # To catch sub-titles
        url = url + "&title=" + title.replace(" ", "+")
        ret = requests.get(url, timeout=TIMEOUT)
        ret.raise_for_status()
        logger.debug(url)

        # if we have an exact match, we don't need to check the similarity
        if '"numFoundExact": true,' not in ret.text:
            return record

        data = json.loads(ret.text)
        items = data["docs"]
        if not items:
            return record
        retrieved_record = open_library_json_to_record(items[0])

        for key, val in retrieved_record.items():
            record[key] = val
        record.update(metadata_source="OPEN_LIBRARY")
        if "title" in record and "booktitle" in record:
            del record["booktitle"]

    except UnicodeEncodeError:
        logger.error("UnicodeEncodeError - this needs to be fixed at some time")
        pass
    except requests.exceptions.ConnectionError:
        logger.error("requests.exceptions.ConnectionError in get_md_from_sem_scholar")
        pass
    return record


def get_dblp_venue(venue_string: str) -> str:
    venue = venue_string
    api_url = "https://dblp.org/search/venue/api?q="
    url = api_url + venue_string.replace(" ", "+") + "&format=json"
    headers = {"user-agent": f"{__name__} (mailto:{EMAIL})"}
    try:
        ret = requests.get(url, headers=headers, timeout=TIMEOUT)
        ret.raise_for_status()
        data = json.loads(ret.text)
        if "hit" not in data["result"]["hits"]:
            return ""
        hits = data["result"]["hits"]["hit"]
        for hit in hits:
            if f"/{venue_string.lower()}/" in hit["info"]["url"]:
                venue = hit["info"]["venue"]
                break

        venue = re.sub(r" \(.*?\)", "", venue)
    except requests.exceptions.ConnectionError:
        logger.error("requests.exceptions.ConnectionError in get_dblp_venue()")
        pass
    return venue


def dblp_json_to_record(item: dict) -> dict:
    # To test in browser:
    # https://dblp.org/search/publ/api?q=ADD_TITLE&format=json
    retrieved_record = {}
    if "Withdrawn Items" == item["type"]:
        if "journals" == item["key"][:8]:
            item["type"] = "Journal Articles"
        if "conf" == item["key"][:4]:
            item["type"] = "Conference and Workshop Papers"
        retrieved_record["warning"] = "Withdrawn (according to DBLP)"
    if "Journal Articles" == item["type"]:
        retrieved_record["ENTRYTYPE"] = "article"
        lpos = item["key"].find("/") + 1
        rpos = item["key"].rfind("/")
        jour = item["key"][lpos:rpos]
        retrieved_record["journal"] = html.unescape(get_dblp_venue(jour))
    if "Conference and Workshop Papers" == item["type"]:
        retrieved_record["ENTRYTYPE"] = "inproceedings"
        retrieved_record["booktitle"] = html.unescape(get_dblp_venue(item["venue"]))
    if "title" in item:
        retrieved_record["title"] = html.unescape(item["title"].rstrip("."))
    if "year" in item:
        retrieved_record["year"] = item["year"]
    if "volume" in item:
        retrieved_record["volume"] = item["volume"]
    if "number" in item:
        retrieved_record["number"] = item["number"]
    if "pages" in item:
        retrieved_record["pages"] = item["pages"].replace("-", "--")
    if "authors" in item:
        if "author" in item["authors"]:
            if isinstance(item["authors"]["author"], dict):
                author_string = item["authors"]["author"]["text"]
            else:
                authors_nodes = [
                    author
                    for author in item["authors"]["author"]
                    if isinstance(author, dict)
                ]
                authors = [x["text"] for x in authors_nodes if "text" in x]
                author_string = " and ".join(authors)
            author_string = format_author_field(author_string)
            retrieved_record["author"] = author_string

    if "doi" in item:
        retrieved_record["doi"] = item["doi"]
    if "url" not in item:
        retrieved_record["url"] = item["ee"]

    return retrieved_record


def get_md_from_dblp(record: dict) -> dict:
    if is_complete_metadata_source(record):
        return record
    # TODO: check if the url/dblp_key already points to a dblp page?
    try:
        api_url = "https://dblp.org/search/publ/api?q="
        query = ""
        if "title" in record:
            query = query + record["title"].replace("-", "_")
        # Note : queries combining title and author/journal do not seem to work any more
        # if "author" in record:
        #     query = query + "_" + record["author"].split(",")[0]
        # if "booktitle" in record:
        #     query = query + "_" + record["booktitle"]
        # if "journal" in record:
        #     query = query + "_" + record["journal"]
        # if "year" in record:
        #     query = query + "_" + record["year"]
        query = re.sub(r"[\W]+", " ", query.replace(" ", "_"))
        url = api_url + query.replace(" ", "+") + "&format=json"
        headers = {"user-agent": f"{__name__}  (mailto:{EMAIL})"}
        logger.debug(url)
        ret = requests.get(url, headers=headers, timeout=TIMEOUT)
        ret.raise_for_status()
        if ret.status_code == 500:
            logger.error("DBLP server error")
            return record

        data = json.loads(ret.text)
        if "hits" not in data["result"]:
            return record
        if "hit" not in data["result"]["hits"]:
            return record
        hits = data["result"]["hits"]["hit"]
        for hit in hits:
            item = hit["info"]

            retrieved_record = dblp_json_to_record(item)

            similarity = get_retrieval_similarity(
                record.copy(), retrieved_record.copy()
            )

            logger.debug(f"dblp similarity: {similarity}")
            if similarity > RETRIEVAL_SIMILARITY:
                for key, val in retrieved_record.items():
                    record[key] = val
                record["dblp_key"] = "https://dblp.org/rec/" + item["key"]
                record.update(metadata_source="DBLP")

    # except KeyError:
    # except json.decoder.JSONDecodeError:
    #     pass
    except UnicodeEncodeError:
        logger.error("UnicodeEncodeError - this needs to be fixed at some time")
        pass
    except requests.exceptions.ReadTimeout as e:
        logger.error(f"exception: {e}")
        pass
    except requests.exceptions.ConnectionError:
        logger.error("requests.exceptions.ConnectionError in crossref_query")
        pass
    return record


# https://www.crossref.org/blog/dois-and-matching-regular-expressions/
doi_regex = re.compile(r"10\.\d{4,9}/[-._;/:A-Za-z0-9]*")


def retrieve_doi_metadata(record: dict) -> dict:
    if "doi" not in record:
        return record

    # for testing:
    # curl -iL -H "accept: application/vnd.citationstyles.csl+json"
    # -H "Content-Type: application/json" http://dx.doi.org/10.1111/joop.12368

    try:
        url = "http://dx.doi.org/" + record["doi"]
        logger.debug(url)
        headers = {"accept": "application/vnd.citationstyles.csl+json"}
        ret = requests.get(url, headers=headers, timeout=TIMEOUT)
        ret.raise_for_status()
        if ret.status_code != 200:
            report_logger.info(
                f' {record["ID"]}'.ljust(PAD, " ")
                + "metadata for "
                + f'doi  {record["doi"]} not (yet) available'
            )
            return record

        # For exceptions:
        orig_record = record.copy()

        retrieved_json = json.loads(ret.text)
        retrieved_record = crossref_json_to_record(retrieved_json)
        for key, val in retrieved_record.items():
            if val:
                record[key] = str(val)

    # except IndexError:
    # except json.decoder.JSONDecodeError:
    # except TypeError:
    except requests.exceptions.HTTPError:
        pass
    except requests.exceptions.ReadTimeout as e:
        logger.error(f"exception: {e}")
        pass
    except requests.exceptions.ConnectionError:
        logger.error(f'ConnectionError: {record["ID"]}')
        pass
        return orig_record
    return record


def get_md_from_urls(record: dict) -> dict:
    if is_complete_metadata_source(record):
        return record

    url = record.get("url", record.get("fulltext", "NA"))
    if "NA" != url:
        try:
            logger.debug(f"Retrieve doi-md from {url}")
            headers = {"user-agent": f"{__name__}  (mailto:{EMAIL})"}
            ret = requests.get(url, headers=headers, timeout=TIMEOUT)
            ret.raise_for_status()
            res = re.findall(doi_regex, ret.text)
            if res:
                if len(res) == 1:
                    ret_dois = res[0]
                else:
                    counter = collections.Counter(res)
                    ret_dois = counter.most_common()

                if not ret_dois:
                    return record
                for doi, freq in ret_dois:
                    retrieved_record = {"doi": doi, "ID": record["ID"]}
                    retrieved_record = retrieve_doi_metadata(retrieved_record)
                    similarity = get_retrieval_similarity(
                        record.copy(), retrieved_record.copy()
                    )
                    if similarity > RETRIEVAL_SIMILARITY:
                        for key, val in retrieved_record.items():
                            record[key] = val

                        report_logger.debug(
                            "Retrieved metadata based on doi from"
                            f' website: {record["doi"]}'
                        )
                        record.update(metadata_source="LINKED_URL")

        except requests.exceptions.ConnectionError:
            pass
        except Exception as e:
            print(f"exception: {e}")
            pass
    return record


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

# book, inbook: author <- editor


def missing_fields(record: dict) -> list:
    missing_fields = []
    if record["ENTRYTYPE"] in record_field_requirements.keys():
        reqs = record_field_requirements[record["ENTRYTYPE"]]
        missing_fields = [x for x in reqs if x not in record.keys() or "" == record[x]]
    else:
        missing_fields = ["no field requirements defined"]
    return missing_fields


def is_complete(record: dict) -> bool:
    sufficiently_complete = False
    if record["ENTRYTYPE"] in record_field_requirements.keys():
        if len(missing_fields(record)) == 0:
            sufficiently_complete = True
    return sufficiently_complete


def is_complete_metadata_source(record: dict) -> bool:
    # Note: metadata_source is set at the end of each procedure
    # that completes/corrects metadata based on an external source
    return "ORIGINAL" != record["metadata_source"]


record_field_inconsistencies: typing.Dict[str, typing.List[str]] = {
    "article": ["booktitle"],
    "inproceedings": ["volume", "issue", "number", "journal"],
    "incollection": [],
    "inbook": ["journal"],
    "book": ["volume", "issue", "number", "journal"],
    "phdthesis": ["volume", "issue", "number", "journal", "booktitle"],
    "masterthesis": ["volume", "issue", "number", "journal", "booktitle"],
    "techreport": ["volume", "issue", "number", "journal", "booktitle"],
    "unpublished": ["volume", "issue", "number", "journal", "booktitle"],
}


def get_inconsistencies(record: dict) -> list:
    inconsistent_fields = []
    if record["ENTRYTYPE"] in record_field_inconsistencies.keys():
        incons_fields = record_field_inconsistencies[record["ENTRYTYPE"]]
        inconsistent_fields = [x for x in incons_fields if x in record]
    # Note: a thesis should be single-authored
    if "thesis" in record["ENTRYTYPE"] and " and " in record.get("author", ""):
        inconsistent_fields.append("author")
    return inconsistent_fields


def has_inconsistent_fields(record: dict) -> bool:
    found_inconsistencies = False
    if record["ENTRYTYPE"] in record_field_inconsistencies.keys():
        inconsistencies = get_inconsistencies(record)
        if inconsistencies:
            found_inconsistencies = True
    return found_inconsistencies


def get_incomplete_fields(record: dict) -> list:
    incomplete_fields = []
    for key in record.keys():
        if key in ["title", "journal", "booktitle", "author"]:
            if record[key].endswith("...") or record[key].endswith("…"):
                incomplete_fields.append(key)
    if record.get("author", "").endswith("and others"):
        incomplete_fields.append("author")
    return incomplete_fields


def has_incomplete_fields(record: dict) -> bool:
    if len(get_incomplete_fields(record)) > 0:
        return True
    return False


fields_to_keep = [
    "ID",
    "ENTRYTYPE",
    "author",
    "year",
    "title",
    "journal",
    "booktitle",
    "series",
    "volume",
    "number",
    "pages",
    "doi",
    "abstract",
    "school",
    "editor",
    "book-group-author",
    "book-author",
    "keywords",
    "file",
    "status",
    "fulltext",
    "origin",
    "publisher",
    "dblp_key",
    "sem_scholar_id",
    "url",
    "metadata_source",
    "isbn",
    "address",
    "edition",
    "warning",
    "crossref",
    "date",
    "grobid-version",
]
fields_to_drop = [
    "type",
    "organization",
    "issn",
    "note",
    "unique-id",
    "month",
    "researcherid-numbers",
    "orcid-numbers",
    "eissn",
    "article-number",
    "author_keywords",
    "source",
    "affiliation",
    "document_type",
    "art_number",
    "language",
    "doc-delivery-number",
    "da",
    "usage-count-last-180-days",
    "usage-count-since-2013",
    "doc-delivery-number",
    "research-areas",
    "web-of-science-categories",
    "number-of-cited-references",
    "times-cited",
    "journal-iso",
    "oa",
    "keywords-plus",
    "funding-text",
    "funding-acknowledgement",
    "day",
    "related",
    "bibsource",
    "timestamp",
    "biburl",
    "man_prep_hints",
]


def drop_fields(record: dict) -> dict:
    for key in list(record):
        if "NA" == record[key]:
            del record[key]
        if key not in fields_to_keep:
            record.pop(key)
            # warn if fields are dropped that are not in fields_to_drop
            if key not in fields_to_drop:
                report_logger.info(f"Dropped {key} field")
    for key in list(record):
        if "" == record[key]:
            del record[key]
    if "article" == record["ENTRYTYPE"] or "inproceedings" == record["ENTRYTYPE"]:
        if "publisher" in record:
            del record["publisher"]
    if "publisher" in record:
        if "researchgate.net" == record["publisher"]:
            del record["publisher"]
    return record


def read_next_record_str() -> typing.Iterator[str]:
    # TODO : we should use the REVIEW_MANAGER.pahts[...] here
    with open("references.bib") as f:
        data = ""
        first_entry_processed = False
        while True:
            line = f.readline()
            if not line:
                break
            if line[:1] == "%" or line == "\n":
                continue
            if line[:1] != "@":
                data += line
            else:
                if first_entry_processed:
                    yield data
                else:
                    first_entry_processed = True
                data = line
        yield data


def get_crossref_record(record) -> dict:
    # Note : the ID of the crossrefed record may have changed.
    # we need to trace based on the origin
    crossref_origin = record["origin"]
    crossref_origin = crossref_origin[: crossref_origin.rfind("/")]
    crossref_origin = crossref_origin + "/" + record["crossref"]
    for record_string in read_next_record_str():
        if crossref_origin in record_string:
            parser = BibTexParser(customization=convert_to_unicode)
            db = bibtexparser.loads(record_string, parser=parser)
            record = db.entries[0]
            if record["origin"] == crossref_origin:
                return record
    return {}


def resolve_crossrefs(record: dict) -> dict:
    if "crossref" in record:
        crossref_record = get_crossref_record(record)
        if 0 != len(crossref_record):
            for k, v in crossref_record.items():
                if k not in record:
                    record[k] = v
    return record


def log_notifications(record: dict, unprepared_record: dict) -> dict:

    msg = ""

    change = 1 - dedupe.get_record_similarity(record.copy(), unprepared_record)
    if change > 0.1:
        report_logger.info(
            f' {record["ID"]}'.ljust(PAD, " ") + f"Change score: {round(change, 2)}"
        )

    if not (is_complete(record) or is_complete_metadata_source(record)):
        report_logger.info(
            f' {record["ID"]}'.ljust(PAD, " ") + f'{str(record["ENTRYTYPE"]).title()} '
            f"missing {missing_fields(record)}"
        )
        msg += f"missing: {missing_fields(record)}"

    if has_inconsistent_fields(record):
        report_logger.info(
            f' {record["ID"]}'.ljust(PAD, " ") + f'{str(record["ENTRYTYPE"]).title()} '
            f"with {get_inconsistencies(record)} field(s)"
            " (inconsistent"
        )
        msg += f'; {record["ENTRYTYPE"]} but {get_inconsistencies(record)}'

    if has_incomplete_fields(record):
        report_logger.info(
            f' {record["ID"]}'.ljust(PAD, " ")
            + f"Incomplete fields {get_incomplete_fields(record)}"
        )
        msg += f"; incomplete: {get_incomplete_fields(record)}"
    if change > 0.1:
        msg += f"; change-score: {change}"

    record["man_prep_hints"] = msg.strip(";").lstrip(" ")

    return record


def remove_nicknames(record: dict) -> dict:
    if "author" in record:
        # Replace nicknames in parentheses
        record["author"] = re.sub(r"\([^)]*\)", "", record["author"])
        record["author"] = record["author"].replace("  ", " ")
    return record


def remove_redundant_fields(record: dict) -> dict:
    if "article" == record["ENTRYTYPE"]:
        if "journal" in record and "booktitle" in record:
            if (
                fuzz.partial_ratio(
                    record["journal"].lower(), record["booktitle"].lower()
                )
                / 100
                > 0.9
            ):
                del record["booktitle"]
    if "inproceedings" == record["ENTRYTYPE"]:
        if "journal" in record and "booktitle" in record:
            if (
                fuzz.partial_ratio(
                    record["journal"].lower(), record["booktitle"].lower()
                )
                / 100
                > 0.9
            ):
                del record["journal"]
    return record


def update_metadata_status(record: dict) -> dict:
    logger.debug(f'is_complete({record["ID"]}): {is_complete(record)}')
    logger.debug(
        f'is_complete_metadata_source({record["ID"]}): '
        f"{is_complete_metadata_source(record)}"
    )
    logger.debug(
        f'has_inconsistent_fields({record["ID"]}): {has_inconsistent_fields(record)}'
    )
    logger.debug(
        f'has_incomplete_fields({record["ID"]}): {has_incomplete_fields(record)}'
    )

    if (
        (is_complete(record) and not has_incomplete_fields(record))
        or is_complete_metadata_source(record)
    ) and not has_inconsistent_fields(record):
        record = drop_fields(record)
        record.update(status=RecordState.md_prepared)
    else:
        record.update(status=RecordState.md_needs_manual_preparation)
    return record


def update_local_paper_index_fields(
    record: dict, LOCAL_PAPER_INDEX_FORMAT: dict
) -> dict:

    if len(LOCAL_PAPER_INDEX_FORMAT) == 0:
        return record

    if "outlet" in LOCAL_PAPER_INDEX_FORMAT:
        outlet, container_name = LOCAL_PAPER_INDEX_FORMAT["outlet"].split("=")
        if "journal" == outlet:
            record["journal"] = container_name
            record["ENTRYTYPE"] = "article"
        if "conference" == outlet:
            record["booktitle"] = container_name
            record["ENTRYTYPE"] = "inproceedings"

    sub_dir_pattern = LOCAL_PAPER_INDEX_FORMAT["sub_dir_pattern"]

    partial_path = Path(record["file"]).parents[0].stem
    if "year" == sub_dir_pattern:
        r_sub_dir_pattern = re.compile("([1-3][0-9]{3})")
        partial_path = Path(record["file"]).parents[0].stem
        # Note: for year-patterns, we allow subfolders (eg., conference tracks)
        partial_path = str(Path(record["file"]).parents[0]).replace(
            LOCAL_PAPER_INDEX_FORMAT["source_url"], ""
        )
        match = r_sub_dir_pattern.search(str(partial_path))
        if match is not None:
            year = match.group(1)
            record["year"] = year

    if "volume_number" == sub_dir_pattern:
        r_sub_dir_pattern = re.compile("([0-9]{1,3})_([0-9]{1,2})")

        if "volume_number" == sub_dir_pattern:
            match = r_sub_dir_pattern.search(str(partial_path))
            if match is not None:
                volume = match.group(1)
                number = match.group(2)
                record["volume"] = volume
                record["number"] = number

    return record


def prepare(item: dict) -> dict:

    record = item["record"]

    if str(RecordState.md_imported) != str(record["status"]):
        return record

    # # Note: we require (almost) perfect matches for the scripts.
    # # Cases with higher dissimilarity will be handled in the prep_man.py
    prep_scripts: typing.List[typing.Dict[str, typing.Any]] = [
        {"script": drop_fields, "params": record},
        {
            "script": update_local_paper_index_fields,
            "params": [record, item["LOCAL_PAPER_INDEX_FORMAT"]],
        },
        {"script": resolve_crossrefs, "params": record},
        {"script": correct_recordtype, "params": record},
        {"script": format, "params": record},
        {"script": apply_local_rules, "params": record},
        {"script": get_md_from_doi, "params": record},
        {"script": get_md_from_crossref, "params": record},
        {"script": get_md_from_dblp, "params": record},
        {"script": get_md_from_sem_scholar, "params": record},
        {"script": get_md_from_open_library, "params": record},
        {"script": get_md_from_urls, "params": record},
        {"script": get_year_from_vol_iss_jour_crossref, "params": record},
        {"script": remove_nicknames, "params": record},
        {"script": remove_redundant_fields, "params": record},
        {"script": format_minor, "params": record},
        {"script": update_metadata_status, "params": record},
    ]

    unprepared_record = record.copy()
    short_form = drop_fields(record.copy())
    report_logger.info(
        f'prepare({record["ID"]})' + f" called with: \n{pp.pformat(short_form)}\n\n"
    )

    for prep_script in prep_scripts:

        prior = record.copy()

        if [] == prep_script["params"]:
            report_logger.debug(f'{prep_script["script"].__name__}() called')
            prep_script["script"]()
        else:
            # TODO
            # if type(prep_script["params"]) != list:
            #     param_names = prep_script["params"]
            # else:
            #     param_names = [x.__name__ for x in prep_script["params"]]
            report_logger.debug(f'{prep_script["script"].__name__}(params) called')
            if type(prep_script["params"]) == list:
                prep_script["script"](*prep_script["params"])
            else:
                prep_script["script"](prep_script["params"])

        diffs = list(dictdiffer.diff(prior, record))
        if diffs:
            report_logger.info(
                f'{prep_script["script"].__name__}({prep_script["params"]["ID"]})'
                f" changed:\n{pp.pformat(diffs)}\n"
            )
        else:
            report_logger.debug(f"{prep_script['script'].__name__} changed: -")
        if DEBUG_MODE:
            print("\n")

    if RecordState.md_needs_manual_preparation == record["status"]:
        record = log_notifications(record, unprepared_record)

    return record


def log_details(preparation_batch: list) -> None:
    metadata_sources = {record["metadata_source"] for record in preparation_batch}
    if "ORIGINAL" in metadata_sources:
        metadata_sources.remove("ORIGINAL")
        nr_recs = len(
            [
                record
                for record in preparation_batch
                if record["metadata_source"] == "ORIGINAL"
                and record["status"] == RecordState.md_prepared
            ]
        )
        report_logger.info(f"Statistics: {nr_recs} records did not need preparation")

    for metadata_source in metadata_sources:
        nr_recs = len(
            [
                record
                for record in preparation_batch
                if record["metadata_source"] == metadata_source
                and record["status"] == RecordState.md_prepared
            ]
        )
        report_logger.info(
            f"Statistics: {nr_recs} records prepared with {metadata_source}"
        )

    nr_recs = len(
        [
            record
            for record in preparation_batch
            if record["status"] == RecordState.md_needs_manual_preparation
        ]
    )
    report_logger.info(f"Statistics: {nr_recs} records not prepared")

    report_logger.info(
        "To reset the metdatata of records, use " "colrev prepare --reset-ID [ID1,ID2]"
    )
    report_logger.info(
        "Further instructions are available in the " "documentation (TODO: link)"
    )
    return


def reset(REVIEW_MANAGER, bib_db: BibDatabase, id: str) -> None:
    MAIN_REFERENCES = REVIEW_MANAGER.paths["MAIN_REFERENCES"]
    record_list = [x for x in bib_db.entries if x["ID"] == id]
    if len(record_list) == 0:
        report_logger.info(f"record with ID {id} not found")
        return
    # Note: the case len(record) > 1 should not occur.
    record: dict = record_list.pop()
    if RecordState.md_prepared != record["status"]:
        report_logger.error(f'{id}: status must be md_prepared (is {record["status"]})')
        return

    origins = record["origin"].split(";")

    git_repo = git.Repo(str(REVIEW_MANAGER.paths["REPO_DIR"]))
    revlist = (
        ((commit.tree / MAIN_REFERENCES).data_stream.read())
        for commit in git_repo.iter_commits(paths=MAIN_REFERENCES)
    )
    for filecontents in list(revlist):
        prior_bib_db = bibtexparser.loads(filecontents)
        for r in prior_bib_db.entries:
            if RecordState.md_imported == r["status"] and any(
                o in r["origin"] for o in origins
            ):
                r.update(status=RecordState.md_needs_manual_preparation)
                report_logger.info(f'reset({record["ID"]}) to\n{pp.pformat(r)}\n\n')
                record.update(r)
                break
    return


def reset_ids(REVIEW_MANAGER, reset_ids: list) -> None:
    bib_db = REVIEW_MANAGER.load_bib_db()
    for reset_id in reset_ids:
        reset(REVIEW_MANAGER, bib_db, reset_id)
    REVIEW_MANAGER.save_bib_db(bib_db)
    git_repo = REVIEW_MANAGER.get_repo()
    git_repo.index.add([str(REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"])])
    REVIEW_MANAGER.create_commit("Reset metadata for manual preparation")
    return


def get_data(REVIEW_MANAGER):
    from colrev_core.review_manager import RecordState

    rsl = REVIEW_MANAGER.get_record_state_list()
    nr_tasks = len([x for x in rsl if str(RecordState.md_imported) == x[1]])

    PAD = min((max(len(x[0]) for x in rsl) + 2), 35)

    items = REVIEW_MANAGER.read_next_record(
        conditions={"status": str(RecordState.md_imported)},
    )

    prior_ids = [x[0] for x in rsl if str(RecordState.md_imported) == x[1]]

    prep_data = {
        "nr_tasks": nr_tasks,
        "PAD": PAD,
        "items": items,
        "prior_ids": prior_ids,
    }
    logger.debug(pp.pformat(prep_data))
    return prep_data


def set_to_reprocess(REVIEW_MANAGER):
    # Note: resetting needs_manual_preparation to imported would also be
    # consistent with the check_valid_transitions because it will either
    # transition to prepared or to needs_manual_preparation

    bib_db = REVIEW_MANAGER.load_bib_db()
    [
        r.update(status=RecordState.md_imported)
        for r in bib_db.entries
        if RecordState.md_needs_manual_preparation == r["status"]
    ]
    REVIEW_MANAGER.save_bib_db(bib_db)
    return


def get_lpi_data(LPI_INDICES, item):

    for LPI_INDEX in LPI_INDICES:
        if not LPI_INDEX:
            continue
        if LPI_INDEX["filename"] in item["origin"]:
            return LPI_INDEX
    return {}


def batch(items, REVIEW_MANAGER):
    n = REVIEW_MANAGER.config["BATCH_SIZE"]

    sources = REVIEW_MANAGER.load_sources()

    LPI_INDICES = [
        {
            key: value
            for key, value in source.items()
            if "LOCAL_PAPER_INDEX" == source["search_type"]
            and key
            in ["filename", "search_type", "source_url", "outlet", "sub_dir_pattern"]
        }
        for source in sources
    ]

    batch = []
    for item in items:
        batch.append(
            {
                "record": item,
                "LOCAL_PAPER_INDEX_FORMAT": get_lpi_data(LPI_INDICES, item),
            }
        )
        if len(batch) == n:
            yield batch
            batch = []
    yield batch


def main(
    REVIEW_MANAGER: ReviewManager,
    reprocess: bool = False,
    keep_ids: bool = False,
) -> None:

    saved_args = locals()
    if not keep_ids:
        del saved_args["keep_ids"]
    if not reprocess:
        del saved_args["reprocess"]

    global EMAIL
    EMAIL = REVIEW_MANAGER.config["EMAIL"]

    global DEBUG_MODE
    DEBUG_MODE = REVIEW_MANAGER.config["DEBUG_MODE"]

    CPUS = REVIEW_MANAGER.config["CPUS"] * 5

    if reprocess:
        set_to_reprocess(REVIEW_MANAGER)

    logger.info("Prepare")
    report_logger.debug(f"Set RETRIEVAL_SIMILARITY={RETRIEVAL_SIMILARITY}")
    saved_args["retrieval_similarity"] = RETRIEVAL_SIMILARITY

    prepare_data = get_data(REVIEW_MANAGER)
    logger.debug(f"prepare_data: {pp.pformat(prepare_data)}")

    global PAD
    PAD = prepare_data["PAD"]

    i = 1
    for preparation_batch in batch(prepare_data["items"], REVIEW_MANAGER):

        print(f"Batch {i}")
        i += 1

        preparation_batch = process_map(prepare, preparation_batch, max_workers=CPUS)

        REVIEW_MANAGER.save_record_list_by_ID(preparation_batch)

        preparation_batch_IDs = [x["ID"] for x in preparation_batch]
        if not keep_ids:
            REVIEW_MANAGER.set_IDs(selected_IDs=preparation_batch_IDs)

        log_details(preparation_batch)

        # Multiprocessing mixes logs of different records.
        # For better readability:
        REVIEW_MANAGER.reorder_log(preparation_batch_IDs)

        REVIEW_MANAGER.create_commit("Prepare records", saved_args=saved_args)

    if 1 == i:
        logger.info("No records to prepare")
    return
