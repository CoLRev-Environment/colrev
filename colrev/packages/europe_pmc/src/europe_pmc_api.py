#! /usr/bin/env python
"""Europe PMC API"""
import typing
from xml.etree.ElementTree import Element  # nosec

import requests
from lxml import etree

import colrev.env.language_service
import colrev.record.record_prep
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class EPMCAPI:
    """Connector for the Europe PMC API"""

    def __init__(self, params: dict, email: str, session: requests.Session) -> None:
        self.params = params

        self.url = (
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query="
            + params["query"]
        )
        self.email = email
        self.session = session
        self.headers = {"user-agent": f"{__name__} (mailto:{email})"}

    def get_records(self) -> typing.Iterator[colrev.record.record_prep.PrepRecord]:
        """Get records from the Europe PMC API"""

        ret = self.session.request("GET", self.url, headers=self.headers, timeout=60)
        ret.raise_for_status()
        if ret.status_code != 200:
            # review_manager.logger.debug(
            #     f"europe_pmc failed with status {ret.status_code}"
            # )
            return

        root = etree.fromstring(str.encode(ret.text))
        result_list = root.findall("resultList")[0]
        for result_item in result_list.findall("result"):
            retrieved_record = self._europe_pmc_xml_to_record(item=result_item)
            yield retrieved_record

        self.url = ""
        next_page_url_node = root.find("nextPageUrl")
        if next_page_url_node is not None:
            if next_page_url_node.text is not None:
                self.url = next_page_url_node.text

    @classmethod
    def _get_string_from_item(cls, *, item, key: str) -> str:  # type: ignore
        return_string = ""
        for selected_node in item.findall(key):
            return_string = selected_node.text
        return return_string

    # pylint: disable=colrev-missed-constant-usage
    @classmethod
    def _europe_pmc_xml_to_record(
        cls, *, item: Element
    ) -> colrev.record.record_prep.PrepRecord:
        retrieved_record_dict: dict = {Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE}
        retrieved_record_dict[Fields.AUTHOR] = cls._get_string_from_item(
            item=item, key="authorString"
        )
        retrieved_record_dict[Fields.JOURNAL] = cls._get_string_from_item(
            item=item, key="journalTitle"
        )
        retrieved_record_dict[Fields.DOI] = cls._get_string_from_item(
            item=item, key="doi"
        )
        retrieved_record_dict[Fields.TITLE] = cls._get_string_from_item(
            item=item, key="title"
        )
        retrieved_record_dict[Fields.YEAR] = cls._get_string_from_item(
            item=item, key="pubYear"
        )
        retrieved_record_dict[Fields.VOLUME] = cls._get_string_from_item(
            item=item, key="journalVolume"
        )
        retrieved_record_dict[Fields.NUMBER] = cls._get_string_from_item(
            item=item, key="issue"
        )
        retrieved_record_dict[Fields.PUBMED_ID] = cls._get_string_from_item(
            item=item, key="pmid"
        )
        retrieved_record_dict[Fields.PMCID] = cls._get_string_from_item(
            item=item, key="pmcid"
        )

        retrieved_record_dict["epmc_source"] = cls._get_string_from_item(
            item=item, key="source"
        )
        retrieved_record_dict["epmc_id"] = cls._get_string_from_item(
            item=item, key="id"
        )
        retrieved_record_dict[Fields.EUROPE_PMC_ID] = (
            retrieved_record_dict.get("epmc_source", "NO_SOURCE")
            + "/"
            + retrieved_record_dict.get("epmc_id", "NO_ID")
        )
        retrieved_record_dict[Fields.ID] = retrieved_record_dict[Fields.EUROPE_PMC_ID]

        retrieved_record_dict = {
            k: v
            for k, v in retrieved_record_dict.items()
            if k not in ["epmc_id", "epmc_source"] and v != ""
        }

        record = colrev.record.record_prep.PrepRecord(retrieved_record_dict)
        return record
