#! /usr/bin/env python
from __future__ import annotations

import itertools
import re
import string
import typing
from pathlib import Path

import colrev.exceptions as colrev_exceptions
import colrev.ops.search_sources
import colrev.process
import colrev.record
import colrev.settings
import colrev.ui_cli.cli_colors as colors


class Load(colrev.process.Process):

    # Note : PDFs should be stored in the pdfs directory
    # They should be included through the search scripts (not the load scripts)

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation=True,
    ) -> None:

        super().__init__(
            review_manager=review_manager,
            process_type=colrev.process.ProcessType.load,
            notify_state_transition_operation=notify_state_transition_operation,
        )
        self.verbose = True

        package_manager = self.review_manager.get_package_manager()
        self.load_scripts: dict[str, typing.Any] = package_manager.load_packages(
            process=self,
            scripts=[
                s.conversion_script
                for s in review_manager.settings.sources
                if "endpoint" in s.conversion_script
            ],
        )

        self.all_available_packages_names = package_manager.discover_packages(
            script_type=str(self.type), installed_only=True
        )

        all_available_packages: dict[str, typing.Any] = package_manager.load_packages(
            process=self,
            scripts=[{"endpoint": p} for p in self.all_available_packages_names],
        )

        self.supported_extensions = [
            item
            for sublist in [
                e.supported_extensions for e in all_available_packages.values()
            ]
            for item in sublist
        ]

        self.search_sources = colrev.ops.search_sources.SearchSources(
            review_manager=self.review_manager
        )

    def get_new_search_files(self) -> list[Path]:
        """ "Retrieve new search files (not yet registered in settings)"""

        if not self.review_manager.search_dir.is_dir():
            return []

        # Only supported filetypes
        files = [
            f.relative_to(self.review_manager.path)
            for f_ in [
                self.review_manager.search_dir.glob(f"**/*.{e}")
                for e in self.supported_extensions
            ]
            for f in f_
        ]

        # Only files that are not yet registered
        # (also exclude bib files corresponding to a registered file)
        files = [
            f
            for f in files
            # if str(f.with_suffix(".bib").name)
            if str(f.with_suffix(".bib"))
            not in [
                str(s.filename.with_suffix(".bib"))
                for s in self.review_manager.settings.sources
            ]
        ]

        return sorted(list(set(files)))

    def check_update_sources(self) -> None:
        # pylint: disable=redefined-outer-name

        sources = self.review_manager.settings.sources

        for sfp in self.get_new_search_files():
            # Note : for non-bib files, we check sources for corresponding bib file
            # (which will be created later in the process)

            sfp_name = sfp
            if sfp_name not in [str(source.filename) for source in sources]:

                print(f"Please provide details for {sfp_name}")

                # Assuming that all other search types are added by query
                # search_type_input = "NA"
                # while search_type_input not in SearchType._member_names_:
                #     print(f"Search type options: {SearchType._member_names_}")
                #     cmd = "Enter search type".ljust(40, " ") + ": "
                #     search_type_input = input(cmd)

                heuristic_result_list = self.apply_source_heuristics(filepath=sfp)

                if 1 == len(heuristic_result_list):
                    heuristic_source = heuristic_result_list[0]
                else:
                    print("\nSelect search source:")
                    for i, heuristic_source in enumerate(heuristic_result_list):
                        print(f"{i+1} {heuristic_source}")

                    while True:
                        selection = input("select nr")
                        if not selection.isdigit():
                            continue
                        if int(selection) in range(0, len(heuristic_result_list)):
                            heuristic_source = heuristic_result_list[int(selection) - 1]
                            break

                # source_name, source_identifier, source_prep_scripts = heuristic_result
                if "NA" == heuristic_source.source_name:
                    if heuristic_source.search_type == "DB":
                        print("   Sources with pre-defined settings:")
                        cl_scripts = "\n    - ".join(
                            self.search_sources.all_available_packages_names
                        )
                        print("    - " + cl_scripts)
                        print("   See colrev/custom_source_load.py for details")

                    while heuristic_source.source_name in ["", "NA"]:
                        cmd = (
                            "Enter source name (e.g., a url or a description)".ljust(
                                40, " "
                            )
                            + ": "
                        )
                        heuristic_source.source_name = input(cmd)

                    while heuristic_source.source_identifier in ["", "NA"]:
                        cmd = (
                            "Enter source identifier "
                            + "(e.g., {{url}} or a description)".ljust(40, " ")
                            + ": "
                        )
                        heuristic_source.source_identifier = input(cmd)

                    cmd = "Enter source_prep_scripts or NA".ljust(40, " ") + ": "
                    prep_script_selection = input(cmd)
                    if prep_script_selection in ["", "NA"]:
                        heuristic_source.source_prep_scripts = []
                    else:
                        heuristic_source.source_prep_scripts = [
                            {"endpoint": str(prep_script_selection)}
                        ]
                else:
                    print(
                        "Source name".ljust(40, " ")
                        + f": {heuristic_source.source_name}"
                    )
                    print(
                        "Source identifier".ljust(40, " ")
                        + f": {heuristic_source.source_identifier}"
                    )
                    print(
                        "Source prep scripts".ljust(40, " ")
                        + f": {heuristic_source.source_prep_scripts}"
                    )

                cmd = "Enter search_parameters".ljust(40, " ") + ": "
                search_parameters = input(cmd)
                heuristic_source.search_parameters = search_parameters

                cmd = "Enter a comment (or NA)".ljust(40, " ") + ": "
                comment_input = input(cmd)
                if comment_input != "":
                    comment = comment_input
                else:
                    comment = None  # type: ignore
                heuristic_source.comment = comment

                if {} == heuristic_source.conversion_script:
                    custom_load_script = input(
                        "provide custom conversion_script [or NA]:"
                    )
                    if "NA" == custom_load_script:
                        heuristic_source.conversion_script = {}
                    else:
                        heuristic_source.conversion_script = {
                            "endpoint": custom_load_script
                        }
                    # TODO : check if custom_load_script is available?

                sources.append(heuristic_source)
                self.review_manager.save_settings()
                self.review_manager.logger.info(
                    f"{colors.GREEN}Added new source: "
                    f"{heuristic_source.source_name}{colors.END}"
                )
                print("\n")

    def check_bib_file(
        self, *, source: colrev.settings.SearchSource, records: dict
    ) -> None:
        if not any("author" in r for ID, r in records.items()):
            raise colrev_exceptions.ImportException(
                f"Import failed (no record with author field): {source.filename.name}"
            )

        if not any("title" in r for ID, r in records.items()):
            raise colrev_exceptions.ImportException(
                f"Import failed (no record with title field): {source.filename.name}"
            )

    def resolve_non_unique_ids(self, *, source: colrev.settings.SearchSource) -> None:
        def get_unique_id(*, non_unique_id: str, id_list: list[str]) -> str:

            order = 0
            letters = list(string.ascii_lowercase)
            temp_id = non_unique_id
            next_unique_id = temp_id
            appends: list = []
            while next_unique_id in id_list:
                if len(appends) == 0:
                    order += 1
                    appends = list(itertools.product(letters, repeat=order))
                next_unique_id = temp_id + "".join(list(appends.pop(0)))

            return next_unique_id

        def inplace_change_second(
            *, filename: Path, old_string: str, new_string: str
        ) -> None:
            new_file_lines = []
            with open(filename, encoding="utf8") as file:
                first_read = False
                replaced = False
                for line in file.readlines():
                    if old_string in line and not first_read:
                        first_read = True
                    if old_string in line and first_read and not replaced:
                        line = line.replace(old_string, new_string)
                        replaced = True
                    new_file_lines.append(line)

                # s = f.read()
                # if old_string not in s:
                #     return
            with open(filename, "w", encoding="utf8") as file:
                for new_file_line in new_file_lines:
                    file.write(new_file_line)

        if not source.get_corresponding_bib_file().is_file():
            return

        with open(source.get_corresponding_bib_file(), encoding="utf8") as bibtex_file:
            cr_dict = self.review_manager.dataset.load_records_dict(
                load_str=bibtex_file.read()
            )

        ids_to_update = []
        current_ids = list(cr_dict.keys())
        for record in cr_dict.values():
            if len([x for x in current_ids if x == record["ID"]]) > 1:
                new_id = get_unique_id(non_unique_id=record["ID"], id_list=current_ids)
                ids_to_update.append([record["ID"], new_id])
                current_ids.append(new_id)

        if len(ids_to_update) > 0:
            self.review_manager.dataset.add_changes(
                path=source.get_corresponding_bib_file()
            )
            self.review_manager.create_commit(
                msg=f"Save original search file: {source.get_corresponding_bib_file().name}",
                script_call="colrev load",
            )

            for old_id, new_id in ids_to_update:
                self.review_manager.logger.info(
                    f"Resolve ID to ensure unique colrev_origins: {old_id} -> {new_id}"
                )
                self.review_manager.report_logger.info(
                    f"Resolve ID to ensure unique colrev_origins: {old_id} -> {new_id}"
                )
                inplace_change_second(
                    filename=source.get_corresponding_bib_file(),
                    old_string=f"{old_id},",
                    new_string=f"{new_id},",
                )
            self.review_manager.dataset.add_changes(
                path=source.get_corresponding_bib_file()
            )
            self.review_manager.create_commit(
                msg=f"Resolve non-unique IDs in {source.get_corresponding_bib_file().name}"
            )

    def load_source_records(
        self, *, source: colrev.settings.SearchSource, keep_ids: bool
    ) -> None:
        def getbib(*, file: Path) -> list[dict]:
            with open(file, encoding="utf8") as bibtex_file:
                contents = bibtex_file.read()
                bib_r = re.compile(r"@.*{.*,", re.M)
                if len(re.findall(bib_r, contents)) == 0:
                    self.review_manager.logger.error(f"Not a bib file? {file.name}")
                if "Early Access Date" in contents:
                    raise colrev_exceptions.BibFileFormatError(
                        "Replace Early Access Date in bibfile before loading! "
                        f"{file.name}"
                    )
            with open(file, encoding="utf8") as bibtex_file:
                search_records_dict = self.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )
            return list(search_records_dict.values())

        def import_record(*, record_dict: dict) -> dict:
            self.review_manager.logger.debug(
                f'import_record {record_dict["ID"]}: '
                f"\n{self.review_manager.p_printer.pformat(record_dict)}\n\n"
            )
            if colrev.record.RecordState.md_retrieved != record_dict["colrev_status"]:
                return record_dict

            # Consistently set keys to lower case
            lower_keys = [k.lower() for k in list(record_dict.keys())]
            for key, n_key in zip(list(record_dict.keys()), lower_keys):
                if key in ["ID", "ENTRYTYPE"]:
                    continue
                record_dict[n_key] = record_dict.pop(key)

            # pylint: disable=duplicate-code
            # For better readability of the git diff:
            fields_to_process = [
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
            for field in fields_to_process:
                if field in record_dict:
                    record_dict[field] = (
                        record_dict[field]
                        .replace("\n", " ")
                        .rstrip()
                        .lstrip()
                        .replace("{", "")
                        .replace("}", "")
                    )
            if "pages" in record_dict:
                record_dict["pages"] = record_dict["pages"].replace("–", "--")
                if record_dict["pages"].count("-") == 1:
                    record_dict["pages"] = record_dict["pages"].replace("-", "--")

            if "number" not in record_dict and "issue" in record_dict:
                record_dict.update(number=record_dict["issue"])
                del record_dict["issue"]

            record = colrev.record.Record(data=record_dict)
            if "doi" in record.data:
                record.data.update(
                    doi=record.data["doi"].replace("http://dx.doi.org/", "").upper()
                )

            record.import_provenance(source_identifier=source.source_identifier)
            record.set_status(target_state=colrev.record.RecordState.md_imported)

            return record.get_data()

        search_records = []
        if source.get_corresponding_bib_file().is_file():
            search_records = getbib(file=source.get_corresponding_bib_file())
            self.review_manager.logger.debug(
                f"Loaded {source.get_corresponding_bib_file().name} "
                f"with {len(search_records)} records"
            )

        if len(search_records) == 0:
            # source.to_import = 0
            # source.source_records_list = list()
            self.review_manager.logger.info(
                f"{colors.GREEN}No records to load{colors.END}"
            )
            print()

            return

        nr_in_bib = self.review_manager.dataset.get_nr_in_bib(
            file_path=source.get_corresponding_bib_file()
        )
        if len(search_records) < nr_in_bib:
            self.review_manager.logger.error(
                "broken bib file (not imported all records)"
            )
            with open(source.get_corresponding_bib_file(), encoding="utf8") as file:
                line = file.readline()
                while line:
                    if "@" in line[:3]:
                        record_id = line[line.find("{") + 1 : line.rfind(",")]
                        if record_id not in [x["ID"] for x in search_records]:
                            self.review_manager.logger.error(
                                f"{record_id} not imported"
                            )
                    line = file.readline()

        record_list = []
        for record in search_records:
            record.update(
                colrev_origin=f"{source.get_corresponding_bib_file().name}/{record['ID']}"
            )

            # Drop empty fields
            record = {k: v for k, v in record.items() if v}

            post_md_processed_states = colrev.record.RecordState.get_post_x_states(
                state=colrev.record.RecordState.md_processed
            )

            if str(record.get("colrev_status", "")) in post_md_processed_states:
                # Note : when importing a record, it always needs to be
                # deduplicated against the other records in the repository
                record.update(colrev_status=colrev.record.RecordState.md_prepared)
            else:
                record.update(colrev_status=colrev.record.RecordState.md_retrieved)

            if "doi" in record:
                record.update(
                    doi=record["doi"].replace("http://dx.doi.org/", "").upper()
                )
                # https://www.crossref.org/blog/dois-and-matching-regular-expressions/
                doi_match = re.match(r"^10.\d{4,9}\/", record["doi"])
                if not doi_match:
                    del record["doi"]

            self.review_manager.logger.debug(
                f'append record {record["ID"]} '
                f"\n{self.review_manager.p_printer.pformat(record)}\n\n"
            )
            record_list.append(record)

        imported_origins = (
            self.review_manager.dataset.get_currently_imported_origin_list()
        )
        record_list = [
            x for x in record_list if x["colrev_origin"] not in imported_origins
        ]
        source.setup_for_load(
            record_list=record_list, imported_origins=imported_origins
        )

        records = self.review_manager.dataset.load_records_dict()
        for source_record in source.source_records_list:
            source_record = import_record(record_dict=source_record)

            # Make sure IDs are unique / do not replace existing records
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

        self.review_manager.dataset.save_records_dict(records=records)

        self.review_manager.logger.info(
            f"Records loaded: {colors.GREEN}{source.to_import}{colors.END}"
        )

        if keep_ids:
            print("Not yet fully implemented. Need to check/resolve ID duplicates.")
        else:
            self.review_manager.logger.info("Set IDs")
            records = self.review_manager.dataset.set_ids(
                records=records,
                selected_ids=[r["ID"] for r in source.source_records_list],
            )

        self.review_manager.dataset.add_setting_changes()
        self.review_manager.dataset.add_changes(
            path=source.get_corresponding_bib_file()
        )
        self.review_manager.dataset.add_changes(path=source.filename)
        self.review_manager.dataset.add_record_changes()

    def validate_load(self, *, source: colrev.settings.SearchSource) -> None:

        imported_origins = (
            self.review_manager.dataset.get_currently_imported_origin_list()
        )
        len_after = len(imported_origins)
        imported = len_after - source.len_before

        if imported != source.to_import:
            self.review_manager.logger.error(f"len_before: {source.len_before}")
            self.review_manager.logger.error(f"len_after: {len_after}")

            origins_to_import = [o["colrev_origin"] for o in source.source_records_list]
            if source.to_import - imported > 0:
                self.review_manager.logger.error(
                    f"PROBLEM: delta: {source.to_import - imported} records missing"
                )

                missing_origins = [
                    o for o in origins_to_import if o not in imported_origins
                ]
                self.review_manager.logger.error(
                    f"Records not yet imported: {missing_origins}"
                )
            else:
                self.review_manager.logger.error(
                    f"PROBLEM: {source.to_import - imported} records too much"
                )

    def save_records(self, *, records: dict, corresponding_bib_file: Path) -> None:
        """Convenience function for the load script implementations"""

        def fix_keys(*, records: dict) -> dict:
            for record in records.values():
                record = {
                    re.sub("[0-9a-zA-Z_]+", "1", k.replace(" ", "_")): v
                    for k, v in record.items()
                }
            return records

        def set_incremental_ids(*, records: dict) -> dict:
            # if IDs to set for some records
            if 0 != len([r for r in records if "ID" not in r]):
                i = 1
                for record in records.values():
                    if "ID" not in record:
                        if "UT_(Unique_WOS_ID)" in record:
                            record["ID"] = record["UT_(Unique_WOS_ID)"].replace(
                                ":", "_"
                            )
                        else:
                            record["ID"] = f"{i+1}".rjust(10, "0")
                        i += 1
            return records

        def drop_empty_fields(*, records: dict) -> dict:

            records_list = list(records.values())
            records_list = [
                {k: v for k, v in record.items() if v is not None}
                for record in records_list
            ]
            records_list = [
                {k: v for k, v in record.items() if v != "nan"}
                for record in records_list
            ]

            return {r["ID"]: r for r in records_list}

        records = fix_keys(records=records)
        records = set_incremental_ids(records=records)
        records = drop_empty_fields(records=records)

        if len(records) == 0:
            self.review_manager.report_logger.error("No records loaded")
            self.review_manager.logger.error("No records loaded")

        if not corresponding_bib_file.is_file():
            self.review_manager.dataset.save_records_dict_to_file(
                records=records, save_path=corresponding_bib_file
            )

    def apply_source_heuristics(
        self, *, filepath: Path
    ) -> list[colrev.settings.SearchSource]:
        """Apply heuristics to identify source"""

        def get_conversion_script(*, filepath: Path) -> dict:

            filetype = filepath.suffix.replace(".", "")

            for (
                endpoint_name,
                endpoint_dict,
            ) in self.all_available_packages_names.items():
                if filetype in endpoint_dict["endpoint"].supported_extensions:
                    return {"endpoint": endpoint_name}

            raise colrev_exceptions.UnsupportedImportFormatError(filepath)

        data = ""
        try:
            data = filepath.read_text()
        except UnicodeDecodeError:
            pass

        results_list = []

        for (
            source_name,
            endpoint,
        ) in self.search_sources.all_available_packages_names.items():
            # pylint: disable=no-member
            has_heuristic = getattr(endpoint, "heuristic", None)
            if not has_heuristic:
                continue
            res = endpoint.heuristic(filepath, data)  # type: ignore
            if res["confidence"] > 0:
                search_type = colrev.settings.SearchType("DB")

                res["source_name"] = source_name
                res["source_prep_scripts"] = (
                    [source_name] if callable(endpoint.prepare) else []  # type: ignore
                )
                if "search_script" not in res:
                    res["search_script"] = {}

                if "filename" not in res:
                    # Correct the file extension if necessary
                    if re.search("%0", data) and filepath.suffix not in [".enl"]:
                        new_filename = filepath.with_suffix(".enl")
                        print(
                            f"{colors.GREEN}Renaming to {new_filename} "
                            f"(because the format is .enl){colors.END}"
                        )
                        filepath.rename(new_filename)
                        filepath = new_filename

                if "conversion_script" not in res:
                    res["conversion_script"] = get_conversion_script(filepath=filepath)

                source_candidate = colrev.settings.SearchSource(
                    filename=filepath,
                    search_type=search_type,
                    source_name=source_name,
                    source_identifier=res["source_identifier"],
                    search_parameters="",
                    search_script=res["search_script"],
                    conversion_script=res["conversion_script"],
                    source_prep_scripts=[
                        {"endpoint": s}
                        for s in res["source_prep_scripts"]  # type: ignore
                    ],
                    comment="",
                )

                results_list.append(source_candidate)

        if 0 == len(results_list):
            source_candidate = colrev.settings.SearchSource(
                filename=Path(filepath),
                search_type=colrev.settings.SearchType("DB"),
                source_name="NA",
                source_identifier="NA",
                search_parameters="NA",
                search_script={},  # Note : primarily adding files (not feeds)
                conversion_script={"endpoint": "bibtex"},
                source_prep_scripts=[],
                comment="",
            )
            results_list.append(source_candidate)

        return results_list

    def main(self, *, keep_ids: bool = False, combine_commits=False) -> None:

        saved_args = locals()
        if not keep_ids:
            # TODO : keep_ids as a potential parameter for the source/settings?
            del saved_args["keep_ids"]

        def load_active_sources() -> list:
            self.review_manager.dataset.check_sources()
            sources = []
            for source in self.review_manager.settings.sources:
                if source.conversion_script["endpoint"] not in self.load_scripts:
                    if self.verbose:
                        print(
                            f"Error: endpoint not available: {source.conversion_script}"
                        )
                    continue
                sources.append(source)
            return sources

        for source in load_active_sources():
            self.review_manager.logger.info(f"Loading {source}")
            saved_args["file"] = source.filename.name

            conversion_script_name = source.conversion_script["endpoint"]

            # 1. convert to bib (if necessary)
            endpoint = self.load_scripts[conversion_script_name]
            endpoint.load(self, source)

            # 2. resolve non-unique IDs (if any)
            self.resolve_non_unique_ids(source=source)

            # 3. load and add records to records.bib
            self.load_source_records(source=source, keep_ids=keep_ids)
            if 0 == source.to_import:
                continue

            # 4. validate load
            self.validate_load(source=source)

            if not combine_commits:
                self.review_manager.create_commit(
                    msg=f"Load {saved_args['file']}",
                    script_call="colrev load",
                    saved_args=saved_args,
                )

            print("\n")

        if combine_commits and self.review_manager.dataset.has_changes():
            self.review_manager.create_commit(
                msg="Load (multiple)", script_call="colrev load", saved_args=saved_args
            )


if __name__ == "__main__":
    pass
