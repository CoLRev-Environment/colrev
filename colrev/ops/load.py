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

# pylint: disable=too-many-lines


class Load(colrev.operation.Operation):
    """Load the records"""

    # Note : PDFs should be stored in the pdfs directory
    # They should be included through colrev search

    supported_extensions: typing.List[str]

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

        if not self.review_manager.search_dir.is_dir():
            return []

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

    def __apply_source_heuristics(
        self,
        *,
        filepath: Path,
        search_sources: dict,
        load_conversion: dict,
    ) -> list[typing.Dict]:
        """Apply heuristics to identify source"""

        # pylint: disable=too-many-statements

        def get_load_conversion_package_endpoint(*, filepath: Path) -> dict:
            filetype = filepath.suffix.replace(".", "")

            for (
                package_identifier,
                selected_package,
            ) in load_conversion.items():
                if filetype in selected_package.supported_extensions:  # type: ignore
                    return {"endpoint": package_identifier}

            raise colrev_exceptions.UnsupportedImportFormatError(filepath)

        data = ""
        try:
            data = filepath.read_text()
        except UnicodeDecodeError:
            pass

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
            try:
                if res["confidence"] > 0:
                    result_item = {}

                    res["endpoint"] = endpoint

                    search_type = endpoint_class.search_type
                    # Note : as the identifier, we use the filename
                    # (if search results are added by file/not via the API)

                    # Correct the file extension if necessary
                    if re.findall(
                        r"^%0", data, re.MULTILINE
                    ) and filepath.suffix not in [".enl"]:
                        new_filename = filepath.with_suffix(".enl")
                        self.review_manager.logger.info(
                            f"{colors.GREEN}Rename to {new_filename} "
                            f"(because the format is .enl){colors.END}"
                        )
                        filepath.rename(new_filename)
                        self.review_manager.dataset.add_changes(
                            path=filepath, remove=True
                        )
                        filepath = new_filename
                        res["filename"] = filepath
                        self.review_manager.dataset.add_changes(path=new_filename)
                        self.review_manager.create_commit(msg=f"Rename {filepath}")

                    if re.findall(
                        r"^TI ", data, re.MULTILINE
                    ) and filepath.suffix not in [".ris"]:
                        new_filename = filepath.with_suffix(".ris")
                        self.review_manager.logger.info(
                            f"{colors.GREEN}Rename to {new_filename} "
                            f"(because the format is .ris){colors.END}"
                        )
                        filepath.rename(new_filename)
                        self.review_manager.dataset.add_changes(
                            path=filepath, remove=True
                        )
                        filepath = new_filename
                        res["filename"] = filepath
                        self.review_manager.dataset.add_changes(path=new_filename)
                        self.review_manager.create_commit(msg=f"Rename {filepath}")

                    if "load_conversion_package_endpoint" not in res:
                        res[
                            "load_conversion_package_endpoint"
                        ] = get_load_conversion_package_endpoint(filepath=filepath)

                    source_candidate = colrev.settings.SearchSource(
                        endpoint=endpoint,
                        filename=filepath,
                        search_type=search_type,
                        search_parameters={},
                        load_conversion_package_endpoint=res[
                            "load_conversion_package_endpoint"
                        ],
                        comment="",
                    )

                    result_item["source_candidate"] = source_candidate
                    result_item["confidence"] = res["confidence"]

                    results_list.append(result_item)
            except colrev_exceptions.UnsupportedImportFormatError:
                continue

        # Reduce the results_list when there are results with very high confidence
        if [r for r in results_list if r["confidence"] > 0.95]:
            results_list = [r for r in results_list if r["confidence"] > 0.8]

        if (
            0 == len(results_list)
            or len([r for r in results_list if r["confidence"] > 0.5]) == 0
        ):
            source_candidate = colrev.settings.SearchSource(
                endpoint="colrev.unknown_source",
                filename=Path(filepath),
                search_type=colrev.settings.SearchType("DB"),
                search_parameters={},
                load_conversion_package_endpoint=get_load_conversion_package_endpoint(
                    filepath=filepath
                ),
                comment="",
            )
            results_list.append(
                {
                    "source_candidate": source_candidate,
                    "confidence": 0.1,  # type: ignore
                }
            )

        return results_list

    def get_new_sources(
        self, *, skip_query: bool = False
    ) -> typing.List[colrev.settings.SearchSource]:
        """Get new SearchSources"""

        # pylint: disable=redefined-outer-name
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-statements
        # pylint: disable=too-many-locals

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

        self.review_manager.logger.debug("Load available load_conversion endpoints...")
        load_conversion_package_identifiers = self.package_manager.discover_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.load_conversion,
            installed_only=True,
        )

        load_conversion_packages = self.package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.load_conversion,
            selected_packages=[
                {"endpoint": p} for p in load_conversion_package_identifiers
            ],
            operation=self,
        )

        self.supported_extensions = [
            item
            for sublist in [
                e.supported_extensions  # type: ignore
                for _, e in load_conversion_packages.items()
            ]
            for item in sublist
        ]

        new_sources = []
        for sfp in new_search_files:
            sfp_name = sfp
            if sfp_name in [
                str(source.filename) for source in self.review_manager.settings.sources
            ]:
                continue

            if not self.review_manager.high_level_operation:
                print()
            self.review_manager.logger.info(f"Discover new source: {sfp_name}")

            # Assuming that all other search types are added by query
            # search_type_input = "NA"
            # while search_type_input not in SearchType.get_options():
            #     print(f"Search type options: {SearchType.get_options()}")
            #     cmd = "Enter search type".ljust(25, " ") + ": "
            #     search_type_input = input(cmd)

            heuristic_result_list = self.__apply_source_heuristics(
                filepath=sfp,
                search_sources=search_sources,
                load_conversion=load_conversion_packages,
            )

            if 1 == len(heuristic_result_list):
                heuristic_source = heuristic_result_list[0]
            else:
                if not skip_query:
                    print(f"{colors.ORANGE}Select search source{colors.END}:")
                    for i, heuristic_source in enumerate(heuristic_result_list):
                        highlight_color = ""
                        if heuristic_source["confidence"] >= 0.7:
                            highlight_color = colors.GREEN
                        elif heuristic_source["confidence"] >= 0.5:
                            highlight_color = colors.ORANGE
                        print(
                            f"{highlight_color}{i+1} "
                            f"(confidence: {round(heuristic_source['confidence'], 2)}):"
                            f" {heuristic_source['source_candidate'].endpoint}{colors.END}"
                        )

                while True:
                    if skip_query:
                        # Use the last / unknown_source
                        selection = str(len(heuristic_result_list))
                    else:
                        selection = input("select nr")
                    if not selection.isdigit():
                        continue
                    if int(selection) in range(1, len(heuristic_result_list) + 1):
                        heuristic_source = heuristic_result_list[int(selection) - 1]
                        break

            if heuristic_source["source_candidate"].endpoint == "colrev.unknown_source":
                cmd = "Enter the search query (or NA)".ljust(25, " ") + ": "
                query_input = ""
                if not skip_query:
                    query_input = input(cmd)
                if query_input not in ["", "NA"]:
                    heuristic_source["source_candidate"].search_parameters = {
                        "query": query_input
                    }
                else:
                    heuristic_source["source_candidate"].search_parameters = {}

            self.review_manager.logger.info(
                f"Source name: {heuristic_source['source_candidate'].endpoint}"
            )

            heuristic_source["source_candidate"].comment = None

            if (
                {}
                == heuristic_source["source_candidate"].load_conversion_package_endpoint
            ):
                custom_load_conversion_package_endpoint = input(
                    "provide custom load_conversion_package_endpoint [or NA]:"
                )
                if custom_load_conversion_package_endpoint == "NA":
                    heuristic_source[
                        "source_candidate"
                    ].load_conversion_package_endpoint = {}
                else:
                    heuristic_source[
                        "source_candidate"
                    ].load_conversion_package_endpoint = {
                        "endpoint": custom_load_conversion_package_endpoint
                    }

            new_sources.append(heuristic_source["source_candidate"])

        return new_sources

    def __check_bib_file(
        self, *, source: colrev.settings.SearchSource, records: dict
    ) -> None:
        if len(records.items()) <= 3:
            return
        if not any("author" in r for ID, r in records.items()):
            raise colrev_exceptions.ImportException(
                f"Import failed (no record with author field): {source.filename.name}"
            )

        if not any("title" in r for ID, r in records.items()):
            raise colrev_exceptions.ImportException(
                f"Import failed (no record with title field): {source.filename.name}"
            )

    def __resolve_non_unique_ids(self, *, source: colrev.settings.SearchSource) -> None:
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

    def __getbib(self, *, file: Path) -> list[dict]:
        with open(file, encoding="utf8") as bibtex_file:
            contents = bibtex_file.read()
            bib_r = re.compile(r"@.*{.*,", re.M)
            if len(re.findall(bib_r, contents)) == 0:
                self.review_manager.logger.error(f"Not a bib file? {file.name}")

        with open(file, encoding="utf8") as bibtex_file:
            search_records_dict = self.review_manager.dataset.load_records_dict(
                load_str=bibtex_file.read()
            )
        return list(search_records_dict.values())

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

            for key in record.data.keys():
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

        def set_initial_non_curated_import_provenance(
            *, record: colrev.record.Record
        ) -> None:
            masterdata_restrictions = (
                self.review_manager.dataset.get_applicable_restrictions(
                    record_dict=record.get_data()
                )
            )
            if masterdata_restrictions:
                record.update_masterdata_provenance(
                    masterdata_restrictions=masterdata_restrictions
                )
            else:
                record.apply_fields_keys_requirements()

            if (
                record.data["ENTRYTYPE"]
                in colrev.record.Record.record_field_inconsistencies
            ):
                inconsistent_fields = colrev.record.Record.record_field_inconsistencies[
                    record.data["ENTRYTYPE"]
                ]
                for inconsistent_field in inconsistent_fields:
                    if inconsistent_field in record.data:
                        inconsistency_note = (
                            f"inconsistent with entrytype ({record.data['ENTRYTYPE']})"
                        )
                        record.add_masterdata_provenance_note(
                            key=inconsistent_field, note=inconsistency_note
                        )

            incomplete_fields = record.get_incomplete_fields()
            for incomplete_field in incomplete_fields:
                record.add_masterdata_provenance_note(
                    key=incomplete_field, note="incomplete"
                )

            defect_fields = record.get_quality_defects()
            if defect_fields:
                for defect_field in defect_fields:
                    record.add_masterdata_provenance_note(
                        key=defect_field, note="quality_defect"
                    )

        if not record.masterdata_is_curated():
            set_initial_import_provenance(record=record)
            set_initial_non_curated_import_provenance(record=record)

    def __import_format_fields(self, *, record: colrev.record.Record) -> None:
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
            if field in record.data:
                if "\\" in record.data[field]:
                    record.data[field] = self.__unescape_latex(
                        input_str=record.data[field]
                    )

                if "<" in record.data[field]:
                    record.data[field] = self.__unescape_html(
                        input_str=record.data[field]
                    )

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

        if "year" in record.data:
            if str(record.data["year"]).endswith(".0"):
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

        if "language" in record.data:
            if len(record.data["language"]) != 3:
                self.language_service.unify_to_iso_639_3_language_codes(record=record)

        if "url" in record.data:
            if "login?url=https" in record.data["url"]:
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
        record.set_status(target_state=colrev.record.RecordState.md_imported)

        if record.check_potential_retracts():
            self.review_manager.logger.info(
                f"{colors.GREEN}Found paper retract: "
                f"{record.data['ID']}{colors.END}"
            )

        return record.get_data()

    def __prep_records_for_import(
        self, *, source: colrev.settings.SearchSource, search_records: list
    ) -> list:
        record_list = []
        origin_prefix = source.get_origin_prefix()
        for record in search_records:
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

            post_md_prepared_states = colrev.record.RecordState.get_post_x_states(
                state=colrev.record.RecordState.md_prepared
            )

            if record.get("colrev_status", "") in post_md_prepared_states:
                # Note : when importing a record, it always needs to be
                # deduplicated against the other records in the repository
                record.update(colrev_status=colrev.record.RecordState.md_prepared)
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
                # https://www.crossref.org/blog/dois-and-matching-regular-expressions/
                doi_match = re.match(r"^10.\d{4,9}\/", record["doi"])
                if not doi_match:
                    self.review_manager.logger.info(
                        f"remove doi (not matching regex): {record['doi']}"
                    )
                    del record["doi"]

            self.review_manager.logger.debug(
                f'append record {record["ID"]} '
                # f"\n{self.review_manager.p_printer.pformat(record)}\n\n"
            )
            record_list.append(record)
        return record_list

    def __get_search_records(self, *, source: colrev.settings.SearchSource) -> list:
        search_records = []
        if source.get_corresponding_bib_file().is_file():
            search_records = self.__getbib(file=source.get_corresponding_bib_file())
            self.review_manager.logger.debug(
                f"Loaded {source.get_corresponding_bib_file().name} "
                f"with {len(search_records)} records"
            )
        else:
            self.review_manager.logger.error(
                f"Did not find bib file {source.get_corresponding_bib_file().name} "
            )
            return []

        if len(search_records) == 0:
            self.review_manager.logger.info(
                f"{colors.GREEN}No records to load{colors.END}"
            )
            return search_records

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
        return search_records

    def __load_source_records(
        self, *, source: colrev.settings.SearchSource, keep_ids: bool
    ) -> None:
        search_records = self.__get_search_records(source=source)

        record_list = self.__prep_records_for_import(
            source=source, search_records=search_records
        )

        imported_origins = self.__get_currently_imported_origin_list()
        record_list = [
            x for x in record_list if x["colrev_origin"][0] not in imported_origins
        ]
        source.setup_for_load(
            record_list=record_list, imported_origins=imported_origins
        )
        if len(search_records) == 0:
            return

        records = self.review_manager.dataset.load_records_dict()
        for source_record in source.source_records_list:
            source_record = self.__import_record(record_dict=source_record)

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

            self.review_manager.logger.info(
                f" {colors.GREEN}{source_record['ID']}".ljust(46)
                + f"md_retrieved →  md_imported{colors.END}"
            )

        self.__check_bib_file(source=source, records=records)
        self.review_manager.dataset.save_records_dict(records=records)

        if keep_ids:
            self.review_manager.logger.warning(
                "Not yet fully implemented. Need to check/resolve ID duplicates."
            )
        else:
            self.review_manager.logger.debug("Set IDs")
            records = self.review_manager.dataset.set_ids(
                records=records,
                selected_ids=[r["ID"] for r in source.source_records_list],
            )

        self.review_manager.logger.info(
            "New records loaded".ljust(38) + f"{source.to_import} records"
        )

        self.review_manager.dataset.add_setting_changes()
        self.review_manager.dataset.add_changes(
            path=source.get_corresponding_bib_file()
        )
        self.review_manager.dataset.add_changes(path=source.filename)
        self.review_manager.dataset.add_record_changes()

    def __validate_load(self, *, source: colrev.settings.SearchSource) -> None:
        imported_origins = self.__get_currently_imported_origin_list()
        imported = len(imported_origins) - source.len_before

        if imported != source.to_import:
            # Note : for diagnostics, it is easier if we complete the process
            # and create the commit (instead of raising an exception)
            self.review_manager.logger.error(f"len_before: {source.len_before}")
            self.review_manager.logger.error(f"len_after: {len(imported_origins)}")

            origins_to_import = [o["colrev_origin"] for o in source.source_records_list]
            if source.to_import - imported > 0:
                self.review_manager.logger.error(
                    f"{colors.RED}PROBLEM: delta: "
                    f"{source.to_import - imported} records missing{colors.END}"
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
                    f"{source.to_import - imported} records too much{colors.END}"
                )

    def __save_records(self, *, records: dict, corresponding_bib_file: Path) -> None:
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
            for record_id in records:
                records[record_id] = {
                    k: v for k, v in records[record_id].items() if v is not None
                }
                records[record_id] = {
                    k: v for k, v in records[record_id].items() if v != "nan"
                }
            return records

        def drop_fields(*, records: dict) -> dict:
            for record_id in records:
                records[record_id] = {
                    k: v
                    for k, v in records[record_id].items()
                    if k not in ["colrev_status", "colrev_masterdata_provenance"]
                }
            return records

        if len(records) == 0:
            self.review_manager.report_logger.debug("No records loaded")
            self.review_manager.logger.debug("No records loaded")
            return

        records = fix_keys(records=records)
        records = set_incremental_ids(records=records)
        records = drop_empty_fields(records=records)
        records = drop_fields(records=records)

        self.review_manager.dataset.save_records_dict_to_file(
            records=records, save_path=corresponding_bib_file
        )

    def __load_active_sources(
        self, *, new_sources: typing.List[colrev.settings.SearchSource]
    ) -> list:
        checker = self.review_manager.get_checker()
        checker.check_sources()
        sources = []
        for source in self.review_manager.settings.sources:
            sources.append(source)
        for source in new_sources:
            if source.filename not in [s.filename for s in sources]:
                sources.append(source)
        return sources

    def main(
        self,
        *,
        new_sources: typing.List[colrev.settings.SearchSource],
        keep_ids: bool = False,
        combine_commits: bool = False,
    ) -> None:
        """Load records (main entrypoint)"""

        if not self.review_manager.high_level_operation:
            print()
        git_repo = self.review_manager.dataset.get_repo()
        part_exact_call = self.review_manager.exact_call
        for source in self.__load_active_sources(new_sources=new_sources):
            try:
                self.review_manager.logger.info(f"Load {source.filename}")

                # Add to settings (if new filename)
                if source.filename not in [
                    s.filename for s in self.review_manager.settings.sources
                ]:
                    self.review_manager.settings.sources.append(source)
                    self.review_manager.save_settings()
                    # Add files that were renamed (removed)
                    for obj in git_repo.index.diff(None).iter_change_type("D"):
                        if source.filename.stem in obj.b_path:
                            self.review_manager.dataset.add_changes(
                                path=Path(obj.b_path), remove=True
                            )

                # 1. convert to bib and fix format (if necessary)
                load_conversion_package_endpoint_dict = self.package_manager.load_packages(
                    package_type=colrev.env.package_manager.PackageEndpointType.load_conversion,
                    selected_packages=[source.load_conversion_package_endpoint],
                    operation=self,
                )

                load_conversion_package_endpoint = (
                    load_conversion_package_endpoint_dict[
                        source.load_conversion_package_endpoint["endpoint"]
                    ]
                )
                records = load_conversion_package_endpoint.load(self, source)  # type: ignore
                self.__save_records(
                    records=records,
                    corresponding_bib_file=source.get_corresponding_bib_file(),
                )

                # 2. resolve non-unique IDs (if any)
                self.__resolve_non_unique_ids(source=source)

                # 3. load and add records to data/records.bib
                self.__load_source_records(source=source, keep_ids=keep_ids)
                if (
                    0 == getattr(source, "to_import", 0)
                    and not self.review_manager.high_level_operation
                ):
                    print()

                # 4. validate load
                self.__validate_load(source=source)

                stashed = "No local changes to save" != git_repo.git.stash(
                    "push", "--keep-index"
                )

                if not combine_commits:
                    self.review_manager.exact_call = (
                        f"{part_exact_call} -s {source.filename.name}"
                    )
                    self.review_manager.create_commit(
                        msg=f"Load {source.filename.name}",
                    )
                if stashed:
                    git_repo.git.stash("pop")
                if not self.review_manager.high_level_operation:
                    print()
            except colrev_exceptions.ImportException as exc:
                print(exc)

        if combine_commits and self.review_manager.dataset.has_changes():
            self.review_manager.create_commit(msg="Load (multiple)")

        self.review_manager.logger.info(
            f"{colors.GREEN}Completed load operation{colors.END}"
        )
        if self.review_manager.in_ci_environment():
            print("\n\n")


if __name__ == "__main__":
    pass
