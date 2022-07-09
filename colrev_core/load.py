#! /usr/bin/env python
import itertools
import re
import string
import typing
from pathlib import Path

from colrev_core.environment import AdapterManager
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import Record
from colrev_core.record import RecordState


class Loader(Process):

    from colrev_core.built_in import load as built_in_load

    # Note : PDFs should be stored in the pdfs directory
    # They should be included through the search scripts (not the load scripts)
    built_in_scripts: typing.Dict[str, typing.Dict[str, typing.Any]] = {
        "bibtex": {
            "endpoint": built_in_load.BibPybtexLoader,
        },
        "csv": {
            "endpoint": built_in_load.CSVLoader,
        },
        "excel": {"endpoint": built_in_load.ExcelLoader},
        "zotero_translate": {
            "endpoint": built_in_load.ZoteroTranslationLoader,
        },
        "md_to_bib": {
            "endpoint": built_in_load.MarkdownLoader,
        },
        "bibutils": {
            "endpoint": built_in_load.BibutilsLoader,
        },
    }

    def __init__(
        self,
        *,
        REVIEW_MANAGER,
        notify_state_transition_process=True,
    ):

        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            type=ProcessType.load,
            notify_state_transition_process=notify_state_transition_process,
        )
        self.verbose = True

        self.load_scripts: typing.Dict[
            str, typing.Dict[str, typing.Any]
        ] = AdapterManager.load_scripts(
            PROCESS=self,
            scripts=[
                s.conversion_script["endpoint"] for s in REVIEW_MANAGER.settings.sources
            ],
        )

        self.supported_extensions = [
            item
            for sublist in [
                e["endpoint"].supported_extensions
                for e in self.built_in_scripts.values()
            ]
            for item in sublist
        ]

    def get_new_search_files(self) -> typing.List[Path]:
        """ "Retrieve new search files (not yet registered in settings)"""

        search_dir = self.REVIEW_MANAGER.paths["SEARCHDIR"]

        if not search_dir.is_dir():
            return []

        # Only supported filetypes
        files = [
            f.relative_to(self.REVIEW_MANAGER.path)
            for f_ in [search_dir.glob(f"**/*.{e}") for e in self.supported_extensions]
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
                for s in self.REVIEW_MANAGER.settings.sources
            ]
        ]

        return sorted(list(set(files)))

    @classmethod
    def get_conversion_script(cls, *, filepath: Path) -> dict:

        filetype = filepath.suffix.replace(".", "")

        for endpoint_name, endpoint_dict in cls.built_in_scripts.items():
            if filetype in endpoint_dict["endpoint"].supported_extensions:
                return {"endpoint": endpoint_name}

        return {"endpoint": "NA"}

    def resolve_non_unique_IDs(self, *, SOURCE) -> None:
        def get_unique_id(*, ID: str, ID_list: typing.List[str]) -> str:

            order = 0
            letters = list(string.ascii_lowercase)
            temp_ID = ID
            next_unique_ID = temp_ID
            appends: list = []
            while next_unique_ID in ID_list:
                if len(appends) == 0:
                    order += 1
                    appends = [p for p in itertools.product(letters, repeat=order)]
                next_unique_ID = temp_ID + "".join(list(appends.pop(0)))

            return next_unique_ID

        def inplace_change_second(
            *, filename: Path, old_string: str, new_string: str
        ) -> None:
            new_file_lines = []
            with open(filename, encoding="utf8") as f:
                first_read = False
                replaced = False
                for line in f.readlines():
                    if old_string in line and not first_read:
                        first_read = True
                    if old_string in line and first_read and not replaced:
                        line = line.replace(old_string, new_string)
                        replaced = True
                    new_file_lines.append(line)

                # s = f.read()
                # if old_string not in s:
                #     return
            with open(filename, "w", encoding="utf8") as f:
                for s in new_file_lines:
                    f.write(s)
            return

        if not SOURCE.corresponding_bib_file.is_file():
            return

        with open(SOURCE.corresponding_bib_file, encoding="utf8") as bibtex_file:
            cr_dict = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                load_str=bibtex_file.read()
            )

        IDs_to_update = []
        current_IDs = list(cr_dict.keys())
        for record in cr_dict.values():
            if len([x for x in current_IDs if x == record["ID"]]) > 1:
                new_id = get_unique_id(ID=record["ID"], ID_list=current_IDs)
                IDs_to_update.append([record["ID"], new_id])
                current_IDs.append(new_id)

        if len(IDs_to_update) > 0:
            self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
                path=str(SOURCE.corresponding_bib_file)
            )
            self.REVIEW_MANAGER.create_commit(
                msg=f"Save original search file: {SOURCE.corresponding_bib_file.name}",
                script_call="colrev load",
            )

            for old_id, new_id in IDs_to_update:
                self.REVIEW_MANAGER.logger.info(
                    f"Resolve ID to ensure unique colrev_origins: {old_id} -> {new_id}"
                )
                self.REVIEW_MANAGER.report_logger.info(
                    f"Resolve ID to ensure unique colrev_origins: {old_id} -> {new_id}"
                )
                inplace_change_second(
                    filename=SOURCE.corresponding_bib_file,
                    old_string=f"{old_id},",
                    new_string=f"{new_id},",
                )
            self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
                path=str(SOURCE.corresponding_bib_file)
            )
            self.REVIEW_MANAGER.create_commit(
                f"Resolve non-unique IDs in {SOURCE.corresponding_bib_file.name}"
            )

        return

    def load_source_records(self, *, SOURCE, keep_ids) -> None:
        def getbib(*, file: Path) -> typing.List[dict]:
            with open(file, encoding="utf8") as bibtex_file:
                contents = bibtex_file.read()
                bib_r = re.compile(r"@.*{.*,", re.M)
                if len(re.findall(bib_r, contents)) == 0:
                    self.REVIEW_MANAGER.logger.error(f"Not a bib file? {file.name}")
                if "Early Access Date" in contents:
                    raise BibFileFormatError(
                        "Replace Early Access Date in bibfile before loading! "
                        f"{file.name}"
                    )
            with open(file, encoding="utf8") as bibtex_file:
                search_records_dict = (
                    self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                        load_str=bibtex_file.read()
                    )
                )
            return search_records_dict.values()

        def import_record(*, record: dict) -> dict:
            self.REVIEW_MANAGER.logger.debug(
                f'import_record {record["ID"]}: '
                f"\n{self.REVIEW_MANAGER.pp.pformat(record)}\n\n"
            )
            if RecordState.md_retrieved != record["colrev_status"]:
                return record

            # Consistently set keys to lower case
            lower_keys = [k.lower() for k in list(record.keys())]
            for key, n_key in zip(list(record.keys()), lower_keys):
                if key in ["ID", "ENTRYTYPE"]:
                    continue
                record[n_key] = record.pop(key)

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
                if field in record:
                    record[field] = (
                        record[field]
                        .replace("\n", " ")
                        .rstrip()
                        .lstrip()
                        .replace("{", "")
                        .replace("}", "")
                    )
            if "pages" in record:
                record["pages"] = record["pages"].replace("–", "--")
                if record["pages"].count("-") == 1:
                    record["pages"] = record["pages"].replace("-", "--")

            if "number" not in record and "issue" in record:
                record.update(number=record["issue"])
                del record["issue"]

            RECORD = Record(data=record)
            RECORD.import_provenance(source_identifier=SOURCE.source_identifier)
            RECORD.set_status(target_state=RecordState.md_imported)

            return RECORD.get_data()

        def get_nr_in_bib(*, file_path: Path) -> int:
            number_in_bib = 0
            with open(file_path, encoding="utf8") as f:
                line = f.readline()
                while line:
                    # Note: the '﻿' occured in some bibtex files
                    # (e.g., Publish or Perish exports)
                    if "@" in line[:3]:
                        if "@comment" not in line[:10].lower():
                            number_in_bib += 1
                    line = f.readline()
            return number_in_bib

        if SOURCE.corresponding_bib_file.is_file():
            search_records = getbib(file=SOURCE.corresponding_bib_file)
            self.REVIEW_MANAGER.logger.debug(
                f"Loaded {SOURCE.corresponding_bib_file.name} "
                f"with {len(search_records)} records"
            )
        else:
            search_records = []

        if len(search_records) == 0:
            SOURCE.to_import = 0
            SOURCE.source_records_list = []
            return

        nr_in_bib = get_nr_in_bib(file_path=SOURCE.corresponding_bib_file)
        if len(search_records) < nr_in_bib:
            self.REVIEW_MANAGER.logger.error(
                "broken bib file (not imported all records)"
            )
            with open(SOURCE.corresponding_bib_file, encoding="utf8") as f:
                line = f.readline()
                while line:
                    if "@" in line[:3]:
                        ID = line[line.find("{") + 1 : line.rfind(",")]
                        if ID not in [x["ID"] for x in search_records]:
                            self.REVIEW_MANAGER.logger.error(f"{ID} not imported")
                    line = f.readline()

        record_list = []
        for record in search_records:
            record.update(
                colrev_origin=f"{SOURCE.corresponding_bib_file.name}/{record['ID']}"
            )

            # Drop empty fields
            record = {k: v for k, v in record.items() if v}

            if record.get("colrev_status", "") in [
                str(RecordState.md_processed),
                str(RecordState.rev_prescreen_included),
                str(RecordState.rev_prescreen_excluded),
                str(RecordState.pdf_needs_manual_retrieval),
                str(RecordState.pdf_not_available),
                str(RecordState.pdf_needs_manual_preparation),
                str(RecordState.pdf_prepared),
                str(RecordState.rev_excluded),
                str(RecordState.rev_included),
                str(RecordState.rev_synthesized),
            ]:
                # Note : when importing a record, it always needs to be
                # deduplicated against the other records in the repository
                record.update(colrev_status=RecordState.md_prepared)
            else:
                record.update(colrev_status=RecordState.md_retrieved)

            if "doi" in record:
                record.update(
                    doi=record["doi"].replace("http://dx.doi.org/", "").upper()
                )
                # https://www.crossref.org/blog/dois-and-matching-regular-expressions/
                d = re.match(r"^10.\d{4,9}\/", record["doi"])
                if not d:
                    del record["doi"]

            self.REVIEW_MANAGER.logger.debug(
                f'append record {record["ID"]} '
                f"\n{self.REVIEW_MANAGER.pp.pformat(record)}\n\n"
            )
            record_list.append(record)

        record_list = [
            x for x in record_list if x["colrev_origin"] not in SOURCE.imported_origins
        ]
        SOURCE.to_import = len(record_list)
        SOURCE.source_records_list = record_list

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        for sr in SOURCE.source_records_list:
            sr = import_record(record=sr)

            # Make sure IDs are unique / do not replace existing records
            order = 0
            letters = list(string.ascii_lowercase)
            next_unique_ID = sr["ID"]
            appends: list = []
            while next_unique_ID in records:
                if len(appends) == 0:
                    order += 1
                    appends = [p for p in itertools.product(letters, repeat=order)]
                next_unique_ID = sr["ID"] + "".join(list(appends.pop(0)))
            sr["ID"] = next_unique_ID
            records[sr["ID"]] = sr

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)

        if not keep_ids:
            self.REVIEW_MANAGER.logger.info("Set IDs")
            records = self.REVIEW_MANAGER.REVIEW_DATASET.set_IDs(
                records=records,
                selected_IDs=[r["ID"] for r in SOURCE.source_records_list],
            )

        self.REVIEW_MANAGER.REVIEW_DATASET.add_setting_changes()
        self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
            path=str(SOURCE.corresponding_bib_file)
        )
        self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(path=str(SOURCE.filename))
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return

    def validate_load(self, *, SOURCE) -> None:

        imported_origins = (
            self.REVIEW_MANAGER.REVIEW_DATASET.get_currently_imported_origin_list()
        )
        len_after = len(imported_origins)
        imported = len_after - SOURCE.len_before

        if imported != SOURCE.to_import:
            self.REVIEW_MANAGER.logger.error(f"len_before: {SOURCE.len_before}")
            self.REVIEW_MANAGER.logger.error(f"len_after: {len_after}")

            origins_to_import = [o["colrev_origin"] for o in SOURCE.source_records_list]
            if SOURCE.to_import - imported > 0:
                self.REVIEW_MANAGER.logger.error(
                    f"PROBLEM: delta: {SOURCE.to_import - imported} records missing"
                )

                missing_origins = [
                    o for o in origins_to_import if o not in imported_origins
                ]
                self.REVIEW_MANAGER.logger.error(
                    f"Records not yet imported: {missing_origins}"
                )
            else:
                self.REVIEW_MANAGER.logger.error(
                    f"PROBLEM: {SOURCE.to_import - imported} records too much"
                )

        print("\n")

        return

    def save_records(self, *, records, corresponding_bib_file) -> None:
        """Convenience function for the load script implementations"""

        def fix_keys(*, records: typing.Dict) -> typing.Dict:
            for ID, record in records.items():
                record = {
                    re.sub("[0-9a-zA-Z_]+", "1", k.replace(" ", "_")): v
                    for k, v in record.items()
                }
            return records

        def set_incremental_IDs(*, records: typing.Dict) -> typing.Dict:
            # if IDs to set for some records
            if 0 != len([r for r in records if "ID" not in r]):
                i = 1
                for ID, record in records.items():
                    if "ID" not in record:
                        if "UT_(Unique_WOS_ID)" in record:
                            record["ID"] = record["UT_(Unique_WOS_ID)"].replace(
                                ":", "_"
                            )
                        else:
                            record["ID"] = f"{i+1}".rjust(10, "0")
                        i += 1
            return records

        def drop_empty_fields(*, records: typing.Dict) -> typing.Dict:

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
        records = set_incremental_IDs(records=records)
        records = drop_empty_fields(records=records)

        if len(records) == 0:
            self.REVIEW_MANAGER.report_logger.error("No records loaded")
            self.REVIEW_MANAGER.logger.error("No records loaded")

        if not corresponding_bib_file.is_file():
            self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict_to_file(
                records=records, save_path=corresponding_bib_file
            )
        return

    def main(self, *, keep_ids: bool = False, combine_commits=False) -> None:

        saved_args = locals()
        if not keep_ids:
            # TODO : keep_ids as a potential parameter for the source/settings?
            del saved_args["keep_ids"]

        REVIEW_DATASET = self.REVIEW_MANAGER.REVIEW_DATASET

        def load_active_sources() -> list:
            REVIEW_DATASET.check_sources()
            SOURCES = []
            for SOURCE in self.REVIEW_MANAGER.settings.sources:
                if SOURCE.conversion_script["endpoint"] not in list(
                    self.load_scripts.keys()
                ):
                    if self.verbose:
                        print(
                            f"Error: endpoint not available: {SOURCE.conversion_script}"
                        )
                    continue
                SOURCE.corresponding_bib_file = SOURCE.filename.with_suffix(".bib")
                imported_origins = REVIEW_DATASET.get_currently_imported_origin_list()
                SOURCE.imported_origins = imported_origins
                SOURCE.len_before = len(SOURCE.imported_origins)
                SOURCES.append(SOURCE)
            return SOURCES

        for SOURCE in load_active_sources():
            self.REVIEW_MANAGER.logger.info(f"Loading {SOURCE}")
            saved_args["file"] = SOURCE.filename.name

            # 1. convert to bib (if necessary)
            ENDPOINT = self.load_scripts[SOURCE.conversion_script["endpoint"]][
                "endpoint"
            ]
            ENDPOINT.load(self, SOURCE)

            # 2. resolve non-unique IDs (if any)
            self.resolve_non_unique_IDs(SOURCE=SOURCE)

            # 3. load and add records to references.bib
            self.load_source_records(SOURCE=SOURCE, keep_ids=keep_ids)
            if 0 == SOURCE.to_import:
                continue

            # 4. validate load
            self.validate_load(SOURCE=SOURCE)

            if not combine_commits:
                self.REVIEW_MANAGER.create_commit(
                    msg=f"Load {saved_args['file']}",
                    script_call="colrev load",
                    saved_args=saved_args,
                )

        if combine_commits and REVIEW_DATASET.has_changes():
            self.REVIEW_MANAGER.create_commit(
                msg="Load (multiple)", script_call="colrev load", saved_args=saved_args
            )
        return


class UnsupportedImportFormatError(Exception):
    def __init__(
        self,
        import_path,
    ):
        self.import_path = import_path
        self.message = (
            "Format of search result file not (yet) supported "
            + f"({self.import_path.name}) "
        )
        super().__init__(self.message)


class BibFileFormatError(Exception):
    def __init__(self, message):
        super().__init__(message)


class ImportException(Exception):
    def __init__(self, message):
        super().__init__(message)


if __name__ == "__main__":
    pass
