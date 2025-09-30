#! /usr/bin/env python
"""SearchSource: AIS electronic Library"""
from __future__ import annotations

import logging
import re
import typing
import urllib.parse
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field

import colrev.exceptions as colrev_exceptions
import colrev.loader.load_utils
import colrev.ops.search_api_feed
import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
import colrev.record.record_prep
import colrev.search_file
import colrev.utils
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search_api_feed import create_api_source
from colrev.ops.search_db import create_db_source
from colrev.ops.search_db import run_db_search
from colrev.packages.ais_library.src import ais_load_utils
from colrev.packages.ais_library.src import aisel_api

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class AISeLibrarySearchSource(base_classes.SearchSourcePackageBaseClass):
    """AIS electronic Library (AISeL)"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "url"
    search_types = [
        SearchType.DB,
        SearchType.TOC,
        SearchType.API,
    ]
    endpoint = "colrev.ais_library"

    ci_supported: bool = Field(default=True)
    heuristic_status = SearchSourceHeuristicStatus.supported

    db_url = "https://aisel.aisnet.org/"

    _conference_abbreviations = {
        "ICIS": "International Conference on Information Systems",
        "PACIS": "Pacific-Asia Conference on Information Systems",
        "ECIS": "European Conference on Information Systems",
        "AMCIS": "Americas Conference on Information Systems",
        "HICSS": "Hawaii International Conference on System Sciences",
        "MCIS": "Mediterranean Conference on Information Systems",
        "ACIS": "Australasian Conference on Information Systems",
        "WHICEB": "Wuhan International Conference on e-Business",
        "CONF-IRM": "International Conference on Information Resources Management",
    }

    _link_confs = {
        "https://aisel.aisnet.org/hicss": "Hawaii International Conference on System Sciences",
        "https://aisel.aisnet.org/amcis": "Americas Conference on Information Systems",
        "https://aisel.aisnet.org/pacis": "Pacific-Asia Conference on Information Systems",
        "https://aisel.aisnet.org/ecis": "European Conference on Information Systems",
        "https://aisel.aisnet.org/icis": "International Conference on Information Systems",
    }

    def __init__(
        self,
        *,
        search_file: colrev.search_file.ExtendedSearchFile,
        logger: typing.Optional[logging.Logger] = None,
        verbose_mode: bool = False,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.verbose_mode = verbose_mode
        self.search_source = search_file
        self.api = aisel_api.AISeLAPI(search_file=search_file)

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
    def _parse_query(cls, *, query: str) -> dict:
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
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""
        params_dict = {}
        if params:
            if params.startswith("http"):
                params_dict = {Fields.URL: params}
            else:
                for item in params.split(";"):
                    key, value = item.split("=")
                    params_dict[key] = value

        search_type = colrev.utils.select_search_type(
            search_types=cls.search_types, params=params_dict
        )

        if search_type == SearchType.DB:
            search_source = create_db_source(
                path=path,
                platform=cls.endpoint,
                params=params_dict,
                add_to_git=True,
                logger=logger,
            )

        # pylint: disable=colrev-missed-constant-usage
        elif search_type == SearchType.API:
            if "url" in params_dict:
                host = urlparse(params_dict["url"]).hostname
                assert host and host.endswith("aisel.aisnet.org")
                q_params = cls._parse_query(query=params_dict["url"])
                filename = colrev.utils.get_unique_filename(
                    base_path=path,
                    file_path_string="ais",
                )
                search_source = colrev.search_file.ExtendedSearchFile(
                    version=cls.CURRENT_SYNTAX_VERSION,
                    platform=cls.endpoint,
                    search_results_path=filename,
                    search_type=SearchType.API,
                    search_string="",
                    search_parameters=q_params,
                    comment="",
                )
            else:
                # Add API search without params
                search_source = create_api_source(platform=cls.endpoint, path=path)

            search_source.search_parameters = {"query": search_source.search_string}
            search_source.search_string = ""

        # elif search_type == SearchType.TOC:
        else:
            raise NotImplementedError
        return search_source

    def _validate_source(self) -> None:
        """Validate the SearchSource (parameters etc.)"""

        source = self.search_source

        self.logger.debug(f"Validate SearchSource {source.search_results_path}")

        if source.search_type == SearchType.API:
            if "query" not in source.search_parameters:
                # if "search_terms" not in source.search_string["query"]:
                raise colrev_exceptions.InvalidQueryException("query parameter missing")

        self.logger.debug("SearchSource %s validated", source.search_results_path)

    def _run_api_search(
        self,
        *,
        ais_feed: colrev.ops.search_api_feed.SearchAPIFeed,
        rerun: bool,
    ) -> None:
        # pylint: disable=too-many-branches

        if rerun:
            self.logger.info("Performing a search of the full history (may take time)")

        try:
            for record_dict in self.api.get_ais_query_return():
                try:
                    # Note : discard "empty" records
                    if "" == record_dict.get(
                        Fields.AUTHOR, ""
                    ) and "" == record_dict.get(Fields.TITLE, ""):
                        continue

                    prep_record = colrev.record.record_prep.PrepRecord(record_dict)
                    ais_feed.add_update_record(prep_record)

                except colrev_exceptions.NotFeedIdentifiableException:
                    continue
        except aisel_api.AISeLAPIError as exc:
            # watch github issue:
            # https://github.com/fabiobatalha/crossrefapi/issues/46
            if "504 Gateway Time-out" in str(exc):
                raise colrev_exceptions.ServiceNotAvailableException(
                    "Crossref (check https://status.crossref.org/)"
                )
            raise colrev_exceptions.ServiceNotAvailableException(
                f"Crossref (check https://status.crossref.org/) ({exc})"
            )

        ais_feed.save()

    def search(self, rerun: bool) -> None:
        """Run a search of AISeLibrary"""

        self._validate_source()

        if self.search_source.search_type == SearchType.API:
            ais_feed = colrev.ops.search_api_feed.SearchAPIFeed(
                source_identifier=self.source_identifier,
                search_source=self.search_source,
                update_only=(not rerun),
                logger=self.logger,
                verbose_mode=self.verbose_mode,
            )
            self._run_api_search(
                ais_feed=ais_feed,
                rerun=rerun,
            )
        elif self.search_source.search_type == SearchType.DB:
            run_db_search(
                db_url=self.db_url,
                source=self.search_source,
                add_to_git=True,
            )

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        """Not implemented"""
        return record

    @classmethod
    def _load_enl(cls, *, filename: Path, logger: logging.Logger) -> dict:

        return colrev.loader.load_utils.load(
            filename=filename,
            id_labeler=ais_load_utils.enl_id_labeler,
            entrytype_setter=ais_load_utils.enl_entrytype_setter,
            field_mapper=ais_load_utils.enl_field_mapper,
            logger=logger,
        )

    @classmethod
    def _load_bib(cls, *, filename: Path, logger: logging.Logger) -> dict:

        records = colrev.loader.load_utils.load(
            filename=filename,
            logger=logger,
            field_mapper=ais_load_utils.bib_field_mapper,
            unique_id_field="ID",
        )

        return records

    def load(self) -> dict:
        """Load the records from the SearchSource file"""

        # pylint: disable=colrev-missed-constant-usage
        if self.search_source.search_results_path.suffix in [".txt", ".enl"]:
            return self._load_enl(
                filename=self.search_source.search_results_path, logger=self.logger
            )

        # for API-based searches
        if self.search_source.search_results_path.suffix == ".bib":
            return self._load_bib(
                filename=self.search_source.search_results_path, logger=self.logger
            )

        raise NotImplementedError

    def _fix_entrytype(
        self,
        *,
        record: colrev.record.record.Record,
    ) -> None:
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

            record.change_entrytype("article")
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

            record.change_entrytype(new_entrytype="inproceedings")

            if record.data.get(Fields.BOOKTITLE, "") in [
                "Research-in-Progress Papers",
                "Research Papers",
            ]:
                if "https://aisel.aisnet.org/ecis" in record.data.get(Fields.URL, ""):
                    record.update_field(
                        key=Fields.BOOKTITLE, value="ECIS", source="prep_ais_source"
                    )

    def _unify_container_titles(self, *, record: colrev.record.record.Record) -> None:
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
            for conf_abbreviation, conf_name in self._conference_abbreviations.items():
                if conf_abbreviation in record.data.get(Fields.BOOKTITLE, ""):
                    record.update_field(
                        key=Fields.BOOKTITLE,
                        value=conf_name,
                        source="prep_ais_source",
                    )

        for link_part, conf_name in self._link_confs.items():
            if link_part in record.data.get(Fields.URL, ""):
                record.update_field(
                    key=Fields.BOOKTITLE,
                    value=conf_name,
                    source="prep_ais_source",
                )

    def _format_fields(self, *, record: colrev.record.record_prep.PrepRecord) -> None:
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
        record.format_if_mostly_upper(Fields.TITLE, case="sentence")
        record.format_if_mostly_upper(Fields.JOURNAL, case=Fields.TITLE)
        record.format_if_mostly_upper(Fields.BOOKTITLE, case=Fields.TITLE)
        record.format_if_mostly_upper(Fields.AUTHOR, case=Fields.TITLE)

    def _exclude_complementary_material(
        self, *, record: colrev.record.record.Record
    ) -> None:
        if re.match(
            r"MISQ Volume \d{1,2}, Issue \d Table of Contents",
            record.data.get(Fields.TITLE, ""),
        ):
            record.prescreen_exclude(reason="complementary material")

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for the AIS electronic Library (AISeL)"""

        self._fix_entrytype(record=record)
        self._unify_container_titles(record=record)
        self._format_fields(record=record)
        self._exclude_complementary_material(record=record)
        return record
