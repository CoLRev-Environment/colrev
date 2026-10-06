#!/usr/bin/env python3
"""Repare CoLRev projects."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import colrev.env.local_index
import colrev.exceptions as colrev_exceptions
import colrev.loader.load_utils_formatter
import colrev.ops.search_api_feed
import colrev.process.operation
import colrev.record.record_similarity
from colrev.constants import DefectCodes
from colrev.constants import Fields
from colrev.constants import FieldSet
from colrev.constants import FieldValues
from colrev.constants import OperationsType
from colrev.constants import RecordState
from colrev.constants import SearchType
from colrev.writer.write_utils import write_file


class Repare(colrev.process.operation.Operation):
    """Repare a CoLRev project."""

    type = OperationsType.check

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
    ) -> None:
        """Initialize the instance."""
        super().__init__(
            review_manager=review_manager,
            operations_type=self.type,
            notify_state_transition_operation=False,
        )
        # fix file no longer available
        self.local_index = colrev.env.local_index.LocalIndex(verbose_mode=False)
        self.pdf_get_operation = self.review_manager.get_pdf_get_operation(
            notify_state_transition_operation=False
        )
        self.load_formatter = colrev.loader.load_utils_formatter.LoadFormatter()

    def _fix_broken_symlink_based_on_local_index(
        self, *, record: colrev.record.record.Record, full_path: Path
    ) -> None:
        """Fix broken symlinks based on local_index."""
        if os.path.islink(full_path) and not os.path.exists(full_path):
            self.review_manager.logger.debug(f" remove broken symlink: {full_path}")
            full_path.unlink()

        try:
            retrieved_record = self.local_index.retrieve(record.data, include_file=True)

            if Fields.FILE not in retrieved_record.data:
                self.review_manager.logger.debug(
                    f" file not linked in retrieved record: {record.data['ID']}"
                )
                return

            if not colrev.record.record_similarity.matches(record, retrieved_record):
                return

            record.update_field(
                key=Fields.FILE,
                value=str(retrieved_record.data[Fields.FILE]),
                source="local_index",
                append_edit=False,
            )
            self.pdf_get_operation.import_pdf(record)
            if Fields.FULLTEXT in retrieved_record.data:
                del retrieved_record.data[Fields.FULLTEXT]
            self.review_manager.logger.info(f" fix broken symlink: {record.data['ID']}")

        except colrev_exceptions.RecordNotInIndexException:
            self.review_manager.logger.debug(
                f" record not in index: {record.data['ID']}"
            )

    def _fix_files(self, records: dict) -> None:
        for record_id, record_dict in self._records_with_file_references(
            records=records
        ):
            self._fix_record_file_reference(
                record_id=record_id, record_dict=record_dict
            )

        file_search_sources = [
            x
            for x in self.review_manager.settings.sources
            if x.search_type == SearchType.FILES
        ]
        for search_source in file_search_sources:
            files_dir_feed = colrev.ops.search_api_feed.SearchAPIFeed(
                source_identifier="UNKNOWN",
                search_source=search_source,
                update_only=True,
                logger=self.review_manager.logger,
                verbose_mode=self.review_manager.verbose_mode,
            )
            prefix = search_source.get_origin_prefix()
            for record_dict in records.values():
                if Fields.FILE not in record_dict:
                    continue
                for origin in record_dict[Fields.ORIGIN]:
                    if origin.startswith(prefix):
                        feed_id = origin[len(prefix) + 1 :]
                        feed_record = files_dir_feed.feed_records[feed_id]
                        if (
                            feed_record.get(Fields.FILE, "a")
                            != record_dict[Fields.FILE]
                        ):
                            feed_record[Fields.FILE] = record_dict[Fields.FILE]
                            files_dir_feed.feed_records[feed_id] = feed_record

            files_dir_feed.save()

    def _records_with_file_references(self, *, records: dict) -> list[tuple[str, dict]]:
        return [
            (record_id, record_dict)
            for record_id, record_dict in records.items()
            if Fields.FILE in record_dict
        ]

    def _fix_record_file_reference(self, *, record_id: str, record_dict: dict) -> None:
        self._normalize_expected_pdf_path(record_dict=record_dict, record_id=record_id)
        full_path = self._full_file_path(record_dict=record_dict)

        if full_path.is_file():
            return

        self._move_missing_pdf_extension_variant_if_exists(full_path=full_path)
        self._normalize_double_blanks_in_file_path(
            record_dict=record_dict, full_path=full_path
        )
        full_path = self._full_file_path(record_dict=record_dict)

        if not full_path.is_file():
            record = colrev.record.record.Record(record_dict)
            self._fix_broken_symlink_based_on_local_index(
                record=record, full_path=full_path
            )

        if full_path.is_file():
            return

        self._handle_missing_file_reference(record_dict=record_dict)

    def _normalize_expected_pdf_path(
        self, *, record_dict: dict, record_id: str
    ) -> None:
        if not record_dict[Fields.FILE].startswith("data/pdfs/"):
            record_dict[Fields.FILE] = f"data/pdfs/{record_id}.pdf"

    def _full_file_path(self, *, record_dict: dict) -> Path:
        return self.review_manager.path / Path(record_dict[Fields.FILE])

    def _move_missing_pdf_extension_variant_if_exists(self, *, full_path: Path) -> None:
        if Path(str(full_path) + ".pdf").is_file():
            shutil.move(str(full_path) + ".pdf", str(full_path))

    def _normalize_double_blanks_in_file_path(
        self, *, record_dict: dict, full_path: Path
    ) -> None:
        try:
            parent_dir = full_path.parent
            same_dir_pdfs = [
                x.relative_to(self.review_manager.path)
                for x in parent_dir.glob("*.pdf")
            ]
            for same_dir_pdf in same_dir_pdfs:
                if record_dict[Fields.FILE].replace("  ", " ") == str(
                    same_dir_pdf
                ).replace("  ", " "):
                    shutil.move(str(same_dir_pdf), str(same_dir_pdf).replace("  ", " "))
                    record_dict[Fields.FILE] = record_dict[Fields.FILE].replace(
                        "  ", " "
                    )
        except ValueError:
            pass

    def _handle_missing_file_reference(self, *, record_dict: dict) -> None:
        record_dict["colrev_status_backup"] = record_dict[Fields.STATUS]
        del record_dict[Fields.FILE]
        record = colrev.record.record.Record(record_dict)
        record.set_status(RecordState.rev_prescreen_included)

    def _get_source_feeds(self) -> dict:
        source_feeds = {}
        for source in self.review_manager.settings.sources:
            source_feeds[
                str(source.search_results_path).replace("data/search/", "")
            ] = colrev.ops.search_api_feed.SearchAPIFeed(
                source_identifier="NA",
                search_source=source,
                update_only=False,
                logger=self.review_manager.logger,
                verbose_mode=self.review_manager.verbose_mode,
            ).feed_records
        return source_feeds

    # pylint: disable=too-many-branches
    def _remove_fields(self, record: colrev.record.record.Record) -> None:
        if "pdf_hash" in record.data:
            record.data[Fields.PDF_ID] = record.data["pdf_hash"]
            del record.data["pdf_hash"]
        if "pdf_prep_hints" in record.data:
            del record.data["pdf_prep_hints"]
        if Fields.GROBID_VERSION in record.data:
            del record.data[Fields.GROBID_VERSION]

        if Fields.D_PROV in record.data:
            mk_to_remove = []
            for key in record.data[Fields.D_PROV]:
                if key not in record.data:
                    mk_to_remove += [key]
            for key in mk_to_remove:
                del record.data[Fields.D_PROV][key]

        if Fields.MD_PROV in record.data:
            mdk_to_remove = []
            for key in record.data[Fields.MD_PROV]:
                if (
                    key not in record.data
                    and FieldValues.CURATED != key
                    and f"IGNORE:{DefectCodes.MISSING}"
                    not in record.data[Fields.MD_PROV][key]["note"]
                ):
                    mdk_to_remove += [key]
            for key in mdk_to_remove:
                del record.data[Fields.MD_PROV][key]

        if self.review_manager.settings.is_curated_masterdata_repo():
            if record.masterdata_is_curated():
                del record.data[Fields.MD_PROV][FieldValues.CURATED]

    def _set_data_provenance_field(
        self, *, record: colrev.record.record.Record, key: str, source_feeds: dict
    ) -> None:
        if key in record.data[Fields.D_PROV]:
            if not any(
                record.data[Fields.D_PROV][key]["source"].startswith(sf)
                for sf in list(source_feeds.keys())
            ):
                del record.data[Fields.D_PROV][key]
        if key not in record.data[Fields.D_PROV]:
            for origin in record.data[Fields.ORIGIN]:
                origin_source = origin.split("/")[0]
                origin_id = origin[len(origin_source) + 1 :]
                if (
                    origin_source not in source_feeds
                    or origin_id not in source_feeds[origin_source]
                ):
                    continue
                if key in source_feeds[origin_source][origin_id]:
                    record.add_field_provenance(key=key, source=origin, note="")
        if key == Fields.LANGUAGE:
            record.add_field_provenance(key=key, source="LanguageDetector", note="")
        if key == "tei_file":
            record.add_field_provenance(key=key, source="file|grobid", note="")
        if key == "colrev_pdf_id":
            record.add_field_provenance(key=key, source="file|pdf_hash", note="")

        if key not in record.data[Fields.D_PROV]:
            record.add_field_provenance(key=key, source="manual", note="")

        for _, prov_details in record.data[Fields.D_PROV].items():
            if prov_details["source"] in record.data[Fields.ORIGIN] + ["manual"]:
                continue
            if prov_details["source"].startswith("file|"):
                continue
            # Note : simple heuristic
            prov_details["source"] = record.data[Fields.ORIGIN][0]

    def _add_missing_masterdata_provenance(
        self,
        *,
        record: colrev.record.record.Record,
        key: str,
        value: str,
        source_feeds: dict,
    ) -> None:
        options = {}
        for origin in record.data[Fields.ORIGIN]:
            origin_source = origin.split("/")[0]
            origin_id = origin[len(origin_source) + 1 :]
            if (
                origin_source not in source_feeds
                or origin_id not in source_feeds[origin_source]
            ):
                continue
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

            for origin in record.data[Fields.ORIGIN]:
                origin_parts = origin.split("/", 1)  # Split on the first "/"
                if len(origin_parts) == 2:
                    origin_source, origin_id = origin.split("/")
                    if source_origin == origin_source:
                        source_value = origin

        record.add_field_provenance(key=key, source=source_value, note="")

    def _set_non_curated_masterdata_provenance_field(
        self,
        *,
        record: colrev.record.record.Record,
        key: str,
        value: str,
        source_feeds: dict,
    ) -> None:
        if key in record.data[Fields.MD_PROV]:
            if not any(
                record.data[Fields.MD_PROV][key]["source"].startswith(sf)
                for sf in list(source_feeds.keys())
            ):
                del record.data[Fields.MD_PROV][key]
        if key not in record.data[Fields.MD_PROV]:
            self._add_missing_masterdata_provenance(
                record=record, key=key, value=value, source_feeds=source_feeds
            )

        for prov_details in record.data[Fields.MD_PROV].values():
            if prov_details["source"] in record.data[Fields.ORIGIN] + ["manual"]:
                continue
            # Note : simple heuristic
            prov_details["source"] = record.data[Fields.ORIGIN][0]

    def _set_provenance_field(
        self,
        *,
        record: colrev.record.record.Record,
        key: str,
        value: str,
        source_feeds: dict,
    ) -> None:
        if key in FieldSet.IDENTIFYING_FIELD_KEYS:
            if record.masterdata_is_curated():
                return
            self._set_non_curated_masterdata_provenance_field(
                record=record, key=key, value=value, source_feeds=source_feeds
            )

        else:
            self._set_data_provenance_field(
                record=record, key=key, source_feeds=source_feeds
            )

    def _set_provenance(
        self, *, record: colrev.record.record.Record, source_feeds: dict
    ) -> None:
        record.align_provenance()
        for key, value in record.data.items():
            if key in [
                Fields.STATUS,
                Fields.ORIGIN,
                Fields.MD_PROV,
                Fields.D_PROV,
                "colrev_pdfid",
                "colrev_pdf_id",
                "colrev_id",
                Fields.ID,
                Fields.ENTRYTYPE,
                Fields.SCREENING_CRITERIA,
            ]:
                continue
            self._set_provenance_field(
                record=record, key=key, value=value, source_feeds=source_feeds
            )

    def _fix_provenance(self, records: dict) -> None:
        source_feeds = self._get_source_feeds()
        for record_dict in records.values():
            record = colrev.record.record.Record(record_dict)
            self._remove_fields(record)
            self._set_provenance(record=record, source_feeds=source_feeds)

    def _fix_curated_sources(self, records: dict) -> None:
        for search_source in self.review_manager.settings.sources:
            if search_source.platform != "colrev.local_index":
                continue

            curation_recs = colrev.loader.load_utils.load(
                filename=search_source.search_results_path,
                logger=self.review_manager.logger,
            )

            for record_id in list(curation_recs.keys()):
                if Fields.CURATION_ID not in curation_recs[record_id]:
                    try:
                        retrieved_record = self.local_index.retrieve(
                            curation_recs[record_id], include_file=False
                        )
                        del retrieved_record.data[Fields.STATUS]
                        curation_recs[record_id] = retrieved_record.data
                    except colrev_exceptions.RecordNotInIndexException:
                        main_record_origin = (
                            search_source.get_origin_prefix() + "/" + record_id
                        )
                        main_record_l = [
                            r
                            for r in records.values()
                            if main_record_origin in r[Fields.ORIGIN]
                        ]
                        if not main_record_l:
                            continue
                        main_record_id = main_record_l[0][Fields.ID]
                        if 1 == len(records[main_record_id][Fields.ORIGIN]):
                            del records[main_record_id]
                        else:
                            records[main_record_id][Fields.ORIGIN].remove(
                                main_record_origin
                            )
                        del curation_recs[record_id]

            write_file(
                records_dict=curation_recs, filename=search_source.search_results_path
            )
            self.review_manager.dataset.git_repo.add_changes(
                search_source.search_results_path
            )

    def _update_field_names(self, records: dict) -> None:
        for record_dict in records.values():
            # TBD: which parts are in upgrade/repare and which parts are in prepare??
            record = colrev.record.record.Record(record_dict)
            if Fields.FULLTEXT in record_dict.get("link", ""):
                record.rename_field(key="link", new_key=Fields.FULLTEXT)
            if (
                record.data.get("note", "").lower().startswith("cited by ")
                and Fields.CITED_BY not in record.data
            ):
                record.data["note"] = record.data["note"][9:]
                record.rename_field(key="note", new_key=Fields.CITED_BY)
            if (
                record.data.get("note", "").lower().startswith("cited by ")
                and Fields.CITED_BY in record.data
            ):
                record.remove_field(key="note")
            if record.data.get("link", "").startswith(
                "https://api.elsevier.com/content/article/"
            ) and record.data.get("link", "").endswith("Accept=text/xml"):
                record.remove_field(key="link")

    def _fix_field_values(self, records: dict) -> None:
        for record_dict in records.values():
            record = colrev.record.record.Record(record_dict)
            self.load_formatter.run(record)

    def _remove_records_not_in_search_results(self, records: dict) -> None:
        """Remove origins (or whole records) if their origin IDs are no longer present
        in the corresponding original search results (data/search/...).

        Logic:
        - Build a lookup: origin_prefix -> {feed_id set} by loading each source's
          search_results_path once.
        - For each record, check every origin like "crossref.bib/1234":
            - if 1234 not in data/search/crossref.bib -> drop that origin
            - if that was the last origin -> drop the whole record
        - If an origin prefix cannot be mapped to a configured search source,
          we keep it and warn (because we cannot verify it safely).
        """
        # 1) Load all configured search result files once (data/search/...)
        origin_prefix_to_ids: dict[str, set[str]] = {}

        for source in self.review_manager.settings.sources:
            try:
                prefix = source.get_origin_prefix()  # e.g., "crossref.bib"
                search_path = (
                    source.search_results_path
                )  # e.g., data/search/crossref.bib
            except Exception as exc:  # very defensive
                self.review_manager.logger.warning("Could not inspect source (%s)", exc)
                continue

            try:
                feed_records = colrev.loader.load_utils.load(
                    filename=search_path,
                    logger=self.review_manager.logger,
                )
                origin_prefix_to_ids[prefix] = set(feed_records.keys())
            except FileNotFoundError:
                # If the search results file doesn't exist, we cannot validate origins safely.
                self.review_manager.logger.warning(
                    "Search results file missing (%s). Keeping origins for prefix '%s' unchanged.",
                    search_path,
                    prefix,
                )
            except Exception as exc:
                self.review_manager.logger.warning(
                    "Could not load search results (%s): %s. "
                    "Keeping origins for prefix '%s' unchanged.",
                    search_path,
                    exc,
                    prefix,
                )

        # 2) Iterate through records and prune invalid origins
        for rec_id in list(records.keys()):
            record_dict = records[rec_id]
            origins = record_dict.get(Fields.ORIGIN, [])

            if isinstance(origins, str):
                origins = [origins]
            if not isinstance(origins, list):
                self.review_manager.logger.warning(
                    "Unexpected ORIGIN format for %s -> %r (keeping record unchanged)",
                    record_dict.get(Fields.ID, rec_id),
                    origins,
                )
                continue

            kept_origins: list[str] = []
            removed_origins: list[str] = []

            for origin in origins:
                if not isinstance(origin, str) or "/" not in origin:
                    # Not in "<prefix>/<id>" format -> cannot validate
                    kept_origins.append(origin)
                    self.review_manager.logger.warning(
                        "Unverifiable origin format for %s -> %r (kept)",
                        record_dict.get(Fields.ID, rec_id),
                        origin,
                    )
                    continue

                origin_prefix, origin_item_id = origin.split("/", 1)

                if origin_prefix not in origin_prefix_to_ids:
                    # We cannot validate because we don't have the corresponding feed ids set
                    kept_origins.append(origin)
                    self.review_manager.logger.warning(
                        "Unknown/unloaded origin prefix '%s' for %s (origin=%r). Kept.",
                        origin_prefix,
                        record_dict.get(Fields.ID, rec_id),
                        origin,
                    )
                    continue

                if origin_item_id in origin_prefix_to_ids[origin_prefix]:
                    kept_origins.append(origin)
                else:
                    removed_origins.append(origin)

            if removed_origins:
                self.review_manager.logger.info(
                    "Pruning missing origin(s) for %s: %s",
                    record_dict.get(Fields.ID, rec_id),
                    ", ".join(removed_origins),
                )

            if not kept_origins:
                self.review_manager.logger.warning(
                    "Removing record %s because all origins are "
                    "missing in their search results (%s)",
                    record_dict.get(Fields.ID, rec_id),
                    ", ".join(removed_origins) if removed_origins else "no origins",
                )
                del records[rec_id]
                continue

            record_dict[Fields.ORIGIN] = kept_origins

    def _fix_misassigned_curated_pdfs(self, records: dict) -> None:
        """Remove misassigned PDFs in curated repositories.

        Heuristics:
        - If file path matches data/pdfs/<YEAR>/..., remove if YEAR != record[year]
        - If file path matches data/pdfs/<VOLUME>_<ISSUE>/..., remove if mismatch with volume/number
        (where issue is typically Fields.NUMBER in CoLRev records)

        Side effect:
        - If we remove Fields.FILE, also remove ORIGIN entries starting with "pdfs.bib/".
        """

        # Only apply in curated masterdata repositories
        if not self.review_manager.settings.is_curated_masterdata_repo():
            return

        year_dir_re = re.compile(r"^data/pdfs/(?P<year>\d{4})/")
        vol_issue_dir_re = re.compile(r"^data/pdfs/(?P<vol>\d+)_(?P<iss>\d+)/")

        def _drop_pdf_origin(record_dict: dict) -> None:
            """Remove any origin entries starting with 'pdfs.bib/'."""
            if Fields.ORIGIN not in record_dict:
                return
            origins = record_dict.get(Fields.ORIGIN) or []

            new_origins = [
                origin for origin in origins if not str(origin).startswith("pdfs.bib/")
            ]
            record_dict[Fields.ORIGIN] = new_origins

        def _remove_file_and_pdf_origin(record_dict: dict) -> None:
            if Fields.FILE in record_dict:
                del record_dict[Fields.FILE]
            _drop_pdf_origin(record_dict)

        for record_dict in records.values():
            file_path = record_dict.get(Fields.FILE)
            if not file_path:
                continue

            # Only validate "structured" paths; leave other schemes alone
            if not isinstance(file_path, str) or not file_path.startswith("data/pdfs/"):
                continue

            rec_year_raw = record_dict.get(Fields.YEAR, "")
            rec_year = None
            try:
                rec_year = (
                    int(str(rec_year_raw).strip())
                    if str(rec_year_raw).strip()
                    else None
                )
            except ValueError:
                rec_year = None

            # --- Case 1: data/pdfs/<YEAR>/...
            m_year = year_dir_re.match(file_path)
            if m_year:
                dir_year = int(m_year.group("year"))
                if rec_year is not None and dir_year != rec_year:
                    _remove_file_and_pdf_origin(record_dict)
                continue

            # --- Case 2: data/pdfs/<VOLUME>_<ISSUE>/...
            m_vi = vol_issue_dir_re.match(file_path)
            if m_vi:
                dir_vol = m_vi.group("vol")
                dir_iss = m_vi.group("iss")

                rec_vol = str(record_dict.get(Fields.VOLUME, "")).strip()
                rec_iss = str(record_dict.get(Fields.NUMBER, "")).strip()

                comparable = False
                mismatch = False

                if rec_vol:
                    comparable = True
                    mismatch = mismatch or (rec_vol != dir_vol)

                if rec_iss:
                    comparable = True
                    mismatch = mismatch or (rec_iss != dir_iss)

                if comparable and mismatch:
                    _remove_file_and_pdf_origin(record_dict)

                continue

            # Other folder conventions: do nothing (avoid false positives)
            continue

        # Drop all records with empty ORIGIN
        for rid in list(records.keys()):
            origins = records[rid].get(Fields.ORIGIN, [])

            if len(origins) == 0:
                del records[rid]

        write_file(records_dict=records, filename=Path("data/records.bib"))

    @colrev.process.operation.Operation.decorate()
    def main(self) -> None:
        """Repare a CoLRev project (main entrypoint)."""
        # Try: open settings, except: notify & start repare

        # ...

        # Try: open records, except: notify & start repare
        try:
            records = self.review_manager.dataset.load_records_dict()
        except AttributeError:
            self.review_manager.logger.error("Could not read bibtex file")

            separated_records = {}  # type: ignore
            with open(self.review_manager.paths.records, encoding="utf-8") as file:
                record_str = ""
                line = file.readline()

                while line:
                    if line == "\n":
                        records = colrev.loader.load_utils.loads(
                            load_string=record_str,
                            implementation="bib",
                            logger=self.review_manager.logger,
                        )

                        if len(records) != 1:
                            print(record_str)
                        else:
                            separated_records = {**separated_records, **records}
                        record_str = ""
                    record_str += line
                    line = file.readline()

            write_file(records_dict=separated_records, filename=Path("extracted.bib"))

            try:
                records = self.review_manager.dataset.load_records_dict()
            except AttributeError:
                return

        self._remove_records_not_in_search_results(records)

        self._fix_misassigned_curated_pdfs(records)

        self._fix_curated_sources(records)

        # removing specific fields
        # for record_dict in records.values():
        #     if "colrev_status_backup" in record_dict:
        #         colrev.record.record.Record(record_dict).remove_field(
        #             key="colrev_status_backup"
        #         )
        #     if "colrev_local_index" in record_dict:
        #         colrev.record.record.Record(record_dict).remove_field(
        #             key="colrev_local_index"
        #         )

        self._update_field_names(records)

        self._fix_provenance(records)

        self._fix_field_values(records)

        self._fix_files(records)

        self.review_manager.dataset.save_records_dict(records)
