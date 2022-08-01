#! /usr/bin/env python
import html
import json
import re
import sys
import urllib
from datetime import timedelta
from pathlib import Path
from sqlite3 import OperationalError
from urllib.parse import unquote

import requests
import requests_cache
from bs4 import BeautifulSoup
from thefuzz import fuzz

import colrev_core.exceptions as colrev_exceptions
from colrev_core.environment import EnvironmentManager
from colrev_core.record import PrepRecord
from colrev_core.record import RecordState


class OpenLibraryConnector:
    @classmethod
    def check_status(cls, *, PREPARATION) -> None:

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
                url, headers=PREPARATION.requests_headers, timeout=PREPARATION.TIMEOUT
            )
            if ret.status_code != 200:
                if not PREPARATION.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException("OPENLIBRARY")
        except requests.exceptions.RequestException:
            pass
            if not PREPARATION.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException("OPENLIBRARY")

        return


class URLConnector:
    @classmethod
    def retrieve_md_from_url(cls, *, RECORD, PREPARATION) -> None:
        from colrev_core.environment import ZoteroTranslationService
        from colrev_core.record import PrepRecord

        """Note: retrieve_md_from_url replaces prior data in RECORD
        (RECORD.copy() - deepcopy() before if necessary)"""

        ZOTERO_TRANSLATION_SERVICE = ZoteroTranslationService()
        ZOTERO_TRANSLATION_SERVICE.start_zotero_translators()

        # TODO : change to the similar merge()/fuse_best_field structure?

        try:
            content_type_header = {"Content-type": "text/plain"}
            headers = {**PREPARATION.requests_headers, **content_type_header}
            et = requests.post(
                "http://127.0.0.1:1969/web",
                headers=headers,
                data=RECORD.data["url"],
                timeout=PREPARATION.TIMEOUT,
            )

            if et.status_code != 200:
                return

            items = json.loads(et.content.decode())
            if len(items) == 0:
                return
            item = items[0]
            if "Shibboleth Authentication Request" == item["title"]:
                return

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
                    DOIConnector.get_link_from_doi(RECORD=DUMMY_R)
                    if "https://doi.org/" not in DUMMY_R.data["url"]:
                        RECORD.data["url"] = DUMMY_R.data["url"]
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
        return


class DOIConnector:
    @classmethod
    def retrieve_doi_metadata(
        cls,
        *,
        REVIEW_MANAGER,
        RECORD,
        session=None,
        TIMEOUT: int = 10,
    ):
        if "doi" not in RECORD.data:
            return RECORD

        try:
            if session is None:
                cache_path = EnvironmentManager.colrev_path / Path(
                    "prep_requests_cache"
                )
                session = requests_cache.CachedSession(
                    str(cache_path), backend="sqlite", expire_after=timedelta(days=30)
                )

            # for testing:
            # curl -iL -H "accept: application/vnd.citationstyles.csl+json"
            # -H "Content-Type: application/json" http://dx.doi.org/10.1111/joop.12368

            try:
                url = "http://dx.doi.org/" + RECORD.data["doi"]
                REVIEW_MANAGER.logger.debug(url)
                headers = {"accept": "application/vnd.citationstyles.csl+json"}
                ret = session.request("GET", url, headers=headers, timeout=TIMEOUT)
                ret.raise_for_status()
                if ret.status_code != 200:
                    REVIEW_MANAGER.report_logger.info(
                        f' {RECORD.data["ID"]}'
                        + "metadata for "
                        + f'doi  {RECORD.data["doi"]} not (yet) available'
                    )
                    return RECORD

                retrieved_json = json.loads(ret.text)
                retrieved_record = CrossrefConnector.crossref_json_to_record(
                    item=retrieved_json
                )
                RETRIEVED_RECORD = PrepRecord(data=retrieved_record)
                RETRIEVED_RECORD.add_provenance_all(source=url)
                RECORD.merge(MERGING_RECORD=RETRIEVED_RECORD, default_source=url)
                RECORD.set_masterdata_complete()
                if "colrev_status" in RECORD.data:
                    RECORD.set_status(target_state=RecordState.md_prepared)
                if "retracted" in RECORD.data.get("warning", ""):
                    RECORD.prescreen_exclude(reason="retracted")
                    RECORD.remove_field(key="warning")

            except json.decoder.JSONDecodeError:
                pass
            except requests.exceptions.RequestException:
                pass
                return RECORD
            except OperationalError:
                pass
                raise colrev_exceptions.ServiceNotAvailableException(
                    "sqlite, required for requests CachedSession "
                    "(possibly caused by concurrent operations)"
                )

            if "title" in RECORD.data:
                RECORD.format_if_mostly_upper(key="title")

        except OperationalError:
            pass
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            )

        return RECORD

    @classmethod
    def get_link_from_doi(
        cls,
        *,
        RECORD,
        session=None,
        TIMEOUT: int = 10,
    ) -> None:

        doi_url = f"https://www.doi.org/{RECORD.data['doi']}"

        # TODO : retry for 50X
        # from requests.adapters import HTTPAdapter
        # from requests.adapters import Retry
        # example for testing: ({'doi':'10.1177/02683962221086300'})
        # s = requests.Session()
        # headers = {"user-agent": f"{__name__} (mailto:{REVIEW_MANAGER.EMAIL})"}
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

        try:
            url = doi_url
            if session is None:
                cache_path = EnvironmentManager.colrev_path / Path(
                    "prep_requests_cache"
                )
                session = requests_cache.CachedSession(
                    str(cache_path), backend="sqlite", expire_after=timedelta(days=30)
                )

            requests_headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/39.0.2171.95 Safari/537.36"
            }
            ret = session.request(
                "GET",
                doi_url,
                headers=requests_headers,
                timeout=TIMEOUT,
            )
            if 503 == ret.status_code:
                return
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
                    ret = session.request(
                        "GET",
                        url,
                        headers=requests_headers,
                        timeout=TIMEOUT,
                    )
            RECORD.update_field(key="url", value=str(url), source=doi_url)
        except requests.exceptions.RequestException:
            pass
        except OperationalError:
            pass
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            )

        return


class CrossrefConnector:

    issn_regex = r"^\d{4}-?\d{3}[\dxX]$"

    def __init__(self, *, REVIEW_MANAGER):

        from crossref.restful import Etiquette
        from importlib.metadata import version

        self.etiquette = Etiquette(
            "CoLRev",
            version("colrev_core"),
            "https://github.com/geritwagner/colrev_core",
            REVIEW_MANAGER.EMAIL,
        )

    @classmethod
    def check_status(cls, *, PREPARATION) -> None:

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
            RETURNED_REC = cls.crossref_query(
                REVIEW_MANAGER=PREPARATION.REVIEW_MANAGER,
                RECORD_INPUT=PrepRecord(data=test_rec),
                jour_vol_iss_list=False,
                session=PREPARATION.session,
                TIMEOUT=PREPARATION.TIMEOUT,
            )[0]

            if 0 != len(RETURNED_REC.data):
                assert RETURNED_REC.data["title"] == test_rec["title"]
                assert RETURNED_REC.data["author"] == test_rec["author"]
            else:
                if not PREPARATION.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException("CROSSREF")
        except (requests.exceptions.RequestException, IndexError) as e:
            print(e)
            pass
            if not PREPARATION.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException("CROSSREF")
        return

    def get_bibliographic_query_return(self, **kwargs):
        from crossref.restful import Works

        assert all(k in ["bibliographic"] for k in kwargs.keys())

        works = Works(etiquette=self.etiquette)
        # use facets:
        # https://api.crossref.org/swagger-ui/index.html#/Works/get_works

        crossref_query_return = works.query(**kwargs)
        for item in crossref_query_return:
            yield self.crossref_json_to_record(item=item)

    def get_journal_query_return(self, *, journal_issn):
        from crossref.restful import Journals

        assert re.match(self.issn_regex, journal_issn)

        journals = Journals(etiquette=self.etiquette)
        crossref_query_return = journals.works(journal_issn).query()
        for item in crossref_query_return:
            yield self.crossref_json_to_record(item=item)

    @classmethod
    def crossref_json_to_record(cls, *, item: dict) -> dict:
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
        # authors_string = PrepRecord.format_author_field(authors_string)
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
                RECORD = PrepRecord(data=record)
                RECORD.unify_pages_field()
                record = RECORD.get_data()

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

        if (
            "published-print" not in item
            and "volume" not in record
            and "number" not in record
            and "year" in record
        ):
            record.update(published_online=record["year"])
            record.update(year="forthcoming")

        if "is-referenced-by-count" in item:
            record["cited_by"] = item["is-referenced-by-count"]

        if "update-to" in item:
            for update_item in item["update-to"]:
                if update_item["type"] == "retraction":
                    record["warning"] = "retracted"

        for k, v in record.items():
            record[k] = str(v).replace("{", "").replace("}", "")
            if k in ["colrev_masterdata_provenance", "colrev_data_provenance", "doi"]:
                continue
            # Note : some dois (and their provenance) contain html entities
            record[k] = html.unescape(str(v))

        if "ENTRYTYPE" not in record:
            record["ENTRYTYPE"] = "misc"

        return record

    @classmethod
    def crossref_query(
        cls,
        *,
        REVIEW_MANAGER,
        RECORD_INPUT,
        jour_vol_iss_list: bool = False,
        session=None,
        TIMEOUT: int = 10,
    ) -> list:
        # https://github.com/CrossRef/rest-api-doc
        api_url = "https://api.crossref.org/works?"

        # Note : only returning a multiple-item list for jour_vol_iss_list

        RECORD = RECORD_INPUT.copy_prep_rec()

        if jour_vol_iss_list:
            params = {"rows": "50"}
            container_title = re.sub(r"[\W]+", " ", RECORD.data["journal"])
            params["query.container-title"] = container_title.replace("_", " ")

            query_field = ""
            if "volume" in RECORD.data:
                query_field = RECORD.data["volume"]
            if "number" in RECORD.data:
                query_field = query_field + "+" + RECORD.data["number"]
            params["query"] = query_field

        else:
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

        url = api_url + urllib.parse.urlencode(params)
        headers = {"user-agent": f"{__name__} (mailto:{REVIEW_MANAGER.EMAIL})"}
        record_list = []
        try:
            if session is None:
                cache_path = EnvironmentManager.colrev_path / Path(
                    "prep_requests_cache"
                )
                session = requests_cache.CachedSession(
                    str(cache_path), backend="sqlite", expire_after=timedelta(days=30)
                )

            REVIEW_MANAGER.logger.debug(url)
            ret = session.request("GET", url, headers=headers, timeout=TIMEOUT)
            ret.raise_for_status()
            if ret.status_code != 200:
                REVIEW_MANAGER.logger.debug(
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

                retrieved_record = cls.crossref_json_to_record(item=item)

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
                if "retracted" in RETRIEVED_RECORD.data.get("warning", ""):
                    RETRIEVED_RECORD.prescreen_exclude(reason="retracted")
                    RETRIEVED_RECORD.remove_field(key="warning")

                RETRIEVED_RECORD.add_provenance_all(
                    source=f'https://api.crossref.org/works/{retrieved_record["doi"]}'
                )

                RECORD.set_masterdata_complete()

                if jour_vol_iss_list:
                    record_list.append(RETRIEVED_RECORD)
                if most_similar < similarity:
                    most_similar = similarity
                    most_similar_record = RETRIEVED_RECORD.get_data()
        except json.decoder.JSONDecodeError:
            pass
        except requests.exceptions.RequestException:
            return []
        except OperationalError:
            pass
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            )

        if not jour_vol_iss_list:
            record_list = [PrepRecord(data=most_similar_record)]

        return record_list

    @classmethod
    def get_masterdata_from_crossref(
        cls, *, PREPARATION, RECORD, session=None, TIMEOUT: int = 10
    ):
        # To test the metadata provided for a particular DOI use:
        # https://api.crossref.org/works/DOI

        if session is None:
            cache_path = EnvironmentManager.colrev_path / Path("prep_requests_cache")
            session = requests_cache.CachedSession(
                str(cache_path), backend="sqlite", expire_after=timedelta(days=30)
            )

        # https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
        if len(RECORD.data.get("title", "")) > 35:
            try:

                RETRIEVED_REC_L = CrossrefConnector.crossref_query(
                    REVIEW_MANAGER=PREPARATION.REVIEW_MANAGER,
                    RECORD_INPUT=RECORD,
                    jour_vol_iss_list=False,
                    session=session,
                    TIMEOUT=TIMEOUT,
                )
                RETRIEVED_RECORD = RETRIEVED_REC_L.pop()

                retries = 0
                while (
                    not RETRIEVED_RECORD and retries < PREPARATION.MAX_RETRIES_ON_ERROR
                ):
                    retries += 1

                    RETRIEVED_REC_L = CrossrefConnector.crossref_query(
                        REVIEW_MANAGER=PREPARATION.REVIEW_MANAGER,
                        RECORD_INPUT=RECORD,
                        jour_vol_iss_list=False,
                        session=session,
                        TIMEOUT=TIMEOUT,
                    )
                    RETRIEVED_RECORD = RETRIEVED_REC_L.pop()

                if 0 == len(RETRIEVED_RECORD.data):
                    return RECORD

                similarity = PrepRecord.get_retrieval_similarity(
                    RECORD_ORIGINAL=RECORD, RETRIEVED_RECORD_ORIGINAL=RETRIEVED_RECORD
                )
                if similarity > PREPARATION.RETRIEVAL_SIMILARITY:
                    PREPARATION.REVIEW_MANAGER.logger.debug("Found matching record")
                    PREPARATION.REVIEW_MANAGER.logger.debug(
                        f"crossref similarity: {similarity} "
                        f"(>{PREPARATION.RETRIEVAL_SIMILARITY})"
                    )
                    source = (
                        f"https://api.crossref.org/works/{RETRIEVED_RECORD.data['doi']}"
                    )
                    RETRIEVED_RECORD.add_provenance_all(source=source)
                    RECORD.merge(MERGING_RECORD=RETRIEVED_RECORD, default_source=source)

                    if "retracted" in RECORD.data.get("warning", ""):
                        RECORD.prescreen_exclude(reason="retracted")
                        RECORD.remove_field(key="warning")
                    else:
                        DOIConnector.get_link_from_doi(RECORD=RECORD)
                        RECORD.set_masterdata_complete()
                        RECORD.set_status(target_state=RecordState.md_prepared)

                else:
                    PREPARATION.REVIEW_MANAGER.logger.debug(
                        f"crossref similarity: {similarity} "
                        f"(<{PREPARATION.RETRIEVAL_SIMILARITY})"
                    )

            except requests.exceptions.RequestException:
                pass
            except IndexError:
                pass
            except KeyboardInterrupt:
                sys.exit()
        return RECORD


class DBLPConnector:
    @classmethod
    def check_status(cls, *, PREPARATION) -> None:

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
                "colrev_status": RecordState.md_prepared,  # type: ignore
            }

            query = "" + str(test_rec.get("title", "")).replace("-", "_")

            DBLP_REC = DBLPConnector.retrieve_dblp_records(
                REVIEW_MANAGER=PREPARATION.REVIEW_MANAGER,
                query=query,
                session=PREPARATION.session,
            )[0]

            if 0 != len(DBLP_REC.data):
                assert DBLP_REC.data["title"] == test_rec["title"]
                assert DBLP_REC.data["author"] == test_rec["author"]
            else:
                if not PREPARATION.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException("DBLP")
        except requests.exceptions.RequestException:
            pass
            if not PREPARATION.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException("DBLP")

        return

    @classmethod
    def retrieve_dblp_records(
        cls,
        *,
        REVIEW_MANAGER,
        query: str = None,
        url: str = None,
        session=None,
        TIMEOUT: int = 10,
    ) -> list:
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
                headers = {"user-agent": f"{__name__} (mailto:{REVIEW_MANAGER.EMAIL})"}
                try:
                    ret = session.request("GET", url, headers=headers, timeout=TIMEOUT)
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
                    author_string = PrepRecord.format_author_field(
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

            for k, v in retrieved_record.items():
                retrieved_record[k] = html.unescape(v).replace("{", "").replace("}", "")

            return retrieved_record

        try:

            assert query is not None or url is not None

            if session is None:
                cache_path = EnvironmentManager.colrev_path / Path(
                    "prep_requests_cache"
                )
                session = requests_cache.CachedSession(
                    str(cache_path), backend="sqlite", expire_after=timedelta(days=30)
                )

            api_url = "https://dblp.org/search/publ/api?q="
            items = []

            if query:
                query = re.sub(r"[\W]+", " ", query.replace(" ", "_"))
                url = api_url + query.replace(" ", "+") + "&format=json"

            headers = {"user-agent": f"{__name__}  (mailto:{REVIEW_MANAGER.EMAIL})"}
            REVIEW_MANAGER.logger.debug(url)
            ret = session.request(
                "GET", url, headers=headers, timeout=TIMEOUT  # type: ignore
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

        except OperationalError:
            pass
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            )

        return RETRIEVED_RECORDS
