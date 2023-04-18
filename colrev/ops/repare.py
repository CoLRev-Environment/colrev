#!/usr/bin/env python3
"""Repare CoLRev projects."""
from __future__ import annotations

import os
from pathlib import Path

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.operation

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.review_manager


# pylint: disable=too-few-public-methods


class Repare(colrev.operation.Operation):
    """Repare a CoLRev project"""

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.check,
            notify_state_transition_operation=False,
        )
        # fix file no longer available
        self.local_index = self.review_manager.get_local_index()
        self.pdf_get_operation = self.review_manager.get_pdf_get_operation()

    def __fix_broken_symlink_based_on_local_index(
        self, *, record: colrev.record.Record, full_path: Path
    ) -> None:
        """Fix broken symlinks based on local_index"""

        if os.path.islink(full_path) and not os.path.exists(full_path):
            self.review_manager.logger.debug(f" remove broken symlink: {full_path}")
            full_path.unlink()

        try:
            retrieved_record = self.local_index.retrieve(
                record_dict=record.data, include_file=True
            )

            if "file" in retrieved_record:
                record.update_field(
                    key="file",
                    value=str(retrieved_record["file"]),
                    source="local_index",
                    append_edit=False,
                )
                self.pdf_get_operation.import_file(record=record)
                if "fulltext" in retrieved_record:
                    del retrieved_record["fulltext"]
                self.review_manager.logger.info(
                    f" fix broken symlink: {record.data['ID']}"
                )
            else:
                self.review_manager.logger.debug(
                    f" file not linked in retrieved record: {record.data['ID']}"
                )

        except colrev_exceptions.RecordNotInIndexException:
            self.review_manager.logger.debug(
                f" record not in index: {record.data['ID']}"
            )

    def __fix_files(self, *, records: dict) -> None:
        for record_dict in records.values():
            if "file" not in record_dict:
                continue

            if not record_dict["file"].startswith("data/pdfs/"):
                record_dict["file"] = f"data/pdfs/{record_dict['ID']}.pdf"

            full_path = self.review_manager.path / Path(record_dict["file"])

            if full_path.is_file():
                continue

            # Add .pdf extension if missing
            if Path(str(full_path) + ".pdf").is_file():
                Path(str(full_path) + ".pdf").rename(full_path)

            # Check / replace multiple blanks in file and filename
            try:
                parent_dir = full_path.parent
                same_dir_pdfs = [
                    x.relative_to(self.review_manager.path)
                    for x in parent_dir.glob("*.pdf")
                ]
                for same_dir_pdf in same_dir_pdfs:
                    if record_dict["file"].replace("  ", " ") == str(
                        same_dir_pdf
                    ).replace("  ", " "):
                        same_dir_pdf.rename(str(same_dir_pdf).replace("  ", " "))
                        record_dict["file"] = record_dict["file"].replace("  ", " ")
            except ValueError:
                pass

            full_path = self.review_manager.path / Path(record_dict["file"])

            if not full_path.is_file():
                record = colrev.record.Record(data=record_dict)
                self.__fix_broken_symlink_based_on_local_index(
                    record=record, full_path=full_path
                )

            if full_path.is_file():
                continue

            record_dict["colrev_status_backup"] = record_dict["colrev_status"]
            del record_dict["file"]
            record = colrev.record.Record(data=record_dict)
            record.set_status(
                target_state=colrev.record.RecordState.rev_prescreen_included
            )

    def __get_source_feeds(self) -> dict:
        source_feeds = {}
        for source in self.review_manager.settings.sources:
            source_feeds[
                str(source.get_corresponding_bib_file()).replace("data/search/", "")
            ] = source.get_feed(
                review_manager=self.review_manager,
                source_identifier="NA",
                update_only=False,
            ).feed_records
        return source_feeds

    def __remove_fields(self, *, record: colrev.record.Record) -> None:
        if "pdf_hash" in record.data:
            record.data["colrev_pdf_id"] = record.data["pdf_hash"]
            del record.data["pdf_hash"]
        if "pdf_prep_hints" in record.data:
            del record.data["pdf_prep_hints"]
        if "grobid-version" in record.data:
            del record.data["grobid-version"]

        mk_to_remove = []
        for key in record.data["colrev_data_provenance"]:
            if key not in record.data:
                mk_to_remove += [key]
        for key in mk_to_remove:
            del record.data["colrev_data_provenance"][key]

        mdk_to_remove = []
        for key in record.data["colrev_masterdata_provenance"]:
            if (
                key not in record.data
                and "CURATED" != key
                and "not_missing"
                not in record.data["colrev_masterdata_provenance"][key]["note"]
            ):
                mdk_to_remove += [key]
        for key in mdk_to_remove:
            del record.data["colrev_masterdata_provenance"][key]

        if self.review_manager.settings.is_curated_masterdata_repo():
            if "CURATED" in record.data["colrev_masterdata_provenance"]:
                del record.data["colrev_masterdata_provenance"]["CURATED"]

    def __set_data_provenance_field(
        self, *, record: colrev.record.Record, key: str, source_feeds: dict
    ) -> None:
        if key in record.data["colrev_data_provenance"]:
            if not any(
                record.data["colrev_data_provenance"][key]["source"].startswith(sf)
                for sf in list(source_feeds.keys())
            ):
                del record.data["colrev_data_provenance"][key]
        if key not in record.data["colrev_data_provenance"]:
            for origin in record.data["colrev_origin"]:
                origin_source, origin_id = origin.split("/")
                if key in source_feeds[origin_source][origin_id]:
                    record.add_data_provenance(key=key, source=origin, note="")
        if key == "language":
            record.add_data_provenance(key=key, source="LanguageDetector", note="")
        if key == "tei_file":
            record.add_data_provenance(key=key, source="file|grobid", note="")
        if key == "colrev_pdf_id":
            record.add_data_provenance(key=key, source="file|pdf_hash", note="")

        if key not in record.data["colrev_data_provenance"]:
            record.add_data_provenance(key=key, source="manual", note="")

        for _, prov_details in record.data["colrev_data_provenance"].items():
            if prov_details["source"] in record.data["colrev_origin"] + ["manual"]:
                continue
            # Note : simple heuristic
            prov_details["source"] = record.data["colrev_origin"][0]

    def __add_missing_masterdata_provenance(
        self, *, record: colrev.record.Record, key: str, value: str, source_feeds: dict
    ) -> None:
        options = {}
        for origin in record.data["colrev_origin"]:
            origin_source, origin_id = origin.split("/")
            if key in source_feeds[origin_source][origin_id]:
                options[origin_source] = source_feeds[origin_source][origin_id][key]

        source_value = "manual"

        # Note : simple heuristics:
        if value in options.values():
            if "md_curated.bib" in options:
                source_origin = "md_curated.bib"
            elif "md_crossref.bib" in options:
                source_origin = "md_crossref.bib"
            elif "CROSSREF.bib" in options:
                source_origin = "CROSSREF.bib"
            elif "md_dblp.bib" in options:
                source_origin = "md_dblp.bib"
            elif "DBLP.bib" in options:
                source_origin = "DBLP.bib"
            else:
                source_origin = [k for k, v in options.items() if v == value][0]

            for origin in record.data["colrev_origin"]:
                origin_source, origin_id = origin.split("/")
                if source_origin == origin_source:
                    source_value = origin

        record.add_masterdata_provenance(key=key, source=source_value, note="")

    def __set_non_curated_masterdata_provenance_field(
        self, *, record: colrev.record.Record, key: str, value: str, source_feeds: dict
    ) -> None:
        if key in record.data["colrev_masterdata_provenance"]:
            if not any(
                record.data["colrev_masterdata_provenance"][key]["source"].startswith(
                    sf
                )
                for sf in list(source_feeds.keys())
            ):
                del record.data["colrev_masterdata_provenance"][key]
        if key not in record.data["colrev_masterdata_provenance"]:
            self.__add_missing_masterdata_provenance(
                record=record, key=key, value=value, source_feeds=source_feeds
            )

        for prov_details in record.data["colrev_masterdata_provenance"].values():
            if prov_details["source"] in record.data["colrev_origin"] + ["manual"]:
                continue
            # Note : simple heuristic
            prov_details["source"] = record.data["colrev_origin"][0]

    def __set_provenance_field(
        self, *, record: colrev.record.Record, key: str, value: str, source_feeds: dict
    ) -> None:
        if key in colrev.record.Record.identifying_field_keys:
            if "CURATED" in record.data["colrev_masterdata_provenance"]:
                return
            self.__set_non_curated_masterdata_provenance_field(
                record=record, key=key, value=value, source_feeds=source_feeds
            )

        else:
            self.__set_data_provenance_field(
                record=record, key=key, source_feeds=source_feeds
            )

    def __set_provenance(
        self, *, record: colrev.record.Record, source_feeds: dict
    ) -> None:
        if "colrev_data_provenance" not in record.data:
            record.data["colrev_data_provenance"] = {}
        if "colrev_masterdata_provenance" not in record.data:
            record.data["colrev_masterdata_provenance"] = {}

        for key, value in record.data.items():
            if key in [
                "colrev_status",
                "colrev_origin",
                "colrev_masterdata_provenance",
                "colrev_data_provenance",
                "colrev_pdfid",
                "colrev_pdf_id",
                "colrev_id",
                "ID",
                "ENTRYTYPE",
                "screening_criteria",
            ]:
                continue
            self.__set_provenance_field(
                record=record, key=key, value=value, source_feeds=source_feeds
            )

    def __fix_provenance(self, *, records: dict) -> None:
        source_feeds = self.__get_source_feeds()
        for record_dict in records.values():
            record = colrev.record.Record(data=record_dict)
            self.__remove_fields(record=record)
            self.__set_provenance(record=record, source_feeds=source_feeds)

    def __fix_curated_sources(self, *, records: dict) -> None:
        local_index = self.review_manager.get_local_index()
        for search_source in self.review_manager.settings.sources:
            if search_source.endpoint != "colrev.local_index":
                continue
            curation_recs = self.review_manager.dataset.load_records_dict(
                file_path=search_source.filename
            )
            for record_id in list(curation_recs.keys()):
                if "curation_ID" not in curation_recs[record_id]:
                    try:
                        retrieved_record_dict = local_index.retrieve(
                            record_dict=curation_recs[record_id], include_file=False
                        )
                        del retrieved_record_dict["colrev_status"]
                        curation_recs[record_id] = retrieved_record_dict
                    except colrev_exceptions.RecordNotInIndexException:
                        main_record_origin = (
                            search_source.get_origin_prefix() + "/" + record_id
                        )
                        main_record_l = [
                            r
                            for r in records.values()
                            if main_record_origin in r["colrev_origin"]
                        ]
                        if not main_record_l:
                            continue
                        main_record_id = main_record_l[0]["ID"]
                        if 1 == len(records[main_record_id]["colrev_origin"]):
                            del records[main_record_id]
                        else:
                            records[main_record_id]["colrev_origin"].remove(
                                main_record_origin
                            )
                        del curation_recs[record_id]

            self.review_manager.dataset.save_records_dict_to_file(
                records=curation_recs, save_path=search_source.filename
            )
            self.review_manager.dataset.add_changes(path=search_source.filename)

    def main(self) -> None:
        """Repare a CoLRev project (main entrypoint)"""

        # Try: open settings, except: notify & start repare

        # ...

        # Try: open records, except: notify & start repare
        try:
            records = self.review_manager.dataset.load_records_dict()
        except AttributeError:
            self.review_manager.logger.error("Could not read bibtex file")

            separated_records = {}  # type: ignore
            with open(
                self.review_manager.dataset.records_file, encoding="utf-8"
            ) as file:
                record_str = ""
                line = file.readline()

                while line:
                    if line == "\n":
                        records = self.review_manager.dataset.load_records_dict(
                            load_str=record_str
                        )
                        if len(records) != 1:
                            print(record_str)
                        else:
                            separated_records = {**separated_records, **records}
                        record_str = ""
                    record_str += line
                    line = file.readline()
            self.review_manager.dataset.save_records_dict_to_file(
                records=separated_records, save_path=Path("extracted.bib")
            )
            try:
                records = self.review_manager.dataset.load_records_dict()
            except AttributeError:
                return

        self.__fix_curated_sources(records=records)

        # removing specific fields
        # for record_dict in records.values():
        #     if "colrev_status_backup" in record_dict:
        #         colrev.record.Record(data=record_dict).remove_field(
        #             key="colrev_status_backup"
        #         )
        #     if "colrev_local_index" in record_dict:
        #         colrev.record.Record(data=record_dict).remove_field(
        #             key="colrev_local_index"
        #         )

        self.__fix_provenance(records=records)

        self.__fix_files(records=records)

        self.review_manager.dataset.save_records_dict(records=records)


if __name__ == "__main__":
    pass
