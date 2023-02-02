#! /usr/bin/env python
"""SearchSource: backward search (based on PDFs and GROBID)"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.search
import colrev.record
import colrev.ui_cli.cli_colors as colors

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class BackwardSearchSource(JsonSchemaMixin):
    """Performs a backward search extracting references from PDFs using GROBID
    Scope: all included papers with colrev_status in (rev_included, rev_synthesized)
    """

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "bwsearch_ref"
    search_type = colrev.settings.SearchType.BACKWARD_SEARCH
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "PDF backward search"
    link = "https://github.com/kermitt2/grobid"

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:

        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.grobid_service = source_operation.review_manager.get_grobid_service()
        self.grobid_service.start()
        self.review_manager = source_operation.review_manager

    @classmethod
    def get_default_source(cls) -> colrev.settings.SearchSource:
        """Get the default SearchSource settings"""

        return colrev.settings.SearchSource(
            endpoint="colrev_built_in.pdf_backward_search",
            filename=Path("data/search/pdf_backward_search.bib"),
            search_type=colrev.settings.SearchType.BACKWARD_SEARCH,
            search_parameters={
                "scope": {"colrev_status": "rev_included|rev_synthesized"}
            },
            load_conversion_package_endpoint={"endpoint": "colrev_built_in.bibtex"},
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

        if "scope" not in source.search_parameters:
            raise colrev_exceptions.InvalidQueryException(
                "Scope required in the search_parameters"
            )

        if source.search_parameters["scope"].get("file", "") == "paper.md":
            pass
        else:
            if (
                source.search_parameters["scope"]["colrev_status"]
                != "rev_included|rev_synthesized"
            ):
                raise colrev_exceptions.InvalidQueryException(
                    "search_parameters/scope/colrev_status must be rev_included|rev_synthesized"
                )

        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )

    def __bw_search_condition(self, *, record: dict) -> bool:
        # rev_included/rev_synthesized
        if "colrev_status" in self.search_source.search_parameters["scope"]:
            if (
                self.search_source.search_parameters["scope"]["colrev_status"]
                == "rev_included|rev_synthesized"
            ) and record["colrev_status"] not in [
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_synthesized,
            ]:
                return False

        # Note: this is for peer_reviews
        if "file" in self.search_source.search_parameters["scope"]:
            if (
                self.search_source.search_parameters["scope"]["file"] == "paper.pdf"
            ) and "data/pdfs/paper.pdf" != record.get("file", ""):
                return False

        pdf_path = self.review_manager.path / Path(record["file"])
        if not Path(pdf_path).is_file():
            self.review_manager.logger.error(f'File not found for {record["ID"]}')
            return False

        return True

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of PDFs (backward search based on GROBID)"""

        # pylint: disable=too-many-branches

        records = search_operation.review_manager.dataset.load_records_dict()

        if not records:
            print("No records imported. Cannot run backward search yet.")
            return

        pdf_backward_search_feed = self.search_source.get_feed(
            review_manager=search_operation.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        nr_added, nr_changed = 0, 0
        for record in records.values():
            if not self.__bw_search_condition(record=record):
                continue

            # Note: IDs generated by GROBID for cited references may change across grobid versions
            # -> challenge for key-handling/updating searches...

            search_operation.review_manager.logger.info(
                f'Run backward search for {record["ID"]} ({record["file"]})'
            )

            pdf_path = self.review_manager.path / Path(record["file"])
            tei = search_operation.review_manager.get_tei(
                pdf_path=pdf_path,
            )
            new_records = tei.get_bibliography()

            for new_record in new_records:
                new_record["bwsearch_ref"] = (
                    record["ID"] + "_backward_search_" + new_record["ID"]
                )
                new_record["cited_by_IDs"] = record["ID"]
                new_record["cited_by_file"] = record["file"]
                try:
                    pdf_backward_search_feed.set_id(record_dict=new_record)
                except colrev_exceptions.NotFeedIdentifiableException:
                    continue

                prev_record_dict_version = {}
                if new_record["ID"] in pdf_backward_search_feed.feed_records:
                    prev_record_dict_version = pdf_backward_search_feed.feed_records[
                        new_record["ID"]
                    ]

                added = pdf_backward_search_feed.add_record(
                    record=colrev.record.Record(data=new_record),
                )

                if added:
                    nr_added += 1
                elif rerun:
                    # Note : only re-index/update
                    changed = search_operation.update_existing_record(
                        records=records,
                        record_dict=new_record,
                        prev_record_dict_version=prev_record_dict_version,
                        source=self.search_source,
                        update_time_variant_fields=rerun,
                    )
                    if changed:
                        nr_changed += 1
        pdf_backward_search_feed.save_feed_file()

        if nr_added > 0:
            search_operation.review_manager.logger.info(
                f"{colors.GREEN}Retrieved {nr_added} records{colors.END}"
            )
        else:
            search_operation.review_manager.logger.info(
                f"{colors.GREEN}No additional records retrieved{colors.END}"
            )

        if rerun:
            if nr_changed > 0:
                search_operation.review_manager.logger.info(
                    f"{colors.GREEN}Updated {nr_changed} records{colors.END}"
                )
            else:
                if records:
                    search_operation.review_manager.logger.info(
                        f"{colors.GREEN}Records (data/records.bib) up-to-date{colors.END}"
                    )

        if search_operation.review_manager.dataset.has_changes():
            search_operation.review_manager.create_commit(
                msg="Backward search", script_call="colrev search"
            )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for PDF backward searches (GROBID)"""

        result = {"confidence": 0.0}
        if str(filename).endswith("_ref_list.pdf"):
            result["confidence"] = 1.0
            return result
        return result

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for PDF backward searches (GROBID)"""

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for PDF backward searches (GROBID)"""

        if (
            "multimedia appendix"
            in record.data.get("title", "").lower()
            + record.data.get("journal", "").lower()
        ):
            record.prescreen_exclude(reason="grobid-error")

        if "misc" == record.data["ENTRYTYPE"] and "publisher" in record.data:
            record.data["ENTRYTYPE"] = "book"

        return record


if __name__ == "__main__":
    pass
