#! /usr/bin/env python
"""SearchSource: AIS electronic Library"""
from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.load_utils_enl
import colrev.ops.search
import colrev.record
from colrev.constants import Fields
from colrev.constants import FieldValues

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class AISeLibrarySearchSource(JsonSchemaMixin):
    """AIS electronic Library (AISeL)"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "url"
    search_types = [
        colrev.settings.SearchType.DB,
        colrev.settings.SearchType.TOC,
        colrev.settings.SearchType.API,
    ]
    endpoint = "colrev.ais_library"

    ci_supported: bool = True
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "AIS eLibrary"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/aisel.md"
    )
    db_url = "https://aisel.aisnet.org/"

    __conference_abbreviations = {
        "ICIS": "International Conference on Information Systems",
        "PACIS": "Pacific-Asia Conference on Information Systems",
        "ECIS": "European Conference on Information Systems",
        "AMCIS": "Americas Conference on Information Systems",
        "HICSS": "Hawaii International Conference on System Sciences",
        "MCIS": "Mediterranean Conference on Information Systems",
        "ACIS": "Australasian Conference on Information Systems",
    }

    __link_confs = {
        "https://aisel.aisnet.org/hicss": "Hawaii International Conference on System Sciences",
        "https://aisel.aisnet.org/amcis": "Americas Conference on Information Systems",
        "https://aisel.aisnet.org/pacis": "Pacific-Asia Conference on Information Systems",
        "https://aisel.aisnet.org/ecis": "European Conference on Information Systems",
        "https://aisel.aisnet.org/icis": "International Conference on Information Systems",
    }

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.review_manager = source_operation.review_manager
        self.quality_model = self.review_manager.get_qm()
        self.operation = source_operation

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for AIS electronic Library (AISeL)"""

        result = {"confidence": 0.0}
        # TBD: aisel does not return bibtex?!
        nr_ais_links = data.count("https://aisel.aisnet.org/")
        nr_items = data.count("\n@")
        if nr_items > 0 and Fields.STATUS not in data:
            result["confidence"] = nr_ais_links / nr_items

        if "%T " in data and Fields.STATUS not in data:
            if data.count("%U https://aisel.aisnet.org") > 0.9 * data.count("%T "):
                result["confidence"] = 1.0

        if "@article" in data or "@inproc" in data and Fields.STATUS not in data:
            if data.count("https://aisel.aisnet.org") > 0.9 * data.count("\n@"):
                result["confidence"] = 1.0

        return result

    @classmethod
    def __parse_query(cls, *, query: str) -> dict:
        peer_reviewed = "peer_reviewed=true" in query
        start_date = ""
        if "start_date=" in query:
            start_date = query[query.find("start_date=") + 11 :]
            start_date = start_date[: start_date.find("&")]
            start_date = start_date.replace("%2F", "/")
        end_date = ""
        if "end_date=" in query:
            end_date = query[query.find("end_date=") + 9 :]
            end_date = end_date[: end_date.find("&")]
            end_date = end_date.replace("%2F", "/")

        query = query[query.find("?q=") + 3 : query.find("&start")]
        query_parts = urllib.parse.unquote(query).split(" ")

        search_terms = []
        query_parts_merged = []
        parenthesis_expression = ""
        for query_part in query_parts:
            if query_part not in ["(", ")"] and "" == parenthesis_expression:
                query_parts_merged.append(query_part)
            elif query_part == "(":
                parenthesis_expression += "("
            elif query_part == ")":
                parenthesis_expression = parenthesis_expression.rstrip().replace(
                    "(", ""
                )
                query_parts_merged.append(parenthesis_expression)
                parenthesis_expression = ""
            else:
                parenthesis_expression = parenthesis_expression + query_part + " "

        term_no = 1
        operator = ""

        for query_part in query_parts_merged:
            if query_part in ["OR", "AND", "NOT"]:
                operator = query_part
                continue

            field = "All fields"
            if "%3A" in query_part:
                field, query_part = query_part.split("%3A")
            search_term = {"operator": operator, "term": query_part, "field": field}

            search_terms.append(search_term)
            term_no += 1

        params = {"query": search_terms, "scope": {"peer_reviewed": peer_reviewed}}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return params

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: dict,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        search_type = operation.select_search_type(
            search_types=cls.search_types, params=params
        )

        if search_type == colrev.settings.SearchType.DB:
            return operation.add_db_source(
                search_source_cls=cls,
                params=params,
            )

        # pylint: disable=colrev-missed-constant-usage
        if search_type == colrev.settings.SearchType.API:
            if "url" not in params:
                # Add API search without params
                add_source = operation.add_api_source(endpoint=cls.endpoint)
                return add_source

            if "url" in params:
                host = urlparse(params["url"]).hostname
                assert host and host.endswith("aisel.aisnet.org")
                q_params = cls.__parse_query(query=params["url"])
                filename = operation.get_unique_filename(file_path_string="ais")
                add_source = colrev.settings.SearchSource(
                    endpoint=cls.endpoint,
                    filename=filename,
                    search_type=colrev.settings.SearchType.API,
                    search_parameters=q_params,
                    comment="",
                )
                return add_source

        # if search_type == colrev.settings.SearchType.TOC:

        raise NotImplementedError

    def __validate_source(self) -> None:
        """Validate the SearchSource (parameters etc.)"""

        source = self.search_source

        self.review_manager.logger.debug(f"Validate SearchSource {source.filename}")

        if source.search_type == colrev.settings.SearchType.API:
            if "query" not in source.search_parameters:
                # if "search_terms" not in source.search_parameters["query"]:
                raise colrev_exceptions.InvalidQueryException("query parameter missing")

        self.review_manager.logger.debug(f"SearchSource {source.filename} validated")

    def __get_ais_query_return(self) -> list:
        def query_from_params(params: dict) -> str:
            final = ""
            for i in params["query"]:
                final = f"{final} {i['operator']} {i['field']}:{i['term']}".strip()
                final = final.replace("All fields:", "")

            if "start_date" in params["query"]:
                final = f"{final}&start_date={params['query']['start_date']}"

            if "end_date" in params["query"]:
                final = f"{final}&end_date={params['query']['end_date']}"

            if "peer_reviewed" in params["query"]:
                final = f"{final}&peer_reviewed=true"

            return urllib.parse.quote(final)

        params = self.search_source.search_parameters
        final_q = query_from_params(params)

        query_string = (
            "https://aisel.aisnet.org/do/search/results/refer?"
            + "start=0&context=509156&sort=score&facet=&dlt=Export122204"
        )
        query_string = f"{query_string}&q={final_q}"

        response = requests.get(query_string, timeout=300)
        response.raise_for_status()

        zotero_translation_service = (
            self.review_manager.get_zotero_translation_service()
        )
        zotero_translation_service.start()

        headers = {"Content-type": "text/plain"}
        ret = requests.post(
            "http://127.0.0.1:1969/import",
            headers=headers,
            data=response.content,
            timeout=30,
        )
        headers = {"Content-type": "application/json"}

        try:
            json_content = json.loads(ret.content)
            export = requests.post(
                "http://127.0.0.1:1969/export?format=bibtex",
                headers=headers,
                json=json_content,
                timeout=30,
            )

        except Exception as exc:
            raise colrev_exceptions.ImportException(
                f"Zotero translators failed ({exc})"
            )

        records = self.review_manager.dataset.load_records_dict(
            load_str=export.content.decode("utf-8")
        )

        return list(records.values())

    def __run_api_search(
        self,
        *,
        ais_feed: colrev.ops.search_feed.GeneralOriginFeed,
        rerun: bool,
    ) -> None:
        # pylint: disable=too-many-branches

        if rerun:
            self.review_manager.logger.info(
                "Performing a search of the full history (may take time)"
            )

        records = self.review_manager.dataset.load_records_dict()

        try:
            for record_dict in self.__get_ais_query_return():
                # Note : discard "empty" records
                if "" == record_dict.get(Fields.AUTHOR, "") and "" == record_dict.get(
                    Fields.TITLE, ""
                ):
                    continue

                try:
                    ais_feed.set_id(record_dict=record_dict)
                except colrev_exceptions.NotFeedIdentifiableException:
                    continue

                # prev_record_dict_version = {}
                # if record_dict[Fields.ID] in ais_feed.feed_records:
                #     prev_record_dict_version = deepcopy(
                #         ais_feed.feed_records[record_dict[Fields.ID]]
                #     )

                prep_record = colrev.record.PrepRecord(data=record_dict)

                if Fields.D_PROV in prep_record.data:
                    del prep_record.data[Fields.D_PROV]

                added = ais_feed.add_record(record=prep_record)

                if added:
                    self.review_manager.logger.info(
                        " retrieve " + prep_record.data[Fields.URL]
                    )
                # else:
                #     search_operation.update_existing_record(
                #         records=records,
                #         record_dict=prep_record.data,
                #         prev_record_dict_version=prev_record_dict_version,
                #         source=self.search_source,
                #         update_time_variant_fields=rerun,
                #     )
        except (
            requests.exceptions.JSONDecodeError,
            requests.exceptions.HTTPError,
        ) as exc:
            # watch github issue:
            # https://github.com/fabiobatalha/crossrefapi/issues/46
            if "504 Gateway Time-out" in str(exc):
                raise colrev_exceptions.ServiceNotAvailableException(
                    "Crossref (check https://status.crossref.org/)"
                )
            raise colrev_exceptions.ServiceNotAvailableException(
                f"Crossref (check https://status.crossref.org/) ({exc})"
            )

        ais_feed.print_post_run_search_infos(records=records)
        ais_feed.save_feed_file()
        self.review_manager.dataset.save_records_dict(records=records)

    def run_search(self, rerun: bool) -> None:
        """Run a search of AISeLibrary"""

        self.__validate_source()

        ais_feed = self.search_source.get_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        if self.search_source.search_type == colrev.settings.SearchType.API:
            self.__run_api_search(
                ais_feed=ais_feed,
                rerun=rerun,
            )
        elif self.search_source.search_type == colrev.settings.SearchType.DB:
            self.operation.run_db_search()  # type: ignore

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.Record:
        """Not implemented"""
        return record

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        # pylint: disable=colrev-missed-constant-usage
        if self.search_source.filename.suffix in [".txt", ".enl"]:
            enl_loader = colrev.ops.load_utils_enl.ENLLoader(
                load_operation=load_operation,
                source=self.search_source,
                unique_id_field="ID",
            )
            entries = enl_loader.load_enl_entries()
            for entry in entries.values():
                entry["ID"] = entry[Fields.URL].replace("https://aisel.aisnet.org/", "")
            records = enl_loader.convert_to_records(entries=entries)
            return records

        # for API-based searches
        if self.search_source.filename.suffix == ".bib":
            records = colrev.ops.load_utils_bib.load_bib_file(
                load_operation=load_operation, source=self.search_source
            )
            return records

        raise NotImplementedError

    def __fix_entrytype(self, *, record: colrev.record.Record) -> None:
        # Note : simple heuristic
        # but at the moment, AISeLibrary only indexes articles and conference papers
        if (
            record.data.get(Fields.VOLUME, FieldValues.UNKNOWN) != FieldValues.UNKNOWN
            or record.data.get(Fields.NUMBER, FieldValues.UNKNOWN)
            != FieldValues.UNKNOWN
        ) and not any(
            x in record.data.get(Fields.JOURNAL, "")
            for x in [
                "HICSS",
                "ICIS",
                "ECIS",
                "AMCIS",
                "Proceedings",
                "All Sprouts Content",
            ]
        ):
            # Journal articles
            if (
                Fields.JOURNAL not in record.data
                and Fields.TITLE in record.data
                and Fields.CHAPTER in record.data
            ):
                record.rename_field(key=Fields.TITLE, new_key=Fields.JOURNAL)
                record.rename_field(key=Fields.CHAPTER, new_key=Fields.TITLE)
                record.remove_field(key=Fields.PUBLISHER)

            record.change_entrytype(new_entrytype="article", qm=self.quality_model)
        else:
            # Inproceedings

            record.remove_field(key=Fields.PUBLISHER)

            if (
                Fields.BOOKTITLE not in record.data
                and Fields.TITLE in record.data
                and Fields.CHAPTER in record.data
            ):
                record.rename_field(key=Fields.TITLE, new_key=Fields.BOOKTITLE)
                record.rename_field(key=Fields.CHAPTER, new_key=Fields.TITLE)

            record.change_entrytype(
                new_entrytype="inproceedings", qm=self.quality_model
            )

            if record.data.get(Fields.BOOKTITLE, "") in [
                "Research-in-Progress Papers",
                "Research Papers",
            ]:
                if "https://aisel.aisnet.org/ecis" in record.data.get(Fields.URL, ""):
                    record.update_field(
                        key=Fields.BOOKTITLE, value="ECIS", source="prep_ais_source"
                    )

    def __unify_container_titles(self, *, record: colrev.record.Record) -> None:
        if "https://aisel.aisnet.org/misq/" in record.data.get(Fields.URL, ""):
            record.update_field(
                key=Fields.JOURNAL, value="MIS Quarterly", source="prep_ais_source"
            )
            record.remove_field(key=Fields.BOOKTITLE)

        if "https://aisel.aisnet.org/misqe/" in record.data.get(Fields.URL, ""):
            record.update_field(
                key=Fields.JOURNAL,
                value="MIS Quarterly Executive",
                source="prep_ais_source",
            )
            record.remove_field(key=Fields.BOOKTITLE)

        if "https://aisel.aisnet.org/bise/" in record.data.get(Fields.URL, ""):
            record.update_field(
                key=Fields.JOURNAL,
                value="Business & Information Systems Engineering",
                source="prep_ais_source",
            )
            record.remove_field(key=Fields.BOOKTITLE)

        if record.data[Fields.ENTRYTYPE] == "inproceedings":
            for conf_abbreviation, conf_name in self.__conference_abbreviations.items():
                if conf_abbreviation in record.data.get(Fields.BOOKTITLE, ""):
                    record.update_field(
                        key=Fields.BOOKTITLE,
                        value=conf_name,
                        source="prep_ais_source",
                    )

        for link_part, conf_name in self.__link_confs.items():
            if link_part in record.data.get(Fields.URL, ""):
                record.update_field(
                    key=Fields.BOOKTITLE,
                    value=conf_name,
                    source="prep_ais_source",
                )

    def __format_fields(self, *, record: colrev.record.Record) -> None:
        if Fields.ABSTRACT in record.data:
            if record.data[Fields.ABSTRACT] == "N/A":
                record.remove_field(key=Fields.ABSTRACT)
        if Fields.AUTHOR in record.data:
            record.update_field(
                key=Fields.AUTHOR,
                value=record.data[Fields.AUTHOR].replace("\n", " "),
                source="prep_ais_source",
                keep_source_if_equal=True,
            )

    def __exclude_complementary_material(self, *, record: colrev.record.Record) -> None:
        if re.match(
            r"MISQ Volume \d{1,2}, Issue \d Table of Contents",
            record.data.get(Fields.TITLE, ""),
        ):
            record.prescreen_exclude(reason="complementary material")

    def prepare(
        self, record: colrev.record.PrepRecord, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for the AIS electronic Library (AISeL)"""

        self.__fix_entrytype(record=record)
        self.__unify_container_titles(record=record)
        self.__format_fields(record=record)
        self.__exclude_complementary_material(record=record)

        return record
