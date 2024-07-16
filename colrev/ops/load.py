#! /usr/bin/env python
"""CoLRev load operation: Load records from search sources into references.bib."""
from __future__ import annotations

import itertools
import string
from pathlib import Path

import colrev.exceptions as colrev_exceptions
import colrev.loader.load_utils_formatter
import colrev.process.operation
import colrev.record.record
import colrev.settings
from colrev.constants import Colors
from colrev.constants import EndpointType
from colrev.constants import Fields
from colrev.constants import FieldSet
from colrev.constants import OperationsType
from colrev.constants import RecordState
from colrev.constants import SearchType


class Load(colrev.process.operation.Operation):
    """Load the records"""

    type = OperationsType.load

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
        hide_load_explanation: bool = False,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=self.type,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.quality_model = review_manager.get_qm()
        self.package_manager = self.review_manager.get_package_manager()

        self.load_formatter = colrev.loader.load_utils_formatter.LoadFormatter()

        if not hide_load_explanation:
            self.review_manager.logger.info("Load")
            self.review_manager.logger.info(
                "Load converts search results and adds them to the shared "
                f"{self.review_manager.paths.records}."
            )
            self.review_manager.logger.info(
                "Original records (search results) are stored in the directory data/search"
            )
            self.review_manager.logger.info(
                "See https://colrev.readthedocs.io/en/latest/manual/metadata_retrieval/load.html"
            )

    def _get_currently_imported_origin_list(self) -> list:
        records_headers = self.review_manager.dataset.load_records_dict(
            header_only=True
        )
        record_header_list = list(records_headers.values())
        imported_origins = [
            item for x in record_header_list for item in x[Fields.ORIGIN]
        ]
        return imported_origins

    def ensure_append_only(self, file: Path) -> None:
        """Ensure that the file was only appended to.

        This method must be called for all packages that work
        with an ex-post assignment of incremental IDs."""

        git_repo = self.review_manager.dataset.get_repo()

        # Ensure the path uses forward slashes, which is compatible with Git's path handling
        search_file_path = str(Path("data/search") / file.name).replace("\\", "/")
        revlist = (
            (
                commit.hexsha,
                (commit.tree / search_file_path).data_stream.read(),
            )
            for commit in git_repo.iter_commits(paths=str(file))
        )
        prior_file_content = ""
        for commit, filecontents in list(revlist):
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

    def _import_provenance(
        self,
        record: colrev.record.record.Record,
    ) -> None:
        """Set the provenance for an imported record"""

        def set_initial_import_provenance(record: colrev.record.record.Record) -> None:
            # Initialize Fields.MD_PROV
            colrev_masterdata_provenance, colrev_data_provenance = {}, {}

            for key in sorted(record.data.keys()):
                if key in FieldSet.IDENTIFYING_FIELD_KEYS:
                    if key not in colrev_masterdata_provenance:
                        colrev_masterdata_provenance[key] = {
                            "source": record.data[Fields.ORIGIN][0],
                            "note": "",
                        }
                elif key not in FieldSet.PROVENANCE_KEYS and key not in [
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
            set_initial_import_provenance(record)
            record.run_quality_model(self.quality_model)

    def _import_record(self, *, record_dict: dict) -> dict:
        self.review_manager.logger.debug(f"import_record {record_dict[Fields.ID]}: ")

        record = colrev.record.record.Record(record_dict)

        # For better readability of the git diff:
        self.load_formatter.run(record)

        self._import_provenance(record)

        if record.data[Fields.STATUS] in [
            RecordState.md_retrieved,
            RecordState.md_needs_manual_preparation,
        ]:
            record.set_status(RecordState.md_imported)

        if record.is_retracted():
            self.review_manager.logger.info(
                f"{Colors.GREEN}Found paper retract: "
                f"{record.data['ID']}{Colors.END}"
            )

        return record.get_data()

    def _validate_source_records(
        self,
        source_records_list: list,
        *,
        source: colrev.package_manager.interfaces.SearchSourceInterface,
    ) -> None:
        # pylint: disable=too-many-branches
        if len(source_records_list) == 0:
            raise colrev_exceptions.ImportException(
                msg=f"{source} has no records to load"
            )
        for source_record in source_records_list:
            if not all(x in source_record for x in [Fields.ID, Fields.ENTRYTYPE]):
                raise colrev_exceptions.ImportException(
                    f"Record should have keys {Fields.ID} and {Fields.ENTRYTYPE}"
                )
            if any(" " in x for x in source_record.keys()):
                raise colrev_exceptions.ImportException(
                    f"Keys should not contain spaces ({source_record.keys()})"
                )
            if not all(
                x.islower()
                for x in source_record.keys()
                if x not in [Fields.ID, Fields.ENTRYTYPE, Fields.CURATION_ID]
            ):
                raise colrev_exceptions.ImportException(
                    f"Keys should be lower case ({source_record.keys()})"
                )
            if any(x == "" for x in source_record.values()):
                raise colrev_exceptions.ImportException(
                    f"Values should not be empty ({source_record.values()})"
                )

            for key in source_record.keys():
                if "." in key:  # namespaced key
                    continue
                if key not in FieldSet.STANDARDIZED_FIELD_KEYS:
                    raise colrev_exceptions.ImportException(
                        f"Non-standardized field without namespace ({key})"
                    )

            for key in FieldSet.PROVENANCE_KEYS + [
                Fields.SCREENING_CRITERIA,
            ]:
                if key == Fields.STATUS:
                    continue
                if (
                    key == Fields.MD_PROV
                    and Fields.MD_PROV in source_record
                    and colrev.record.record.Record(
                        source_record
                    ).masterdata_is_curated()
                ):
                    continue
                if key in source_record:
                    raise colrev_exceptions.ImportException(
                        f"Key {key} should not be in imported record"
                    )

    def setup_source_for_load(
        self,
        source: colrev.package_manager.interfaces.SearchSourceInterface,
        *,
        select_new_records: bool = True,
    ) -> None:
        """
        Prepares a search source for loading records into the review manager's dataset.

        This method initializes the loading process by selecting new records from the source
        based on the `select_new_records` flag. It then prepares the source records for import
        by filtering out already imported records if `select_new_records` is True.

        Args:
            source: The search source package endpoint interface to prepare for loading.
            select_new_records: A boolean flag indicating whether to filter out records
                                that have already been imported. Defaults to True.
        """
        source_records_list = list(source.load(self).values())  # type: ignore
        self._validate_source_records(source_records_list, source=source)

        origin_prefix = source.search_source.get_origin_prefix()
        for source_record in source_records_list:
            record_origin = f"{origin_prefix}/{source_record['ID']}"
            source_record.update(colrev_origin=[record_origin])
            colrev.record.record.Record(source_record).set_status(
                target_state=RecordState.md_retrieved
            )

        imported_origins = []
        if select_new_records:
            imported_origins = self._get_currently_imported_origin_list()
            source_records_list = [
                x
                for x in source_records_list
                if x[Fields.ORIGIN][0] not in imported_origins
            ]

        source.search_source.setup_for_load(
            source_records_list=source_records_list, imported_origins=imported_origins
        )

    def load_source_records(
        self,
        source: colrev.package_manager.interfaces.SearchSourceInterface,
        *,
        keep_ids: bool,
    ) -> None:
        """
        Loads records from a specified source into the review manager's dataset.

        This method prepares the source for loading by calling `setup_source_for_load`
        and then proceeds to load the records. It takes into account whether the IDs
        of the records should be kept as is or generated anew.

        Args:
            source: The search source package endpoint interface from which records are loaded.
            keep_ids: A boolean flag indicating whether to keep the original IDs of the records.
        """
        self.review_manager.logger.debug(
            f"Load source records {source.search_source.filename}"
        )

        self.setup_source_for_load(source)
        records = self.review_manager.dataset.load_records_dict()

        self.review_manager.logger.debug(
            f"Import individual source records {source.search_source.filename}"
        )
        for source_record in source.search_source.source_records_list:
            source_record = self._import_record(record_dict=source_record)

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

        self.review_manager.logger.debug(
            f"Save records {source.search_source.filename}"
        )
        self.review_manager.dataset.save_records_dict(records)
        self._validate_load(source=source)

        if source.search_source.to_import == 0:
            self.review_manager.logger.info("No additional records loaded")
            if not self.review_manager.high_level_operation:
                print()

            return

        if not keep_ids:
            # Set IDs based on local_index
            # (the same records are more likely to have the same ID on the same machine)
            self.review_manager.logger.debug("Set IDs")
            records = self.review_manager.dataset.set_ids()

        self.review_manager.logger.info(
            "New records loaded".ljust(38) + f"{source.search_source.to_import} records"
        )
        self.review_manager.dataset.add_setting_changes()
        self.review_manager.dataset.add_changes(source.search_source.filename)

    def _add_source_to_settings(
        self,
        source: colrev.package_manager.interfaces.SearchSourceInterface,
    ) -> None:

        # Add to settings (if new filename)
        if source.search_source.filename in [
            s.filename for s in self.review_manager.settings.sources
        ]:
            return

        self.review_manager.logger.debug(
            f"Add source to settings {source.search_source.filename}"
        )
        git_repo = self.review_manager.dataset.get_repo()
        self.review_manager.settings.sources.append(source.search_source)
        self.review_manager.save_settings()
        # Add files that were renamed (removed)
        for obj in git_repo.index.diff(None).iter_change_type("D"):
            if source.search_source.filename.stem in obj.b_path:
                self.review_manager.dataset.add_changes(Path(obj.b_path), remove=True)

    def load_active_sources(self, *, include_md: bool = False) -> list:
        """
        Loads and returns a list of active source endpoints from the settings.

        Returns:
            list: A list of active source endpoint objects.
        """
        checker = self.review_manager.get_checker()
        checker.check_sources()
        sources_settings = []
        for source in self.review_manager.settings.sources:
            assert isinstance(source, colrev.settings.SearchSource)
            sources_settings.append(source)
        sources = []
        for source in sources_settings:
            try:
                search_source_class = self.package_manager.get_package_endpoint_class(
                    package_type=EndpointType.search_source,
                    package_identifier=source.endpoint,
                )
                endpoint = search_source_class(
                    source_operation=self, settings=source.get_dict()
                )

                s_type = endpoint.search_source.search_type  # type: ignore
                if s_type == SearchType.MD and not include_md:
                    continue
                sources.append(endpoint)

            except colrev_exceptions.MissingDependencyError as exc:
                self.review_manager.logger.error(exc)
                self.review_manager.logger.error(
                    f"Cannot load records for {source.filename}"
                )
                print()

        return sources

    def _validate_load(
        self,
        *,
        source: colrev.package_manager.interfaces.SearchSourceInterface,
    ) -> None:
        imported_origins = self._get_currently_imported_origin_list()
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

    def _create_load_commit(self, source: colrev.settings.SearchSource) -> None:
        git_repo = self.review_manager.dataset.get_repo()
        stashed = "No local changes to save" != git_repo.git.stash(
            "push", "--keep-index"
        )
        # part_exact_call = self.review_manager.exact_call
        # self.review_manager.exact_call = (
        #     f"{part_exact_call} -s {source.search_source.filename.name}"
        # )
        self.review_manager.dataset.create_commit(
            msg=f"Load {source.search_source.filename.name}", skip_hooks=True
        )
        if stashed:
            git_repo.git.stash("pop")
        if not self.review_manager.high_level_operation:
            print()

    @colrev.process.operation.Operation.decorate()
    def main(
        self,
        *,
        keep_ids: bool = False,
    ) -> None:
        """Load records (main entrypoint)"""

        if not self.review_manager.high_level_operation:
            print()

        for source in self.load_active_sources():
            try:
                self.review_manager.logger.info(f"Load {source.search_source.filename}")
                self._add_source_to_settings(source)
                self.load_source_records(source, keep_ids=keep_ids)
                self._create_load_commit(source)

            except FileNotFoundError:
                self.review_manager.logger.info(" Nothing to load")
                print()
            except colrev_exceptions.ImportException as exc:
                print(exc)

        self.review_manager.logger.info(
            f"{Colors.GREEN}Completed load operation{Colors.END}"
        )
