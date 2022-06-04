#! /usr/bin/env python
import collections
import html
import importlib
import json
import logging
import multiprocessing as mp
import re
import sys
import time
import typing
import urllib
from datetime import timedelta
from pathlib import Path
from urllib.parse import unquote

import dictdiffer
import git
import requests
import requests_cache
import zope.interface
from alphabet_detector import AlphabetDetector
from bs4 import BeautifulSoup
from lingua.builder import LanguageDetectorBuilder
from nameparser import HumanName
from opensearchpy import NotFoundError
from pathos.multiprocessing import ProcessPool
from thefuzz import fuzz

from colrev_core.environment import EnvironmentManager
from colrev_core.environment import LocalIndex
from colrev_core.environment import RecordNotInIndexException
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import Record
from colrev_core.record import RecordState

# from datetime import datetime

logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("requests_cache").setLevel(logging.ERROR)


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

    def format_authors_string(self):
        if "author" not in self.data:
            return
        authors = self.data["author"]
        authors = str(authors).lower()
        authors_string = ""
        authors = Record.remove_accents(input_str=authors)

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
        self.data["author"] = authors_string
        return

    @classmethod
    def get_retrieval_similarity(
        self, *, RECORD_ORIGINAL: Record, RETRIEVED_RECORD_ORIGINAL: Record
    ) -> float:
        RECORD = PrepRecord(data=RECORD_ORIGINAL.data.copy())
        RETRIEVED_RECORD = PrepRecord(data=RETRIEVED_RECORD_ORIGINAL.data.copy())
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
            RECORD.format_authors_string()
            RECORD.data["author"] = RECORD.data["author"][:45]
        if "author" in RETRIEVED_RECORD.data:
            RETRIEVED_RECORD.format_authors_string()
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

        if "editorial" in RECORD.data.get("title", "NA").lower():
            if not all(x in RECORD.data for x in ["volume", "number"]):
                return 0
        # print(RECORD)
        # print(RETRIEVED_RECORD)
        similarity = Record.get_record_similarity(
            RECORD_A=RECORD, RECORD_B=RETRIEVED_RECORD
        )

        return similarity

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

    def prescreen_exclude(self, *, reason) -> None:
        self.data["colrev_status"] = RecordState.rev_prescreen_excluded
        self.data["prescreen_exclusion"] = reason

        to_drop = []
        for k, v in self.data.items():
            if "UNKNOWN" == v:
                to_drop.append(k)
        for k in to_drop:
            del self.data[k]

        return


class PrepScript(zope.interface.Interface):
    def prepare(self, x):
        pass


class Preparation(Process):

    alphabet_detector = AlphabetDetector()
    HTML_CLEANER = re.compile("<.*?>")
    PAD = 0
    TIMEOUT = 10
    MAX_RETRIES_ON_ERROR = 3

    requests_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"
    }

    # https://www.crossref.org/blog/dois-and-matching-regular-expressions/
    doi_regex = re.compile(r"10\.\d{4,9}/[-._;/:A-Za-z0-9]*")

    fields_to_keep = [
        "ID",
        "ENTRYTYPE",
        "colrev_status",
        "colrev_origin",
        "colrev_masterdata_provenance",
        "colrev_data_provenance",
        "colrev_pid",
        "colrev_id",
        "author",
        "year",
        "title",
        "journal",
        "booktitle",
        "chapter",
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
        "fulltext",
        "publisher",
        "dblp_key",
        "sem_scholar_id",
        "url",
        "isbn",
        "address",
        "edition",
        "warning",
        "crossref",
        "date",
        "wos_accession_number",
        "link",
        "url",
        "crossmark",
        "warning",
        "note",
        "issn",
        "language",
    ]

    # Note : the followin objects have heavy memory footprints and should be
    # class (not object) properties to keep parallel processing as
    # efficient as possible (the object is passed to each thread)
    language_detector = (
        LanguageDetectorBuilder.from_all_languages_with_latin_script().build()
    )

    # session = requests_cache.CachedSession("requests_cache")
    cache_path = EnvironmentManager.colrev_path / Path("prep_requests_cache")
    session = requests_cache.CachedSession(
        str(cache_path), backend="sqlite", expire_after=timedelta(days=30)
    )

    def __init__(
        self,
        *,
        REVIEW_MANAGER,
        force=False,
        similarity: float = 0.9,
        notify_state_transition_process: bool = True,
        debug: str = "NA",
        languages_to_include: str = "en",
    ):
        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            type=ProcessType.prep,
            notify_state_transition_process=notify_state_transition_process,
            debug=(debug != "NA"),
        )
        self.notify_state_transition_process = notify_state_transition_process

        self.RETRIEVAL_SIMILARITY = similarity

        self.languages_to_include = languages_to_include.split(",")

        self.fields_to_keep += self.REVIEW_MANAGER.settings.prep.fields_to_keep

        self.predatory_journals = self.load_predatory_journals()
        # Note : Lingua is tested/evaluated relative to other libraries:
        # https://github.com/pemistahl/lingua-py
        # It performs particularly well for short strings (single words/word pairs)
        # The langdetect library is non-deterministic, especially for short strings
        # https://pypi.org/project/langdetect/

        # if similarity == 0.0:  # if it has not been set use default
        # saved_args["RETRIEVAL_SIMILARITY"] = self.RETRIEVAL_SIMILARITY
        # RETRIEVAL_SIMILARITY = self.RETRIEVAL_SIMILARITY
        # saved_args["RETRIEVAL_SIMILARITY"] = similarity

        self.CPUS = self.CPUS * 15

        # Note: for these scripts, only the similarity changes.
        self.prep_scripts: typing.Dict[str, typing.Dict[str, typing.Any]] = {
            "exclude_non_latin_alphabets": {
                "script": self.exclude_non_latin_alphabets,
            },
            "exclude_languages": {
                "script": self.exclude_languages,
            },
            "exclude_collections": {
                "script": self.exclude_collections,
            },
            "exclude_predatory_journals": {
                "script": self.exclude_predatory_journals,
            },
            "remove_urls_with_500_errors": {
                "script": self.remove_urls_with_500_errors,
            },
            "remove_broken_IDs": {
                "script": self.remove_broken_IDs,
            },
            "global_ids_consistency_check": {
                "script": self.global_ids_consistency_check,
            },
            "prep_curated": {
                "script": self.prep_curated,
            },
            "format": {
                "script": self.format,
            },
            "resolve_crossrefs": {
                "script": self.resolve_crossrefs,
            },
            "get_doi_from_sem_scholar": {
                "script": self.get_doi_from_sem_scholar,
                "source_correction_hint": "fill out the online form: "
                "https://www.semanticscholar.org/faq#correct-error",
            },
            "get_doi_from_urls": {"script": self.get_doi_from_urls},
            "get_masterdata_from_doi": {
                "script": self.get_masterdata_from_doi,
                "source_correction_hint": "ask the publisher to correct the metadata"
                " (see https://www.crossref.org/blog/"
                "metadata-corrections-updates-and-additions-in-metadata-manager/",
            },
            "get_masterdata_from_crossref": {
                "script": self.get_masterdata_from_crossref,
                "source_correction_hint": "ask the publisher to correct the metadata"
                " (see https://www.crossref.org/blog/"
                "metadata-corrections-updates-and-additions-in-metadata-manager/",
            },
            "get_masterdata_from_dblp": {
                "script": self.get_masterdata_from_dblp,
                "source_correction_hint": "send and email to dblp@dagstuhl.de"
                " (see https://dblp.org/faq/How+can+I+correct+errors+in+dblp.html)",
            },
            "get_masterdata_from_open_library": {
                "script": self.get_masterdata_from_open_library,
                "source_correction_hint": "ask the publisher to correct the metadata"
                " (see https://www.crossref.org/blog/"
                "metadata-corrections-updates-and-additions-in-metadata-manager/",
            },
            "get_year_from_vol_iss_jour_crossref": {
                "script": self.get_year_from_vol_iss_jour_crossref,
                "source_correction_hint": "ask the publisher to correct the metadata"
                " (see https://www.crossref.org/blog/"
                "metadata-corrections-updates-and-additions-in-metadata-manager/",
            },
            "get_record_from_local_index": {
                "script": self.get_record_from_local_index,
                "source_correction_hint": "correct the metadata in the source "
                "repository (as linked in the provenance field)",
            },
            "remove_nicknames": {
                "script": self.remove_nicknames,
            },
            "format_minor": {
                "script": self.format_minor,
            },
            "drop_fields": {
                "script": self.drop_fields,
            },
            "remove_redundant_fields": {
                "script": self.remove_redundant_fields,
            },
            "correct_recordtype": {
                "script": self.correct_recordtype,
            },
            "update_metadata_status": {
                "script": self.update_metadata_status,
            },
        }

    def check_DBs_availability(self) -> None:
        try:
            test_rec = {
                "doi": "10.17705/1cais.04607",
                "author": "Schryen, Guido and Wagner, Gerit and Benlian, Alexander "
                "and Paré, Guy",
                "title": "A Knowledge Development Perspective on Literature Reviews: "
                "Validation of a new Typology in the IS Field",
                "ID": "SchryenEtAl2021",
                "journal": "Communications of the Association for Information Systems",
            }
            RETURNED_REC = self.__crossref_query(
                RECORD_INPUT=PrepRecord(data=test_rec)
            )[0]
            if 0 != len(RETURNED_REC.data):
                assert RETURNED_REC.data["title"] == test_rec["title"]
                assert RETURNED_REC.data["author"] == test_rec["author"]
            else:
                if not self.force_mode:
                    raise ServiceNotAvailableException("CROSSREF")
        except requests.exceptions.RequestException as e:
            print(e)
            pass
            if not self.force_mode:
                raise ServiceNotAvailableException("CROSSREF")

        try:
            test_rec = {
                "doi": "10.17705/1cais.04607",
                "author": "Schryen, Guido and Wagner, Gerit and Benlian, Alexander "
                "and Paré, Guy",
                "title": "A Knowledge Development Perspective on Literature Reviews - "
                "Validation of a new Typology in the IS Field.",
                "ID": "SchryenEtAl2021",
                "journal": "Communications of the Association for Information Systems",
                "volume": "46",
                "year": "2020",
                "colrev_status": RecordState.md_prepared,  # type: ignore
            }
            RET_REC = self.get_masterdata_from_dblp(
                RECORD=PrepRecord(data=test_rec.copy())
            )
            if 0 != len(RET_REC.data):
                assert RET_REC.data["title"] == test_rec["title"]
                assert RET_REC.data["author"] == test_rec["author"]
            else:
                if not self.force_mode:
                    raise ServiceNotAvailableException("DBLP")
        except requests.exceptions.RequestException:
            pass
            if not self.force_mode:
                raise ServiceNotAvailableException("DBLP")

        test_rec = {
            "ENTRYTYPE": "book",
            "isbn": "9781446201435",
            # 'author': 'Ridley, Diana',
            "title": "The Literature Review A Stepbystep Guide For Students",
            "ID": "Ridley2012",
            "year": "2012",
        }
        try:
            url = f"https://openlibrary.org/isbn/{test_rec['isbn']}.json"
            ret = requests.get(url, headers=self.requests_headers, timeout=self.TIMEOUT)
            if ret.status_code != 200:
                if not self.force_mode:
                    raise ServiceNotAvailableException("OPENLIBRARY")
        except requests.exceptions.RequestException:
            pass
            if not self.force_mode:
                raise ServiceNotAvailableException("OPENLIBRARY")
        return

    def load_predatory_journals(self) -> dict:

        import pkgutil

        predatory_journals = {}

        filedata = pkgutil.get_data(__name__, "template/predatory_journals_beall.csv")
        if filedata:
            for pj in filedata.decode("utf-8").splitlines():
                predatory_journals[pj.lower()] = pj.lower()

        return predatory_journals

    #
    # prep_scripts (in the order in which they should run)
    #

    def exclude_non_latin_alphabets(self, RECORD: PrepRecord) -> PrepRecord:
        def mostly_latin_alphabet(str_to_check) -> bool:
            assert len(str_to_check) != 0
            nr_non_latin = 0
            for c in str_to_check:
                if not self.alphabet_detector.only_alphabet_chars(c, "LATIN"):
                    nr_non_latin += 1
            return nr_non_latin / len(str_to_check) > 0.75

        str_to_check = " ".join(
            [
                RECORD.data.get("title", ""),
                RECORD.data.get("author", ""),
                RECORD.data.get("journal", ""),
                RECORD.data.get("booktitle", ""),
            ]
        )
        if mostly_latin_alphabet(str_to_check):
            RECORD.prescreen_exclude(reason="non_latin_alphabet")

        return RECORD

    def exclude_languages(self, RECORD: PrepRecord) -> PrepRecord:

        # TODO : switch language formats to ISO 639-1 standard language codes
        # https://github.com/flyingcircusio/pycountry
        if "language" in RECORD.data:
            RECORD.data["language"] = (
                RECORD.data["language"].replace("English", "en").replace("ENG", "en")
            )
            if RECORD.data["language"] not in self.languages_to_include:
                RECORD.prescreen_exclude(
                    reason=(
                        "language of title not in "
                        f"[{','.join(self.languages_to_include)}]"
                    )
                )

            return RECORD

        # To avoid misclassifications for short titles
        if len(RECORD.data.get("title", "")) < 30:
            return RECORD

        confidenceValues = self.language_detector.compute_language_confidence_values(
            text=RECORD.data["title"]
        )
        # Format: ENGLISH

        if self.REVIEW_MANAGER.DEBUG_MODE:
            print(RECORD.data["title"].lower())
            self.REVIEW_MANAGER.pp.pprint(confidenceValues)
        for lang, conf in confidenceValues:
            if "ENGLISH" == lang.name:
                if conf > 0.95:
                    return RECORD

        RECORD.prescreen_exclude(
            reason=f"language of title not in [{','.join(self.languages_to_include)}]"
        )

        return RECORD

    def exclude_collections(self, RECORD: PrepRecord) -> PrepRecord:

        if "proceedings" == RECORD.data["ENTRYTYPE"].lower():
            RECORD.prescreen_exclude(reason="collection/proceedings")

        return RECORD

    def exclude_predatory_journals(self, RECORD: PrepRecord) -> PrepRecord:

        if RECORD.data.get("journal", "NA").lower() in self.predatory_journals:
            RECORD.prescreen_exclude(reason="predatory_journal")

        return RECORD

    def remove_urls_with_500_errors(self, RECORD: PrepRecord) -> PrepRecord:

        try:
            if "url" in RECORD.data:
                r = self.session.request(
                    "GET",
                    RECORD.data["url"],
                    headers=self.requests_headers,
                    timeout=self.TIMEOUT,
                )
                if r.status_code >= 500:
                    del RECORD.data["url"]
        except requests.exceptions.RequestException:
            pass
        try:
            if "fulltext" in RECORD.data:
                r = self.session.request(
                    "GET",
                    RECORD.data["fulltext"],
                    headers=self.requests_headers,
                    timeout=self.TIMEOUT,
                )
                if r.status_code >= 500:
                    del RECORD.data["fulltext"]
        except requests.exceptions.RequestException:
            pass

        return RECORD

    def remove_broken_IDs(self, RECORD: PrepRecord) -> PrepRecord:

        if "doi" in RECORD.data:
            # https://www.crossref.org/blog/dois-and-matching-regular-expressions/
            d = re.match(r"^10.\d{4,9}\/", RECORD.data["doi"])
            if not d:
                del RECORD.data["doi"]
        if "isbn" in RECORD.data:
            isbn = RECORD.data["isbn"].replace("-", "").replace(" ", "")
            url = f"https://openlibrary.org/isbn/{isbn}.json"
            ret = self.session.request(
                "GET", url, headers=self.requests_headers, timeout=self.TIMEOUT
            )
            if '"error": "notfound"' in ret.text:
                del RECORD.data["isbn"]

        return RECORD

    def global_ids_consistency_check(self, RECORD: PrepRecord) -> PrepRecord:
        """When metadata provided by DOI/crossref or on the website (url) differs from
        the RECORD: set status to md_needs_manual_preparation."""

        from copy import deepcopy

        fields_to_check = ["author", "title", "journal", "year", "volume", "number"]

        if "doi" in RECORD.data:
            R_COPY = PrepRecord(data=deepcopy(RECORD.get_data()))
            CROSSREF_MD = self.get_masterdata_from_crossref(RECORD=R_COPY)
            for k, v in CROSSREF_MD.data.items():
                if k not in fields_to_check:
                    continue
                if not isinstance(v, str):
                    continue
                if k in RECORD.data:
                    if len(CROSSREF_MD.data[k]) < 5 or len(RECORD.data[k]) < 5:
                        continue
                    if (
                        fuzz.partial_ratio(
                            RECORD.data[k].lower(), CROSSREF_MD.data[k].lower()
                        )
                        < 70
                    ):
                        RECORD.data[
                            "colrev_status"
                        ] = RecordState.md_needs_manual_preparation
                        RECORD.add_masterdata_provenance_hint(
                            field=k, hint=f"disagreement with doi metadata ({v})"
                        )

        if "url" in RECORD.data:
            R_COPY = PrepRecord(data=deepcopy(RECORD.get_data()))
            URL_MD = self.retrieve_md_from_url(RECORD=R_COPY)
            for k, v in URL_MD.data.items():
                if k not in fields_to_check:
                    continue
                if not isinstance(v, str):
                    continue
                if k in RECORD.data:
                    if len(URL_MD.data[k]) < 5 or len(RECORD.data[k]) < 5:
                        continue
                    if (
                        fuzz.partial_ratio(
                            RECORD.data[k].lower(), URL_MD.data[k].lower()
                        )
                        < 70
                    ):
                        RECORD.data[
                            "colrev_status"
                        ] = RecordState.md_needs_manual_preparation
                        RECORD.add_masterdata_provenance_hint(
                            field=k,
                            hint=f"disagreement with website metadata ({v})",
                        )

        return RECORD

    def prep_curated(self, RECORD: PrepRecord) -> PrepRecord:
        if RECORD.masterdata_is_curated():
            if RecordState.md_imported == RECORD.data["colrev_status"]:
                RECORD.data["colrev_status"] = RecordState.md_prepared
        return RECORD

    def format(self, RECORD: PrepRecord) -> PrepRecord:

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
            if field in RECORD.data:
                RECORD.data[field] = (
                    RECORD.data[field]
                    .replace("\n", " ")
                    .rstrip()
                    .lstrip()
                    .replace("{", "")
                    .replace("}", "")
                )

        if "author" in RECORD.data:
            # DBLP appends identifiers to non-unique authors
            RECORD.data.update(
                author=str(re.sub(r"[0-9]{4}", "", RECORD.data["author"]))
            )

            # fix name format
            if (1 == len(RECORD.data["author"].split(" ")[0])) or (
                ", " not in RECORD.data["author"]
            ):
                RECORD.data.update(
                    author=self.format_author_field(input_string=RECORD.data["author"])
                )

        if "title" in RECORD.data:
            RECORD.data.update(
                title=re.sub(r"\s+", " ", RECORD.data["title"]).rstrip(".")
            )
            if "UNKNOWN" != RECORD.data["title"]:
                RECORD.data.update(
                    title=self.__format_if_mostly_upper(
                        input_string=RECORD.data["title"]
                    )
                )

        if "booktitle" in RECORD.data:
            if "UNKNOWN" != RECORD.data["booktitle"]:
                RECORD.data.update(
                    booktitle=self.__format_if_mostly_upper(
                        input_string=RECORD.data["booktitle"], case="title"
                    )
                )

                stripped_btitle = re.sub(r"\d{4}", "", RECORD.data["booktitle"])
                stripped_btitle = re.sub(r"\d{1,2}th", "", stripped_btitle)
                stripped_btitle = re.sub(r"\d{1,2}nd", "", stripped_btitle)
                stripped_btitle = re.sub(r"\d{1,2}rd", "", stripped_btitle)
                stripped_btitle = re.sub(r"\d{1,2}st", "", stripped_btitle)
                stripped_btitle = re.sub(r"\([A-Z]{3,6}\)", "", stripped_btitle)
                stripped_btitle = stripped_btitle.replace(
                    "Proceedings of the", ""
                ).replace("Proceedings", "")
                stripped_btitle = stripped_btitle.lstrip().rstrip()
                RECORD.data.update(booktitle=stripped_btitle)

        if "date" in RECORD.data and "year" not in RECORD.data:
            year = re.search(r"\d{4}", RECORD.data["date"])
            if year:
                RECORD.data["year"] = year.group(0)

        if "journal" in RECORD.data:
            if len(RECORD.data["journal"]) > 10 and "UNKNOWN" != RECORD.data["journal"]:
                RECORD.data.update(
                    journal=self.__format_if_mostly_upper(
                        input_string=RECORD.data["journal"], case="title"
                    )
                )

        if "pages" in RECORD.data:
            if "N.PAG" == RECORD.data.get("pages", ""):
                del RECORD.data["pages"]
            else:
                RECORD.data.update(
                    pages=self.__unify_pages_field(input_string=RECORD.data["pages"])
                )
                if (
                    not re.match(r"^\d*$", RECORD.data["pages"])
                    and not re.match(r"^\d*--\d*$", RECORD.data["pages"])
                    and not re.match(r"^[xivXIV]*--[xivXIV]*$", RECORD.data["pages"])
                ):
                    self.REVIEW_MANAGER.report_logger.info(
                        f' {RECORD.data["ID"]}:'.ljust(self.PAD, " ")
                        + f'Unusual pages: {RECORD.data["pages"]}'
                    )

        if "language" in RECORD.data:
            # TODO : use https://pypi.org/project/langcodes/
            RECORD.data["language"] = (
                RECORD.data["language"].replace("English", "en").replace("ENG", "en")
            )

        if "doi" in RECORD.data:
            RECORD.data.update(
                doi=RECORD.data["doi"].replace("http://dx.doi.org/", "").upper()
            )

        if "number" not in RECORD.data and "issue" in RECORD.data:
            RECORD.data.update(number=RECORD.data["issue"])
            del RECORD.data["issue"]
        if "volume" in RECORD.data:
            RECORD.data.update(volume=RECORD.data["volume"].replace("Volume ", ""))

        if "url" in RECORD.data and "fulltext" in RECORD.data:
            if RECORD.data["url"] == RECORD.data["fulltext"]:
                del RECORD.data["fulltext"]

        return RECORD

    def resolve_crossrefs(self, RECORD: PrepRecord) -> PrepRecord:
        def read_next_record_str() -> typing.Iterator[str]:
            with open(
                self.REVIEW_MANAGER.paths["MAIN_REFERENCES"], encoding="utf8"
            ) as f:
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
            # we need to trace based on the colrev_origin
            crossref_origin = record["colrev_origin"]
            crossref_origin = crossref_origin[: crossref_origin.rfind("/")]
            crossref_origin = crossref_origin + "/" + record["crossref"]
            for record_string in read_next_record_str():
                if crossref_origin in record_string:
                    records_dict = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                        load_str=record_string
                    )
                    record = records_dict.values()[0]
                    if record["colrev_origin"] == crossref_origin:
                        return record
            return {}

        if "crossref" in RECORD.data:
            crossref_record = get_crossref_record(RECORD.data)
            if 0 != len(crossref_record):
                for k, v in crossref_record.items():
                    if k not in RECORD.data:
                        RECORD.data[k] = v
        return RECORD

    def get_doi_from_sem_scholar(self, RECORD: PrepRecord) -> PrepRecord:

        try:
            search_api_url = (
                "https://api.semanticscholar.org/graph/v1/paper/search?query="
            )
            url = search_api_url + RECORD.data.get("title", "").replace(" ", "+")

            RETRIEVED_RECORD = self.retrieve_record_from_semantic_scholar(
                url=url, RECORD_IN=RECORD
            )
            if "sem_scholar_id" not in RETRIEVED_RECORD.data:
                return RECORD

            # Remove fields that are not/rarely available before
            # calculating similarity metrics
            red_record_copy = RECORD.data.copy()
            for key in ["volume", "number", "number", "pages"]:
                if key in red_record_copy:
                    del red_record_copy[key]
            RED_REC_COPY = PrepRecord(data=red_record_copy)

            similarity = PrepRecord.get_retrieval_similarity(
                RECORD_ORIGINAL=RED_REC_COPY, RETRIEVED_RECORD_ORIGINAL=RETRIEVED_RECORD
            )
            if similarity > self.RETRIEVAL_SIMILARITY:
                self.REVIEW_MANAGER.logger.debug("Found matching record")
                self.REVIEW_MANAGER.logger.debug(
                    f"scholar similarity: {similarity} "
                    f"(>{self.RETRIEVAL_SIMILARITY})"
                )

                RECORD.merge(
                    MERGING_RECORD=RETRIEVED_RECORD,
                    default_source=RETRIEVED_RECORD.data["sem_scholar_id"],
                )

            else:
                self.REVIEW_MANAGER.logger.debug(
                    f"scholar similarity: {similarity} "
                    f"(<{self.RETRIEVAL_SIMILARITY})"
                )
        except KeyError:
            pass
        except UnicodeEncodeError:
            self.REVIEW_MANAGER.logger.error(
                "UnicodeEncodeError - this needs to be fixed at some time"
            )
            pass
        except requests.exceptions.RequestException:
            pass
        return RECORD

    def get_doi_from_urls(self, RECORD: PrepRecord) -> PrepRecord:

        url = RECORD.data.get("url", RECORD.data.get("fulltext", "NA"))
        if "NA" != url:
            try:
                self.REVIEW_MANAGER.logger.debug(f"Retrieve doi-md from {url}")
                headers = {
                    "user-agent": f"{__name__}  (mailto:{self.REVIEW_MANAGER.EMAIL})"
                }
                ret = self.session.request(
                    "GET", url, headers=headers, timeout=self.TIMEOUT
                )
                ret.raise_for_status()
                res = re.findall(self.doi_regex, ret.text)
                if res:
                    if len(res) == 1:
                        ret_dois = [(res[0], 1)]
                    else:
                        counter = collections.Counter(res)
                        ret_dois = counter.most_common()

                    if not ret_dois:
                        return RECORD
                    for doi, freq in ret_dois:
                        retrieved_record = {"doi": doi.upper(), "ID": RECORD.data["ID"]}
                        RETRIEVED_RECORD = PrepRecord(data=retrieved_record)
                        self.retrieve_doi_metadata(RECORD=RETRIEVED_RECORD)

                        similarity = PrepRecord.get_retrieval_similarity(
                            RECORD_ORIGINAL=RECORD,
                            RETRIEVED_RECORD_ORIGINAL=RETRIEVED_RECORD,
                        )
                        if similarity > self.RETRIEVAL_SIMILARITY:
                            RECORD.merge(
                                MERGING_RECORD=RETRIEVED_RECORD, default_source=url
                            )

                            self.REVIEW_MANAGER.report_logger.debug(
                                "Retrieved metadata based on doi from"
                                f' website: {RECORD.data["doi"]}'
                            )

            except requests.exceptions.RequestException:
                pass
        return RECORD

    def get_masterdata_from_doi(self, RECORD: PrepRecord) -> PrepRecord:
        if "doi" not in RECORD.data:
            return RECORD
        self.retrieve_doi_metadata(RECORD=RECORD)
        self.get_link_from_doi(RECORD=RECORD)
        return RECORD

    def get_masterdata_from_crossref(self, RECORD: PrepRecord) -> PrepRecord:
        # To test the metadata provided for a particular DOI use:
        # https://api.crossref.org/works/DOI

        # https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
        if len(RECORD.data.get("title", "")) > 35:
            try:

                RETRIEVED_REC_L = self.__crossref_query(RECORD_INPUT=RECORD)
                RETRIEVED_RECORD = RETRIEVED_REC_L.pop()

                retries = 0
                while not RETRIEVED_RECORD and retries < self.MAX_RETRIES_ON_ERROR:
                    retries += 1
                    RETRIEVED_REC_L = self.__crossref_query(RECORD_INPUT=RECORD)
                    RETRIEVED_RECORD = RETRIEVED_REC_L.pop()

                if 0 == len(RETRIEVED_RECORD.data):
                    return RECORD

                similarity = PrepRecord.get_retrieval_similarity(
                    RECORD_ORIGINAL=RECORD, RETRIEVED_RECORD_ORIGINAL=RETRIEVED_RECORD
                )
                if similarity > self.RETRIEVAL_SIMILARITY:
                    self.REVIEW_MANAGER.logger.debug("Found matching record")
                    self.REVIEW_MANAGER.logger.debug(
                        f"crossref similarity: {similarity} "
                        f"(>{self.RETRIEVAL_SIMILARITY})"
                    )
                    source_link = (
                        f"https://api.crossref.org/works/{RETRIEVED_RECORD.data['doi']}"
                    )
                    RECORD.merge(
                        MERGING_RECORD=RETRIEVED_RECORD, default_source=source_link
                    )
                    self.get_link_from_doi(RECORD=RECORD)
                    RECORD.set_masterdata_complete()
                    RECORD.set_status(target_state=RecordState.md_prepared)

                else:
                    self.REVIEW_MANAGER.logger.debug(
                        f"crossref similarity: {similarity} "
                        f"(<{self.RETRIEVAL_SIMILARITY})"
                    )

            except requests.exceptions.RequestException:
                pass
            except IndexError:
                pass
            except KeyboardInterrupt:
                sys.exit()
        return RECORD

    def get_masterdata_from_dblp(self, RECORD: PrepRecord) -> PrepRecord:
        if "dblp_key" in RECORD.data:
            return RECORD

        try:
            query = "" + RECORD.data.get("title", "").replace("-", "_")
            # Note: queries combining title+author/journal do not seem to work any more
            # if "author" in record:
            #     query = query + "_" + record["author"].split(",")[0]
            # if "booktitle" in record:
            #     query = query + "_" + record["booktitle"]
            # if "journal" in record:
            #     query = query + "_" + record["journal"]
            # if "year" in record:
            #     query = query + "_" + record["year"]

            for RETRIEVED_RECORD in self.retrieve_dblp_records(query=query):
                similarity = PrepRecord.get_retrieval_similarity(
                    RECORD_ORIGINAL=RECORD, RETRIEVED_RECORD_ORIGINAL=RETRIEVED_RECORD
                )
                if similarity > self.RETRIEVAL_SIMILARITY:
                    self.REVIEW_MANAGER.logger.debug("Found matching record")
                    self.REVIEW_MANAGER.logger.debug(
                        f"dblp similarity: {similarity} "
                        f"(>{self.RETRIEVAL_SIMILARITY})"
                    )
                    RECORD.merge(
                        MERGING_RECORD=RETRIEVED_RECORD,
                        default_source=RETRIEVED_RECORD.data["dblp_key"],
                    )
                    RECORD.set_masterdata_complete()
                    RECORD.set_status(target_state=RecordState.md_prepared)
                else:
                    self.REVIEW_MANAGER.logger.debug(
                        f"dblp similarity: {similarity} "
                        f"(<{self.RETRIEVAL_SIMILARITY})"
                    )
        except UnicodeEncodeError:
            pass
        except requests.exceptions.RequestException:
            pass
        return RECORD

    def get_masterdata_from_open_library(self, RECORD: PrepRecord) -> PrepRecord:

        if RECORD.data.get("ENTRYTYPE", "NA") != "book":
            return RECORD

        try:
            # TODO : integrate more functionality into __open_library_json_to_record()
            url = "NA"
            if "isbn" in RECORD.data:
                isbn = RECORD.data["isbn"].replace("-", "").replace(" ", "")
                url = f"https://openlibrary.org/isbn/{isbn}.json"
                ret = self.session.request(
                    "GET", url, headers=self.requests_headers, timeout=self.TIMEOUT
                )
                ret.raise_for_status()
                self.REVIEW_MANAGER.logger.debug(url)
                if '"error": "notfound"' in ret.text:
                    del RECORD.data["isbn"]

                item = json.loads(ret.text)

            else:
                base_url = "https://openlibrary.org/search.json?"
                url = ""
                if RECORD.data.get("author", "NA").split(",")[0]:
                    url = (
                        base_url
                        + "&author="
                        + RECORD.data.get("author", "NA").split(",")[0]
                    )
                if "inbook" == RECORD.data["ENTRYTYPE"] and "editor" in RECORD.data:
                    if RECORD.data.get("editor", "NA").split(",")[0]:
                        url = (
                            base_url
                            + "&author="
                            + RECORD.data.get("editor", "NA").split(",")[0]
                        )
                if base_url not in url:
                    return RECORD

                title = RECORD.data.get("title", RECORD.data.get("booktitle", "NA"))
                if len(title) < 10:
                    return RECORD
                if ":" in title:
                    title = title[: title.find(":")]  # To catch sub-titles
                url = url + "&title=" + title.replace(" ", "+")
                ret = self.session.request(
                    "GET", url, headers=self.requests_headers, timeout=self.TIMEOUT
                )
                ret.raise_for_status()
                self.REVIEW_MANAGER.logger.debug(url)

                # if we have an exact match, we don't need to check the similarity
                if '"numFoundExact": true,' not in ret.text:
                    return RECORD

                data = json.loads(ret.text)
                items = data["docs"]
                if not items:
                    return RECORD
                item = items[0]

            RETRIEVED_RECORD = self.__open_library_json_to_record(item=item, url=url)

            RECORD.merge(MERGING_RECORD=RETRIEVED_RECORD, default_source=url)

            # if "title" in RECORD.data and "booktitle" in RECORD.data:
            #     del RECORD.data["booktitle"]

        except requests.exceptions.RequestException:
            pass
        except UnicodeEncodeError:
            self.REVIEW_MANAGER.logger.error(
                "UnicodeEncodeError - this needs to be fixed at some time"
            )
            pass
        return RECORD

    def get_year_from_vol_iss_jour_crossref(self, RECORD: PrepRecord) -> PrepRecord:
        # The year depends on journal x volume x issue
        if (
            "journal" in RECORD.data
            and "volume" in RECORD.data
            and "number" in RECORD.data
        ) and "year" not in RECORD.data:
            pass
        else:
            return RECORD

        try:
            modified_record = RECORD.data.copy()
            modified_record = {
                k: v
                for k, v in modified_record.items()
                if k in ["journal", "volume", "number"]
            }

            # http://api.crossref.org/works?
            # query.container-title=%22MIS+Quarterly%22&query=%2216+2%22

            RETRIEVED_REC_L = self.__crossref_query(
                RECORD_INPUT=RECORD, jour_vol_iss_list=True
            )
            retries = 0
            while not RETRIEVED_REC_L and retries < self.MAX_RETRIES_ON_ERROR:
                retries += 1
                RETRIEVED_REC_L = self.__crossref_query(
                    RECORD_INPUT=RECORD, jour_vol_iss_list=True
                )
            if 0 == len(RETRIEVED_REC_L):
                return RECORD

            RETRIEVED_RECORDS = [
                REC
                for REC in RETRIEVED_REC_L
                if REC.data.get("volume", "NA") == RECORD.data.get("volume", "NA")
                and REC.data.get("journal", "NA") == RECORD.data.get("journal", "NA")
                and REC.data.get("number", "NA") == RECORD.data.get("number", "NA")
            ]
            years = [r.data["year"] for r in RETRIEVED_RECORDS]
            if len(years) == 0:
                return RECORD
            most_common = max(years, key=years.count)
            self.REVIEW_MANAGER.logger.debug(most_common)
            self.REVIEW_MANAGER.logger.debug(years.count(most_common))
            if years.count(most_common) > 3:
                RECORD.update_field(
                    field="year", value=most_common, source="CROSSREF(average)"
                )
        except requests.exceptions.RequestException:
            pass
        except KeyboardInterrupt:
            sys.exit()

        return RECORD

    def get_record_from_local_index(self, RECORD: PrepRecord) -> PrepRecord:
        # TODO: how to distinguish masterdata and complementary CURATED sources?

        # Note : cannot use LOCAL_INDEX as an attribute of PrepProcess
        # because it creates problems with multiprocessing
        LOCAL_INDEX = LocalIndex()

        retrieved = False
        try:
            retrieved_record = LOCAL_INDEX.retrieve(
                record=RECORD.get_data(), include_file=False
            )
            retrieved = True
        except (RecordNotInIndexException, NotFoundError):
            pass
            try:
                # Note: Records can be CURATED without being indexed
                if not RECORD.masterdata_is_curated():
                    retrieved_record = LOCAL_INDEX.retrieve_from_toc(
                        record=RECORD.data,
                        similarity_threshold=self.RETRIEVAL_SIMILARITY,
                        include_file=False,
                    )
                    retrieved = True
            except (RecordNotInIndexException, NotFoundError):
                pass

        if retrieved:
            RETRIEVED_RECORD = PrepRecord(data=retrieved_record)

            default_source = "UNDETERMINED"
            if "colrev_masterdata_provenance" in RETRIEVED_RECORD.data:
                default_source = RETRIEVED_RECORD.data["colrev_masterdata_provenance"][
                    "CURATED"
                ]["source"]

            RECORD.merge(
                MERGING_RECORD=RETRIEVED_RECORD,
                default_source=default_source,
            )

            git_repo = git.Repo(str(self.REVIEW_MANAGER.path))
            cur_project_source_paths = [str(self.REVIEW_MANAGER.path)]
            for remote in git_repo.remotes:
                if remote.url:
                    shared_url = remote.url
                    shared_url = shared_url.rstrip(".git")
                    cur_project_source_paths.append(shared_url)
                    break

            # extend fields_to_keep (to retrieve all fields from the index)
            for k in retrieved_record.keys():
                if k not in self.fields_to_keep:
                    self.fields_to_keep.append(k)

        return RECORD

    def remove_nicknames(self, RECORD: PrepRecord) -> PrepRecord:
        if "author" in RECORD.data:
            # Replace nicknames in parentheses
            RECORD.data["author"] = re.sub(r"\([^)]*\)", "", RECORD.data["author"])
            RECORD.data["author"] = RECORD.data["author"].replace("  ", " ")
        return RECORD

    def format_minor(self, RECORD: PrepRecord) -> PrepRecord:

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
            if field in RECORD.data:
                RECORD.data[field] = (
                    str(RECORD.data[field])
                    .replace("\n", " ")
                    .rstrip()
                    .lstrip()
                    .replace("{", "")
                    .replace("}", "")
                    .rstrip(",")
                )
                RECORD.data[field] = re.sub(r"\s+", " ", RECORD.data[field])
                if field in [
                    "colrev_masterdata_provenance",
                    "colrev_data_provenance",
                    "doi",
                ]:
                    continue
                # Note : some dois (and their provenance) contain html entities
                RECORD.data[field] = re.sub(self.HTML_CLEANER, "", RECORD.data[field])

        if RECORD.data.get("volume", "") == "ahead-of-print":
            del RECORD.data["volume"]
        if RECORD.data.get("number", "") == "ahead-of-print":
            del RECORD.data["number"]

        return RECORD

    def drop_fields(self, RECORD: PrepRecord) -> PrepRecord:
        for key in list(RECORD.data.keys()):
            if key not in self.fields_to_keep:
                RECORD.data.pop(key)
                self.REVIEW_MANAGER.report_logger.info(f"Dropped {key} field")
        for key in list(RECORD.data.keys()):
            if key in self.fields_to_keep:
                continue
            if RECORD.data[key] in ["", "NA"]:
                del RECORD.data[key]

        if RECORD.data.get("publisher", "") in ["researchgate.net"]:
            del RECORD.data["publisher"]

        if "volume" in RECORD.data.keys() and "number" in RECORD.data.keys():
            # Note : cannot use LOCAL_INDEX as an attribute of PrepProcess
            # because it creates problems with multiprocessing
            LOCAL_INDEX = LocalIndex()

            fields_to_remove = LOCAL_INDEX.get_fields_to_remove(
                record=RECORD.get_data()
            )
            for field_to_remove in fields_to_remove:
                if field_to_remove in RECORD.data:
                    del RECORD.data[field_to_remove]

        return RECORD

    def remove_redundant_fields(self, RECORD: PrepRecord) -> PrepRecord:
        if "article" == RECORD.data["ENTRYTYPE"]:
            if "journal" in RECORD.data and "booktitle" in RECORD.data:
                if (
                    fuzz.partial_ratio(
                        RECORD.data["journal"].lower(), RECORD.data["booktitle"].lower()
                    )
                    / 100
                    > 0.9
                ):
                    del RECORD.data["booktitle"]
        if "inproceedings" == RECORD.data["ENTRYTYPE"]:
            if "journal" in RECORD.data and "booktitle" in RECORD.data:
                if (
                    fuzz.partial_ratio(
                        RECORD.data["journal"].lower(), RECORD.data["booktitle"].lower()
                    )
                    / 100
                    > 0.9
                ):
                    del RECORD.data["journal"]
        return RECORD

    def correct_recordtype(self, RECORD: PrepRecord) -> PrepRecord:

        if RECORD.has_inconsistent_fields() and not RECORD.masterdata_is_curated():
            pass
        else:
            return RECORD

        if self.RETRIEVAL_SIMILARITY > 0.9:
            return RECORD

        if (
            "dissertation" in RECORD.data.get("fulltext", "NA").lower()
            and RECORD.data["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = RECORD.data["ENTRYTYPE"]
            RECORD.data.update(ENTRYTYPE="phdthesis")
            self.REVIEW_MANAGER.report_logger.info(
                f' {RECORD.data["ID"]}'.ljust(self.PAD, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("dissertation" in fulltext link)'
            )

        if (
            "thesis" in RECORD.data.get("fulltext", "NA").lower()
            and RECORD.data["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = RECORD.data["ENTRYTYPE"]
            RECORD.data.update(ENTRYTYPE="phdthesis")
            self.REVIEW_MANAGER.report_logger.info(
                f' {RECORD.data["ID"]}'.ljust(self.PAD, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("thesis" in fulltext link)'
            )

        if (
            "This thesis" in RECORD.data.get("abstract", "NA").lower()
            and RECORD.data["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = RECORD.data["ENTRYTYPE"]
            RECORD.data.update(ENTRYTYPE="phdthesis")
            self.REVIEW_MANAGER.report_logger.info(
                f' {RECORD.data["ID"]}'.ljust(self.PAD, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("thesis" in abstract)'
            )

        # Journal articles should not have booktitles/series set.
        if "article" == RECORD.data["ENTRYTYPE"]:
            if "booktitle" in RECORD.data:
                if "journal" not in RECORD.data:
                    RECORD.data.update(journal=RECORD.data["booktitle"])
                    del RECORD.data["booktitle"]
            if "series" in RECORD.data:
                if "journal" not in RECORD.data:
                    RECORD.data.update(journal=RECORD.data["series"])
                    del RECORD.data["series"]

        if "article" == RECORD.data["ENTRYTYPE"]:
            if "journal" not in RECORD.data:
                if "series" in RECORD.data:
                    journal_string = RECORD.data["series"]
                    RECORD.data.update(journal=journal_string)
                    del RECORD.data["series"]

        return RECORD

    def update_metadata_status(self, RECORD: PrepRecord) -> PrepRecord:

        RECORD.check_potential_retracts()
        if "crossmark" in RECORD.data:
            return RECORD
        if RECORD.masterdata_is_curated():
            RECORD.set_status(target_state=RecordState.md_prepared)
            return RECORD

        self.REVIEW_MANAGER.logger.debug(
            f'is_complete({RECORD.data["ID"]}): {RECORD.masterdata_is_complete()}'
        )

        self.REVIEW_MANAGER.logger.debug(
            f'has_inconsistent_fields({RECORD.data["ID"]}): '
            f"{RECORD.has_inconsistent_fields()}"
        )
        self.REVIEW_MANAGER.logger.debug(
            f'has_incomplete_fields({RECORD.data["ID"]}): '
            f"{RECORD.has_incomplete_fields()}"
        )

        if (
            not RECORD.masterdata_is_complete()
            or RECORD.has_incomplete_fields()
            or RECORD.has_inconsistent_fields()
        ):
            RECORD.set_status(target_state=RecordState.md_needs_manual_preparation)
        else:
            RECORD.set_status(target_state=RecordState.md_prepared)

        return RECORD

    #
    # END prep scripts section
    #

    def get_link_from_doi(self, RECORD: PrepRecord) -> PrepRecord:

        doi_url = f"https://www.doi.org/{RECORD.data['doi']}"

        # TODO : retry for 50X
        # from requests.adapters import HTTPAdapter
        # from requests.adapters import Retry
        # example for testing: ({'doi':'10.1177/02683962221086300'})
        # s = requests.Session()
        # headers = {"user-agent": f"{__name__} (mailto:{self.REVIEW_MANAGER.EMAIL})"}
        # retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 502, 503, 504 ])
        # s.mount('https://', HTTPAdapter(max_retries=retries))
        # ret = s.get(url, headers=headers)
        # print(ret)

        def meta_redirect(content: str):
            soup = BeautifulSoup(content, "lxml")
            result = soup.find("meta", attrs={"http-equiv": "REFRESH"})
            if result:
                wait, text = result["content"].split(";")
                if "http" in text:
                    url = text[text.lower().find("http") :]
                    url = unquote(url, encoding="utf-8", errors="replace")
                    url = url[: url.find("?")]
                    return str(url)
            return None

        url = doi_url
        try:
            ret = self.session.request(
                "GET", doi_url, headers=self.requests_headers, timeout=self.TIMEOUT
            )
            if 503 == ret.status_code:
                return RECORD
            elif (
                200 == ret.status_code
                and "doi.org" not in ret.url
                and "linkinghub" not in ret.url
            ):
                url = ret.url
            else:
                # follow the chain of redirects
                while meta_redirect(ret.content.decode("utf-8")):
                    url = meta_redirect(ret.content.decode("utf-8"))
                    ret = self.session.request(
                        "GET", url, headers=self.requests_headers, timeout=self.TIMEOUT
                    )
            RECORD.update_field(field="url", value=str(url), source=doi_url)
        except requests.exceptions.RequestException:
            pass
        return RECORD

    def retrieve_md_from_url(self, RECORD: PrepRecord) -> PrepRecord:
        from colrev_core.environment import ZoteroTranslationService

        ZOTERO_TRANSLATION_SERVICE = ZoteroTranslationService()
        ZOTERO_TRANSLATION_SERVICE.start_zotero_translators()

        # TODO : change to the similar merge()/fuse_best_field structure?

        try:
            content_type_header = {"Content-type": "text/plain"}
            headers = {**self.requests_headers, **content_type_header}
            et = requests.post(
                "http://127.0.0.1:1969/web",
                headers=headers,
                data=RECORD.data["url"],
                timeout=self.TIMEOUT,
            )

            if et.status_code != 200:
                return RECORD

            items = json.loads(et.content.decode())
            if len(items) == 0:
                return RECORD
            item = items[0]
            if "Shibboleth Authentication Request" == item["title"]:
                return RECORD

            # self.REVIEW_MANAGER.pp.pprint(item)
            RECORD.data["ID"] = item["key"]
            RECORD.data["ENTRYTYPE"] = "article"  # default
            if "journalArticle" == item.get("itemType", ""):
                RECORD.data["ENTRYTYPE"] = "article"
                if "publicationTitle" in item:
                    RECORD.data["journal"] = item["publicationTitle"]
                if "volume" in item:
                    RECORD.data["volume"] = item["volume"]
                if "issue" in item:
                    RECORD.data["number"] = item["issue"]
            if "conferencePaper" == item.get("itemType", ""):
                RECORD.data["ENTRYTYPE"] = "inproceedings"
                if "proceedingsTitle" in item:
                    RECORD.data["booktitle"] = item["proceedingsTitle"]
            if "creators" in item:
                author_str = ""
                for creator in item["creators"]:
                    author_str += (
                        " and "
                        + creator.get("lastName", "")
                        + ", "
                        + creator.get("firstName", "")
                    )
                author_str = author_str[5:]  # drop the first " and "
                RECORD.data["author"] = author_str
            if "title" in item:
                RECORD.data["title"] = item["title"]
            if "doi" in item:
                RECORD.data["doi"] = item["doi"]
            if "date" in item:
                year = re.search(r"\d{4}", item["date"])
                if year:
                    RECORD.data["year"] = year.group(0)
            if "pages" in item:
                RECORD.data["pages"] = item["pages"]
            if "url" in item:
                if "https://doi.org/" in item["url"]:
                    RECORD.data["doi"] = item["url"].replace("https://doi.org/", "")
                    DUMMY_R = PrepRecord(data={"doi": RECORD.data["doi"]})
                    RET_REC = self.get_link_from_doi(RECORD=DUMMY_R)
                    if "https://doi.org/" not in RET_REC.data["url"]:
                        RECORD.data["url"] = RET_REC.data["url"]
                else:
                    RECORD.data["url"] = item["url"]

            if "tags" in item:
                if len(item["tags"]) > 0:
                    keywords = ", ".join([k["tag"] for k in item["tags"]])
                    RECORD.data["keywords"] = keywords
        except (json.decoder.JSONDecodeError, UnicodeEncodeError):
            pass
        except requests.exceptions.RequestException:
            pass
        except KeyError:
            pass
        return RECORD

    def __format_if_mostly_upper(
        self, *, input_string: str, case: str = "capitalize"
    ) -> str:
        def percent_upper_chars(input_string: str) -> float:
            return sum(map(str.isupper, input_string)) / len(input_string)

        if not re.match(r"[a-zA-Z]+", input_string):
            return input_string

        if percent_upper_chars(input_string) > 0.8:
            if "capitalize" == case:
                return input_string.capitalize()
            if "title" == case:
                input_string = (
                    input_string.title()
                    .replace(" Of ", " of ")
                    .replace(" For ", " for ")
                    .replace(" The ", " the ")
                    .replace("Ieee", "IEEE")
                    .replace("Acm", "ACM")
                    .replace(" And ", " and ")
                )
                return input_string

        return input_string

    def format_author_field(self, *, input_string: str) -> str:
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

    def __unify_pages_field(self, *, input_string: str) -> str:
        if not isinstance(input_string, str):
            return input_string
        if 1 == input_string.count("-"):
            input_string = input_string.replace("-", "--")
        input_string = (
            input_string.replace("–", "--")
            .replace("----", "--")
            .replace(" -- ", "--")
            .rstrip(".")
        )
        return input_string

    def crossref_json_to_record(self, *, item: dict) -> dict:
        # Note: the format differst between crossref and doi.org
        record: dict = {}

        # Note : better use the doi-link resolution
        # if "link" in item:
        #     fulltext_link_l = [
        #         u["URL"] for u in item["link"] if "pdf" in u["content-type"]
        #     ]
        #     if len(fulltext_link_l) == 1:
        #         record["fulltext"] = fulltext_link_l.pop()
        #     item["link"] = [u for u in item["link"] if "pdf" not in u["content-type"]]
        #     if len(item["link"]) >= 1:
        #         link = item["link"][0]["URL"]
        #         if link != record.get("fulltext", ""):
        #             record["link"] = link

        if "title" in item:
            if isinstance(item["title"], list):
                if len(item["title"]) > 0:
                    retrieved_title = item["title"][0]
                    retrieved_title = re.sub(r"\s+", " ", str(retrieved_title))
                    retrieved_title = retrieved_title.replace("\n", " ")
                    record.update(title=retrieved_title)
            elif isinstance(item["title"], str):
                retrieved_title = item["title"]
                record.update(title=retrieved_title)

        container_title = ""
        if "container-title" in item:
            if isinstance(item["container-title"], list):
                if len(item["container-title"]) > 0:
                    container_title = item["container-title"][0]
            elif isinstance(item["container-title"], str):
                container_title = item["container-title"]

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
            record.update(doi=item["DOI"].upper())

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
                record.update(
                    pages=self.__unify_pages_field(input_string=str(retrieved_pages))
                )
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
                retrieved_abstract = re.sub(
                    r"<\/?jats\:[^>]*>", " ", retrieved_abstract
                )
                retrieved_abstract = re.sub(r"\s+", " ", retrieved_abstract)
                retrieved_abstract = str(retrieved_abstract).replace("\n", "")
                retrieved_abstract = retrieved_abstract.lstrip().rstrip()
                record.update(abstract=retrieved_abstract)

        if "language" in item:
            record["language"] = item["language"]

        if "content-domain" in item:
            if "crossmark" in item["content-domain"]:
                if item["content-domain"]["crossmark"]:
                    record["crossmark"] = "True"

        for k, v in record.items():
            record[k] = v.replace("{", "").replace("}", "")
            if k in ["colrev_masterdata_provenance", "colrev_data_provenance", "doi"]:
                continue
            # Note : some dois (and their provenance) contain html entities
            record[k] = html.unescape(v)

        return record

    def __crossref_query(
        self, *, RECORD_INPUT: PrepRecord, jour_vol_iss_list: bool = False
    ) -> typing.List[PrepRecord]:
        # https://github.com/CrossRef/rest-api-doc
        api_url = "https://api.crossref.org/works?"

        # Note : only returning a multiple-item list for jour_vol_iss_list

        RECORD = PrepRecord(data=RECORD_INPUT.data.copy())

        if not jour_vol_iss_list:
            params = {"rows": "15"}
            bibl = (
                RECORD.data["title"].replace("-", "_")
                + " "
                + RECORD.data.get("year", "")
            )
            bibl = re.sub(r"[\W]+", "", bibl.replace(" ", "_"))
            params["query.bibliographic"] = bibl.replace("_", " ")

            container_title = RECORD.get_container_title()
            if "." not in container_title:
                container_title = container_title.replace(" ", "_")
                container_title = re.sub(r"[\W]+", "", container_title)
                params["query.container-title"] = container_title.replace("_", " ")

            author_last_names = [
                x.split(",")[0] for x in RECORD.data.get("author", "").split(" and ")
            ]
            author_string = " ".join(author_last_names)
            author_string = re.sub(r"[\W]+", "", author_string.replace(" ", "_"))
            params["query.author"] = author_string.replace("_", " ")
        else:
            params = {"rows": "25"}
            container_title = re.sub(r"[\W]+", " ", RECORD.data["journal"])
            params["query.container-title"] = container_title.replace("_", " ")

            query_field = ""
            if "volume" in RECORD.data:
                query_field = RECORD.data["volume"]
            if "number" in RECORD.data:
                query_field = query_field + "+" + RECORD.data["number"]
            params["query"] = query_field

        url = api_url + urllib.parse.urlencode(params)
        headers = {"user-agent": f"{__name__} (mailto:{self.REVIEW_MANAGER.EMAIL})"}
        record_list = []
        try:
            self.REVIEW_MANAGER.logger.debug(url)
            ret = self.session.request(
                "GET", url, headers=headers, timeout=self.TIMEOUT
            )
            ret.raise_for_status()
            if ret.status_code != 200:
                self.REVIEW_MANAGER.logger.debug(
                    f"crossref_query failed with status {ret.status_code}"
                )
                return []

            data = json.loads(ret.text)
            items = data["message"]["items"]
            most_similar = 0
            most_similar_record = {}
            for item in items:
                if "title" not in item:
                    continue

                retrieved_record = self.crossref_json_to_record(item=item)

                title_similarity = fuzz.partial_ratio(
                    retrieved_record["title"].lower(),
                    RECORD.data.get("title", "").lower(),
                )
                container_similarity = fuzz.partial_ratio(
                    PrepRecord(data=retrieved_record).get_container_title().lower(),
                    RECORD.get_container_title().lower(),
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

                RETRIEVED_RECORD = PrepRecord(data=retrieved_record)
                RETRIEVED_RECORD.add_provenance_all(
                    source=f'https://api.crossref.org/works/{retrieved_record["doi"]}'
                )

                if jour_vol_iss_list:
                    record_list.append(RETRIEVED_RECORD)
                if most_similar < similarity:
                    most_similar = similarity
                    most_similar_record = RETRIEVED_RECORD.get_data()
        except json.decoder.JSONDecodeError:
            pass
        except requests.exceptions.RequestException:
            return []

        if not jour_vol_iss_list:
            record_list = [PrepRecord(data=most_similar_record)]

        return record_list

    def retrieve_record_from_semantic_scholar(
        self, *, url: str, RECORD_IN: PrepRecord
    ) -> PrepRecord:

        self.REVIEW_MANAGER.logger.debug(url)
        headers = {"user-agent": f"{__name__} (mailto:{self.REVIEW_MANAGER.EMAIL})"}
        ret = self.session.request("GET", url, headers=headers, timeout=self.TIMEOUT)
        ret.raise_for_status()

        data = json.loads(ret.text)
        items = data["data"]
        if len(items) == 0:
            return RECORD_IN
        if "paperId" not in items[0]:
            return RECORD_IN

        paper_id = items[0]["paperId"]
        record_retrieval_url = "https://api.semanticscholar.org/v1/paper/" + paper_id
        self.REVIEW_MANAGER.logger.debug(record_retrieval_url)
        ret_ent = self.session.request(
            "GET", record_retrieval_url, headers=headers, timeout=self.TIMEOUT
        )
        ret_ent.raise_for_status()
        item = json.loads(ret_ent.text)

        retrieved_record: dict = {}
        if "authors" in item:
            authors_string = " and ".join(
                [author["name"] for author in item["authors"] if "name" in author]
            )
            authors_string = self.format_author_field(input_string=authors_string)
            retrieved_record.update(author=authors_string)
        if "abstract" in item:
            retrieved_record.update(abstract=item["abstract"])
        if "doi" in item:
            retrieved_record.update(doi=str(item["doi"]).upper())
        if "title" in item:
            retrieved_record.update(title=item["title"])
        if "year" in item:
            retrieved_record.update(year=item["year"])
        # Note: semantic scholar does not provide data on the type of venue.
        # we therefore use the original ENTRYTYPE
        if "venue" in item:
            if "journal" in RECORD_IN.data:
                retrieved_record.update(journal=item["venue"])
            if "booktitle" in RECORD_IN.data:
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

        REC = PrepRecord(data=retrieved_record)
        REC.add_provenance_all(source=record_retrieval_url)
        return REC

    def __open_library_json_to_record(self, *, item: dict, url=str) -> PrepRecord:
        retrieved_record: dict = {}

        if "author_name" in item:
            authors_string = " and ".join(
                [
                    self.format_author_field(input_string=author)
                    for author in item["author_name"]
                ]
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

        REC = PrepRecord(data=retrieved_record)
        REC.add_provenance_all(source=url)
        return REC

    def retrieve_dblp_records(self, *, query: str = None, url: str = None) -> list:
        assert query is not None or url is not None

        def dblp_json_to_dict(item: dict) -> dict:
            # To test in browser:
            # https://dblp.org/search/publ/api?q=ADD_TITLE&format=json

            def get_dblp_venue(venue_string: str, type: str) -> str:
                # Note : venue_string should be like "behaviourIT"
                # Note : journals that have been renamed seem to return the latest
                # journal name. Example:
                # https://dblp.org/db/journals/jasis/index.html
                venue = venue_string
                api_url = "https://dblp.org/search/venue/api?q="
                url = api_url + venue_string.replace(" ", "+") + "&format=json"
                headers = {
                    "user-agent": f"{__name__} (mailto:{self.REVIEW_MANAGER.EMAIL})"
                }
                try:
                    ret = self.session.request(
                        "GET", url, headers=headers, timeout=self.TIMEOUT
                    )
                    ret.raise_for_status()
                    data = json.loads(ret.text)
                    if "hit" not in data["result"]["hits"]:
                        return ""
                    hits = data["result"]["hits"]["hit"]
                    for hit in hits:
                        if hit["info"]["type"] != type:
                            continue
                        if f"/{venue_string.lower()}/" in hit["info"]["url"].lower():
                            venue = hit["info"]["venue"]
                            break

                    venue = re.sub(r" \(.*?\)", "", venue)
                except requests.exceptions.RequestException:
                    pass
                return venue

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
                ven_key = item["key"][lpos:rpos]
                retrieved_record["journal"] = get_dblp_venue(ven_key, "Journal")
            if "Conference and Workshop Papers" == item["type"]:
                retrieved_record["ENTRYTYPE"] = "inproceedings"
                lpos = item["key"].find("/") + 1
                rpos = item["key"].rfind("/")
                ven_key = item["key"][lpos:rpos]
                retrieved_record["booktitle"] = get_dblp_venue(
                    ven_key, "Conference or Workshop"
                )
            if "title" in item:
                retrieved_record["title"] = item["title"].rstrip(".")
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
                    author_string = self.format_author_field(input_string=author_string)
                    retrieved_record["author"] = author_string

            if "key" in item:
                retrieved_record["dblp_key"] = "https://dblp.org/rec/" + item["key"]

            if "doi" in item:
                retrieved_record["doi"] = item["doi"].upper()
            if "ee" in item:
                if "https://doi.org" not in item["ee"]:
                    retrieved_record["url"] = item["ee"]

            for k, v in retrieved_record.items():
                retrieved_record[k] = html.unescape(v).replace("{", "").replace("}", "")

            return retrieved_record

        api_url = "https://dblp.org/search/publ/api?q="
        items = []

        if query:
            query = re.sub(r"[\W]+", " ", query.replace(" ", "_"))
            url = api_url + query.replace(" ", "+") + "&format=json"

        headers = {"user-agent": f"{__name__}  (mailto:{self.REVIEW_MANAGER.EMAIL})"}
        self.REVIEW_MANAGER.logger.debug(url)
        ret = self.session.request(
            "GET", url, headers=headers, timeout=self.TIMEOUT  # type: ignore
        )
        ret.raise_for_status()
        if ret.status_code == 500:
            return []

        data = json.loads(ret.text)
        if "hits" not in data["result"]:
            return []
        if "hit" not in data["result"]["hits"]:
            return []
        hits = data["result"]["hits"]["hit"]
        items = [hit["info"] for hit in hits]
        dblp_dicts = [dblp_json_to_dict(item) for item in items]
        RETRIEVED_RECORDS = [PrepRecord(data=dblp_dict) for dblp_dict in dblp_dicts]
        [R.add_provenance_all(source=R.data["dblp_key"]) for R in RETRIEVED_RECORDS]
        return RETRIEVED_RECORDS

    def retrieve_doi_metadata(self, RECORD: PrepRecord) -> PrepRecord:
        if "doi" not in RECORD.data:
            return RECORD

        # for testing:
        # curl -iL -H "accept: application/vnd.citationstyles.csl+json"
        # -H "Content-Type: application/json" http://dx.doi.org/10.1111/joop.12368

        try:
            url = "http://dx.doi.org/" + RECORD.data["doi"]
            self.REVIEW_MANAGER.logger.debug(url)
            headers = {"accept": "application/vnd.citationstyles.csl+json"}
            ret = self.session.request(
                "GET", url, headers=headers, timeout=self.TIMEOUT
            )
            ret.raise_for_status()
            if ret.status_code != 200:
                self.REVIEW_MANAGER.report_logger.info(
                    f' {RECORD.data["ID"]}'.ljust(self.PAD, " ")
                    + "metadata for "
                    + f'doi  {RECORD.data["doi"]} not (yet) available'
                )
                return RECORD

            retrieved_json = json.loads(ret.text)
            retrieved_record = self.crossref_json_to_record(item=retrieved_json)
            RETRIEVED_RECORD = PrepRecord(data=retrieved_record)
            RETRIEVED_RECORD.add_provenance_all(source=url)
            RECORD.merge(MERGING_RECORD=RETRIEVED_RECORD, default_source=url)
            RECORD.set_masterdata_complete()
            if "colrev_status" in RECORD.data:
                RECORD.set_status(target_state=RecordState.md_prepared)

        except json.decoder.JSONDecodeError:
            pass
        except requests.exceptions.RequestException:
            pass
            return RECORD

        if "title" in RECORD.data:
            RECORD.data["title"] = self.__format_if_mostly_upper(
                input_string=RECORD.data["title"]
            )
            RECORD.data["title"] = RECORD.data["title"].replace("\n", " ")

        return RECORD

    def update_masterdata_provenance(
        self, *, RECORD: PrepRecord, UNPREPARED_RECORD: PrepRecord
    ) -> PrepRecord:

        missing_fields = RECORD.missing_fields()
        if missing_fields:
            for missing_field in missing_fields:
                RECORD.add_masterdata_provenance_hint(
                    field=missing_field, hint="missing"
                )
        else:
            RECORD.set_masterdata_complete()

        inconsistencies = RECORD.get_inconsistencies()
        if inconsistencies:
            for inconsistency in inconsistencies:
                RECORD.add_masterdata_provenance_hint(
                    field=inconsistency,
                    hint="inconsistent with ENTRYTYPE",
                )
        else:
            RECORD.set_masterdata_consistent()

        incomplete_fields = RECORD.get_incomplete_fields()
        if incomplete_fields:
            for incomplete_field in incomplete_fields:
                RECORD.add_masterdata_provenance_hint(
                    field=incomplete_field, hint="incomplete"
                )
        else:
            RECORD.set_fields_complete()

        defect_fields = RECORD.get_quality_defects()
        if defect_fields:
            for defect_field in defect_fields:
                RECORD.add_masterdata_provenance_hint(
                    field=defect_field, hint="quality_defect"
                )
        else:
            RECORD.remove_quality_defect_notes()

        change = 1 - Record.get_record_similarity(
            RECORD_A=RECORD, RECORD_B=UNPREPARED_RECORD
        )
        if change > 0.1:
            self.REVIEW_MANAGER.report_logger.info(
                f' {RECORD.data["ID"]}'.ljust(self.PAD, " ")
                + f"Change score: {round(change, 2)}"
            )

        return RECORD

    # Note : no named arguments for multiprocessing
    def prepare(self, item: dict) -> dict:

        RECORD = item["record"]

        # TODO : if we exclude the RecordState.md_prepared
        # from all of the following prep-scripts, we are missing out
        # on potential improvements...
        # if RecordState.md_imported != record["colrev_status"]:
        if RECORD.data["colrev_status"] not in [
            RecordState.md_imported,
            # RecordState.md_prepared, # avoid changing prepared records
            RecordState.md_needs_manual_preparation,
        ]:
            return RECORD

        self.REVIEW_MANAGER.logger.info("Prepare " + RECORD.data["ID"])

        #  preparation_record will change and eventually replace record (if successful)
        preparation_record = RECORD.data.copy()

        # UNPREPARED_RECORD will not change (for diffs)
        UNPREPARED_RECORD = PrepRecord(data=RECORD.data.copy())

        # Note: we require (almost) perfect matches for the scripts.
        # Cases with higher dissimilarity will be handled in the prep_man.py
        # Note : the record should always be the first element of the list.
        # Note : we need to rerun all preparation scripts because records are not stored
        # if not prepared successfully.

        SF_REC = PrepRecord(data=RECORD.data.copy())
        short_form = self.drop_fields(RECORD=SF_REC)

        preparation_details = []
        preparation_details.append(
            f'prepare({RECORD.data["ID"]})'
            + f" called with: \n{self.REVIEW_MANAGER.pp.pformat(short_form)}\n\n"
        )

        for settings_prep_script in item["prep_round_scripts"]:

            # Note : we have to select scripts here because pathus/multiprocessing
            # does not support functions as parameters
            if settings_prep_script in self.prep_scripts:
                prep_script = self.prep_scripts[settings_prep_script]

            # custom/external scripts
            elif settings_prep_script in self._custom_prep_scripts:
                try:
                    prep_script = {
                        "name": settings_prep_script,
                        "script": self._custom_prep_scripts[
                            settings_prep_script
                        ].prepare,
                    }
                except Exception as e:
                    print(e)
                    pass
                    return RECORD

            elif settings_prep_script in self._module_prep_scripts:
                try:
                    prep_script = {
                        "name": settings_prep_script,
                        "script": self._module_prep_scripts[
                            settings_prep_script
                        ].prepare,
                    }
                except Exception as e:
                    print(e)
                    pass
                    return RECORD
            else:
                print(
                    f"prep_script ({settings_prep_script}) not available "
                    "in colrev_core.prep (prep_script)"
                )
                continue

            # startTime = datetime.now()

            prior = preparation_record.copy()

            if self.REVIEW_MANAGER.DEBUG_MODE:
                self.REVIEW_MANAGER.logger.info(
                    f"{prep_script['script'].__name__}(...) called"
                )

            PREPARATION_RECORD = PrepRecord(data=preparation_record)
            PREPARATION_RECORD = prep_script["script"](PREPARATION_RECORD)
            preparation_record = PREPARATION_RECORD.get_data()

            diffs = list(dictdiffer.diff(prior, preparation_record))
            if diffs:
                # print(PREPARATION_RECORD)
                change_report = (
                    f"{prep_script['script'].__name__}"
                    f'({preparation_record["ID"]})'
                    f" changed:\n{self.REVIEW_MANAGER.pp.pformat(diffs)}\n"
                )
                preparation_details.append(change_report)
                if self.REVIEW_MANAGER.DEBUG_MODE:
                    self.REVIEW_MANAGER.logger.info(change_report)
                    self.REVIEW_MANAGER.logger.info(
                        "To correct errors in the script,"
                        " open an issue at "
                        "https://github.com/geritwagner/colrev_core/issues"
                    )
                    if "source_correction_hint" in prep_script:
                        self.REVIEW_MANAGER.logger.info(
                            "To correct potential errors at source,"
                            f" {prep_script['source_correction_hint']}"
                        )
                    input("Press Enter to continue")
                    print("\n")
            else:
                self.REVIEW_MANAGER.logger.debug(
                    f"{prep_script['script'].__name__} changed: -"
                )
                if self.REVIEW_MANAGER.DEBUG_MODE:
                    print("\n")
                    time.sleep(0.7)

            if preparation_record["colrev_status"] in [
                RecordState.rev_prescreen_excluded,
                RecordState.md_prepared,
            ] or "disagreement with " in preparation_record.get(
                "colrev_masterdata_provenance", ""
            ):
                RECORD.data = preparation_record.copy()
                # break

            # diff = (datetime.now() - startTime).total_seconds()
            # with open("stats.csv", "a", encoding="utf8") as f:
            #     f.write(f'{prep_script["script"].__name__};{record["ID"]};{diff};\n')

        # TODO : deal with "crossmark" in preparation_record

        if self.LAST_ROUND:
            RECORD.data = preparation_record.copy()
            if (
                RecordState.md_needs_manual_preparation
                == preparation_record["colrev_status"]
            ):
                RECORD = self.update_masterdata_provenance(
                    RECORD=RECORD, UNPREPARED_RECORD=UNPREPARED_RECORD
                )
        else:
            if self.REVIEW_MANAGER.DEBUG_MODE:
                if (
                    RecordState.md_needs_manual_preparation
                    == preparation_record["colrev_status"]
                ):
                    self.REVIEW_MANAGER.logger.debug(
                        "Resetting values (instead of saving them)."
                    )
                    # for the readability of diffs,
                    # we change records only once (in the last round)

        # TBD: rely on colrev prep --debug ID (instead of printing everyting?)
        # for preparation_detail in preparation_details:
        #     self.REVIEW_MANAGER.report_logger.info(preparation_detail)
        return RECORD

    def __log_details(self, *, preparation_batch: list) -> None:

        nr_recs = len(
            [
                record
                for record in preparation_batch
                if record["colrev_status"] == RecordState.md_needs_manual_preparation
            ]
        )
        if nr_recs > 0:
            self.REVIEW_MANAGER.report_logger.info(
                f"Statistics: {nr_recs} records not prepared"
            )

        nr_recs = len(
            [
                record
                for record in preparation_batch
                if record["colrev_status"] == RecordState.rev_prescreen_excluded
            ]
        )
        if nr_recs > 0:
            self.REVIEW_MANAGER.report_logger.info(
                f"Statistics: {nr_recs} records (prescreen) excluded "
                "(non-latin alphabet)"
            )

        return

    def reset(self, *, record_list: typing.List[dict]):
        from colrev_core.prep_man import PrepMan

        record_list = [
            r
            for r in record_list
            if str(r["colrev_status"])
            in [
                str(RecordState.md_prepared),
                str(RecordState.md_needs_manual_preparation),
            ]
        ]

        for r in [
            r
            for r in record_list
            if str(r["colrev_status"])
            not in [
                str(RecordState.md_prepared),
                str(RecordState.md_needs_manual_preparation),
            ]
        ]:
            msg = (
                f"{r['ID']}: status must be md_prepared/md_needs_manual_preparation "
                + f'(is {r["colrev_status"]})'
            )
            self.REVIEW_MANAGER.logger.error(msg)
            self.REVIEW_MANAGER.report_logger.error(msg)

        record_reset_list = [[record, record.copy()] for record in record_list]

        MAIN_REFERENCES_RELATIVE = self.REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]
        git_repo = git.Repo(str(self.REVIEW_MANAGER.paths["REPO_DIR"]))
        revlist = (
            (
                commit.hexsha,
                commit.message,
                (commit.tree / str(MAIN_REFERENCES_RELATIVE)).data_stream.read(),
            )
            for commit in git_repo.iter_commits(paths=str(MAIN_REFERENCES_RELATIVE))
        )

        for commit_id, cmsg, filecontents in list(revlist):
            cmsg_l1 = str(cmsg).split("\n")[0]
            if "colrev load" not in cmsg:
                print(f"Skip {str(commit_id)} (non-load commit) - {str(cmsg_l1)}")
                continue
            print(f"Check {str(commit_id)} - {str(cmsg_l1)}")

            prior_records_dict = self.REVIEW_MANAGER.REVIEW_DATASET.load_records(
                load_str=filecontents.decode("utf-8")
            )
            for prior_record in prior_records_dict.values():
                if str(prior_record["colrev_status"]) != str(RecordState.md_imported):
                    continue
                for record_to_unmerge, record in record_reset_list:

                    if any(
                        o in prior_record["colrev_origin"]
                        for o in record["colrev_origin"].split(";")
                    ):
                        self.REVIEW_MANAGER.report_logger.info(
                            f'reset({record["ID"]}) to'
                            f"\n{self.REVIEW_MANAGER.pp.pformat(prior_record)}\n\n"
                        )
                        # Note : we don't want to restore the old ID...
                        current_id = record_to_unmerge["ID"]
                        record_to_unmerge.clear()
                        for k, v in prior_record.items():
                            record_to_unmerge[k] = v
                        record_to_unmerge["ID"] = current_id
                        break
                # Stop if all original records have been found
                if (
                    len(
                        [
                            x["colrev_status"] != "md_imported"
                            for x, y in record_reset_list
                        ]
                    )
                    == 0
                ):
                    break

        PREP_MAN = PrepMan(REVIEW_MANAGER=self.REVIEW_MANAGER)
        # TODO : double-check! resetting the prep does not necessarily mean
        # that wrong records were merged...
        # TODO : if any record_to_unmerge['status'] != RecordState.md_imported:
        # retrieve the original record from the search/source file
        for record_to_unmerge, record in record_reset_list:
            PREP_MAN.append_to_non_dupe_db(
                record_to_unmerge_original=record_to_unmerge, record_original=record
            )
            record_to_unmerge.update(
                colrev_status=RecordState.md_needs_manual_preparation
            )

        return

    def reset_records(self, *, reset_ids: list) -> None:
        # Note: entrypoint for CLI

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        records_to_reset = []
        for reset_id in reset_ids:
            if reset_id in records:
                records_to_reset.append(records[reset_id])
            else:
                print(f"Error: record not found (ID={reset_id})")

        self.reset(record_list=records_to_reset)

        saved_args = {"reset_records": ",".join(reset_ids)}
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        # self.REVIEW_MANAGER.format_references()
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        self.REVIEW_MANAGER.create_commit(
            msg="Reset metadata for manual preparation", saved_args=saved_args
        )
        return

    def reset_ids(self) -> None:
        # Note: entrypoint for CLI

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        git_repo = self.REVIEW_MANAGER.REVIEW_DATASET.get_repo()
        MAIN_REFERENCES_RELATIVE = self.REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]
        revlist = (
            ((commit.tree / str(MAIN_REFERENCES_RELATIVE)).data_stream.read())
            for commit in git_repo.iter_commits(paths=str(MAIN_REFERENCES_RELATIVE))
        )
        filecontents = next(revlist)  # noqa
        prior_records_dict = self.REVIEW_MANAGER.REVIEW_DATASET.load_records(
            load_str=filecontents.decode("utf-8")
        )
        for record in records.values():
            prior_record_l = [
                x
                for x in prior_records_dict.values()
                if x["colrev_origin"] == record["colrev_origin"]
            ]
            if len(prior_record_l) != 1:
                continue
            prior_record = prior_record_l[0]
            record["ID"] = prior_record["ID"]

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)

        return

    def set_ids(
        self,
    ) -> None:
        # Note: entrypoint for CLI

        self.REVIEW_MANAGER.REVIEW_DATASET.set_IDs()
        self.REVIEW_MANAGER.create_commit(msg="Set IDs")

        return

    def update_doi_md(
        self,
    ) -> None:
        # Note: entrypoint for CLI

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        for record in records.values():
            if "doi" in record and record.get("journal", "") == "MIS Quarterly":
                record = self.get_masterdata_from_doi(RECORD=record)
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        self.REVIEW_MANAGER.create_commit(msg="Update metadata based on DOIs")
        return

    def print_doi_metadata(self, *, doi: str) -> None:
        """CLI entrypoint"""

        DUMMY_R = PrepRecord(data={"doi": doi})
        RECORD = self.get_masterdata_from_doi(RECORD=DUMMY_R)
        print(RECORD)

        if "url" in RECORD.data:
            print("Metadata retrieved from website:")
            RETRIEVED_RECORD = self.retrieve_md_from_url(RECORD=RECORD)
            print(RETRIEVED_RECORD)

        return

    def setup_custom_script(self) -> None:
        import pkgutil

        filedata = pkgutil.get_data(__name__, "template/custom_prep_script.py")
        if filedata:
            with open("custom_prep_script.py", "w") as file:
                file.write(filedata.decode("utf-8"))

        self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(path="custom_prep_script.py")

        prep_round = self.REVIEW_MANAGER.settings.prep.prep_rounds[-1]
        prep_round.scripts.append("custom_prep_script")
        self.REVIEW_MANAGER.save_settings()

        return

    def main(
        self,
        *,
        keep_ids: bool = False,
        debug_ids: str = "NA",
        debug_file: str = "NA",
    ) -> None:
        """Preparation of records"""
        from colrev_core.settings import PrepRound

        saved_args = locals()

        self.check_DBs_availability()

        if self.REVIEW_MANAGER.DEBUG_MODE:
            print("\n\n\n")
            self.REVIEW_MANAGER.logger.info("Start debug prep\n")
            self.REVIEW_MANAGER.logger.info(
                "The script will replay the preparation procedures"
                " step-by-step, allow you to identify potential errors, trace them to "
                "their colrev_origin and correct them."
            )
            input("\nPress Enter to continue")
            print("\n\n")

        if not keep_ids:
            del saved_args["keep_ids"]

        def load_prep_data():
            from colrev_core.record import RecordState

            record_state_list = (
                self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
            )
            nr_tasks = len(
                [
                    x
                    for x in record_state_list
                    if str(RecordState.md_imported) == x["colrev_status"]
                ]
            )

            PAD = min((max(len(x["ID"]) for x in record_state_list) + 2), 35)

            items = self.REVIEW_MANAGER.REVIEW_DATASET.read_next_record(
                conditions=[
                    {"colrev_status": RecordState.md_imported},
                    {"colrev_status": RecordState.md_prepared},
                    {"colrev_status": RecordState.md_needs_manual_preparation},
                ],
            )

            prior_ids = [
                x["ID"]
                for x in record_state_list
                if str(RecordState.md_imported) == x["colrev_status"]
            ]

            prep_data = {
                "nr_tasks": nr_tasks,
                "PAD": PAD,
                "items": list(items),
                "prior_ids": prior_ids,
            }
            self.REVIEW_MANAGER.logger.debug(self.REVIEW_MANAGER.pp.pformat(prep_data))
            return prep_data

        def get_preparation_batch(*, prep_round: PrepRound):
            if self.REVIEW_MANAGER.DEBUG_MODE:
                prepare_data = load_prep_data_for_debug(
                    debug_ids=debug_ids, debug_file=debug_file
                )
                if prepare_data["nr_tasks"] == 0:
                    print("ID not found in history.")
            else:
                prepare_data = load_prep_data()

            if self.REVIEW_MANAGER.DEBUG_MODE:
                self.REVIEW_MANAGER.logger.info(
                    "In this round, we set the similarity "
                    f"threshold ({self.RETRIEVAL_SIMILARITY})"
                )
                input("Press Enter to continue")
                print("\n\n")
                self.REVIEW_MANAGER.logger.info(
                    f"prepare_data: " f"{self.REVIEW_MANAGER.pp.pformat(prepare_data)}"
                )
            self.PAD = prepare_data["PAD"]
            items = prepare_data["items"]
            batch = []
            for item in items:
                batch.append(
                    {
                        "record": PrepRecord(data=item),
                        "prep_round_scripts": prep_round.scripts,
                        "prep_round": prep_round.name,
                    }
                )
            return batch

        def load_prep_data_for_debug(
            *, debug_ids: str, debug_file: str = "NA"
        ) -> typing.Dict:

            self.REVIEW_MANAGER.logger.info("Data passed to the scripts")
            if debug_file is None:
                debug_file = "NA"
            if "NA" != debug_file:
                with open(debug_file, encoding="utf8") as target_db:
                    records_dict = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                        load_str=target_db.read()
                    )

                for record in records_dict.values():
                    if RecordState.md_imported != record.get("state", ""):
                        self.REVIEW_MANAGER.logger.info(
                            f"Setting colrev_status to md_imported {record['ID']}"
                        )
                        record["colrev_status"] = RecordState.md_imported
                debug_ids_list = list(records_dict.keys())
                debug_ids = ",".join(debug_ids_list)
                self.REVIEW_MANAGER.logger.info("Imported record (retrieved from file)")

            else:
                records = []
                debug_ids_list = debug_ids.split(",")
                REVIEW_DATASET = self.REVIEW_MANAGER.REVIEW_DATASET
                original_records = list(
                    REVIEW_DATASET.read_next_record(
                        conditions=[{"ID": ID} for ID in debug_ids_list]
                    )
                )
                # self.REVIEW_MANAGER.logger.info("Current record")
                # self.REVIEW_MANAGER.pp.pprint(original_records)
                records = REVIEW_DATASET.retrieve_records_from_history(
                    original_records=original_records,
                    condition_state=RecordState.md_imported,
                )
                self.REVIEW_MANAGER.logger.info(
                    "Imported record (retrieved from history)"
                )

            if len(records) == 0:
                prep_data = {"nr_tasks": 0, "PAD": 0, "items": [], "prior_ids": []}
            else:
                print(PrepRecord(data=records[0]))
                input("Press Enter to continue")
                print("\n\n")
                prep_data = {
                    "nr_tasks": len(debug_ids_list),
                    "PAD": len(debug_ids),
                    "items": records,
                    "prior_ids": [debug_ids_list],
                }
            return prep_data

        def setup_prep_round(*, i, prep_round):
            from zope.interface.verify import verifyObject

            if i == 0:
                self.FIRST_ROUND = True

            else:
                self.FIRST_ROUND = False

            if i == len(self.REVIEW_MANAGER.settings.prep.prep_rounds) - 1:
                self.LAST_ROUND = True
            else:
                self.LAST_ROUND = False
            # https://dev.to/charlesw001/plugin-architecture-in-python-jla
            # TODO : script to validate CustomPrepare (has a name/prepare function)
            # TODO : the same module/custom_script could contain multiple functions...
            list_custom_scripts = [
                s
                for s in prep_round.scripts
                if Path(s + ".py").is_file() and s not in self.prep_scripts
            ]
            self._custom_prep_scripts = {}
            sys.path.append(".")  # to import custom scripts from the project dir
            for plugin_script in list_custom_scripts:
                if Path(plugin_script + ".py").is_file():
                    self._custom_prep_scripts[plugin_script] = importlib.import_module(
                        plugin_script, "."
                    ).CustomPrepare()
                    verifyObject(PrepScript, self._custom_prep_scripts[plugin_script])

            list_module_scripts = [
                s
                for s in prep_round.scripts
                if not Path(s + ".py").is_file() and s not in self.prep_scripts
            ]
            self._module_prep_scripts = {}
            for plugin_script in list_module_scripts:
                if not Path(plugin_script + ".py").is_file():
                    self._module_prep_scripts[plugin_script] = importlib.import_module(
                        plugin_script
                    ).CustomPrepare()

                # from inspect import getmembers, isfunction
                # print(getmembers(plugin, isfunction))

            # Note : we add the script automatically (not as part of the settings.json)
            # because it must always be executed at the end
            if "exclusion" != prep_round.name:
                prep_round.scripts.append("update_metadata_status")

            # Note : can set selected prep scripts/rounds in the settings...
            # if self.FIRST_ROUND and not self.REVIEW_MANAGER.DEBUG_MODE:
            #     if prepare_data["nr_tasks"] < 20:
            #         self.REVIEW_MANAGER.logger.info(
            #             "Less than 20 records: prepare in one batch."
            #         )
            #         modes = [m for m in modes if "low_confidence" == m["name"]]
            # use one mode/run to avoid multiple commits

            self.REVIEW_MANAGER.logger.info(f"Prepare ({prep_round.name})")
            if self.FIRST_ROUND:
                self.session.remove_expired_responses()  # Note : this takes long...

            self.RETRIEVAL_SIMILARITY = prep_round.similarity  # type: ignore
            saved_args["similarity"] = self.RETRIEVAL_SIMILARITY
            self.REVIEW_MANAGER.report_logger.debug(
                f"Set RETRIEVAL_SIMILARITY={self.RETRIEVAL_SIMILARITY}"
            )
            return

        if "NA" != debug_ids:
            self.REVIEW_MANAGER.DEBUG_MODE = True

        for i, prep_round in enumerate(self.REVIEW_MANAGER.settings.prep.prep_rounds):

            setup_prep_round(i=i, prep_round=prep_round)

            preparation_batch = get_preparation_batch(prep_round=prep_round)
            if len(preparation_batch) == 0:
                return

            if self.REVIEW_MANAGER.DEBUG_MODE:
                # Note: preparation_batch is not turned into a list of records.
                preparation_batch_items = preparation_batch
                preparation_batch = []
                for item in preparation_batch_items:
                    r = self.prepare(item)
                    preparation_batch.append(r)
            else:
                # Note : p_map shows the progress (tqdm) but it is inefficient
                # https://github.com/swansonk14/p_tqdm/issues/34
                # from p_tqdm import p_map
                # preparation_batch = p_map(self.prepare, preparation_batch)

                if "exclude_languages" in prep_round.scripts:  # type: ignore
                    pool = ProcessPool(nodes=mp.cpu_count() // 2)
                else:
                    pool = ProcessPool(nodes=self.CPUS)
                preparation_batch = pool.map(self.prepare, preparation_batch)

                pool.close()
                pool.join()
                pool.clear()

            if not self.REVIEW_MANAGER.DEBUG_MODE:
                preparation_batch = [x.get_data() for x in preparation_batch]
                self.REVIEW_MANAGER.REVIEW_DATASET.save_record_list_by_ID(
                    record_list=preparation_batch
                )

                self.__log_details(preparation_batch=preparation_batch)

                # Multiprocessing mixes logs of different records.
                # For better readability:
                preparation_batch_IDs = [x["ID"] for x in preparation_batch]
                self.REVIEW_MANAGER.reorder_log(IDs=preparation_batch_IDs)

                # Note: for formatting...
                # records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
                # self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
                # self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

                self.REVIEW_MANAGER.create_commit(
                    msg=f"Prepare records ({prep_round.name})", saved_args=saved_args
                )
                self.REVIEW_MANAGER.reset_log()
                print()

        if not keep_ids and not self.REVIEW_MANAGER.DEBUG_MODE:
            self.REVIEW_MANAGER.REVIEW_DATASET.set_IDs()
            self.REVIEW_MANAGER.create_commit(msg="Set IDs", saved_args=saved_args)

        return


class ServiceNotAvailableException(Exception):
    def __init__(self, msg: str):
        self.message = msg
        super().__init__(f"Service not available: {self.message}")


if __name__ == "__main__":
    pass
