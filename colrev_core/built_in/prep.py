#! /usr/bin/env python
import collections
import json
import re
import sys
import typing
from pathlib import Path

import git
import pycountry
import requests
import timeout_decorator
import zope.interface
from alphabet_detector import AlphabetDetector
from dacite import from_dict
from lingua.builder import LanguageDetectorBuilder
from opensearchpy import NotFoundError
from opensearchpy.exceptions import TransportError
from thefuzz import fuzz

import colrev_core.built_in.database_connectors
import colrev_core.exceptions as colrev_exceptions
import colrev_core.process
import colrev_core.record
import colrev_core.search_sources


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class LoadFixesPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):
        # TODO : may need to rerun import_provenance

        SEARCH_SCOURCES = colrev_core.search_sources.SearchSources(
            REVIEW_MANAGER=PREPARATION.REVIEW_MANAGER
        )

        origin_source = RECORD.data["colrev_origin"].split("/")[0]

        custom_prep_scripts = [
            r["endpoint"]
            for s in PREPARATION.REVIEW_MANAGER.settings.sources
            if s.filename.with_suffix(".bib") == Path("search") / Path(origin_source)
            for r in s.source_prep_scripts
        ]

        for custom_prep_script_name in custom_prep_scripts:

            endpoint = SEARCH_SCOURCES.search_source_scripts[custom_prep_script_name]

            if callable(endpoint.prepare):
                RECORD = endpoint.prepare(RECORD)
            else:
                print(f"error: {custom_prep_script_name}")

        if "howpublished" in RECORD.data and "url" not in RECORD.data:
            if "url" in RECORD.data["howpublished"]:
                RECORD.rename_field(key="howpublished", new_key="url")
                RECORD.data["url"] = (
                    RECORD.data["url"].replace("\\url{", "").rstrip("}")
                )

        if "webpage" == RECORD.data["ENTRYTYPE"].lower() or (
            "misc" == RECORD.data["ENTRYTYPE"].lower() and "url" in RECORD.data
        ):
            RECORD.data["ENTRYTYPE"] = "online"

        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class ExcludeNonLatinAlphabetsPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True
    alphabet_detector = AlphabetDetector()

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):
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


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class ExcludeLanguagesPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, PREPARATION, SETTINGS):

        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

        # Note : Lingua is tested/evaluated relative to other libraries:
        # https://github.com/pemistahl/lingua-py
        # It performs particularly well for short strings (single words/word pairs)
        # The langdetect library is non-deterministic, especially for short strings
        # https://pypi.org/project/langdetect/

        # Note : the following objects have heavy memory footprints and should be
        # class (not object) properties to keep parallel processing as
        # efficient as possible (the object is passed to each thread)
        self.language_detector = (
            LanguageDetectorBuilder.from_all_languages_with_latin_script().build()
        )
        # Language formats: ISO 639-1 standard language codes
        # https://github.com/flyingcircusio/pycountry

        languages_to_include = ["en"]
        if "scope_prescreen" in [
            s["endpoint"] for s in PREPARATION.REVIEW_MANAGER.settings.prescreen.scripts
        ]:
            for scope_prescreen in [
                s
                for s in PREPARATION.REVIEW_MANAGER.settings.prescreen.scripts
                if "scope_prescreen" == s["endpoint"]
            ]:
                languages_to_include.extend(
                    scope_prescreen.get("LanguageScope", ["en"])
                )
        self.languages_to_include = list(set(languages_to_include))

        self.lang_code_mapping = {}
        for country in pycountry.languages:
            try:
                self.lang_code_mapping[country.name.lower()] = country.alpha_2
            except AttributeError:
                pass

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):

        # Note : other languages are not yet supported
        # because the dedupe does not yet support cross-language merges

        if "language" in RECORD.data:
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
            # If language not in record, add language
            # (always - needed in dedupe.)
            RECORD.data["language"] = "en"
            return RECORD

        confidenceValues = self.language_detector.compute_language_confidence_values(
            text=RECORD.data["title"]
        )

        if PREPARATION.REVIEW_MANAGER.DEBUG_MODE:
            print(RECORD.data["title"].lower())
            PREPARATION.REVIEW_MANAGER.pp.pprint(confidenceValues)

        # If language not in record, add language (always - needed in dedupe.)
        set_most_likely_language = False
        for lang, conf in confidenceValues:

            predicted_language = "not-found"
            # Map to ISO 639-3 language code
            if lang.name.lower() in self.lang_code_mapping:
                predicted_language = self.lang_code_mapping[lang.name.lower()]

            if not set_most_likely_language:
                RECORD.data["language"] = predicted_language
                set_most_likely_language = True
            if "en" == predicted_language:
                if conf > 0.95:
                    RECORD.data["language"] = predicted_language
                    return RECORD

        RECORD.prescreen_exclude(
            reason=f"language of title not in [{','.join(self.languages_to_include)}]"
        )

        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class ExcludeCollectionsPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):
        if "proceedings" == RECORD.data["ENTRYTYPE"].lower():
            RECORD.prescreen_exclude(reason="collection/proceedings")
        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class RemoveError500URLsPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):

        try:
            if "url" in RECORD.data:
                r = PREPARATION.session.request(
                    "GET",
                    RECORD.data["url"],
                    headers=PREPARATION.requests_headers,
                    timeout=PREPARATION.TIMEOUT,
                )
                if r.status_code >= 500:
                    RECORD.remove_field(key="url")
        except requests.exceptions.RequestException:
            pass
        try:
            if "fulltext" in RECORD.data:
                r = PREPARATION.session.request(
                    "GET",
                    RECORD.data["fulltext"],
                    headers=PREPARATION.requests_headers,
                    timeout=PREPARATION.TIMEOUT,
                )
                if r.status_code >= 500:
                    RECORD.remove_field(key="fulltext")
        except requests.exceptions.RequestException:
            pass

        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class RemoveBrokenIDPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    # check_status: relies on crossref / openlibrary connectors!
    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):

        if "doi" in RECORD.data:
            # https://www.crossref.org/blog/dois-and-matching-regular-expressions/
            d = re.match(r"^10.\d{4,9}\/", RECORD.data["doi"])
            if not d:
                RECORD.remove_field(key="doi")
        if "isbn" in RECORD.data:
            isbn = RECORD.data["isbn"].replace("-", "").replace(" ", "")
            url = f"https://openlibrary.org/isbn/{isbn}.json"
            ret = PREPARATION.session.request(
                "GET",
                url,
                headers=PREPARATION.requests_headers,
                timeout=PREPARATION.TIMEOUT,
            )
            if '"error": "notfound"' in ret.text:
                RECORD.remove_field(key="isbn")
        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class GlobalIDConsistencyPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):

        """When metadata provided by DOI/crossref or on the website (url) differs from
        the RECORD: set status to md_needs_manual_preparation."""

        fields_to_check = ["author", "title", "journal", "year", "volume", "number"]

        if "doi" in RECORD.data:
            R_COPY = RECORD.copy_prep_rec()
            CrossrefConnector = (
                colrev_core.built_in.database_connectors.CrossrefConnector
            )
            CROSSREF_MD = CrossrefConnector.get_masterdata_from_crossref(
                PREPARATION=PREPARATION, RECORD=R_COPY
            )
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
                        ] = colrev_core.record.RecordState.md_needs_manual_preparation
                        RECORD.add_masterdata_provenance_note(
                            key=k, note=f"disagreement with doi metadata ({v})"
                        )

        if "url" in RECORD.data:
            try:
                URL_CONNECTOR = colrev_core.database_connectors.URLConnector()
                URL_MD = RECORD.copy_prep_rec()
                URL_MD = URL_CONNECTOR.retrieve_md_from_url(
                    RECORD=URL_MD, PREPARATION=PREPARATION
                )
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
                            ] = (
                                colrev_core.record.RecordState.md_needs_manual_preparation
                            )
                            RECORD.add_masterdata_provenance_note(
                                key=k,
                                note=f"disagreement with website metadata ({v})",
                            )
            except AttributeError:
                pass

        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class CuratedPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):
        if RECORD.masterdata_is_curated():
            if (
                colrev_core.record.RecordState.md_imported
                == RECORD.data["colrev_status"]
            ):
                RECORD.data[
                    "colrev_status"
                ] = colrev_core.record.RecordState.md_prepared

        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class FormatPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = False

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):

        if "author" in RECORD.data and "UNKNOWN" != RECORD.data.get(
            "author", "UNKNOWN"
        ):
            # DBLP appends identifiers to non-unique authors
            RECORD.update_field(
                key="author",
                value=str(re.sub(r"[0-9]{4}", "", RECORD.data["author"])),
                source="FormatPrep",
                keep_source_if_equal=True,
            )

            # fix name format
            if (1 == len(RECORD.data["author"].split(" ")[0])) or (
                ", " not in RECORD.data["author"]
            ):
                RECORD.update_field(
                    key="author",
                    value=colrev_core.record.PrepRecord.format_author_field(
                        input_string=RECORD.data["author"]
                    ),
                    source="FormatPrep",
                    keep_source_if_equal=True,
                )

        if "title" in RECORD.data and "UNKNOWN" != RECORD.data.get("title", "UNKNOWN"):
            RECORD.update_field(
                key="title",
                value=re.sub(r"\s+", " ", RECORD.data["title"]).rstrip("."),
                source="FormatPrep",
                keep_source_if_equal=True,
            )
            if "UNKNOWN" != RECORD.data["title"]:
                RECORD.format_if_mostly_upper(key="title")

        if "booktitle" in RECORD.data and "UNKNOWN" != RECORD.data.get(
            "booktitle", "UNKNOWN"
        ):
            if "UNKNOWN" != RECORD.data["booktitle"]:
                RECORD.format_if_mostly_upper(key="booktitle", case="title")

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
                RECORD.update_field(
                    key="booktitle",
                    value=stripped_btitle,
                    source="FormatPrep",
                    keep_source_if_equal=True,
                )

        if "date" in RECORD.data and "year" not in RECORD.data:
            year = re.search(r"\d{4}", RECORD.data["date"])
            if year:
                RECORD.update_field(
                    key="year",
                    value=year.group(0),
                    source="FormatPrep",
                    keep_source_if_equal=True,
                )

        if "journal" in RECORD.data and "UNKNOWN" != RECORD.data.get(
            "journal", "UNKNOWN"
        ):
            if len(RECORD.data["journal"]) > 10 and "UNKNOWN" != RECORD.data["journal"]:
                RECORD.format_if_mostly_upper(key="journal", case="title")

        if "pages" in RECORD.data and "UNKNOWN" != RECORD.data.get("pages", "UNKNOWN"):
            if "N.PAG" == RECORD.data.get("pages", ""):
                RECORD.remove_field(key="pages")
            else:
                RECORD.unify_pages_field()
                if (
                    not re.match(r"^\d*$", RECORD.data["pages"])
                    and not re.match(r"^\d*--\d*$", RECORD.data["pages"])
                    and not re.match(r"^[xivXIV]*--[xivXIV]*$", RECORD.data["pages"])
                ):
                    PREPARATION.REVIEW_MANAGER.report_logger.info(
                        f' {RECORD.data["ID"]}:'.ljust(PREPARATION.PAD, " ")
                        + f'Unusual pages: {RECORD.data["pages"]}'
                    )

        if "language" in RECORD.data:
            # TODO : use https://pypi.org/project/langcodes/
            RECORD.update_field(
                key="language",
                value=RECORD.data["language"]
                .replace("English", "en")
                .replace("ENG", "en"),
                source="FormatPrep",
                keep_source_if_equal=True,
            )

        if "doi" in RECORD.data:
            RECORD.update_field(
                key="doi",
                value=RECORD.data["doi"].replace("http://dx.doi.org/", "").upper(),
                source="FormatPrep",
                keep_source_if_equal=True,
            )

        if "number" not in RECORD.data and "issue" in RECORD.data:
            RECORD.update_field(
                key="number",
                value=RECORD.data["issue"],
                source="FormatPrep",
                keep_source_if_equal=True,
            )
            RECORD.remove_field(key="issue")

        if "volume" in RECORD.data and "UNKNOWN" != RECORD.data.get(
            "volume", "UNKNOWN"
        ):
            RECORD.update_field(
                key="volume",
                value=RECORD.data["volume"].replace("Volume ", ""),
                source="FormatPrep",
                keep_source_if_equal=True,
            )

        if "url" in RECORD.data and "fulltext" in RECORD.data:
            if RECORD.data["url"] == RECORD.data["fulltext"]:
                RECORD.remove_field(key="fulltext")

        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class BibTexCrossrefResolutionPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = False

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):
        def read_next_record_str() -> typing.Iterator[str]:
            with open(
                PREPARATION.REVIEW_MANAGER.paths["RECORDS_FILE"], encoding="utf8"
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
                    records_dict = (
                        PREPARATION.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                            load_str=record_string
                        )
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


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class SemanticScholarPrep:

    source_correction_hint = (
        "fill out the online form: "
        + "https://www.semanticscholar.org/faq#correct-error"
    )
    always_apply_changes = False

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    def retrieve_record_from_semantic_scholar(
        self, *, PREPARATION, url: str, RECORD_IN: colrev_core.record.PrepRecord
    ) -> colrev_core.record.PrepRecord:

        PREPARATION.REVIEW_MANAGER.logger.debug(url)
        headers = {
            "user-agent": f"{__name__} (mailto:{PREPARATION.REVIEW_MANAGER.EMAIL})"
        }
        ret = PREPARATION.session.request(
            "GET", url, headers=headers, timeout=PREPARATION.TIMEOUT
        )
        ret.raise_for_status()

        data = json.loads(ret.text)
        items = data["data"]
        if len(items) == 0:
            return RECORD_IN
        if "paperId" not in items[0]:
            return RECORD_IN

        paper_id = items[0]["paperId"]
        record_retrieval_url = "https://api.semanticscholar.org/v1/paper/" + paper_id
        PREPARATION.REVIEW_MANAGER.logger.debug(record_retrieval_url)
        ret_ent = PREPARATION.session.request(
            "GET", record_retrieval_url, headers=headers, timeout=PREPARATION.TIMEOUT
        )
        ret_ent.raise_for_status()
        item = json.loads(ret_ent.text)

        retrieved_record: dict = {}
        if "authors" in item:
            authors_string = " and ".join(
                [author["name"] for author in item["authors"] if "name" in author]
            )
            authors_string = colrev_core.record.PrepRecord.format_author_field(
                input_string=authors_string
            )
            retrieved_record.update(author=authors_string)
        if "abstract" in item:
            retrieved_record.update(abstract=item["abstract"])
        if "doi" in item:
            if "none" != str(item["doi"]).lower():
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
            RECORD_IN.remove_field(key=key)

        REC = colrev_core.record.PrepRecord(data=retrieved_record)
        REC.add_provenance_all(source=record_retrieval_url)
        return REC

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):

        same_record_type_required = (
            PREPARATION.REVIEW_MANAGER.settings.project.curated_masterdata
        )
        try:
            search_api_url = (
                "https://api.semanticscholar.org/graph/v1/paper/search?query="
            )
            url = search_api_url + RECORD.data.get("title", "").replace(" ", "+")

            RETRIEVED_RECORD = self.retrieve_record_from_semantic_scholar(
                PREPARATION=PREPARATION, url=url, RECORD_IN=RECORD
            )
            if "sem_scholar_id" not in RETRIEVED_RECORD.data:
                return RECORD

            # Remove fields that are not/rarely available before
            # calculating similarity metrics
            RED_REC_COPY = RECORD.copy_prep_rec()
            for key in ["volume", "number", "number", "pages"]:
                if key in RED_REC_COPY.data:
                    RECORD.remove_field(key=key)

            similarity = colrev_core.record.PrepRecord.get_retrieval_similarity(
                RECORD_ORIGINAL=RED_REC_COPY,
                RETRIEVED_RECORD_ORIGINAL=RETRIEVED_RECORD,
                same_record_type_required=same_record_type_required,
            )
            if similarity > PREPARATION.RETRIEVAL_SIMILARITY:
                PREPARATION.REVIEW_MANAGER.logger.debug("Found matching record")
                PREPARATION.REVIEW_MANAGER.logger.debug(
                    f"scholar similarity: {similarity} "
                    f"(>{PREPARATION.RETRIEVAL_SIMILARITY})"
                )

                RECORD.merge(
                    MERGING_RECORD=RETRIEVED_RECORD,
                    default_source=RETRIEVED_RECORD.data["sem_scholar_id"],
                )

            else:
                PREPARATION.REVIEW_MANAGER.logger.debug(
                    f"scholar similarity: {similarity} "
                    f"(<{PREPARATION.RETRIEVAL_SIMILARITY})"
                )
        except KeyError:
            pass
        except UnicodeEncodeError:
            PREPARATION.REVIEW_MANAGER.logger.error(
                "UnicodeEncodeError - this needs to be fixed at some time"
            )
        except requests.exceptions.RequestException:
            pass
        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class DOIFromURLsPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = False

    # https://www.crossref.org/blog/dois-and-matching-regular-expressions/
    doi_regex = re.compile(r"10\.\d{4,9}/[-._;/:A-Za-z0-9]*")

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):

        same_record_type_required = (
            PREPARATION.REVIEW_MANAGER.settings.project.curated_masterdata
        )

        url = RECORD.data.get("url", RECORD.data.get("fulltext", "NA"))
        if "NA" != url:
            try:
                PREPARATION.REVIEW_MANAGER.logger.debug(f"Retrieve doi-md from {url}")
                headers = {
                    "user-agent": f"{__name__}  "
                    f"(mailto:{PREPARATION.REVIEW_MANAGER.EMAIL})"
                }
                ret = PREPARATION.session.request(
                    "GET", url, headers=headers, timeout=PREPARATION.TIMEOUT
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
                    for doi, _ in ret_dois:
                        retrieved_record = {"doi": doi.upper(), "ID": RECORD.data["ID"]}
                        RETRIEVED_RECORD = colrev_core.record.PrepRecord(
                            data=retrieved_record
                        )
                        colrev_core.built_in.database_connectors.DOIConnector.retrieve_doi_metadata(
                            REVIEW_MANAGER=PREPARATION.REVIEW_MANAGER,
                            RECORD=RETRIEVED_RECORD,
                            session=PREPARATION.session,
                            TIMEOUT=PREPARATION.TIMEOUT,
                        )

                        similarity = (
                            colrev_core.record.PrepRecord.get_retrieval_similarity(
                                RECORD_ORIGINAL=RECORD,
                                RETRIEVED_RECORD_ORIGINAL=RETRIEVED_RECORD,
                                same_record_type_required=same_record_type_required,
                            )
                        )
                        if similarity > PREPARATION.RETRIEVAL_SIMILARITY:
                            RECORD.merge(
                                MERGING_RECORD=RETRIEVED_RECORD, default_source=url
                            )

                            PREPARATION.REVIEW_MANAGER.report_logger.debug(
                                "Retrieved metadata based on doi from"
                                f' website: {RECORD.data["doi"]}'
                            )

            except requests.exceptions.RequestException:
                pass
        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class DOIMetadataPrep:

    source_correction_hint = (
        "ask the publisher to correct the metadata"
        + " (see https://www.crossref.org/blog/"
        + "metadata-corrections-updates-and-additions-in-metadata-manager/"
    )
    always_apply_changes = False

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):
        if "doi" not in RECORD.data:
            return RECORD
        colrev_core.built_in.database_connectors.DOIConnector.retrieve_doi_metadata(
            REVIEW_MANAGER=PREPARATION.REVIEW_MANAGER,
            RECORD=RECORD,
            session=PREPARATION.session,
            TIMEOUT=PREPARATION.TIMEOUT,
        )
        colrev_core.built_in.database_connectors.DOIConnector.get_link_from_doi(
            RECORD=RECORD
        )
        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class CrossrefMetadataPrep:

    source_correction_hint = (
        "ask the publisher to correct the metadata"
        + " (see https://www.crossref.org/blog/"
        + "metadata-corrections-updates-and-additions-in-metadata-manager/"
    )
    always_apply_changes = False

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):
        colrev_core.built_in.database_connectors.CrossrefConnector.get_masterdata_from_crossref(
            PREPARATION=PREPARATION, RECORD=RECORD
        )
        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class DBLPMetadataPrep:

    source_correction_hint = (
        "send and email to dblp@dagstuhl.de"
        + " (see https://dblp.org/faq/How+can+I+correct+errors+in+dblp.html)"
    )
    always_apply_changes = False

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):
        if "dblp_key" in RECORD.data:
            return RECORD

        same_record_type_required = (
            PREPARATION.REVIEW_MANAGER.settings.project.curated_masterdata
        )

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

            for (
                RETRIEVED_RECORD
            ) in colrev_core.built_in.database_connectors.DBLPConnector.retrieve_dblp_records(
                REVIEW_MANAGER=PREPARATION.REVIEW_MANAGER,
                query=query,
                session=PREPARATION.session,
            ):
                similarity = colrev_core.record.PrepRecord.get_retrieval_similarity(
                    RECORD_ORIGINAL=RECORD,
                    RETRIEVED_RECORD_ORIGINAL=RETRIEVED_RECORD,
                    same_record_type_required=same_record_type_required,
                )
                if similarity > PREPARATION.RETRIEVAL_SIMILARITY:
                    PREPARATION.REVIEW_MANAGER.logger.debug("Found matching record")
                    PREPARATION.REVIEW_MANAGER.logger.debug(
                        f"dblp similarity: {similarity} "
                        f"(>{PREPARATION.RETRIEVAL_SIMILARITY})"
                    )
                    RECORD.merge(
                        MERGING_RECORD=RETRIEVED_RECORD,
                        default_source=RETRIEVED_RECORD.data["dblp_key"],
                    )
                    RECORD.set_masterdata_complete()
                    RECORD.set_status(
                        target_state=colrev_core.record.RecordState.md_prepared
                    )
                    if "Withdrawn (according to DBLP)" in RECORD.data.get(
                        "warning", ""
                    ):
                        RECORD.prescreen_exclude(reason="retracted")
                        RECORD.remove_field(key="warning")

                else:
                    PREPARATION.REVIEW_MANAGER.logger.debug(
                        f"dblp similarity: {similarity} "
                        f"(<{PREPARATION.RETRIEVAL_SIMILARITY})"
                    )
        except UnicodeEncodeError:
            pass
        except requests.exceptions.RequestException:
            pass
        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class OpenLibraryMetadataPrep:

    source_correction_hint = (
        "ask the publisher to correct the metadata"
        + " (see https://www.crossref.org/blog/"
        + "metadata-corrections-updates-and-additions-in-metadata-manager/"
    )
    always_apply_changes = False

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):
        def open_library_json_to_record(
            *, item: dict, url=str
        ) -> colrev_core.record.PrepRecord:
            retrieved_record: dict = {}

            if "author_name" in item:
                authors_string = " and ".join(
                    [
                        colrev_core.record.PrepRecord.format_author_field(
                            input_string=author
                        )
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

            REC = colrev_core.record.PrepRecord(data=retrieved_record)
            REC.add_provenance_all(source=url)
            return REC

        if RECORD.data.get("ENTRYTYPE", "NA") != "book":
            return RECORD

        try:
            # TODO : integrate more functionality into open_library_json_to_record()
            url = "NA"
            if "isbn" in RECORD.data:
                isbn = RECORD.data["isbn"].replace("-", "").replace(" ", "")
                url = f"https://openlibrary.org/isbn/{isbn}.json"
                ret = PREPARATION.session.request(
                    "GET",
                    url,
                    headers=PREPARATION.requests_headers,
                    timeout=PREPARATION.TIMEOUT,
                )
                ret.raise_for_status()
                PREPARATION.REVIEW_MANAGER.logger.debug(url)
                if '"error": "notfound"' in ret.text:
                    RECORD.remove_field(key="isbn")

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
                ret = PREPARATION.session.request(
                    "GET",
                    url,
                    headers=PREPARATION.requests_headers,
                    timeout=PREPARATION.TIMEOUT,
                )
                ret.raise_for_status()
                PREPARATION.REVIEW_MANAGER.logger.debug(url)

                # if we have an exact match, we don't need to check the similarity
                if '"numFoundExact": true,' not in ret.text:
                    return RECORD

                data = json.loads(ret.text)
                items = data["docs"]
                if not items:
                    return RECORD
                item = items[0]

            RETRIEVED_RECORD = open_library_json_to_record(item=item, url=url)

            RECORD.merge(MERGING_RECORD=RETRIEVED_RECORD, default_source=url)

            # if "title" in RECORD.data and "booktitle" in RECORD.data:
            #     RECORD.remove_field(key="booktitle")

        except requests.exceptions.RequestException:
            pass
        except UnicodeEncodeError:
            PREPARATION.REVIEW_MANAGER.logger.error(
                "UnicodeEncodeError - this needs to be fixed at some time"
            )

        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class CiteAsPrep:

    source_correction_hint = "Search on https://citeas.org/ and click 'modify'"
    always_apply_changes = False

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):
        def cite_as_json_to_record(
            *, data: dict, url=str
        ) -> colrev_core.record.PrepRecord:
            retrieved_record: dict = {}

            if "author" in data["metadata"]:
                authors = data["metadata"]["author"]
                authors_string = ""
                for author in authors:
                    authors_string += author.get("family", "") + ", "
                    authors_string += author.get("given", "") + " "
                authors_string = authors_string.lstrip().rstrip().replace("  ", " ")
                retrieved_record.update(author=authors_string)
            if "container-title" in data["metadata"]:
                retrieved_record.update(title=data["metadata"]["container-title"])
            if "URL" in data["metadata"]:
                retrieved_record.update(url=data["metadata"]["URL"])
            if "note" in data["metadata"]:
                retrieved_record.update(note=data["metadata"]["note"])
            if "type" in data["metadata"]:
                retrieved_record.update(ENTRYTYPE=data["metadata"]["type"])
            if "year" in data["metadata"]:
                retrieved_record.update(year=data["metadata"]["year"])
            if "DOI" in data["metadata"]:
                retrieved_record.update(doi=data["metadata"]["DOI"])

            REC = colrev_core.record.PrepRecord(data=retrieved_record)
            REC.add_provenance_all(source=url)
            return REC

        if RECORD.data.get("ENTRYTYPE", "NA") not in ["misc", "software"]:
            return RECORD
        if "title" not in RECORD.data:
            return RECORD

        same_record_type_required = (
            PREPARATION.REVIEW_MANAGER.settings.project.curated_masterdata
        )
        try:

            url = (
                f"https://api.citeas.org/product/{RECORD.data['title']}?"
                + f"email={PREPARATION.REVIEW_MANAGER.EMAIL}"
            )
            ret = PREPARATION.session.request(
                "GET",
                url,
                headers=PREPARATION.requests_headers,
                timeout=PREPARATION.TIMEOUT,
            )
            ret.raise_for_status()
            PREPARATION.REVIEW_MANAGER.logger.debug(url)

            data = json.loads(ret.text)

            RETRIEVED_RECORD = cite_as_json_to_record(data=data, url=url)

            similarity = colrev_core.record.PrepRecord.get_retrieval_similarity(
                RECORD_ORIGINAL=RETRIEVED_RECORD,
                RETRIEVED_RECORD_ORIGINAL=RETRIEVED_RECORD,
                same_record_type_required=same_record_type_required,
            )
            if similarity > PREPARATION.RETRIEVAL_SIMILARITY:

                RECORD.merge(MERGING_RECORD=RETRIEVED_RECORD, default_source=url)

        except requests.exceptions.RequestException:
            pass
        except UnicodeEncodeError:
            PREPARATION.REVIEW_MANAGER.logger.error(
                "UnicodeEncodeError - this needs to be fixed at some time"
            )

        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class CrossrefYearVolIssPrep:

    source_correction_hint = (
        "ask the publisher to correct the metadata"
        + " (see https://www.crossref.org/blog/"
        + "metadata-corrections-updates-and-additions-in-metadata-manager/"
    )
    always_apply_changes = True

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):

        # The year depends on journal x volume x issue
        if (
            "journal" in RECORD.data
            and "volume" in RECORD.data
            and "number" in RECORD.data
        ) and "UNKNOWN" == RECORD.data.get("year", "UNKNOWN"):
            pass
        else:
            return RECORD

        CrossrefConnector = colrev_core.built_in.database_connectors.CrossrefConnector
        try:

            RETRIEVED_REC_L = CrossrefConnector.crossref_query(
                REVIEW_MANAGER=PREPARATION.REVIEW_MANAGER,
                RECORD_INPUT=RECORD,
                jour_vol_iss_list=True,
                session=PREPARATION.session,
                TIMEOUT=PREPARATION.TIMEOUT,
            )
            retries = 0
            while not RETRIEVED_REC_L and retries < PREPARATION.MAX_RETRIES_ON_ERROR:
                retries += 1
                RETRIEVED_REC_L = CrossrefConnector.crossref_query(
                    REVIEW_MANAGER=PREPARATION.REVIEW_MANAGER,
                    RECORD_INPUT=RECORD,
                    jour_vol_iss_list=True,
                    session=PREPARATION.session,
                    TIMEOUT=PREPARATION.TIMEOUT,
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
            PREPARATION.REVIEW_MANAGER.logger.debug(most_common)
            PREPARATION.REVIEW_MANAGER.logger.debug(years.count(most_common))
            if years.count(most_common) > 3:
                RECORD.update_field(
                    key="year", value=most_common, source="CROSSREF(average)"
                )
        except requests.exceptions.RequestException:
            pass
        except KeyboardInterrupt:
            sys.exit()

        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class LocalIndexPrep:

    source_correction_hint = (
        "correct the metadata in the source "
        + "repository (as linked in the provenance field)"
    )
    always_apply_changes = True

    def __init__(self, *, PREPARATION, SETTINGS):
        from colrev_core.environment import LocalIndex

        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )
        self.LOCAL_INDEX = LocalIndex()

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):

        # TODO: how to distinguish masterdata and complementary CURATED sources?

        # TBD: maybe extract the following three lines as a separate script...
        if not RECORD.masterdata_is_curated():
            year = self.LOCAL_INDEX.get_year_from_toc(record=RECORD.get_data())
            if "NA" != year:
                RECORD.update_field(
                    key="year",
                    value=year,
                    source="LocalIndexPrep",
                    keep_source_if_equal=True,
                )

        # Note : cannot use LOCAL_INDEX as an attribute of PrepProcess
        # because it creates problems with multiprocessing
        retrieved = False
        try:
            retrieved_record = self.LOCAL_INDEX.retrieve(
                record=RECORD.get_data(), include_file=False
            )
            retrieved = True
        except (colrev_exceptions.RecordNotInIndexException, NotFoundError):
            try:
                # Note: Records can be CURATED without being indexed
                if not RECORD.masterdata_is_curated():
                    retrieved_record = self.LOCAL_INDEX.retrieve_from_toc(
                        record=RECORD.data,
                        similarity_threshold=PREPARATION.RETRIEVAL_SIMILARITY,
                        include_file=False,
                    )
                    retrieved = True
            except (
                colrev_exceptions.RecordNotInIndexException,
                NotFoundError,
                TransportError,
            ):
                pass

        if retrieved:
            RETRIEVED_RECORD = colrev_core.record.PrepRecord(data=retrieved_record)

            default_source = "UNDETERMINED"
            if "colrev_masterdata_provenance" in RETRIEVED_RECORD.data:
                if "CURATED" in RETRIEVED_RECORD.data["colrev_masterdata_provenance"]:
                    default_source = RETRIEVED_RECORD.data[
                        "colrev_masterdata_provenance"
                    ]["CURATED"]["source"]
            RECORD.merge(
                MERGING_RECORD=RETRIEVED_RECORD,
                default_source=default_source,
            )

            git_repo = git.Repo(str(PREPARATION.REVIEW_MANAGER.path))
            cur_project_source_paths = [str(PREPARATION.REVIEW_MANAGER.path)]
            for remote in git_repo.remotes:
                if remote.url:
                    shared_url = remote.url
                    shared_url = shared_url.rstrip(".git")
                    cur_project_source_paths.append(shared_url)
                    break

            # extend fields_to_keep (to retrieve all fields from the index)
            for k in retrieved_record.keys():
                if k not in PREPARATION.fields_to_keep:
                    PREPARATION.fields_to_keep.append(k)

        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class RemoveNicknamesPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = False

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):
        if "author" in RECORD.data:
            # Replace nicknames in parentheses
            RECORD.data["author"] = re.sub(r"\([^)]*\)", "", RECORD.data["author"])
            RECORD.data["author"] = RECORD.data["author"].replace("  ", " ")
        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class FormatMinorPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = False
    HTML_CLEANER = re.compile("<.*?>")

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):

        for field in list(RECORD.data.keys()):

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
            RECORD.remove_field(key="volume")
        if RECORD.data.get("number", "") == "ahead-of-print":
            RECORD.remove_field(key="number")

        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class DropFieldsPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = False

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):

        RECORD.drop_fields(PREPARATION)

        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class RemoveRedundantFieldPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = False

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):

        if "article" == RECORD.data["ENTRYTYPE"]:
            if "journal" in RECORD.data and "booktitle" in RECORD.data:
                if (
                    fuzz.partial_ratio(
                        RECORD.data["journal"].lower(), RECORD.data["booktitle"].lower()
                    )
                    / 100
                    > 0.9
                ):
                    RECORD.remove_field(key="booktitle")
        if "inproceedings" == RECORD.data["ENTRYTYPE"]:
            if "journal" in RECORD.data and "booktitle" in RECORD.data:
                if (
                    fuzz.partial_ratio(
                        RECORD.data["journal"].lower(), RECORD.data["booktitle"].lower()
                    )
                    / 100
                    > 0.9
                ):
                    RECORD.remove_field(key="journal")
        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class CorrectRecordTypePrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):

        if RECORD.has_inconsistent_fields() and not RECORD.masterdata_is_curated():
            pass
        else:
            return RECORD

        if PREPARATION.RETRIEVAL_SIMILARITY > 0.9:
            return RECORD

        if (
            "dissertation" in RECORD.data.get("fulltext", "NA").lower()
            and RECORD.data["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = RECORD.data["ENTRYTYPE"]
            RECORD.data.update(ENTRYTYPE="phdthesis")
            PREPARATION.REVIEW_MANAGER.report_logger.info(
                f' {RECORD.data["ID"]}'.ljust(PREPARATION.PAD, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("dissertation" in fulltext link)'
            )

        if (
            "thesis" in RECORD.data.get("fulltext", "NA").lower()
            and RECORD.data["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = RECORD.data["ENTRYTYPE"]
            RECORD.data.update(ENTRYTYPE="phdthesis")
            PREPARATION.REVIEW_MANAGER.report_logger.info(
                f' {RECORD.data["ID"]}'.ljust(PREPARATION.PAD, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("thesis" in fulltext link)'
            )

        if (
            "This thesis" in RECORD.data.get("abstract", "NA").lower()
            and RECORD.data["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = RECORD.data["ENTRYTYPE"]
            RECORD.data.update(ENTRYTYPE="phdthesis")
            PREPARATION.REVIEW_MANAGER.report_logger.info(
                f' {RECORD.data["ID"]}'.ljust(PREPARATION.PAD, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("thesis" in abstract)'
            )

        # Journal articles should not have booktitles/series set.
        if "article" == RECORD.data["ENTRYTYPE"]:
            if "booktitle" in RECORD.data:
                if "journal" not in RECORD.data:
                    RECORD.data.update(journal=RECORD.data["booktitle"])
                    RECORD.remove_field(key="booktitle")
            if "series" in RECORD.data:
                if "journal" not in RECORD.data:
                    RECORD.data.update(journal=RECORD.data["series"])
                    RECORD.remove_field(key="series")

        if "article" == RECORD.data["ENTRYTYPE"]:
            if "journal" not in RECORD.data:
                if "series" in RECORD.data:
                    journal_string = RECORD.data["series"]
                    RECORD.data.update(journal=journal_string)
                    RECORD.remove_field(key="series")
        return RECORD


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class UpdateMetadataStatusPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):

        RECORD.update_metadata_status(REVIEW_MANAGER=PREPARATION.REVIEW_MANAGER)
        return RECORD
