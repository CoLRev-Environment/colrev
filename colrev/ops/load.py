#! /usr/bin/env python
"""CoLRev load operation: Load records from search sources into references.bib."""
from __future__ import annotations

import itertools
import string
from pathlib import Path

import colrev.constants as c
import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.ops.load_utils_formatter
import colrev.record
import colrev.settings
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import FieldValues


class Load(colrev.operation.Operation):

    """Load the records"""

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
        hide_load_explanation: bool = False,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.load,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.quality_model = review_manager.get_qm()
        self.package_manager = self.review_manager.get_package_manager()

        self.load_formatter = colrev.ops.load_utils_formatter.LoadFormatter()

        if not hide_load_explanation:
            self.review_manager.logger.info("Load")
            self.review_manager.logger.info(
                "Load converts search results and adds them to the shared data/records.bib."
            )
            self.review_manager.logger.info(
                "Original records (search results) are stored in the directory data/search"
            )
            self.review_manager.logger.info(
                "See https://colrev.readthedocs.io/en/latest/manual/metadata_retrieval/load.html"
            )

    def __get_currently_imported_origin_list(self) -> list:
        records_headers = self.review_manager.dataset.load_records_dict(
            header_only=True
        )
        record_header_list = list(records_headers.values())
        imported_origins = [
            item for x in record_header_list for item in x[Fields.ORIGIN]
        ]
        return imported_origins

    def ensure_append_only(self, *, file: Path) -> None:
        """Ensure that the file was only appended to.

        This method must be called for all packages that work
        with an ex-post assignment of incremental IDs."""

        git_repo = self.review_manager.dataset.get_repo()
        revlist = (
            (
                commit.hexsha,
                (commit.tree / "data" / "search" / file.name).data_stream.read(),
            )
            for commit in git_repo.iter_commits(paths=str(file))
        )
        prior_file_content = ""
        for commit, filecontents in list(revlist):
            print(prior_file_content)
            if not filecontents.decode("utf-8").startswith(prior_file_content):
                raise colrev_exceptions.AppendOnlyViolation(
                    f"{file} was changed (commit: {commit})"
                )
            prior_file_content = filecontents.decode("utf-8").replace("\r", "")
        current_contents = file.read_text(encoding="utf-8").replace("\r", "")

        if not current_contents.startswith(prior_file_content):
            raise colrev_exceptions.AppendOnlyViolation(
                f"{file} was changed (uncommitted file)"
            )

    def __import_provenance(
        self,
        *,
        record: colrev.record.Record,
    ) -> None:
        """Set the provenance for an imported record"""

        def set_initial_import_provenance(*, record: colrev.record.Record) -> None:
            # Initialize Fields.MD_PROV
            colrev_masterdata_provenance, colrev_data_provenance = {}, {}

            for key in sorted(record.data.keys()):
                if key in c.FieldSet.IDENTIFYING_FIELD_KEYS:
                    if key not in colrev_masterdata_provenance:
                        colrev_masterdata_provenance[key] = {
                            "source": record.data[Fields.ORIGIN][0],
                            "note": "",
                        }
                elif key not in c.FieldSet.PROVENANCE_KEYS and key not in [
                    "colrev_source_identifier",
                    Fields.ID,
                    Fields.ENTRYTYPE,
                ]:
                    colrev_data_provenance[key] = {
                        "source": record.data[Fields.ORIGIN][0],
                        "note": "",
                    }

            record.data[Fields.D_PROV] = colrev_data_provenance
            record.data[Fields.MD_PROV] = colrev_masterdata_provenance

        if not record.masterdata_is_curated():
            set_initial_import_provenance(record=record)
            record.run_quality_model(qm=self.quality_model)

    def __import_record(self, *, record_dict: dict) -> dict:
        self.review_manager.logger.debug(f"import_record {record_dict[Fields.ID]}: ")

        record = colrev.record.Record(data=record_dict)

        # For better readability of the git diff:
        self.load_formatter.run(record=record)

        self.__import_provenance(record=record)

        if record.data[Fields.STATUS] in [
            colrev.record.RecordState.md_retrieved,
            colrev.record.RecordState.md_needs_manual_preparation,
        ]:
            record.set_status(target_state=colrev.record.RecordState.md_imported)

        if record.check_potential_retracts():
            self.review_manager.logger.info(
                f"{Colors.GREEN}Found paper retract: "
                f"{record.data['ID']}{Colors.END}"
            )

        return record.get_data()

    def __prep_records_for_import(
        self, *, source_settings: colrev.settings.SearchSource, search_records: dict
    ) -> list:
        record_list = []
        origin_prefix = source_settings.get_origin_prefix()
        for record in search_records.values():
            for key in c.FieldSet.PROVENANCE_KEYS + [
                Fields.SCREENING_CRITERIA,
            ]:
                if key == Fields.STATUS:
                    continue
                if key in record:
                    del record[key]

            record.update(colrev_origin=[f"{origin_prefix}/{record['ID']}"])

            # Drop empty fields
            record = {k: v for k, v in record.items() if v}

            if source_settings.endpoint == "colrev.local_index":
                # Note : when importing a record, it always needs to be
                # deduplicated against the other records in the repository
                record.update(colrev_status=colrev.record.RecordState.md_prepared)
                if "curation_ID" in record:
                    record[Fields.MD_PROV] = {
                        FieldValues.CURATED: {
                            "source": record["curation_ID"].split("#")[0],
                            "note": "",
                        }
                    }
            else:
                record.update(colrev_status=colrev.record.RecordState.md_retrieved)

            if Fields.DOI in record:
                formatted_doi = (
                    record[Fields.DOI]
                    .lower()
                    .replace("https://", "http://")
                    .replace("dx.doi.org", "doi.org")
                    .replace("http://doi.org/", "")
                    .upper()
                )
                record.update(doi=formatted_doi)

            self.review_manager.logger.debug(
                f"append record {record[Fields.ID]} "
                # f"\n{self.review_manager.p_printer.pformat(record)}\n\n"
            )
            record_list.append(record)
        return record_list

    def __setup_source_for_load(
        self, *, source: colrev.env.package_manager.SearchSourcePackageEndpointInterface
    ) -> None:
        search_records = source.load(self)  # type: ignore

        source_records_list = self.__prep_records_for_import(
            source_settings=source.search_source, search_records=search_records
        )
        imported_origins = self.__get_currently_imported_origin_list()
        source_records_list = [
            x
            for x in source_records_list
            if x[Fields.ORIGIN][0] not in imported_origins
        ]
        source.search_source.setup_for_load(
            source_records_list=source_records_list, imported_origins=imported_origins
        )
        if len(search_records) == 0:
            raise colrev_exceptions.ImportException(
                msg=f"{source} has no records to load"
            )

    def __load_source_records(
        self,
        *,
        source: colrev.env.package_manager.SearchSourcePackageEndpointInterface,
        keep_ids: bool,
    ) -> None:
        self.__setup_source_for_load(source=source)
        records = self.review_manager.dataset.load_records_dict()
        for source_record in source.search_source.source_records_list:
            colrev.record.Record(data=source_record).prefix_non_standardized_field_keys(
                prefix=source.search_source.endpoint
            )

            source_record = self.__import_record(record_dict=source_record)

            # Make sure not to replace existing records
            order = 0
            letters = list(string.ascii_lowercase)
            next_unique_id = source_record[Fields.ID]
            appends: list = []
            while next_unique_id in records:
                if len(appends) == 0:
                    order += 1
                    appends = list(itertools.product(letters, repeat=order))
                next_unique_id = source_record[Fields.ID] + "".join(
                    list(appends.pop(0))
                )
            source_record[Fields.ID] = next_unique_id

            records[source_record[Fields.ID]] = source_record

            self.review_manager.logger.info(
                f" {Colors.GREEN}{source_record['ID']}".ljust(46)
                + f"md_retrieved →  {source_record['colrev_status']}{Colors.END}"
            )

        self.review_manager.dataset.save_records_dict(records=records)
        self.__validate_load(source=source)

        if not keep_ids:
            # Set IDs based on local_index
            # (the same records are more likely to have the same ID on the same machine)
            self.review_manager.logger.debug("Set IDs")
            records = self.review_manager.dataset.set_ids(
                records=records,
                selected_ids=[
                    r[Fields.ID] for r in source.search_source.source_records_list
                ],
            )

        self.review_manager.logger.info(
            "New records loaded".ljust(38) + f"{source.search_source.to_import} records"
        )

        self.review_manager.dataset.add_setting_changes()
        self.review_manager.dataset.add_changes(path=source.search_source.filename)
        if (
            0 == getattr(source.search_source, "to_import", 0)
            and not self.review_manager.high_level_operation
        ):
            print()

    def __add_source_to_settings(
        self, *, source: colrev.env.package_manager.SearchSourcePackageEndpointInterface
    ) -> None:
        # Add to settings (if new filename)
        if source.search_source.filename in [
            s.filename for s in self.review_manager.settings.sources
        ]:
            return
        git_repo = self.review_manager.dataset.get_repo()
        self.review_manager.settings.sources.append(source.search_source)
        self.review_manager.save_settings()
        # Add files that were renamed (removed)
        for obj in git_repo.index.diff(None).iter_change_type("D"):
            if source.search_source.filename.stem in obj.b_path:
                self.review_manager.dataset.add_changes(
                    path=Path(obj.b_path), remove=True
                )

    def __load_active_sources(self) -> list:
        checker = self.review_manager.get_checker()
        checker.check_sources()
        sources_settings = []
        for source in self.review_manager.settings.sources:
            assert isinstance(source, colrev.settings.SearchSource)
            sources_settings.append(source)
        sources = []
        for source in sources_settings:
            endpoint_dict = self.package_manager.load_packages(
                package_type=colrev.env.package_manager.PackageEndpointType.search_source,
                selected_packages=[source.get_dict()],
                operation=self,
            )
            # if source.endpoint.lower() not in endpoint_dict:
            #     raise ...
            endpoint = endpoint_dict[source.endpoint.lower()]
            sources.append(endpoint)

        return sources

    def __validate_load(
        self, *, source: colrev.env.package_manager.SearchSourcePackageEndpointInterface
    ) -> None:
        imported_origins = self.__get_currently_imported_origin_list()
        imported = len(imported_origins) - source.search_source.len_before

        if imported == source.search_source.to_import:
            return
        # Note : for diagnostics, it is easier if we complete the process
        # and create the commit (instead of raising an exception)
        self.review_manager.logger.error(
            f"len_before: {source.search_source.len_before}"
        )
        self.review_manager.logger.error(f"len_after: {len(imported_origins)}")

        origins_to_import = [
            o[Fields.ORIGIN] for o in source.search_source.source_records_list
        ]
        if source.search_source.to_import - imported > 0:
            self.review_manager.logger.error(
                f"{Colors.RED}PROBLEM: delta: "
                f"{source.search_source.to_import - imported} records missing{Colors.END}"
            )

            missing_origins = [
                o for o in origins_to_import if o not in imported_origins
            ]
            self.review_manager.logger.error(
                f"{Colors.RED}Records not yet imported: {missing_origins}{Colors.END}"
            )
        else:
            self.review_manager.logger.error(
                f"{Colors.RED}PROBLEM: "
                f"{-1*(source.search_source.to_import - imported)}"
                f" records too much{Colors.END}"
            )
            additional_origins = [
                o for o in imported_origins if o not in origins_to_import
            ]
            self.review_manager.logger.error(
                f"{Colors.RED}Records additionally imported: {additional_origins}{Colors.END}"
            )

    def __create_load_commit(self, source: colrev.settings.SearchSource) -> None:
        git_repo = self.review_manager.dataset.get_repo()
        stashed = "No local changes to save" != git_repo.git.stash(
            "push", "--keep-index"
        )
        part_exact_call = self.review_manager.exact_call
        self.review_manager.exact_call = (
            f"{part_exact_call} -s {source.search_source.filename.name}"
        )
        self.review_manager.create_commit(
            msg=f"Load {source.search_source.filename.name}",
        )
        if stashed:
            git_repo.git.stash("pop")
        if not self.review_manager.high_level_operation:
            print()

    @colrev.operation.Operation.decorate()
    def main(
        self,
        *,
        keep_ids: bool = False,
    ) -> None:
        """Load records (main entrypoint)"""

        if not self.review_manager.high_level_operation:
            print()

        for source in self.__load_active_sources():
            try:
                self.review_manager.logger.info(f"Load {source.search_source.filename}")
                self.__add_source_to_settings(source=source)
                self.__load_source_records(source=source, keep_ids=keep_ids)
                self.__create_load_commit(source=source)

            except colrev_exceptions.ImportException as exc:
                print(exc)

        self.review_manager.logger.info(
            f"{Colors.GREEN}Completed load operation{Colors.END}"
        )
