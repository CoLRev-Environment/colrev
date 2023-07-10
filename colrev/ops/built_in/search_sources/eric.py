#! /usr/bin/env python
"""SearchSource: ERIC"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path
import urllib.parse
import requests
from typing import Optional
import colrev.exceptions as colrev_exceptions

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class ERICSearchSource(JsonSchemaMixin):
    """SearchSource for the ERIC API"""
    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "ID"
    search_type = colrev.settings.SearchType.DB
    api_search_supported = True
    ci_supported: bool = True
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.oni
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/eric.md"
    )
    short_name = "ERIC"

    def __init__(
        self,
        *,
        source_operation: colrev.operation.Operation,
        settings: Optional[dict] = None,
    ) -> None:
        if settings:
            # ERIC as a search_source
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )
        else:
            self.search_source = colrev.settings.SearchSource(
                    endpoint="colrev.eric",
                    filename=Path("data/search/eric.bib"),
                    search_type=colrev.settings.SearchType.OTHER,
                    search_parameters={},
                    load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
                    comment="",
                )

        

    
    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
        )

        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )
    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for ERIC"""

        result = {"confidence": 0.1}

        # Note : no features in bib file for identification

        return result
    

    def __search_split(search) -> str:
        if ' AND ' in search:
            search_parts = search.split(' AND ')
            field_values = []
            for part in search_parts:
                field, value = part.split(':')
                field = field.strip()
                value = value.strip().strip("'")
                field_value = f'{field}%3A%22{urllib.parse.quote(value)}%22'
                field_values.append(field_value)
            return ' AND '.join(field_values)
        else:
            field, value = search.split(':')
            field = field.strip()
            value = value.strip().strip("'")
            field_value = f'{field}%3A%22{urllib.parse.quote(value)}%22'
            return field_value
    

    
    @classmethod
    def add_endpoint(
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> typing.Optional[colrev.settings.SearchSource]:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a)"""

        if "https://api.ies.ed.gov/eric/?" in query:
            url_parsed = urllib.parse.urlparse(query)
            query = urllib.parse.parse_qs(url_parsed.query)
            search = query.get('search', [''])[0]
            start = query.get('start', ['0'])[0]
            rows = query.get('rows', ['2000'])[0]
            if ':' in search:
                search = ERICSearchSource.search_split(search)
            filename = search_operation.get_unique_filename(
                file_path_string=f"eric_{search}"
            )
            add_source = colrev.settings.SearchSource(
                endpoint="colrev.eric",
                filename=filename,
                search_type=colrev.settings.SearchType.DB,
                search_parameters={"query": search, 'start': start, 'rows': rows},
                load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
                comment="",
            )
            return add_source

        return None

    


    def run_search(self, search_operation, rerun):
        eric_feed = self.search_source.get_feed(
            review_manager=search_operation.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )
        prev_record_dict_version = {}
        full_url = self.build_search_url()
    
        response = requests.get(full_url)
        if response.status_code == 200:
            data = response.json()
            records = search_operation.review_manager.dataset.load_records_dict()
            
            for doc in data['response']['docs']:
                record_id = doc['id']
                if record_id not in records:
                    record_dict = self.create_record_dict(doc)
                    updated_record_dict = self.update_record_fields(record_dict)
                    record = colrev.record.Record(data=updated_record_dict)
                    added = eric_feed.add_record(record=record)

                    if added:
                        search_operation.review_manager.logger.info(
                            " retrieve " + record.data["ID"]
                        )
                        eric_feed.nr_added += 1
                    else:
                        changed = self.update_existing_record(
                        search_operation, records, record.data, prev_record_dict_version, rerun
                    )
                        if changed:
                            search_operation.review_manager.logger.info(
                                " update " + record.data["ID"]
                            )
                            eric_feed.nr_changed += 1
                            
            eric_feed.save_feed_file()
            search_operation.review_manager.dataset.save_records_dict(records=records)
            search_operation.review_manager.dataset.add_record_changes()
        else:
            raise colrev_exceptions.ServiceNotAvailableException(
                    "Could not reach API. Status Code: " + response.status_code
                ) 
        
        
    def build_search_url(self):
        url = 'https://api.ies.ed.gov/eric/'
        params = self.search_source.search_parameters
        query = params['query']
        format_param = 'json'
        start_param = params.get('start', '0')
        rows_param = params.get('rows', '2000')
        return f"{url}?search={query}&format={format_param}&start={start_param}&rows={rows_param}"
            

    def create_record_dict(self, doc):
        record_dict = {'ID': doc['id']}

        api_fields = ['id', 'title', 'author', 'source', 'publicationdateyear', 'description',
                    'subject', 'peerreviewed', 'abstractor', 'audience', 'authorxlink',
                    'e_datemodified', 'e_fulltextauth', 'e yearadded', 'educationlevel',
                    'identifiersgeo', 'identifierslaw', 'identifierstest', 'iescited',
                    'iesfunded', 'iesgrantcontractnum', 'iesgrantcontractnumxlink',
                    'ieslinkpublication', 'ieslinkwwcreviewguide', 'ieswwcreviewed',
                    'institution', 'isbn', 'issn', 'language', 'publicationtype',
                    'publisher', 'sourceid', 'sponsor', 'url']

        for field in api_fields:
            field_value = doc.get(field)
            record_dict['ENTRYTYPE'] = 'article'
            if field_value is not None:
                if field == 'publicationtype':
                    record_dict['ENTRYTYPE'] = field_value
                else:
                    record_dict[field] = str(field_value)

        return record_dict 
         
    def update_record_fields(self,
        record_dict: dict, 
    ) -> dict:
        if "publicationdateyear" in record_dict:
            record_dict["year"] = record_dict.pop("publicationdateyear")
        if "publicationtype" in record_dict:
            record_dict["howpublished"] = record_dict.pop("publicationtype")
        if "source" in record_dict:
            record_dict["journal"] = record_dict.pop("source")
        if "sourceid" in record_dict:
            record_dict["volume"] = record_dict.pop("sourceid")
        if "authorxlink" in record_dict:
            record_dict["address"] = record_dict.pop("authorxlink")
        if "description" in record_dict:
            record_dict["abstract"] = record_dict.pop("description")
        if "sponsor" in record_dict:
            record_dict["organization"] = record_dict.pop("sponsor")
        if "id" in record_dict:
            record_dict["doi"] = record_dict.pop("id")
        return record_dict
    
    def update_existing_record(
        self, search_operation, records, record_dict, prev_record_dict_version, rerun
    ):
        changed = search_operation.update_existing_record(
            records=records,
            record_dict=record_dict,
            prev_record_dict_version=prev_record_dict_version,
            source=self.search_source,
            update_time_variant_fields=rerun,
        )
        return changed

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.Record:
        """Not implemented"""
        return record

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for ERIC"""

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for ERIC"""

        return record

