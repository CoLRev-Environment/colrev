#! /usr/bin/env python
import itertools
import re
import string
import typing
from pathlib import Path

from colrev_core.environment import AdapterManager
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import LoadRecord
from colrev_core.record import RecordState


class Loader(Process):

    from colrev_core.built_in import load as built_in_load

    # Note : PDFs should be stored in the pdfs directory
    # They should be included through the search scripts (not the load scripts)
    built_in_scripts: typing.Dict[str, typing.Dict[str, typing.Any]] = {
        "bib_pybtex": {
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
                s.script["endpoint"] for s in REVIEW_MANAGER.settings.search.sources
            ],
        )

        self.extensions_scripts = {
            k: s["endpoint"].supported_extensions
            for k, s in self.built_in_scripts.items()
        }

    def get_search_files(self, *, restrict: list = None) -> typing.List[Path]:
        """ "Retrieve search files"""

        supported_extensions = [
            item for sublist in self.extensions_scripts.values() for item in sublist
        ]

        if restrict:
            supported_extensions = restrict

        search_dir = self.REVIEW_MANAGER.paths["SEARCHDIR"]

        if not search_dir.is_dir():
            raise NoSearchResultsAvailableError()

        files = [
            f
            for f_ in [search_dir.glob(f"**/*.{e}") for e in supported_extensions]
            for f in f_
        ]

        return sorted(files)

    def __getbib(self, *, file: Path) -> typing.List[dict]:
        with open(file, encoding="utf8") as bibtex_file:
            contents = bibtex_file.read()
            bib_r = re.compile(r"@.*{.*,", re.M)
            if len(re.findall(bib_r, contents)) == 0:
                self.REVIEW_MANAGER.logger.error(f"Not a bib file? {file.name}")
            if "Early Access Date" in contents:
                raise BibFileFormatError(
                    f"Replace Early Access Date in bibfile before loading! {file.name}"
                )

        with open(file, encoding="utf8") as bibtex_file:
            search_records_dict = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                load_str=bibtex_file.read()
            )

        return search_records_dict.values()

    def __load_records(self, *, filepath: Path) -> list:

        search_records = self.__getbib(file=filepath)

        self.REVIEW_MANAGER.logger.debug(
            f"Loaded {filepath.name} with {len(search_records)} records"
        )

        if len(search_records) == 0:
            return []

        nr_in_bib = self.__get_nr_in_bib(file_path=filepath)
        if len(search_records) < nr_in_bib:
            self.REVIEW_MANAGER.logger.error(
                "broken bib file (not imported all records)"
            )
            with open(filepath, encoding="utf8") as f:
                line = f.readline()
                while line:
                    if "@" in line[:3]:
                        ID = line[line.find("{") + 1 : line.rfind(",")]
                        if ID not in [x["ID"] for x in search_records]:
                            self.REVIEW_MANAGER.logger.error(f"{ID} not imported")
                    line = f.readline()

        source_identifier = [
            x.source_identifier
            for x in self.REVIEW_MANAGER.settings.search.sources
            if str(filepath.name) == str(x.filename.name)
        ][0]

        record_list = []
        for record in search_records:
            record.update(colrev_origin=f"{filepath.name}/{record['ID']}")
            record.update(colrev_source_identifier=source_identifier)

            # Drop empty fields
            record = {k: v for k, v in record.items() if v}

            if "colrev_status" not in record:
                record.update(colrev_status=RecordState.md_retrieved)
            elif record["colrev_status"] in [
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
                record["colrev_status"] = RecordState.md_prepared

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

        return record_list

    def __import_record(self, *, record: dict) -> dict:

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

        RECORD = LoadRecord(data=record)
        RECORD.import_provenance()
        record = RECORD.get_data()

        record.update(colrev_status=RecordState.md_imported)

        return record

    def validate_file_formats(self) -> None:
        print("TODO : reactivate validate_file_formats()")
        # search_files = self.get_search_files()
        # for sfp in search_files:
        #     if not any(
        #         sfp.suffix == f".{ext}" for ext in self.conversion_scripts.keys()
        #     ):
        #         if not sfp.suffix == ".bib":
        #             raise UnsupportedImportFormatError(sfp)
        return None

    def drop_empty_fields(self, *, records: typing.Dict) -> typing.Dict:

        records_list = list(records.values())
        records_list = [
            {k: v for k, v in record.items() if v is not None}
            for record in records_list
        ]
        records_list = [
            {k: v for k, v in record.items() if v != "nan"} for record in records_list
        ]

        return {r["ID"]: r for r in records_list}

    def set_incremental_IDs(self, *, records: typing.Dict) -> typing.Dict:
        # if IDs to set for some records
        if 0 != len([r for r in records if "ID" not in r]):
            i = 1
            for ID, record in records.items():
                if "ID" not in record:
                    if "UT_(Unique_WOS_ID)" in record:
                        record["ID"] = record["UT_(Unique_WOS_ID)"].replace(":", "_")
                    else:
                        record["ID"] = f"{i+1}".rjust(10, "0")
                    i += 1
        return records

    def fix_keys(self, *, records: typing.Dict) -> typing.Dict:
        for ID, record in records.items():
            record = {
                re.sub("[0-9a-zA-Z_]+", "1", k.replace(" ", "_")): v
                for k, v in record.items()
            }
        return records

    def get_script(self, *, filepath: str) -> dict:

        filetype = Path(filepath).suffix.replace(".", "")

        for endpoint_name, endpoint_dict in self.built_in_scripts.items():
            if filetype in endpoint_dict["endpoint"].supported_extensions:
                return {"endpoint": endpoint_name}

        return {"endpoint": "NA"}

    def get_unique_id(self, *, ID: str, ID_list: typing.List[str]) -> str:

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

    def __inplace_change_second(
        self, *, filename: Path, old_string: str, new_string: str
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

    def resolve_non_unique_IDs(self, *, corresponding_bib_file: Path) -> None:

        with open(corresponding_bib_file, encoding="utf8") as bibtex_file:
            cr_dict = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                load_str=bibtex_file.read()
            )

        IDs_to_update = []
        current_IDs = list(cr_dict.keys())
        for record in cr_dict.values():
            if len([x for x in current_IDs if x == record["ID"]]) > 1:
                new_id = self.get_unique_id(ID=record["ID"], ID_list=current_IDs)
                IDs_to_update.append([record["ID"], new_id])
                current_IDs.append(new_id)

        if len(IDs_to_update) > 0:
            self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
                path=str(corresponding_bib_file)
            )
            self.REVIEW_MANAGER.create_commit(
                msg=f"Save original search file: {corresponding_bib_file.name}"
            )

            for old_id, new_id in IDs_to_update:
                self.REVIEW_MANAGER.logger.info(
                    f"Resolve ID to ensure unique colrev_origins: {old_id} -> {new_id}"
                )
                self.REVIEW_MANAGER.report_logger.info(
                    f"Resolve ID to ensure unique colrev_origins: {old_id} -> {new_id}"
                )
                self.__inplace_change_second(
                    filename=corresponding_bib_file,
                    old_string=f"{old_id},",
                    new_string=f"{new_id},",
                )
            self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
                path=str(corresponding_bib_file)
            )
            self.REVIEW_MANAGER.create_commit(
                f"Resolve non-unique IDs in {corresponding_bib_file.name}"
            )

        return

    def __get_nr_in_bib(self, *, file_path: Path) -> int:

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

    def get_currently_imported_origin_list(self) -> list:
        record_header_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_header_list()
        imported_origins = [x["colrev_origin"].split(";") for x in record_header_list]
        imported_origins = list(itertools.chain(*imported_origins))
        return imported_origins

    def preprocess_records(self, *, records: list) -> list:
        ID = 1
        for x in records:
            if "ENTRYTYPE" not in x:
                if "" != x.get("journal", ""):
                    x["ENTRYTYPE"] = "article"
                if "" != x.get("booktitle", ""):
                    x["ENTRYTYPE"] = "inproceedings"
                else:
                    x["ENTRYTYPE"] = "misc"

            if "ID" not in x:
                if "citation_key" in x:
                    x["ID"] = x["citation_key"]
                else:
                    x["ID"] = ID
                    ID += 1

            for k, v in x.items():
                x[k] = str(v)

        for x in records:
            if "no year" == x.get("year", "NA"):
                del x["year"]
            if "no journal" == x.get("journal", "NA"):
                del x["journal"]
            if "no volume" == x.get("volume", "NA"):
                del x["volume"]
            if "no pages" == x.get("pages", "NA"):
                del x["pages"]
            if "no issue" == x.get("issue", "NA"):
                del x["issue"]
            if "no number" == x.get("number", "NA"):
                del x["number"]
            if "no doi" == x.get("doi", "NA"):
                del x["doi"]
            if "no type" == x.get("type", "NA"):
                del x["type"]
            if "author_count" in x:
                del x["author_count"]
            if "no Number-of-Cited-References" == x.get(
                "number_of_cited_references", "NA"
            ):
                del x["number_of_cited_references"]
            if "no file" in x.get("file_name", "NA"):
                del x["file_name"]
            if "times_cited" == x.get("times_cited", "NA"):
                del x["times_cited"]

        return records

    def save_records(self, *, records, corresponding_bib_file) -> None:
        records = self.fix_keys(records=records)
        records = self.set_incremental_IDs(records=records)
        records = self.drop_empty_fields(records=records)

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
            del saved_args["keep_ids"]

        self.REVIEW_MANAGER.REVIEW_DATASET.check_sources()
        self.REVIEW_MANAGER.REVIEW_DATASET.add_setting_changes()
        for search_file in self.get_search_files():

            if str(search_file.with_suffix(".bib").name) not in [
                str(s.filename) for s in self.REVIEW_MANAGER.settings.search.sources
            ]:
                continue
            SOURCE = [
                s
                for s in self.REVIEW_MANAGER.settings.search.sources
                if str(s.filename) == str(search_file.with_suffix(".bib").name)
            ][0]

            if SOURCE.script["endpoint"] not in list(self.load_scripts.keys()):
                if self.verbose:
                    print(f"Error: endpoint not available: {SOURCE.script}")
                continue

            endpoint = self.load_scripts[SOURCE.script["endpoint"]]
            ENDPOINT = endpoint["endpoint"]
            self.REVIEW_MANAGER.report_logger.info(f"Loading {SOURCE}")
            self.REVIEW_MANAGER.logger.info(f"Loading {SOURCE}")

            corresponding_bib_file = ENDPOINT.load(
                self, Path("search") / Path(search_file)
            )

            if not corresponding_bib_file.is_file():
                continue

            imported_origins = self.get_currently_imported_origin_list()
            len_before = len(imported_origins)

            self.REVIEW_MANAGER.report_logger.info(f"Load {SOURCE.filename.name}")
            self.REVIEW_MANAGER.logger.info(f"Load {SOURCE.filename.name}")
            saved_args["file"] = SOURCE.filename.name

            self.resolve_non_unique_IDs(corresponding_bib_file=corresponding_bib_file)

            search_records_list = self.__load_records(filepath=corresponding_bib_file)
            nr_search_recs = len(search_records_list)

            nr_in_bib = self.__get_nr_in_bib(file_path=corresponding_bib_file)
            if nr_in_bib != nr_search_recs:
                self.REVIEW_MANAGER.logger.error(
                    f"ERROR in bib file:  {corresponding_bib_file}"
                )

            search_records_list = [
                x
                for x in search_records_list
                if x["colrev_origin"] not in imported_origins
            ]
            to_import = len(search_records_list)
            if 0 == to_import:
                continue

            records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

            for sr in search_records_list:
                sr = self.__import_record(record=sr)

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

            self.REVIEW_MANAGER.logger.info("Save records to references.bib")
            self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)

            # TBD: does the following create errors!?
            # REVIEW_MANAGER.save_record_list_by_ID(record_list=search_records,
            #                                        append_new=True)

            if not keep_ids:
                self.REVIEW_MANAGER.logger.info("Set IDs")
                records = self.REVIEW_MANAGER.REVIEW_DATASET.set_IDs(
                    records=records,
                    selected_IDs=[r["ID"] for r in search_records_list],
                )

            if not combine_commits:
                self.REVIEW_MANAGER.logger.info("Add changes and create commit")

            self.REVIEW_MANAGER.REVIEW_DATASET.add_setting_changes()
            self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
                path=str(corresponding_bib_file)
            )
            self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
                path=str(Path("search") / SOURCE.filename)
            )
            if not combine_commits:

                self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
                self.REVIEW_MANAGER.create_commit(
                    msg=f"Load {saved_args['file']}", saved_args=saved_args
                )

            imported_origins = self.get_currently_imported_origin_list()
            len_after = len(imported_origins)
            imported = len_after - len_before

            if imported != to_import:

                origins_to_import = [o["colrev_origin"] for o in search_records_list]

                # self.REVIEW_MANAGER.pp.pprint(search_records_list)
                # print(origins_to_import)
                # self.REVIEW_MANAGER.pp.pprint(imported_origins)

                self.REVIEW_MANAGER.logger.error(f"len_before: {len_before}")
                self.REVIEW_MANAGER.logger.error(f"len_after: {len_after}")
                if to_import - imported > 0:
                    self.REVIEW_MANAGER.logger.error(
                        f"PROBLEM: delta: {to_import - imported} records missing"
                    )

                    missing_origins = [
                        o for o in origins_to_import if o not in imported_origins
                    ]
                    self.REVIEW_MANAGER.logger.error(
                        f"Records not yet imported: {missing_origins}"
                    )
                else:
                    self.REVIEW_MANAGER.logger.error(
                        f"PROBLEM: delta: {to_import - imported} records too much"
                    )

            print("\n")

        if combine_commits and self.REVIEW_MANAGER.REVIEW_DATASET.has_changes():
            self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
            self.REVIEW_MANAGER.create_commit(
                msg="Load (multiple)", saved_args=saved_args
            )
        return


class NoSearchResultsAvailableError(Exception):
    def __init__(self):
        self.message = (
            "no search results files of supported types in /search/ directory."
        )
        super().__init__(self.message)


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
