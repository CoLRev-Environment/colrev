#! /usr/bin/env python
import typing
from pathlib import Path

import requests
import zope.interface
from dacite import from_dict

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.database_connectors
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.SearchSourcePackageInterface)
class BackwardSearchSource:
    """Performs a backward search extracting references from PDFs using GROBID
    Scope: all included papers with colrev_status in (rev_included, rev_synthesized)
    """

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "{{cited_by_file}} (references)"

    source_identifier_search = "{{cited_by_file}} (references)"
    search_mode = "individual"

    def __init__(self, *, source_operation, settings: dict) -> None:
        if settings["search_parameters"]["scope"].get("file", "") != "paper.md":
            if (
                settings["search_parameters"]["scope"]["colrev_status"]
                != "rev_included|rev_synthesized"
            ):
                raise colrev_exceptions.InvalidQueryException(
                    "search_parameters/scope/colrev_status must be rev_included|rev_synthesized"
                )

        self.settings = from_dict(data_class=self.settings_class, data=settings)
        self.grobid_service = source_operation.review_manager.get_grobid_service()
        self.grobid_service.start()

    def __load_feed_file_records(
        self, *, search_operation: colrev.ops.search.Search
    ) -> typing.List[typing.Dict]:
        feed_file_records: typing.List[typing.Dict] = []
        if self.settings.filename.is_file():
            with open(self.settings.filename, encoding="utf8") as bibtex_file:
                if bibtex_file.read() == "":
                    feed_file_records = []
                else:
                    feed_rd = search_operation.review_manager.dataset.load_records_dict(
                        load_str=bibtex_file.read()
                    )
                    feed_file_records = list(feed_rd.values())
        return feed_file_records

    def __bw_search_condition(self, *, record: dict) -> bool:
        # rev_included/rev_synthesized
        if "colrev_status" in self.settings.search_parameters["scope"]:
            if (
                self.settings.search_parameters["scope"]["colrev_status"]
                == "rev_included|rev_synthesized"
            ) and record["colrev_status"] not in [
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_synthesized,
            ]:
                return False

        # Note: this is for peer_reviews
        if "file" in self.settings.search_parameters["scope"]:
            if (
                self.settings.search_parameters["scope"]["file"] == "paper.pdf"
            ) and "pdfs/paper.pdf" != record.get("file", ""):
                return False

        return True

    def __append_references_from_pdf(
        self,
        *,
        search_operation: colrev.ops.search.Search,
        feed_file_records: list,
        record: dict,
    ) -> list:

        pdf_path = search_operation.review_manager.path / Path(record["file"])
        if not Path(pdf_path).is_file():
            search_operation.review_manager.logger.error(
                f'File not found for {record["ID"]}'
            )
            return feed_file_records

        search_operation.review_manager.logger.info(
            f'Running backward search for {record["ID"]} ({record["file"]})'
        )

        # pylint: disable=consider-using-with
        options = {"consolidateHeader": "0", "consolidateCitations": "0"}
        ret = requests.post(
            self.grobid_service.GROBID_URL + "/api/processReferences",
            files=dict(input=open(pdf_path, "rb"), encoding="utf8"),
            data=options,
            headers={"Accept": "application/x-bibtex"},
        )

        new_records_dict = search_operation.review_manager.dataset.load_records_dict(
            load_str=ret.text
        )
        new_records = list(new_records_dict.values())
        for new_record in new_records:
            # IDs have to be distinct
            new_record["ID"] = record["ID"] + "_backward_search_" + new_record["ID"]
            new_record["cited_by"] = record["ID"]
            new_record["cited_by_file"] = record["file"]
            if new_record["ID"] not in [r["ID"] for r in feed_file_records]:
                feed_file_records.append(new_record)

        return feed_file_records

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:

        if not search_operation.review_manager.dataset.records_file.is_file():
            print("No records imported. Cannot run backward search yet.")
            return

        records = search_operation.review_manager.dataset.load_records_dict()

        feed_file_records: typing.List[typing.Dict] = self.__load_feed_file_records(
            search_operation=search_operation
        )

        for record in records.values():
            if not self.__bw_search_condition(record=record):
                continue
            self.__append_references_from_pdf(
                search_operation=search_operation,
                feed_file_records=feed_file_records,
                record=record,
            )

        records_dict = {r["ID"]: r for r in feed_file_records}
        search_operation.save_feed_file(
            records=records_dict, feed_file=self.settings.filename
        )
        search_operation.review_manager.dataset.add_changes(path=self.settings.filename)

        if search_operation.review_manager.dataset.has_changes():
            search_operation.review_manager.create_commit(
                msg="Backward search", script_call="colrev search"
            )
        else:
            print("No new records added.")

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0, "source_identifier": cls.source_identifier}
        if str(filename).endswith("_ref_list.pdf"):
            result["confidence"] = 1.0
            return result
        return result

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        return record


if __name__ == "__main__":
    pass
