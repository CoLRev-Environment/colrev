#! /usr/bin/env python
"""Connectors to academic databases (APIs)"""
from __future__ import annotations

import html
import json
import re
import sys
import typing
import urllib
from sqlite3 import OperationalError
from typing import TYPE_CHECKING
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup
from thefuzz import fuzz

import colrev.exceptions as colrev_exceptions
import colrev.record


if TYPE_CHECKING:
    import colrev.ops.prep


# pylint: disable=too-few-public-methods
# pylint: disable=too-many-lines


class OpenLibraryConnector:
    @classmethod
    def check_status(cls, *, prep_operation: colrev.ops.prep.Prep) -> None:

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
            ret = requests.get(
                url,
                headers=prep_operation.requests_headers,
                timeout=prep_operation.timeout,
            )
            if ret.status_code != 200:
                if not prep_operation.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException("OPENLIBRARY")
        except requests.exceptions.RequestException as exc:
            if not prep_operation.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException(
                    "OPENLIBRARY"
                ) from exc


class URLConnector:
    @classmethod
    def __update_record(
        cls,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        item: dict,
    ) -> None:
        # pylint: disable=too-many-branches

        record.data["ID"] = item["key"]
        record.data["ENTRYTYPE"] = "article"  # default
        if "journalArticle" == item.get("itemType", ""):
            record.data["ENTRYTYPE"] = "article"
            if "publicationTitle" in item:
                record.data["journal"] = item["publicationTitle"]
            if "volume" in item:
                record.data["volume"] = item["volume"]
            if "issue" in item:
                record.data["number"] = item["issue"]
        if "conferencePaper" == item.get("itemType", ""):
            record.data["ENTRYTYPE"] = "inproceedings"
            if "proceedingsTitle" in item:
                record.data["booktitle"] = item["proceedingsTitle"]
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
            record.data["author"] = author_str
        if "title" in item:
            record.data["title"] = item["title"]
        if "doi" in item:
            record.data["doi"] = item["doi"]
        if "date" in item:
            year = re.search(r"\d{4}", item["date"])
            if year:
                record.data["year"] = year.group(0)
        if "pages" in item:
            record.data["pages"] = item["pages"]
        if "url" in item:
            if "https://doi.org/" in item["url"]:
                record.data["doi"] = item["url"].replace("https://doi.org/", "")
                dummy_record = colrev.record.PrepRecord(
                    data={"doi": record.data["doi"]}
                )
                DOIConnector.get_link_from_doi(
                    record=dummy_record,
                    review_manager=prep_operation.review_manager,
                )
                if "https://doi.org/" not in dummy_record.data["url"]:
                    record.data["url"] = dummy_record.data["url"]
            else:
                record.data["url"] = item["url"]

        if "tags" in item:
            if len(item["tags"]) > 0:
                keywords = ", ".join([k["tag"] for k in item["tags"]])
                record.data["keywords"] = keywords

    @classmethod
    def retrieve_md_from_url(
        cls, *, record: colrev.record.Record, prep_operation: colrev.ops.prep.Prep
    ) -> None:

        zotero_translation_service = (
            prep_operation.review_manager.get_zotero_translation_service()
        )

        # Note: retrieve_md_from_url replaces prior data in RECORD
        # (record.copy() - deepcopy() before if necessary)

        zotero_translation_service.start_zotero_translators()

        # TODO : change to the similar merge()/fuse_best_field structure?

        try:
            content_type_header = {"Content-type": "text/plain"}
            headers = {**prep_operation.requests_headers, **content_type_header}
            export = requests.post(
                "http://127.0.0.1:1969/web",
                headers=headers,
                data=record.data["url"],
                timeout=prep_operation.timeout,
            )

            if export.status_code != 200:
                return

            items = json.loads(export.content.decode())
            if len(items) == 0:
                return
            item = items[0]
            if "Shibboleth Authentication Request" == item["title"]:
                return

            cls.__update_record(prep_operation=prep_operation, record=record, item=item)

        except (
            json.decoder.JSONDecodeError,
            UnicodeEncodeError,
            requests.exceptions.RequestException,
            KeyError,
        ):
            pass


class DOIConnector:
    @classmethod
    def retrieve_doi_metadata(
        cls,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        record: colrev.record.PrepRecord,
        timeout: int = 10,
    ) -> colrev.record.Record:
        if "doi" not in record.data:
            return record

        try:

            session = review_manager.get_cached_session()

            # for testing:
            # curl -iL -H "accept: application/vnd.citationstyles.csl+json"
            # -H "Content-Type: application/json" http://dx.doi.org/10.1111/joop.12368

            try:
                url = "http://dx.doi.org/" + record.data["doi"]
                review_manager.logger.debug(url)
                headers = {"accept": "application/vnd.citationstyles.csl+json"}
                ret = session.request("GET", url, headers=headers, timeout=timeout)
                ret.raise_for_status()
                if ret.status_code != 200:
                    review_manager.report_logger.info(
                        f' {record.data["ID"]}'
                        + "metadata for "
                        + f'doi  {record.data["doi"]} not (yet) available'
                    )
                    return record

                retrieved_json = json.loads(ret.text)
                retrieved_record_dict = CrossrefConnector.crossref_json_to_record(
                    item=retrieved_json
                )
                retrieved_record = colrev.record.PrepRecord(data=retrieved_record_dict)
                retrieved_record.add_provenance_all(source=url)
                record.merge(merging_record=retrieved_record, default_source=url)
                record.set_masterdata_complete(source_identifier=url)
                if "colrev_status" in record.data:
                    record.set_status(
                        target_state=colrev.record.RecordState.md_prepared
                    )
                if "retracted" in record.data.get("warning", ""):
                    record.prescreen_exclude(reason="retracted")
                    record.remove_field(key="warning")

            except (json.decoder.JSONDecodeError, TypeError) as exc:
                print(exc)
            except requests.exceptions.RequestException:
                return record
            except OperationalError as exc:
                raise colrev_exceptions.ServiceNotAvailableException(
                    "sqlite, required for requests CachedSession "
                    "(possibly caused by concurrent operations)"
                ) from exc

            if "title" in record.data:
                record.format_if_mostly_upper(key="title")

        except OperationalError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            ) from exc

        return record

    @classmethod
    def get_link_from_doi(
        cls,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        record: colrev.record.Record,
        timeout: int = 10,
    ) -> None:

        doi_url = f"https://www.doi.org/{record.data['doi']}"

        # TODO : retry for 50X
        # from requests.adapters import HTTPAdapter
        # from requests.adapters import Retry
        # example for testing: ({'doi':'10.1177/02683962221086300'})
        # s = requests.Session()
        # headers = {"user-agent": f"{__name__} (mailto:{review_manager.email})"}
        # retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 502, 503, 504 ])
        # s.mount('https://', HTTPAdapter(max_retries=retries))
        # ret = s.get(url, headers=headers)
        # print(ret)

        def meta_redirect(*, content: bytes) -> str:
            if "<!DOCTYPE HTML PUBLIC" not in str(content):
                raise TypeError
            soup = BeautifulSoup(content, "lxml")
            result = soup.find("meta", attrs={"http-equiv": "REFRESH"})
            if result:
                _, text = result["content"].split(";")
                if "http" in text:
                    url = text[text.lower().find("http") :]
                    url = unquote(url, encoding="utf-8", errors="replace")
                    url = url[: url.find("?")]
                    return str(url)
            return ""

        try:
            url = doi_url

            session = review_manager.get_cached_session()

            requests_headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/39.0.2171.95 Safari/537.36"
            }
            ret = session.request(
                "GET",
                doi_url,
                headers=requests_headers,
                timeout=timeout,
            )
            if 503 == ret.status_code:
                return
            if (
                200 == ret.status_code
                and "doi.org" not in ret.url
                and "linkinghub" not in ret.url
            ):
                url = ret.url
            else:
                # follow the chain of redirects
                while meta_redirect(content=ret.content):
                    url = meta_redirect(content=ret.content)
                    ret = session.request(
                        "GET",
                        url,
                        headers=requests_headers,
                        timeout=timeout,
                    )
            record.update_field(
                key="url",
                value=str(url.rstrip("/")),
                source=doi_url,
                keep_source_if_equal=True,
            )
        except (requests.exceptions.RequestException, TypeError):
            pass
        except OperationalError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            ) from exc


class CrossrefConnector:

    issn_regex = r"^\d{4}-?\d{3}[\dxX]$"

    # https://github.com/CrossRef/rest-api-doc
    api_url = "https://api.crossref.org/works?"

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager):

        # pylint: disable=import-outside-toplevel
        from crossref.restful import Etiquette
        from importlib.metadata import version

        self.etiquette = Etiquette(
            "CoLRev",
            version("colrev"),
            "https://github.com/geritwagner/colrev",
            review_manager.email,
        )

    @classmethod
    def check_status(cls, *, prep_operation: colrev.ops.prep.Prep) -> None:

        try:
            test_rec = {
                "doi": "10.17705/1cais.04607",
                "author": "Schryen, Guido and Wagner, Gerit and Benlian, Alexander "
                "and Paré, Guy",
                "title": "A Knowledge Development Perspective on Literature Reviews: "
                "Validation of a new Typology in the IS Field",
                "ID": "SchryenEtAl2021",
                "journal": "Communications of the Association for Information Systems",
                "ENTRYTYPE": "article",
            }
            returned_record = cls.crossref_query(
                review_manager=prep_operation.review_manager,
                record_input=colrev.record.PrepRecord(data=test_rec),
                jour_vol_iss_list=False,
                timeout=prep_operation.timeout,
            )[0]

            if 0 != len(returned_record.data):
                assert returned_record.data["title"] == test_rec["title"]
                assert returned_record.data["author"] == test_rec["author"]
            else:
                if not prep_operation.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException("CROSSREF")
        except (requests.exceptions.RequestException, IndexError) as exc:
            print(exc)
            if not prep_operation.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException(
                    "CROSSREF"
                ) from exc

    def get_bibliographic_query_return(self, **kwargs) -> typing.Iterator[dict]:  # type: ignore
        # pylint: disable=import-outside-toplevel
        from crossref.restful import Works

        assert all(k in ["bibliographic"] for k in kwargs)

        works = Works(etiquette=self.etiquette)
        # use facets:
        # https://api.crossref.org/swagger-ui/index.html#/Works/get_works

        crossref_query_return = works.query(**kwargs)
        for item in crossref_query_return:
            yield self.crossref_json_to_record(item=item)

    def get_journal_query_return(self, *, journal_issn: str) -> typing.Iterator[dict]:
        # pylint: disable=import-outside-toplevel
        from crossref.restful import Journals

        assert re.match(self.issn_regex, journal_issn)

        journals = Journals(etiquette=self.etiquette)
        crossref_query_return = journals.works(journal_issn).query()
        for item in crossref_query_return:
            yield self.crossref_json_to_record(item=item)

    @classmethod
    def crossref_json_to_record(cls, *, item: dict) -> dict:
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-statements
        # pylint: disable=too-many-locals

        # Note: the format differst between crossref and doi.org
        record_dict: dict = {}

        # Note : better use the doi-link resolution
        if "link" in item:
            fulltext_link_l = [
                u["URL"] for u in item["link"] if "pdf" in u["content-type"]
            ]
            if len(fulltext_link_l) == 1:
                record_dict["fulltext"] = fulltext_link_l.pop()
        #     item["link"] = [u for u in item["link"] if "pdf" not in u["content-type"]]
        #     if len(item["link"]) >= 1:
        #         link = item["link"][0]["URL"]
        #         if link != record_dict.get("fulltext", ""):
        #             record_dict["link"] = link

        if "title" in item:
            if isinstance(item["title"], list):
                if len(item["title"]) > 0:
                    retrieved_title = item["title"][0]
                    retrieved_title = re.sub(r"\s+", " ", str(retrieved_title))
                    retrieved_title = retrieved_title.replace("\n", " ")
                    record_dict.update(title=retrieved_title)
            elif isinstance(item["title"], str):
                retrieved_title = item["title"]
                record_dict.update(title=retrieved_title)

        container_title = ""
        if "container-title" in item:
            if isinstance(item["container-title"], list):
                if len(item["container-title"]) > 0:
                    container_title = item["container-title"][0]
            elif isinstance(item["container-title"], str):
                container_title = item["container-title"]

        container_title = container_title.replace("\n", " ")
        container_title = re.sub(r"\s+", " ", container_title)
        if "type" in item:
            if "journal-article" == item.get("type", "NA"):
                record_dict.update(ENTRYTYPE="article")
                if container_title is not None:
                    record_dict.update(journal=container_title)
            if "proceedings-article" == item.get("type", "NA"):
                record_dict.update(ENTRYTYPE="inproceedings")
                if container_title is not None:
                    record_dict.update(booktitle=container_title)
            if "book" == item.get("type", "NA"):
                record_dict.update(ENTRYTYPE="book")
                if container_title is not None:
                    record_dict.update(series=container_title)

        if "DOI" in item:
            record_dict.update(doi=item["DOI"].upper())

        authors = [
            f'{author["family"]}, {author.get("given", "")}'
            for author in item.get("author", "NA")
            if "family" in author
        ]
        authors_string = " and ".join(authors)
        # authors_string = PrepRecord.format_author_field(authors_string)
        record_dict.update(author=authors_string)

        try:
            if "published-print" in item:
                date_parts = item["published-print"]["date-parts"]
                record_dict.update(year=str(date_parts[0][0]))
            elif "published-online" in item:
                date_parts = item["published-online"]["date-parts"]
                record_dict.update(year=str(date_parts[0][0]))
        except KeyError:
            pass

        retrieved_pages = item.get("page", "")
        if retrieved_pages != "":
            # DOI data often has only the first page.
            if (
                not record_dict.get("pages", "no_pages") in retrieved_pages
                and "-" in retrieved_pages
            ):
                record = colrev.record.PrepRecord(data=record_dict)
                record.unify_pages_field()
                record_dict = record.get_data()

        retrieved_volume = item.get("volume", "")
        if not retrieved_volume == "":
            record_dict.update(volume=str(retrieved_volume))

        retrieved_number = item.get("issue", "")
        if "journal-issue" in item:
            if "issue" in item["journal-issue"]:
                retrieved_number = item["journal-issue"]["issue"]
        if not retrieved_number == "":
            record_dict.update(number=str(retrieved_number))

        if "abstract" in item:
            retrieved_abstract = item["abstract"]
            if not retrieved_abstract == "":
                retrieved_abstract = re.sub(
                    r"<\/?jats\:[^>]*>", " ", retrieved_abstract
                )
                retrieved_abstract = re.sub(r"\s+", " ", retrieved_abstract)
                retrieved_abstract = str(retrieved_abstract).replace("\n", "")
                retrieved_abstract = retrieved_abstract.lstrip().rstrip()
                record_dict.update(abstract=retrieved_abstract)

        if "language" in item:
            record_dict["language"] = item["language"]
            # convert to ISO 639-3
            # TODO : other languages/more systematically
            if "en" == record_dict["language"]:
                record_dict["language"] = record_dict["language"].replace("en", "eng")

        if (
            "published-print" not in item
            and "volume" not in record_dict
            and "number" not in record_dict
            and "year" in record_dict
        ):
            record_dict.update(published_online=record_dict["year"])
            record_dict.update(year="forthcoming")

        if "is-referenced-by-count" in item:
            record_dict["cited_by"] = item["is-referenced-by-count"]

        if "update-to" in item:
            for update_item in item["update-to"]:
                if update_item["type"] == "retraction":
                    record_dict["warning"] = "retracted"

        for key, value in record_dict.items():
            record_dict[key] = str(value).replace("{", "").replace("}", "")
            if key in ["colrev_masterdata_provenance", "colrev_data_provenance", "doi"]:
                continue
            # Note : some dois (and their provenance) contain html entities
            record_dict[key] = html.unescape(str(value))

        if "ENTRYTYPE" not in record_dict:
            record_dict["ENTRYTYPE"] = "misc"

        return record_dict

    @classmethod
    def __create_query_url(
        cls, *, record: colrev.record.Record, jour_vol_iss_list: bool
    ) -> str:

        if jour_vol_iss_list:
            params = {"rows": "50"}
            container_title = re.sub(r"[\W]+", " ", record.data["journal"])
            params["query.container-title"] = container_title.replace("_", " ")

            query_field = ""
            if "volume" in record.data:
                query_field = record.data["volume"]
            if "number" in record.data:
                query_field = query_field + "+" + record.data["number"]
            params["query"] = query_field

        else:
            params = {"rows": "15"}
            bibl = (
                record.data["title"].replace("-", "_")
                + " "
                + record.data.get("year", "")
            )
            bibl = re.sub(r"[\W]+", "", bibl.replace(" ", "_"))
            params["query.bibliographic"] = bibl.replace("_", " ")

            container_title = record.get_container_title()
            if "." not in container_title:
                container_title = container_title.replace(" ", "_")
                container_title = re.sub(r"[\W]+", "", container_title)
                params["query.container-title"] = container_title.replace("_", " ")

            author_last_names = [
                x.split(",")[0] for x in record.data.get("author", "").split(" and ")
            ]
            author_string = " ".join(author_last_names)
            author_string = re.sub(r"[\W]+", "", author_string.replace(" ", "_"))
            params["query.author"] = author_string.replace("_", " ")

        url = cls.api_url + urllib.parse.urlencode(params)
        return url

    @classmethod
    def __get_similarity(
        cls, *, record: colrev.record.Record, retrieved_record_dict: dict
    ) -> float:
        title_similarity = fuzz.partial_ratio(
            retrieved_record_dict["title"].lower(),
            record.data.get("title", "").lower(),
        )
        container_similarity = fuzz.partial_ratio(
            colrev.record.PrepRecord(data=retrieved_record_dict)
            .get_container_title()
            .lower(),
            record.get_container_title().lower(),
        )
        weights = [0.6, 0.4]
        similarities = [title_similarity, container_similarity]

        similarity = sum(similarities[g] * weights[g] for g in range(len(similarities)))
        # logger.debug(f'record: {pp.pformat(record)}')
        # logger.debug(f'similarities: {similarities}')
        # logger.debug(f'similarity: {similarity}')
        # pp.pprint(retrieved_record_dict)
        return similarity

    @classmethod
    def crossref_query(
        cls,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        record_input: colrev.record.Record,
        jour_vol_iss_list: bool = False,
        timeout: int = 10,
    ) -> list:

        # pylint: disable=too-many-branches
        # pylint: disable=too-many-statements
        # pylint: disable=too-many-locals

        # Note : only returning a multiple-item list for jour_vol_iss_list

        try:

            record = record_input.copy_prep_rec()

            url = cls.__create_query_url(
                record=record, jour_vol_iss_list=jour_vol_iss_list
            )
            headers = {"user-agent": f"{__name__} (mailto:{review_manager.email})"}
            record_list = []
            session = review_manager.get_cached_session()

            review_manager.logger.debug(url)
            ret = session.request("GET", url, headers=headers, timeout=timeout)
            ret.raise_for_status()
            if ret.status_code != 200:
                review_manager.logger.debug(
                    f"crossref_query failed with status {ret.status_code}"
                )
                return []

            most_similar, most_similar_record = 0.0, {}
            data = json.loads(ret.text)
            for item in data["message"]["items"]:
                if "title" not in item:
                    continue

                retrieved_record_dict = cls.crossref_json_to_record(item=item)

                similarity = cls.__get_similarity(
                    record=record, retrieved_record_dict=retrieved_record_dict
                )

                retrieved_record = colrev.record.PrepRecord(data=retrieved_record_dict)
                if "retracted" in retrieved_record.data.get("warning", ""):
                    retrieved_record.prescreen_exclude(reason="retracted")
                    retrieved_record.remove_field(key="warning")

                source = (
                    f'https://api.crossref.org/works/{retrieved_record.data["doi"]}'
                )
                retrieved_record.add_provenance_all(source=source)

                record.set_masterdata_complete(source_identifier=source)

                if jour_vol_iss_list:
                    record_list.append(retrieved_record)
                if most_similar < similarity:
                    most_similar = similarity
                    most_similar_record = retrieved_record.get_data()
        except json.decoder.JSONDecodeError:
            pass
        except requests.exceptions.RequestException:
            return []
        except OperationalError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            ) from exc

        if not jour_vol_iss_list:
            record_list = [colrev.record.PrepRecord(data=most_similar_record)]

        return record_list

    @classmethod
    def get_masterdata_from_crossref(
        cls,
        *,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        timeout: int = 10,
    ) -> colrev.record.Record:
        # To test the metadata provided for a particular DOI use:
        # https://api.crossref.org/works/DOI

        # https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
        if len(record.data.get("title", "")) > 35:
            try:

                retrieved_records = CrossrefConnector.crossref_query(
                    review_manager=prep_operation.review_manager,
                    record_input=record,
                    jour_vol_iss_list=False,
                    timeout=timeout,
                )
                retrieved_record = retrieved_records.pop()

                retries = 0
                while (
                    not retrieved_record
                    and retries < prep_operation.max_retries_on_error
                ):
                    retries += 1

                    retrieved_records = CrossrefConnector.crossref_query(
                        review_manager=prep_operation.review_manager,
                        record_input=record,
                        jour_vol_iss_list=False,
                        timeout=timeout,
                    )
                    retrieved_record = retrieved_records.pop()

                if 0 == len(retrieved_record.data):
                    return record

                similarity = colrev.record.PrepRecord.get_retrieval_similarity(
                    record_original=record, retrieved_record_original=retrieved_record
                )
                if similarity > prep_operation.retrieval_similarity:
                    prep_operation.review_manager.logger.debug("Found matching record")
                    prep_operation.review_manager.logger.debug(
                        f"crossref similarity: {similarity} "
                        f"(>{prep_operation.retrieval_similarity})"
                    )
                    source = (
                        f"https://api.crossref.org/works/{retrieved_record.data['doi']}"
                    )
                    retrieved_record.add_provenance_all(source=source)
                    record.merge(merging_record=retrieved_record, default_source=source)

                    if "retracted" in record.data.get("warning", ""):
                        record.prescreen_exclude(reason="retracted")
                        record.remove_field(key="warning")
                    else:
                        DOIConnector.get_link_from_doi(
                            review_manager=prep_operation.review_manager,
                            record=record,
                        )
                        record.set_masterdata_complete(source_identifier=source)
                        record.set_status(
                            target_state=colrev.record.RecordState.md_prepared
                        )

                else:
                    prep_operation.review_manager.logger.debug(
                        f"crossref similarity: {similarity} "
                        f"(<{prep_operation.retrieval_similarity})"
                    )

            except requests.exceptions.RequestException:
                pass
            except IndexError:
                pass
            except KeyboardInterrupt:
                sys.exit()
        return record


class DBLPConnector:
    api_url = "https://dblp.org/search/publ/api?q="
    api_url_venues = "https://dblp.org/search/venue/api?q="

    @classmethod
    def check_status(cls, *, prep_operation: colrev.ops.prep.Prep) -> None:

        try:
            test_rec = {
                "ENTRYTYPE": "article",
                "doi": "10.17705/1cais.04607",
                "author": "Schryen, Guido and Wagner, Gerit and Benlian, Alexander "
                "and Paré, Guy",
                "title": "A Knowledge Development Perspective on Literature Reviews: "
                "Validation of a new Typology in the IS Field",
                "ID": "SchryenEtAl2021",
                "journal": "Communications of the Association for Information Systems",
                "volume": "46",
                "year": "2020",
                "colrev_status": colrev.record.RecordState.md_prepared,  # type: ignore
            }

            query = "" + str(test_rec.get("title", "")).replace("-", "_")

            dblp_record = DBLPConnector.retrieve_dblp_records(
                review_manager=prep_operation.review_manager,
                query=query,
            )[0]

            if 0 != len(dblp_record.data):
                assert dblp_record.data["title"] == test_rec["title"]
                assert dblp_record.data["author"] == test_rec["author"]
            else:
                if not prep_operation.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException("DBLP")
        except requests.exceptions.RequestException as exc:
            if not prep_operation.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException("DBLP") from exc

    @classmethod
    def __get_dblp_venue(
        cls,
        *,
        session: requests.Session,
        review_manager: colrev.review_manager.ReviewManager,
        timeout: int,
        venue_string: str,
        venue_type: str,
    ) -> str:
        # Note : venue_string should be like "behaviourIT"
        # Note : journals that have been renamed seem to return the latest
        # journal name. Example:
        # https://dblp.org/db/journals/jasis/index.html
        venue = venue_string
        url = cls.api_url_venues + venue_string.replace(" ", "+") + "&format=json"
        headers = {"user-agent": f"{__name__} (mailto:{review_manager.email})"}
        try:
            ret = session.request("GET", url, headers=headers, timeout=timeout)
            ret.raise_for_status()
            data = json.loads(ret.text)
            if "hit" not in data["result"]["hits"]:
                return ""
            hits = data["result"]["hits"]["hit"]
            for hit in hits:
                if hit["info"]["type"] != venue_type:
                    continue
                if f"/{venue_string.lower()}/" in hit["info"]["url"].lower():
                    venue = hit["info"]["venue"]
                    break

            venue = re.sub(r" \(.*?\)", "", venue)
        except requests.exceptions.RequestException:
            pass
        return venue

    @classmethod
    def __dblp_json_to_dict(
        cls,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        session: requests.Session,
        item: dict,
        timeout: int,
    ) -> dict:
        # pylint: disable=too-many-branches

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
            ven_key = item["key"][lpos:rpos]
            retrieved_record["journal"] = cls.__get_dblp_venue(
                session=session,
                review_manager=review_manager,
                timeout=timeout,
                venue_string=ven_key,
                venue_type="Journal",
            )
        if "Conference and Workshop Papers" == item["type"]:
            retrieved_record["ENTRYTYPE"] = "inproceedings"
            lpos = item["key"].find("/") + 1
            rpos = item["key"].rfind("/")
            ven_key = item["key"][lpos:rpos]
            retrieved_record["booktitle"] = cls.__get_dblp_venue(
                session=session,
                review_manager=review_manager,
                venue_string=ven_key,
                venue_type="Conference or Workshop",
                timeout=timeout,
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
                author_string = colrev.record.PrepRecord.format_author_field(
                    input_string=author_string
                )
                retrieved_record["author"] = author_string

        if "key" in item:
            retrieved_record["dblp_key"] = "https://dblp.org/rec/" + item["key"]

        if "doi" in item:
            retrieved_record["doi"] = item["doi"].upper()
        if "ee" in item:
            if "https://doi.org" not in item["ee"]:
                retrieved_record["url"] = item["ee"]

        for key, value in retrieved_record.items():
            retrieved_record[key] = (
                html.unescape(value).replace("{", "").replace("}", "")
            )

        return retrieved_record

    @classmethod
    def retrieve_dblp_records(
        cls,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        query: str = None,
        url: str = None,
        timeout: int = 10,
    ) -> list:

        try:
            assert query is not None or url is not None
            session = review_manager.get_cached_session()
            items = []

            if query:
                query = re.sub(r"[\W]+", " ", query.replace(" ", "_"))
                url = cls.api_url + query.replace(" ", "+") + "&format=json"

            headers = {"user-agent": f"{__name__}  (mailto:{review_manager.email})"}
            review_manager.logger.debug(url)
            ret = session.request(
                "GET", url, headers=headers, timeout=timeout  # type: ignore
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
            dblp_dicts = [
                cls.__dblp_json_to_dict(
                    review_manager=review_manager,
                    session=session,
                    item=item,
                    timeout=timeout,
                )
                for item in items
            ]
            retrieved_records = [
                colrev.record.PrepRecord(data=dblp_dict) for dblp_dict in dblp_dicts
            ]
            for retrieved_record in retrieved_records:
                retrieved_record.add_provenance_all(
                    source=retrieved_record.data["dblp_key"]
                )

        except OperationalError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            ) from exc

        return retrieved_records


if __name__ == "__main__":
    pass
