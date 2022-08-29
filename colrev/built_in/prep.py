#! /usr/bin/env python
import collections
import json
import re
import sys
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

import colrev.built_in.database_connectors
import colrev.exceptions as colrev_exceptions
import colrev.process
import colrev.record
import colrev.search_sources


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class LoadFixesPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):
        # TODO : may need to rerun import_provenance

        search_sources = colrev.search_sources.SearchSources(
            review_manager=preparation.review_manager
        )

        origin_source = record.data["colrev_origin"].split("/")[0]

        custom_prep_scripts = [
            r["endpoint"]
            for s in preparation.review_manager.settings.sources
            if s.filename.with_suffix(".bib") == Path("search") / Path(origin_source)
            for r in s.source_prep_scripts
        ]

        for custom_prep_script_name in custom_prep_scripts:

            endpoint = search_sources.search_source_scripts[custom_prep_script_name]

            if callable(endpoint.prepare):
                record = endpoint.prepare(record)
            else:
                print(f"error: {custom_prep_script_name}")

        if "howpublished" in record.data and "url" not in record.data:
            if "url" in record.data["howpublished"]:
                record.rename_field(key="howpublished", new_key="url")
                record.data["url"] = (
                    record.data["url"].replace("\\url{", "").rstrip("}")
                )

        if "webpage" == record.data["ENTRYTYPE"].lower() or (
            "misc" == record.data["ENTRYTYPE"].lower() and "url" in record.data
        ):
            record.data["ENTRYTYPE"] = "online"

        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class ExcludeNonLatinAlphabetsPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True
    alphabet_detector = AlphabetDetector()

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):
        def mostly_latin_alphabet(str_to_check) -> bool:
            assert len(str_to_check) != 0
            nr_non_latin = 0
            for character in str_to_check:
                if not self.alphabet_detector.only_alphabet_chars(character, "LATIN"):
                    nr_non_latin += 1
            return nr_non_latin / len(str_to_check) > 0.75

        str_to_check = " ".join(
            [
                record.data.get("title", ""),
                record.data.get("author", ""),
                record.data.get("journal", ""),
                record.data.get("booktitle", ""),
            ]
        )
        if mostly_latin_alphabet(str_to_check):
            record.prescreen_exclude(reason="non_latin_alphabet")

        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class ExcludeLanguagesPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, preparation, settings):

        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
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
            s["endpoint"] for s in preparation.review_manager.settings.prescreen.scripts
        ]:
            for scope_prescreen in [
                s
                for s in preparation.review_manager.settings.prescreen.scripts
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
    def prepare(self, preparation, record):

        # Note : other languages are not yet supported
        # because the dedupe does not yet support cross-language merges

        if "language" in record.data:
            if record.data["language"] not in self.languages_to_include:
                record.prescreen_exclude(
                    reason=(
                        "language of title not in "
                        f"[{','.join(self.languages_to_include)}]"
                    )
                )

            return record

        # To avoid misclassifications for short titles
        if len(record.data.get("title", "")) < 30:
            # If language not in record, add language
            # (always - needed in dedupe.)
            record.data["language"] = "en"
            return record

        confidence_values = self.language_detector.compute_language_confidence_values(
            text=record.data["title"]
        )

        if preparation.review_manager.debug_mode:
            print(record.data["title"].lower())
            preparation.review_manager.p_printer.pprint(confidence_values)

        # If language not in record, add language (always - needed in dedupe.)
        set_most_likely_language = False
        for lang, conf in confidence_values:

            predicted_language = "not-found"
            # Map to ISO 639-3 language code
            if lang.name.lower() in self.lang_code_mapping:
                predicted_language = self.lang_code_mapping[lang.name.lower()]

            if not set_most_likely_language:
                record.data["language"] = predicted_language
                set_most_likely_language = True
            if "en" == predicted_language:
                if conf > 0.95:
                    record.data["language"] = predicted_language
                    return record

        record.prescreen_exclude(
            reason=f"language of title not in [{','.join(self.languages_to_include)}]"
        )

        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class ExcludeCollectionsPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):
        if "proceedings" == record.data["ENTRYTYPE"].lower():
            record.prescreen_exclude(reason="collection/proceedings")
        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class RemoveError500URLsPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):

        session = preparation.review_manager.get_cached_session()

        try:
            if "url" in record.data:
                ret = session.request(
                    "GET",
                    record.data["url"],
                    headers=preparation.requests_headers,
                    timeout=preparation.TIMEOUT,
                )
                if ret.status_code >= 500:
                    record.remove_field(key="url")
        except requests.exceptions.RequestException:
            pass
        try:
            if "fulltext" in record.data:
                ret = session.request(
                    "GET",
                    record.data["fulltext"],
                    headers=preparation.requests_headers,
                    timeout=preparation.TIMEOUT,
                )
                if ret.status_code >= 500:
                    record.remove_field(key="fulltext")
        except requests.exceptions.RequestException:
            pass

        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class RemoveBrokenIDPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    # check_status: relies on crossref / openlibrary connectors!
    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):

        if "doi" in record.data:
            # https://www.crossref.org/blog/dois-and-matching-regular-expressions/
            doi_match = re.match(r"^10.\d{4,9}\/", record.data["doi"])
            if not doi_match:
                record.remove_field(key="doi")
        if "isbn" in record.data:
            try:
                session = preparation.review_manager.get_cached_session()

                isbn = record.data["isbn"].replace("-", "").replace(" ", "")
                url = f"https://openlibrary.org/isbn/{isbn}.json"
                ret = session.request(
                    "GET",
                    url,
                    headers=preparation.requests_headers,
                    timeout=preparation.TIMEOUT,
                )
                ret.raise_for_status()
            except requests.exceptions.RequestException:
                record.remove_field(key="isbn")
        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class GlobalIDConsistencyPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):

        """When metadata provided by DOI/crossref or on the website (url) differs from
        the RECORD: set status to md_needs_manual_preparation."""

        fields_to_check = ["author", "title", "journal", "year", "volume", "number"]

        if "doi" in record.data:
            record_copy = record.copy_prep_rec()
            crossref_connector = colrev.built_in.database_connectors.CrossrefConnector
            crossref_md = crossref_connector.get_masterdata_from_crossref(
                preparation=preparation, RECORD=record_copy
            )
            for key, value in crossref_md.data.items():
                if key not in fields_to_check:
                    continue
                if not isinstance(value, str):
                    continue
                if key in record.data:
                    if len(crossref_md.data[key]) < 5 or len(record.data[key]) < 5:
                        continue
                    if (
                        fuzz.partial_ratio(
                            record.data[key].lower(), crossref_md.data[key].lower()
                        )
                        < 70
                    ):
                        record.data[
                            "colrev_status"
                        ] = colrev.record.RecordState.md_needs_manual_preparation
                        record.add_masterdata_provenance_note(
                            key=key, note=f"disagreement with doi metadata ({value})"
                        )

        if "url" in record.data:
            try:
                url_connector = colrev.database_connectors.URLConnector()
                url_metadata = record.copy_prep_rec()
                url_record = url_connector.retrieve_md_from_url(
                    RECORD=url_metadata, preparation=preparation
                )
                for key, value in url_record.data.items():
                    if key not in fields_to_check:
                        continue
                    if not isinstance(value, str):
                        continue
                    if key in record.data:
                        if len(url_record.data[key]) < 5 or len(record.data[key]) < 5:
                            continue
                        if (
                            fuzz.partial_ratio(
                                record.data[key].lower(), url_record.data[key].lower()
                            )
                            < 70
                        ):
                            record.data[
                                "colrev_status"
                            ] = colrev.record.RecordState.md_needs_manual_preparation
                            record.add_masterdata_provenance_note(
                                key=key,
                                note=f"disagreement with website metadata ({value})",
                            )
            except AttributeError:
                pass

        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class CuratedPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):
        if record.masterdata_is_curated():
            if colrev.record.RecordState.md_imported == record.data["colrev_status"]:
                record.data["colrev_status"] = colrev.record.RecordState.md_prepared

        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class FormatPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = False

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):

        if "author" in record.data and "UNKNOWN" != record.data.get(
            "author", "UNKNOWN"
        ):
            # DBLP appends identifiers to non-unique authors
            record.update_field(
                key="author",
                value=str(re.sub(r"[0-9]{4}", "", record.data["author"])),
                source="FormatPrep",
                keep_source_if_equal=True,
            )

            # fix name format
            if (1 == len(record.data["author"].split(" ")[0])) or (
                ", " not in record.data["author"]
            ):
                record.update_field(
                    key="author",
                    value=colrev.record.PrepRecord.format_author_field(
                        input_string=record.data["author"]
                    ),
                    source="FormatPrep",
                    keep_source_if_equal=True,
                )

        if "title" in record.data and "UNKNOWN" != record.data.get("title", "UNKNOWN"):
            record.update_field(
                key="title",
                value=re.sub(r"\s+", " ", record.data["title"]).rstrip("."),
                source="FormatPrep",
                keep_source_if_equal=True,
            )
            if "UNKNOWN" != record.data["title"]:
                record.format_if_mostly_upper(key="title")

        if "booktitle" in record.data and "UNKNOWN" != record.data.get(
            "booktitle", "UNKNOWN"
        ):
            if "UNKNOWN" != record.data["booktitle"]:
                record.format_if_mostly_upper(key="booktitle", case="title")

                stripped_btitle = re.sub(r"\d{4}", "", record.data["booktitle"])
                stripped_btitle = re.sub(r"\d{1,2}th", "", stripped_btitle)
                stripped_btitle = re.sub(r"\d{1,2}nd", "", stripped_btitle)
                stripped_btitle = re.sub(r"\d{1,2}rd", "", stripped_btitle)
                stripped_btitle = re.sub(r"\d{1,2}st", "", stripped_btitle)
                stripped_btitle = re.sub(r"\([A-Z]{3,6}\)", "", stripped_btitle)
                stripped_btitle = stripped_btitle.replace(
                    "Proceedings of the", ""
                ).replace("Proceedings", "")
                stripped_btitle = stripped_btitle.lstrip().rstrip()
                record.update_field(
                    key="booktitle",
                    value=stripped_btitle,
                    source="FormatPrep",
                    keep_source_if_equal=True,
                )

        if "date" in record.data and "year" not in record.data:
            year = re.search(r"\d{4}", record.data["date"])
            if year:
                record.update_field(
                    key="year",
                    value=year.group(0),
                    source="FormatPrep",
                    keep_source_if_equal=True,
                )

        if "journal" in record.data and "UNKNOWN" != record.data.get(
            "journal", "UNKNOWN"
        ):
            if len(record.data["journal"]) > 10 and "UNKNOWN" != record.data["journal"]:
                record.format_if_mostly_upper(key="journal", case="title")

        if "pages" in record.data and "UNKNOWN" != record.data.get("pages", "UNKNOWN"):
            if "N.PAG" == record.data.get("pages", ""):
                record.remove_field(key="pages")
            else:
                record.unify_pages_field()
                if (
                    not re.match(r"^\d*$", record.data["pages"])
                    and not re.match(r"^\d*--\d*$", record.data["pages"])
                    and not re.match(r"^[xivXIV]*--[xivXIV]*$", record.data["pages"])
                ):
                    preparation.review_manager.report_logger.info(
                        f' {record.data["ID"]}:'.ljust(preparation.pad, " ")
                        + f'Unusual pages: {record.data["pages"]}'
                    )

        if "language" in record.data:
            # TODO : use https://pypi.org/project/langcodes/
            record.update_field(
                key="language",
                value=record.data["language"]
                .replace("English", "en")
                .replace("ENG", "en"),
                source="FormatPrep",
                keep_source_if_equal=True,
            )

        if "doi" in record.data:
            record.update_field(
                key="doi",
                value=record.data["doi"].replace("http://dx.doi.org/", "").upper(),
                source="FormatPrep",
                keep_source_if_equal=True,
            )

        if "number" not in record.data and "issue" in record.data:
            record.update_field(
                key="number",
                value=record.data["issue"],
                source="FormatPrep",
                keep_source_if_equal=True,
            )
            record.remove_field(key="issue")

        if "volume" in record.data and "UNKNOWN" != record.data.get(
            "volume", "UNKNOWN"
        ):
            record.update_field(
                key="volume",
                value=record.data["volume"].replace("Volume ", ""),
                source="FormatPrep",
                keep_source_if_equal=True,
            )

        if "url" in record.data and "fulltext" in record.data:
            if record.data["url"] == record.data["fulltext"]:
                record.remove_field(key="fulltext")

        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class BibTexCrossrefResolutionPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = False

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):
        if "crossref" in record.data:
            crossref_record = preparation.review_manager.dataset.get_crossref_record(
                record=record.data
            )
            if 0 != len(crossref_record):
                for key, value in crossref_record.items():
                    if key not in record.data:
                        record.data[key] = value

        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class SemanticScholarPrep:

    source_correction_hint = (
        "fill out the online form: "
        + "https://www.semanticscholar.org/faq#correct-error"
    )
    always_apply_changes = False

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def retrieve_record_from_semantic_scholar(
        self, *, preparation, url: str, record_in: colrev.record.PrepRecord
    ) -> colrev.record.PrepRecord:

        session = preparation.review_manager.get_cached_session()

        preparation.review_manager.logger.debug(url)
        headers = {"user-agent": f"{__name__} (mailto:{preparation.debug_mode})"}
        ret = session.request("GET", url, headers=headers, timeout=preparation.TIMEOUT)
        ret.raise_for_status()

        data = json.loads(ret.text)
        items = data["data"]
        if len(items) == 0:
            return record_in
        if "paperId" not in items[0]:
            return record_in

        paper_id = items[0]["paperId"]
        record_retrieval_url = "https://api.semanticscholar.org/v1/paper/" + paper_id
        preparation.review_manager.logger.debug(record_retrieval_url)
        ret_ent = session.request(
            "GET", record_retrieval_url, headers=headers, timeout=preparation.TIMEOUT
        )
        ret_ent.raise_for_status()
        item = json.loads(ret_ent.text)

        retrieved_record: dict = {}
        if "authors" in item:
            authors_string = " and ".join(
                [author["name"] for author in item["authors"] if "name" in author]
            )
            authors_string = colrev.record.PrepRecord.format_author_field(
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
            if "journal" in record_in.data:
                retrieved_record.update(journal=item["venue"])
            if "booktitle" in record_in.data:
                retrieved_record.update(booktitle=item["venue"])
        if "url" in item:
            retrieved_record.update(sem_scholar_id=item["url"])

        keys_to_drop = []
        for key, value in retrieved_record.items():
            retrieved_record[key] = str(value).replace("\n", " ").lstrip().rstrip()
            if value in ["", "None"] or value is None:
                keys_to_drop.append(key)
        for key in keys_to_drop:
            record_in.remove_field(key=key)

        record = colrev.record.PrepRecord(data=retrieved_record)
        record.add_provenance_all(source=record_retrieval_url)
        return record

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):

        same_record_type_required = (
            preparation.review_manager.settings.project.curated_masterdata
        )
        try:
            search_api_url = (
                "https://api.semanticscholar.org/graph/v1/paper/search?query="
            )
            url = search_api_url + record.data.get("title", "").replace(" ", "+")

            retrieved_record = self.retrieve_record_from_semantic_scholar(
                preparation=preparation, url=url, record_in=record
            )
            if "sem_scholar_id" not in retrieved_record.data:
                return record

            # Remove fields that are not/rarely available before
            # calculating similarity metrics
            orig_record = record.copy_prep_rec()
            for key in ["volume", "number", "number", "pages"]:
                if key in orig_record.data:
                    record.remove_field(key=key)

            similarity = colrev.record.PrepRecord.get_retrieval_similarity(
                record_original=orig_record,
                retrieved_record_original=retrieved_record,
                same_record_type_required=same_record_type_required,
            )
            if similarity > preparation.retrieval_similarity:
                preparation.review_manager.logger.debug("Found matching record")
                preparation.review_manager.logger.debug(
                    f"scholar similarity: {similarity} "
                    f"(>{preparation.retrieval_similarity})"
                )

                record.merge(
                    merging_record=retrieved_record,
                    default_source=retrieved_record.data["sem_scholar_id"],
                )

            else:
                preparation.review_manager.logger.debug(
                    f"scholar similarity: {similarity} "
                    f"(<{preparation.retrieval_similarity})"
                )
        except KeyError:
            pass
        except UnicodeEncodeError:
            preparation.review_manager.logger.error(
                "UnicodeEncodeError - this needs to be fixed at some time"
            )
        except requests.exceptions.RequestException:
            pass
        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class DOIFromURLsPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = False

    # https://www.crossref.org/blog/dois-and-matching-regular-expressions/
    doi_regex = re.compile(r"10\.\d{4,9}/[-._;/:A-Za-z0-9]*")

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):

        same_record_type_required = (
            preparation.review_manager.settings.project.curated_masterdata
        )

        session = preparation.review_manager.get_cached_session()

        url = record.data.get("url", record.data.get("fulltext", "NA"))
        if "NA" != url:
            try:
                preparation.review_manager.logger.debug(f"Retrieve doi-md from {url}")
                headers = {
                    "user-agent": f"{__name__}  " f"(mailto:{preparation.debug_mode})"
                }
                ret = session.request(
                    "GET", url, headers=headers, timeout=preparation.TIMEOUT
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
                        return record
                    for doi, _ in ret_dois:
                        retrieved_record = {"doi": doi.upper(), "ID": record.data["ID"]}
                        retrieved_record = colrev.record.PrepRecord(
                            data=retrieved_record
                        )
                        colrev.built_in.database_connectors.DOIConnector.retrieve_doi_metadata(
                            review_manager=preparation.review_manager,
                            RECORD=retrieved_record,
                            TIMEOUT=preparation.TIMEOUT,
                        )

                        similarity = colrev.record.PrepRecord.get_retrieval_similarity(
                            record_original=record,
                            retrieved_record_original=retrieved_record,
                            same_record_type_required=same_record_type_required,
                        )
                        if similarity > preparation.retrieval_similarity:
                            record.merge(
                                merging_record=retrieved_record, default_source=url
                            )

                            preparation.review_manager.report_logger.debug(
                                "Retrieved metadata based on doi from"
                                f' website: {record.data["doi"]}'
                            )

            except requests.exceptions.RequestException:
                pass
        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class DOIMetadataPrep:

    source_correction_hint = (
        "ask the publisher to correct the metadata"
        + " (see https://www.crossref.org/blog/"
        + "metadata-corrections-updates-and-additions-in-metadata-manager/"
    )
    always_apply_changes = False

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):
        if "doi" not in record.data:
            return record
        colrev.built_in.database_connectors.DOIConnector.retrieve_doi_metadata(
            review_manager=preparation.review_manager,
            RECORD=record,
            TIMEOUT=preparation.TIMEOUT,
        )
        colrev.built_in.database_connectors.DOIConnector.get_link_from_doi(
            RECORD=record,
            review_manager=preparation.review_manager,
        )
        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class CrossrefMetadataPrep:

    source_correction_hint = (
        "ask the publisher to correct the metadata"
        + " (see https://www.crossref.org/blog/"
        + "metadata-corrections-updates-and-additions-in-metadata-manager/"
    )
    always_apply_changes = False

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):
        colrev.built_in.database_connectors.CrossrefConnector.get_masterdata_from_crossref(
            preparation=preparation, RECORD=record
        )
        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class DBLPMetadataPrep:

    source_correction_hint = (
        "send and email to dblp@dagstuhl.de"
        + " (see https://dblp.org/faq/How+can+I+correct+errors+in+dblp.html)"
    )
    always_apply_changes = False

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):
        if "dblp_key" in record.data:
            return record

        same_record_type_required = (
            preparation.review_manager.settings.project.curated_masterdata
        )

        try:
            query = "" + record.data.get("title", "").replace("-", "_")
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
                retrieved_record
            ) in colrev.built_in.database_connectors.DBLPConnector.retrieve_dblp_records(
                review_manager=preparation.review_manager,
                query=query,
            ):
                similarity = colrev.record.PrepRecord.get_retrieval_similarity(
                    record_original=record,
                    retrieved_record_original=retrieved_record,
                    same_record_type_required=same_record_type_required,
                )
                if similarity > preparation.retrieval_similarity:
                    preparation.review_manager.logger.debug("Found matching record")
                    preparation.review_manager.logger.debug(
                        f"dblp similarity: {similarity} "
                        f"(>{preparation.retrieval_similarity})"
                    )
                    record.merge(
                        merging_record=retrieved_record,
                        default_source=retrieved_record.data["dblp_key"],
                    )
                    record.set_masterdata_complete()
                    record.set_status(
                        target_state=colrev.record.RecordState.md_prepared
                    )
                    if "Withdrawn (according to DBLP)" in record.data.get(
                        "warning", ""
                    ):
                        record.prescreen_exclude(reason="retracted")
                        record.remove_field(key="warning")

                else:
                    preparation.review_manager.logger.debug(
                        f"dblp similarity: {similarity} "
                        f"(<{preparation.retrieval_similarity})"
                    )
        except UnicodeEncodeError:
            pass
        except requests.exceptions.RequestException:
            pass
        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class OpenLibraryMetadataPrep:

    source_correction_hint = (
        "ask the publisher to correct the metadata"
        + " (see https://www.crossref.org/blog/"
        + "metadata-corrections-updates-and-additions-in-metadata-manager/"
    )
    always_apply_changes = False

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):
        def open_library_json_to_record(
            *, item: dict, url=str
        ) -> colrev.record.PrepRecord:
            retrieved_record: dict = {}

            if "author_name" in item:
                authors_string = " and ".join(
                    [
                        colrev.record.PrepRecord.format_author_field(
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

            record = colrev.record.PrepRecord(data=retrieved_record)
            record.add_provenance_all(source=url)
            return record

        if record.data.get("ENTRYTYPE", "NA") != "book":
            return record

        session = preparation.review_manager.get_cached_session()

        try:
            # TODO : integrate more functionality into open_library_json_to_record()
            url = "NA"
            if "isbn" in record.data:
                isbn = record.data["isbn"].replace("-", "").replace(" ", "")
                url = f"https://openlibrary.org/isbn/{isbn}.json"
                ret = session.request(
                    "GET",
                    url,
                    headers=preparation.requests_headers,
                    timeout=preparation.TIMEOUT,
                )
                ret.raise_for_status()
                preparation.review_manager.logger.debug(url)
                if '"error": "notfound"' in ret.text:
                    record.remove_field(key="isbn")

                item = json.loads(ret.text)

            else:
                base_url = "https://openlibrary.org/search.json?"
                url = ""
                if record.data.get("author", "NA").split(",")[0]:
                    url = (
                        base_url
                        + "&author="
                        + record.data.get("author", "NA").split(",")[0]
                    )
                if "inbook" == record.data["ENTRYTYPE"] and "editor" in record.data:
                    if record.data.get("editor", "NA").split(",")[0]:
                        url = (
                            base_url
                            + "&author="
                            + record.data.get("editor", "NA").split(",")[0]
                        )
                if base_url not in url:
                    return record

                title = record.data.get("title", record.data.get("booktitle", "NA"))
                if len(title) < 10:
                    return record
                if ":" in title:
                    title = title[: title.find(":")]  # To catch sub-titles
                url = url + "&title=" + title.replace(" ", "+")
                ret = session.request(
                    "GET",
                    url,
                    headers=preparation.requests_headers,
                    timeout=preparation.TIMEOUT,
                )
                ret.raise_for_status()
                preparation.review_manager.logger.debug(url)

                # if we have an exact match, we don't need to check the similarity
                if '"numFoundExact": true,' not in ret.text:
                    return record

                data = json.loads(ret.text)
                items = data["docs"]
                if not items:
                    return record
                item = items[0]

            retrieved_record = open_library_json_to_record(item=item, url=url)

            record.merge(merging_record=retrieved_record, default_source=url)

            # if "title" in record.data and "booktitle" in record.data:
            #     record.remove_field(key="booktitle")

        except requests.exceptions.RequestException:
            pass
        except UnicodeEncodeError:
            preparation.review_manager.logger.error(
                "UnicodeEncodeError - this needs to be fixed at some time"
            )

        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class CiteAsPrep:

    source_correction_hint = "Search on https://citeas.org/ and click 'modify'"
    always_apply_changes = False

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):
        def cite_as_json_to_record(*, data: dict, url=str) -> colrev.record.PrepRecord:
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

            record = colrev.record.PrepRecord(data=retrieved_record)
            record.add_provenance_all(source=url)
            return record

        if record.data.get("ENTRYTYPE", "NA") not in ["misc", "software"]:
            return record
        if "title" not in record.data:
            return record

        try:

            same_record_type_required = (
                preparation.review_manager.settings.project.curated_masterdata
            )

            session = preparation.review_manager.get_cached_session()
            url = (
                f"https://api.citeas.org/product/{record.data['title']}?"
                + f"email={preparation.debug_mode}"
            )
            ret = session.request(
                "GET",
                url,
                headers=preparation.requests_headers,
                timeout=preparation.TIMEOUT,
            )
            ret.raise_for_status()
            preparation.review_manager.logger.debug(url)

            data = json.loads(ret.text)

            retrieved_record = cite_as_json_to_record(data=data, url=url)

            similarity = colrev.record.PrepRecord.get_retrieval_similarity(
                record_original=retrieved_record,
                retrieved_record_original=retrieved_record,
                same_record_type_required=same_record_type_required,
            )
            if similarity > preparation.retrieval_similarity:

                record.merge(merging_record=retrieved_record, default_source=url)

        except requests.exceptions.RequestException:
            pass
        except UnicodeEncodeError:
            preparation.review_manager.logger.error(
                "UnicodeEncodeError - this needs to be fixed at some time"
            )

        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class CrossrefYearVolIssPrep:

    source_correction_hint = (
        "ask the publisher to correct the metadata"
        + " (see https://www.crossref.org/blog/"
        + "metadata-corrections-updates-and-additions-in-metadata-manager/"
    )
    always_apply_changes = True

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):

        # The year depends on journal x volume x issue
        if (
            "journal" in record.data
            and "volume" in record.data
            and "number" in record.data
        ) and "UNKNOWN" == record.data.get("year", "UNKNOWN"):
            pass
        else:
            return record

        CrossrefConnector = colrev.built_in.database_connectors.CrossrefConnector
        try:

            retrieved_records = CrossrefConnector.crossref_query(
                review_manager=preparation.review_manager,
                record_input=record,
                jour_vol_iss_list=True,
                TIMEOUT=preparation.TIMEOUT,
            )
            retries = 0
            while not retrieved_records and retries < preparation.MAX_RETRIES_ON_ERROR:
                retries += 1
                retrieved_records = CrossrefConnector.crossref_query(
                    review_manager=preparation.review_manager,
                    record_input=record,
                    jour_vol_iss_list=True,
                    TIMEOUT=preparation.TIMEOUT,
                )
            if 0 == len(retrieved_records):
                return record

            retrieved_records = [
                retrieved_record
                for retrieved_record in retrieved_records
                if retrieved_record.data.get("volume", "NA")
                == record.data.get("volume", "NA")
                and retrieved_record.data.get("journal", "NA")
                == record.data.get("journal", "NA")
                and retrieved_record.data.get("number", "NA")
                == record.data.get("number", "NA")
            ]

            years = [r.data["year"] for r in retrieved_records]
            if len(years) == 0:
                return record
            most_common = max(years, key=years.count)
            preparation.review_manager.logger.debug(most_common)
            preparation.review_manager.logger.debug(years.count(most_common))
            if years.count(most_common) > 3:
                record.update_field(
                    key="year", value=most_common, source="CROSSREF(average)"
                )
        except requests.exceptions.RequestException:
            pass
        except KeyboardInterrupt:
            sys.exit()

        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class LocalIndexPrep:

    source_correction_hint = (
        "correct the metadata in the source "
        + "repository (as linked in the provenance field)"
    )
    always_apply_changes = True

    def __init__(self, *, preparation, settings):

        self.local_index = preparation.review_manager.get_local_index()

        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):

        # TODO: how to distinguish masterdata and complementary CURATED sources?

        # TBD: maybe extract the following three lines as a separate script...
        if not record.masterdata_is_curated():
            year = self.local_index.get_year_from_toc(record=record.get_data())
            if "NA" != year:
                record.update_field(
                    key="year",
                    value=year,
                    source="LocalIndexPrep",
                    keep_source_if_equal=True,
                )

        # Note : cannot use local_index as an attribute of PrepProcess
        # because it creates problems with multiprocessing
        retrieved = False
        try:
            retrieved_record_dict = self.local_index.retrieve(
                record=record.get_data(), include_file=False
            )
            retrieved = True
        except (colrev_exceptions.RecordNotInIndexException, NotFoundError):
            try:
                # Note: Records can be CURATED without being indexed
                if not record.masterdata_is_curated():
                    retrieved_record_dict = self.local_index.retrieve_from_toc(
                        record=record.data,
                        similarity_threshold=preparation.retrieval_similarity,
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
            retrieved_record = colrev.record.PrepRecord(data=retrieved_record_dict)

            default_source = "UNDETERMINED"
            if "colrev_masterdata_provenance" in retrieved_record.data:
                if "CURATED" in retrieved_record.data["colrev_masterdata_provenance"]:
                    default_source = retrieved_record.data[
                        "colrev_masterdata_provenance"
                    ]["CURATED"]["source"]
            record.merge(
                merging_record=retrieved_record,
                default_source=default_source,
            )

            git_repo = git.Repo(str(preparation.review_manager.path))
            cur_project_source_paths = [str(preparation.review_manager.path)]
            for remote in git_repo.remotes:
                if remote.url:
                    shared_url = remote.url
                    shared_url = shared_url.rstrip(".git")
                    cur_project_source_paths.append(shared_url)
                    break

            # extend fields_to_keep (to retrieve all fields from the index)
            for key in retrieved_record.data.keys():
                if key not in preparation.fields_to_keep:
                    preparation.fields_to_keep.append(key)

        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class RemoveNicknamesPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = False

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):
        if "author" in record.data:
            # Replace nicknames in parentheses
            record.data["author"] = re.sub(r"\([^)]*\)", "", record.data["author"])
            record.data["author"] = record.data["author"].replace("  ", " ")
        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class FormatMinorPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = False
    HTML_CLEANER = re.compile("<.*?>")

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):

        for field in list(record.data.keys()):
            # Note : some dois (and their provenance) contain html entities
            if field in [
                "colrev_masterdata_provenance",
                "colrev_data_provenance",
                "doi",
            ]:
                continue
            if field in ["author", "title", "journal"]:
                record.data[field] = re.sub(r"\s+", " ", record.data[field])
                record.data[field] = re.sub(self.HTML_CLEANER, "", record.data[field])

        if record.data.get("volume", "") == "ahead-of-print":
            record.remove_field(key="volume")
        if record.data.get("number", "") == "ahead-of-print":
            record.remove_field(key="number")

        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class DropFieldsPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = False

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):

        for key in list(record.data.keys()):
            if key not in preparation.fields_to_keep:
                record.remove_field(key=key)
                preparation.review_manager.report_logger.info(f"Dropped {key} field")

            elif record.data[key] in ["", "NA"]:
                record.remove_field(key=key)

        if record.data.get("publisher", "") in ["researchgate.net"]:
            record.remove_field(key="publisher")

        if "volume" in record.data.keys() and "number" in record.data.keys():
            # Note : cannot use local_index as an attribute of PrepProcess
            # because it creates problems with multiprocessing

            self.local_index = preparation.review_manager.get_local_index()

            fields_to_remove = self.local_index.get_fields_to_remove(
                record=record.get_data()
            )
            for field_to_remove in fields_to_remove:
                if field_to_remove in record.data:
                    # TODO : maybe use set_masterdata_complete()?
                    record.remove_field(
                        key=field_to_remove, not_missing_note=True, source="local_index"
                    )

        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class RemoveRedundantFieldPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = False

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):

        if "article" == record.data["ENTRYTYPE"]:
            if "journal" in record.data and "booktitle" in record.data:
                if (
                    fuzz.partial_ratio(
                        record.data["journal"].lower(), record.data["booktitle"].lower()
                    )
                    / 100
                    > 0.9
                ):
                    record.remove_field(key="booktitle")
        if "inproceedings" == record.data["ENTRYTYPE"]:
            if "journal" in record.data and "booktitle" in record.data:
                if (
                    fuzz.partial_ratio(
                        record.data["journal"].lower(), record.data["booktitle"].lower()
                    )
                    / 100
                    > 0.9
                ):
                    record.remove_field(key="journal")
        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class CorrectRecordTypePrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):

        if record.has_inconsistent_fields() and not record.masterdata_is_curated():
            pass
        else:
            return record

        if preparation.retrieval_similarity > 0.9:
            return record

        if (
            "dissertation" in record.data.get("fulltext", "NA").lower()
            and record.data["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = record.data["ENTRYTYPE"]
            record.data.update(ENTRYTYPE="phdthesis")
            preparation.review_manager.report_logger.info(
                f' {record.data["ID"]}'.ljust(preparation.pad, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("dissertation" in fulltext link)'
            )

        if (
            "thesis" in record.data.get("fulltext", "NA").lower()
            and record.data["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = record.data["ENTRYTYPE"]
            record.data.update(ENTRYTYPE="phdthesis")
            preparation.review_manager.report_logger.info(
                f' {record.data["ID"]}'.ljust(preparation.pad, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("thesis" in fulltext link)'
            )

        if (
            "This thesis" in record.data.get("abstract", "NA").lower()
            and record.data["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = record.data["ENTRYTYPE"]
            record.data.update(ENTRYTYPE="phdthesis")
            preparation.review_manager.report_logger.info(
                f' {record.data["ID"]}'.ljust(preparation.pad, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("thesis" in abstract)'
            )

        # Journal articles should not have booktitles/series set.
        if "article" == record.data["ENTRYTYPE"]:
            if "booktitle" in record.data:
                if "journal" not in record.data:
                    record.data.update(journal=record.data["booktitle"])
                    record.remove_field(key="booktitle")
            if "series" in record.data:
                if "journal" not in record.data:
                    record.data.update(journal=record.data["series"])
                    record.remove_field(key="series")

        if "article" == record.data["ENTRYTYPE"]:
            if "journal" not in record.data:
                if "series" in record.data:
                    journal_string = record.data["series"]
                    record.data.update(journal=journal_string)
                    record.remove_field(key="series")
        return record


@zope.interface.implementer(colrev.process.PreparationEndpoint)
class UpdateMetadataStatusPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, preparation, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, preparation, record):

        record.update_metadata_status(review_manager=preparation.review_manager)
        return record
