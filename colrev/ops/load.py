#! /usr/bin/env python
"""CoLRev load operation: Load records from search sources into references.bib."""
from __future__ import annotations

import html
import itertools
import re
import string
import typing
from pathlib import Path

import colrev.env.language_service
import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.record
import colrev.settings
import colrev.ui_cli.cli_colors as colors


class Load(colrev.operation.Operation):
    """Load the records"""

    # TODO : extract to separate format conversion script
    __LATEX_SPECIAL_CHAR_MAPPING = {
        '\\"u': "ü",
        "\\&": "&",
        '\\"o': "ö",
        '\\"a': "ä",
        '\\"A': "Ä",
        '\\"O': "Ö",
        '\\"U': "Ü",
        "\\textendash": "–",
        "\\textemdash": "—",
        "\\~a": "ã",
        "\\'o": "ó",
    }

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
        self.language_service = colrev.env.language_service.LanguageService()

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

    def __get_new_search_files(self) -> list[Path]:
        """Retrieve new search files (not yet registered in settings)"""

        files = [
            f.relative_to(self.review_manager.path)
            for f in self.review_manager.search_dir.glob("**/*")
        ]

        # Only files that are not yet registered
        # (also exclude bib files corresponding to a registered file)
        files = [
            f
            for f in files
            if str(f.with_suffix(".bib"))
            not in [
                str(s.filename.with_suffix(".bib"))
                for s in self.review_manager.settings.sources
            ]
        ]

        return sorted(list(set(files)))

    def __get_currently_imported_origin_list(self) -> list:
        records_headers = self.review_manager.dataset.load_records_dict(
            header_only=True
        )
        record_header_list = list(records_headers.values())
        imported_origins = [
            item for x in record_header_list for item in x["colrev_origin"]
        ]
        return imported_origins

    def __get_heuristics_results_list(
        self,
        *,
        filepath: Path,
        search_sources: dict,
        data: str,
    ) -> list:
        results_list = []
        for (
            endpoint,
            endpoint_class,
        ) in search_sources.items():
            # pylint: disable=no-member
            has_heuristic = getattr(endpoint_class, "heuristic", None)
            if not has_heuristic:
                self.review_manager.logger.debug(f"- {endpoint}: no heuristic")
                continue
            res = endpoint_class.heuristic(filepath, data)  # type: ignore
            self.review_manager.logger.debug(f"- {endpoint}: {res['confidence']}")
            if res["confidence"] == 0.0:
                continue
            try:
                result_item = {}

                res["endpoint"] = endpoint

                search_type = endpoint_class.search_type
                # Note : as the identifier, we use the filename
                # (if search results are added by file/not via the API)

                # Correct the file extension if necessary
                if re.findall(r"^%0", data, re.MULTILINE) and filepath.suffix not in [
                    ".enl"
                ]:
                    new_filename = filepath.with_suffix(".enl")
                    self.review_manager.logger.info(
                        f"{colors.GREEN}Rename to {new_filename} "
                        f"(because the format is .enl){colors.END}"
                    )
                    filepath.rename(new_filename)
                    self.review_manager.dataset.add_changes(path=filepath, remove=True)
                    filepath = new_filename
                    res["filename"] = filepath
                    self.review_manager.dataset.add_changes(path=new_filename)
                    self.review_manager.create_commit(msg=f"Rename {filepath}")

                if re.findall(r"^TI ", data, re.MULTILINE) and filepath.suffix not in [
                    ".ris"
                ]:
                    new_filename = filepath.with_suffix(".ris")
                    self.review_manager.logger.info(
                        f"{colors.GREEN}Rename to {new_filename} "
                        f"(because the format is .ris){colors.END}"
                    )
                    filepath.rename(new_filename)
                    self.review_manager.dataset.add_changes(path=filepath, remove=True)
                    filepath = new_filename
                    res["filename"] = filepath
                    self.review_manager.dataset.add_changes(path=new_filename)
                    self.review_manager.create_commit(msg=f"Rename {filepath}")

                source_candidate = colrev.settings.SearchSource(
                    endpoint=endpoint,
                    filename=filepath,
                    search_type=search_type,
                    search_parameters={},
                    comment="",
                )

                result_item["source_candidate"] = source_candidate
                result_item["confidence"] = res["confidence"]

                results_list.append(result_item)
            except colrev_exceptions.UnsupportedImportFormatError:
                continue
        return results_list

    def __apply_source_heuristics(
        self,
        *,
        filepath: Path,
        search_sources: dict,
    ) -> list[typing.Dict]:
        """Apply heuristics to identify source"""

        data = ""
        try:
            data = filepath.read_text()
        except UnicodeDecodeError:
            pass

        results_list = self.__get_heuristics_results_list(
            filepath=filepath,
            search_sources=search_sources,
            data=data,
        )

        # Reduce the results_list when there are results with very high confidence
        if [r for r in results_list if r["confidence"] > 0.95]:
            results_list = [r for r in results_list if r["confidence"] > 0.8]

        return results_list

    def get_new_sources_heuristic_list(self) -> list:
        """Get the heuristic result list of new SearchSources"""

        # pylint: disable=redefined-outer-name

        new_search_files = self.__get_new_search_files()
        if not new_search_files:
            self.review_manager.logger.info("No new search files...")
            return []

        self.review_manager.logger.debug("Load available search_source endpoints...")

        search_source_identifiers = self.package_manager.discover_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            installed_only=True,
        )

        search_sources = self.package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            selected_packages=[{"endpoint": p} for p in search_source_identifiers],
            operation=self,
            instantiate_objects=False,
        )

        heuristic_result_list = []
        for sfp in new_search_files:
            sfp_name = sfp
            if sfp_name in [
                str(source.filename) for source in self.review_manager.settings.sources
            ]:
                continue

            if not self.review_manager.high_level_operation:
                print()
            self.review_manager.logger.info(f"Discover new source: {sfp_name}")

            heuristic_result_list.append(
                self.__apply_source_heuristics(
                    filepath=sfp,
                    search_sources=search_sources,
                )
            )
        return heuristic_result_list

    def __unescape_latex(self, *, input_str: str) -> str:
        # Based on
        # https://en.wikibooks.org/wiki/LaTeX/Special_Characters

        for latex_char, repl_char in self.__LATEX_SPECIAL_CHAR_MAPPING.items():
            input_str = input_str.replace(latex_char, repl_char)

        input_str = input_str.replace("\\emph", "")
        input_str = input_str.replace("\\textit", "")

        return input_str

    def __unescape_html(self, *, input_str: str) -> str:
        input_str = html.unescape(input_str)
        if "<" in input_str:
            input_str = re.sub(r"<.*?>", "", input_str)
        return input_str

    def import_provenance(
        self,
        *,
        record: colrev.record.Record,
    ) -> None:
        """Set the provenance for an imported record"""

        def set_initial_import_provenance(*, record: colrev.record.Record) -> None:
            # Initialize colrev_masterdata_provenance
            colrev_masterdata_provenance, colrev_data_provenance = {}, {}

            for key in sorted(record.data.keys()):
                if key in colrev.record.Record.identifying_field_keys:
                    if key not in colrev_masterdata_provenance:
                        colrev_masterdata_provenance[key] = {
                            "source": record.data["colrev_origin"][0],
                            "note": "",
                        }
                elif key not in colrev.record.Record.provenance_keys and key not in [
                    "colrev_source_identifier",
                    "ID",
                    "ENTRYTYPE",
                ]:
                    colrev_data_provenance[key] = {
                        "source": record.data["colrev_origin"][0],
                        "note": "",
                    }

            record.data["colrev_data_provenance"] = colrev_data_provenance
            record.data["colrev_masterdata_provenance"] = colrev_masterdata_provenance

        if not record.masterdata_is_curated():
            set_initial_import_provenance(record=record)
            record.update_masterdata_provenance(qm=self.quality_model)

    def __import_format_fields(self, *, record: colrev.record.Record) -> None:
        # pylint: disable=duplicate-code
        # For better readability of the git diff:
        fields_to_process = [
            f
            for f in [
                "author",
                "year",
                "title",
                "journal",
                "booktitle",
                "series",
                "volume",
                "number",
                "pages",
                "doi",
                "abstract",
            ]
            if f in record.data
        ]

        for field in fields_to_process:
            if "\\" in record.data[field]:
                record.data[field] = self.__unescape_latex(input_str=record.data[field])
            if "<" in record.data[field]:
                record.data[field] = self.__unescape_html(input_str=record.data[field])

            record.data[field] = (
                record.data[field]
                .replace("\n", " ")
                .rstrip()
                .lstrip()
                .replace("{", "")
                .replace("}", "")
            )
        if record.data.get("title", "UNKNOWN") != "UNKNOWN":
            record.data["title"] = re.sub(r"\s+", " ", record.data["title"]).rstrip(".")

        if "year" in record.data and str(record.data["year"]).endswith(".0"):
            record.data["year"] = str(record.data["year"])[:-2]

        if "pages" in record.data:
            record.data["pages"] = record.data["pages"].replace("–", "--")
            if record.data["pages"].count("-") == 1:
                record.data["pages"] = record.data["pages"].replace("-", "--")
            if record.data["pages"].lower() == "n.pag":
                del record.data["pages"]

    def __import_process_fields(self, *, record: colrev.record.Record) -> None:
        # Consistently set keys to lower case
        lower_keys = [k.lower() for k in list(record.data.keys())]
        for key, n_key in zip(list(record.data.keys()), lower_keys):
            if key not in ["ID", "ENTRYTYPE"]:
                record.data[n_key] = record.data.pop(key)

        self.__import_format_fields(record=record)

        if "number" not in record.data and "issue" in record.data:
            record.data.update(number=record.data["issue"])
            del record.data["issue"]

        if record.data.get("volume", "") == "ahead-of-print":
            del record.data["volume"]
        if record.data.get("number", "") == "ahead-of-print":
            del record.data["number"]

        if "language" in record.data and len(record.data["language"]) != 3:
            self.language_service.unify_to_iso_639_3_language_codes(record=record)

        if "url" in record.data and "login?url=https" in record.data["url"]:
            record.data["url"] = record.data["url"][
                record.data["url"].find("login?url=https") + 10 :
            ]

    def __import_record(self, *, record_dict: dict) -> dict:
        self.review_manager.logger.debug(
            f'import_record {record_dict["ID"]}: '
            # f"\n{self.review_manager.p_printer.pformat(record_dict)}\n\n"
        )

        record = colrev.record.Record(data=record_dict)
        if record.data["colrev_status"] == colrev.record.RecordState.md_retrieved:
            self.__import_process_fields(record=record)

        if "doi" in record.data:
            record.data.update(
                doi=record.data["doi"].replace("http://dx.doi.org/", "").upper()
            )
        self.import_provenance(
            record=record,
        )

        if record.data["colrev_status"] in [
            colrev.record.RecordState.md_retrieved,
            colrev.record.RecordState.md_needs_manual_preparation,
        ]:
            record.set_status(target_state=colrev.record.RecordState.md_imported)

        if record.check_potential_retracts():
            self.review_manager.logger.info(
                f"{colors.GREEN}Found paper retract: "
                f"{record.data['ID']}{colors.END}"
            )

        return record.get_data()

    def __prep_records_for_import(
        self, *, source_settings: colrev.settings.SearchSource, search_records: dict
    ) -> list:
        record_list = []
        origin_prefix = source_settings.get_origin_prefix()
        for record in search_records.values():
            for key in colrev.record.Record.provenance_keys + [
                "screening_criteria",
            ]:
                if key == "colrev_status":
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
                    record.update(
                        colrev_masterdata_provenance={
                            "CURATED": {
                                "source": record["curation_ID"].split("#")[0],
                                "note": "",
                            }
                        }
                    )
            else:
                record.update(colrev_status=colrev.record.RecordState.md_retrieved)

            if "doi" in record:
                formatted_doi = (
                    record["doi"]
                    .lower()
                    .replace("https://", "http://")
                    .replace("dx.doi.org", "doi.org")
                    .replace("http://doi.org/", "")
                    .upper()
                )
                record.update(doi=formatted_doi)

            self.review_manager.logger.debug(
                f'append record {record["ID"]} '
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
            if x["colrev_origin"][0] not in imported_origins
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
            source_record = self.__import_record(record_dict=source_record)

            # Make sure not to replace existing records
            order = 0
            letters = list(string.ascii_lowercase)
            next_unique_id = source_record["ID"]
            appends: list = []
            while next_unique_id in records:
                if len(appends) == 0:
                    order += 1
                    appends = list(itertools.product(letters, repeat=order))
                next_unique_id = source_record["ID"] + "".join(list(appends.pop(0)))
            source_record["ID"] = next_unique_id
            records[source_record["ID"]] = source_record

            self.review_manager.logger.info(
                f" {colors.GREEN}{source_record['ID']}".ljust(46)
                + f"md_retrieved →  {source_record['colrev_status']}{colors.END}"
            )

        self.review_manager.dataset.save_records_dict(records=records)
        self.__validate_load(source=source)

        if keep_ids:
            self.review_manager.logger.warning(
                "Not yet fully implemented. Need to check/resolve ID duplicates."
            )
        else:
            self.review_manager.logger.debug("Set IDs")
            records = self.review_manager.dataset.set_ids(
                records=records,
                selected_ids=[
                    r["ID"] for r in source.search_source.source_records_list
                ],
            )

        self.review_manager.logger.info(
            "New records loaded".ljust(38) + f"{source.search_source.to_import} records"
        )

        self.review_manager.dataset.add_setting_changes()
        self.review_manager.dataset.add_changes(
            path=source.search_source.get_corresponding_bib_file()
        )
        self.review_manager.dataset.add_changes(path=source.search_source.filename)
        self.review_manager.dataset.add_record_changes()
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

    def __load_active_sources(
        self, *, new_sources: typing.List[colrev.settings.SearchSource]
    ) -> list:
        checker = self.review_manager.get_checker()
        checker.check_sources()
        sources_settings = []
        for source in self.review_manager.settings.sources:
            sources_settings.append(source)
        for source in new_sources:
            if source.filename not in [s.filename for s in sources_settings]:
                sources_settings.append(source)
        sources = []
        package_manager = self.review_manager.get_package_manager()
        for source in sources_settings:
            endpoint_dict = package_manager.load_packages(
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
            o["colrev_origin"] for o in source.search_source.source_records_list
        ]
        if source.search_source.to_import - imported > 0:
            self.review_manager.logger.error(
                f"{colors.RED}PROBLEM: delta: "
                f"{source.search_source.to_import - imported} records missing{colors.END}"
            )

            missing_origins = [
                o for o in origins_to_import if o not in imported_origins
            ]
            self.review_manager.logger.error(
                f"{colors.RED}Records not yet imported: {missing_origins}{colors.END}"
            )
        else:
            self.review_manager.logger.error(
                f"{colors.RED}PROBLEM: "
                f"{source.search_source.to_import - imported} records too much{colors.END}"
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
        new_sources: typing.List[colrev.settings.SearchSource],
        keep_ids: bool = False,
    ) -> None:
        """Load records (main entrypoint)"""

        if not self.review_manager.high_level_operation:
            print()

        for source in self.__load_active_sources(new_sources=new_sources):
            try:
                self.review_manager.logger.info(f"Load {source.search_source.filename}")
                self.__add_source_to_settings(source=source)
                self.__load_source_records(source=source, keep_ids=keep_ids)
                self.__create_load_commit(source=source)

            except colrev_exceptions.ImportException as exc:
                print(exc)

        self.review_manager.logger.info(
            f"{colors.GREEN}Completed load operation{colors.END}"
        )
