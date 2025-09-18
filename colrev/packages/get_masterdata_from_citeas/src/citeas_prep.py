#! /usr/bin/env python
"""Consolidation of metadata based on CiteAs API as a prep operation"""
from __future__ import annotations

import json
import logging
import typing

import requests
from pydantic import Field

import colrev.env.environment_manager
import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.record.record
import colrev.record.record_prep
import colrev.record.record_similarity
import colrev.utils
from colrev.constants import Fields

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


class CiteAsPrep(base_classes.PrepPackageBaseClass):
    """Prepares records based on citeas.org metadata"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings

    source_correction_hint = "Search on https://citeas.org/ and click 'modify'"
    always_apply_changes = False
    ci_supported: bool = Field(default=True)

    requests_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"
    }

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,
        settings: dict,
        logger: typing.Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.settings = self.settings_class(**settings)
        self.prep_operation = prep_operation
        self.review_manager = prep_operation.review_manager
        self.same_record_type_required = (
            prep_operation.review_manager.settings.is_curated_masterdata_repo()
        )
        self.session = colrev.utils.get_cached_session()
        _, self.email = (
            colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git()
        )

    def _cite_as_json_to_record(
        self, *, json_str: str, url: str
    ) -> colrev.record.record_prep.PrepRecord:
        retrieved_record: dict = {}
        data = json.loads(json_str)

        if Fields.AUTHOR in data["metadata"]:
            authors = data["metadata"][Fields.AUTHOR]
            authors_string = ""
            for author in authors:
                authors_string += author.get("family", "") + ", "
                authors_string += author.get("given", "") + " "
            authors_string = authors_string.lstrip().rstrip().replace("  ", " ")
            retrieved_record.update(author=authors_string)
        if "container-title" in data["metadata"]:
            container_title = data["metadata"]["container-title"]
            if isinstance(data["metadata"]["container-title"], list):
                container_title = "".join(data["metadata"]["container-title"])
            retrieved_record.update(title=container_title)
        if "URL" in data["metadata"]:
            retrieved_record.update(url=data["metadata"]["URL"])
        if "note" in data["metadata"]:
            retrieved_record.update(note=data["metadata"]["note"])
        if "type" in data["metadata"]:
            retrieved_record.update(ENTRYTYPE=data["metadata"]["type"])
        if Fields.YEAR in data["metadata"]:
            retrieved_record.update(year=data["metadata"][Fields.YEAR])
        if "DOI" in data["metadata"]:
            retrieved_record.update(doi=data["metadata"]["DOI"])

        record = colrev.record.record_prep.PrepRecord(retrieved_record)
        record.add_provenance_all(source=url)
        return record

    # pylint: disable=unused-argument
    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Prepare the record based on citeas"""

        if record.data.get(Fields.ENTRYTYPE, "NA") not in ["misc", "software"]:
            return record
        if Fields.TITLE not in record.data:
            return record

        try:
            url = (
                f"https://api.citeas.org/product/{record.data['title']}?"
                + f"email={self.email}"
            )
            ret = self.session.request(
                "GET",
                url,
                headers=self.requests_headers,
                timeout=self.prep_operation.timeout,
            )
            ret.raise_for_status()

            retrieved_record = self._cite_as_json_to_record(json_str=ret.text, url=url)

            if not colrev.record.record_similarity.matches(record, retrieved_record):
                return record

            record.merge(retrieved_record, default_source=url)

        except requests.exceptions.RequestException:
            pass
        except UnicodeEncodeError:
            self.logger.error(
                "UnicodeEncodeError - this needs to be fixed at some time"
            )

        return record
