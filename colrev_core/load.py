#! /usr/bin/env python
import itertools
import re
import shutil
import string
import typing
from pathlib import Path

import docker
import pandas as pd
import requests

from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import Record
from colrev_core.record import RecordState


class LoadRecord(Record):
    def __init__(self, *, data: dict):
        super().__init__(data=data)

    def import_provenance(self) -> None:
        def percent_upper_chars(input_string: str) -> float:
            return sum(map(str.isupper, input_string)) / len(input_string)

        # Initialize colrev_masterdata_provenance
        if "colrev_masterdata_provenance" in self.data:
            colrev_masterdata_provenance = self.data["colrev_masterdata_provenance"]
        else:
            source_identifier_string = self.data["colrev_source_identifier"]
            marker = re.search(r"\{\{(.*)\}\}", source_identifier_string)
            if marker:
                marker_string = marker.group(0)
                key = marker_string[2:-2]

                try:
                    marker_replacement = self.data[key]
                    source_identifier_string = source_identifier_string.replace(
                        marker_string, marker_replacement
                    )
                except KeyError as e:
                    print(e)
                    pass

            colrev_masterdata_provenance = {}
            colrev_data_provenance = {}
            for key in self.data.keys():
                if key in Record.identifying_fields:
                    colrev_masterdata_provenance[key] = {
                        "source": source_identifier_string,
                        "note": "",
                    }
                elif key not in Record.provenance_keys and key not in [
                    "colrev_source_identifier",
                    "ID",
                    "ENTRYTYPE",
                    "source_url",
                ]:
                    colrev_data_provenance[key] = {
                        "source": source_identifier_string,
                        "note": "",
                    }

            del self.data["colrev_source_identifier"]

        if not self.masterdata_is_curated():
            if self.data["ENTRYTYPE"] in self.record_field_requirements:
                required_fields = self.record_field_requirements[self.data["ENTRYTYPE"]]
                for required_field in required_fields:
                    if required_field in self.data:
                        if percent_upper_chars(self.data[required_field]) > 0.8:
                            self.add_masterdata_provenance_hint(
                                field=required_field, hint="mostly upper case"
                            )
                    else:
                        self.data[required_field] = "UNKNOWN"
            # TODO : how to handle cases where we do not have field_requirements?

        if self.data["ENTRYTYPE"] in self.record_field_inconsistencies:
            inconsistent_fields = self.record_field_inconsistencies[
                self.data["ENTRYTYPE"]
            ]
            for inconsistent_field in inconsistent_fields:
                if inconsistent_field in self.data:
                    inconsistency_hint = (
                        f"inconsistent with entrytype ({self.data['ENTRYTYPE']})"
                    )
                    self.add_masterdata_provenance_hint(
                        field=inconsistent_field, hint=inconsistency_hint
                    )

        incomplete_fields = self.get_incomplete_fields()
        for incomplete_field in incomplete_fields:
            self.add_masterdata_provenance_hint(
                field=incomplete_field, hint="incomplete"
            )

        defect_fields = self.get_quality_defects()
        if defect_fields:
            for defect_field in defect_fields:
                self.add_masterdata_provenance_hint(
                    field=defect_field, hint="quality_defect"
                )

        self.data["colrev_data_provenance"] = colrev_data_provenance
        self.data["colrev_masterdata_provenance"] = colrev_masterdata_provenance
        return


class Loader(Process):
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

        self.conversion_scripts = {
            "ris": self.__zotero_translate,
            # Zotero does not support enl:
            # https://www.zotero.org/support/kb/endnote_import
            # "enl": self.__zotero_translate,
            # "end": self.__zotero_translate,
            "rdf": self.__zotero_translate,
            "json": self.__zotero_translate,
            "mods": self.__zotero_translate,
            "xml": self.__zotero_translate,
            "marc": self.__zotero_translate,
            "txt": self.__zotero_translate,  # __txt2bib,
            "md": self.__txt2bib,
            "csv": self.__csv2bib,
            "xlsx": self.__xlsx2bib,
            "xls": self.__xlsx2bib,
            "pdf": self.__pdf2bib,
            "pdf_refs": self.__pdfRefs2bib,
        }

    def get_search_files(self, *, restrict: list = None) -> typing.List[Path]:
        """ "Retrieve search files"""

        supported_extensions = [
            "bib",
            "ris",
            # "enl",
            # "end",
            "txt",
            "csv",
            "md",
            "xlsx",
            "xls",
            "pdf",
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
            if str(filepath.name) == str(x.filename)
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

    def __zotero_translate(self, *, file: Path) -> typing.List[dict]:
        import requests
        from colrev_core.environment import ZoteroTranslationService
        import json

        ZOTERO_TRANSLATION_SERVICE = ZoteroTranslationService()
        ZOTERO_TRANSLATION_SERVICE.start_zotero_translators()

        files = {"file": open(file, "rb")}
        headers = {"Content-type": "text/plain"}
        r = requests.post("http://127.0.0.1:1969/import", headers=headers, files=files)
        headers = {"Content-type": "application/json"}
        if "No suitable translators found" == r.content.decode("utf-8"):
            raise ImportException(
                "Zotero translators: No suitable import translators found"
            )

        try:
            zotero_format = json.loads(r.content)
            et = requests.post(
                "http://127.0.0.1:1969/export?format=bibtex",
                headers=headers,
                json=zotero_format,
            )
            rec_dict = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                load_str=et.content
            )

        except Exception as e:
            pass
            raise ImportException(f"Zotero import translators failed ({e})")

        return rec_dict.values()

    def __txt2bib(self, *, file: Path) -> typing.List[dict]:
        from colrev_core.environment import GrobidService

        GROBID_SERVICE = GrobidService()
        GROBID_SERVICE.check_grobid_availability()
        with open(file, encoding="utf8") as f:
            if file.suffix == ".md":
                references = [line.rstrip() for line in f if "#" not in line[:2]]
            else:
                references = [line.rstrip() for line in f]

        data = ""
        ind = 0
        for ref in references:
            options = {}
            options["consolidateCitations"] = "1"
            options["citations"] = ref
            r = requests.post(
                GROBID_SERVICE.GROBID_URL + "/api/processCitation",
                data=options,
                headers={"Accept": "application/x-bibtex"},
            )
            ind += 1
            data = data + "\n" + r.text.replace("{-1,", "{" + str(ind) + ",")

        search_records_dict = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
            load_str=data
        )

        return search_records_dict.values()

    def __preprocess_records(self, *, data: list) -> list:
        ID = 1
        for x in data:
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

        for x in data:
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

        return data

    def __csv2bib(self, *, file: Path) -> typing.List[dict]:
        try:
            data = pd.read_csv(file)
        except pd.errors.ParserError:
            self.REVIEW_MANAGER.logger.error(f"Error: Not a csv file? {file.name}")
            pass
            return []
        data.columns = data.columns.str.replace(" ", "_")
        data.columns = data.columns.str.replace("-", "_")
        data = data.to_dict("records")
        data = self.__preprocess_records(data=data)

        return data

    def __xlsx2bib(self, *, file: Path) -> typing.List[dict]:
        try:
            data = pd.read_excel(file, dtype=str)  # dtype=str to avoid type casting
        except pd.errors.ParserError:
            self.REVIEW_MANAGER.logger.error(f"Error: Not an xlsx file: {file.name}")
            pass
            return []
        data.columns = data.columns.str.replace(" ", "_")
        data.columns = data.columns.str.replace("-", "_")
        data = data.to_dict("records")
        data = self.__preprocess_records(data=data)

        return data

    def __move_to_pdf_dir(self, *, filepath: Path) -> Path:
        PDF_DIRECTORY = self.REVIEW_MANAGER.paths["PDF_DIRECTORY"]
        # We should avoid re-extracting data from PDFs repeatedly (e.g., status.py)
        Path(PDF_DIRECTORY).mkdir(exist_ok=True)
        new_fp = Path(PDF_DIRECTORY) / filepath.name
        shutil.move(str(filepath), new_fp)
        return new_fp

    # curl -v --form input=@./profit.pdf localhost:8070/api/processHeaderDocument
    # curl -v --form input=@./thefile.pdf -H "Accept: application/x-bibtex"
    # -d "consolidateHeader=0" localhost:8070/api/processHeaderDocument
    def __pdf2bib(self, file: Path) -> typing.List[dict]:
        from colrev_core.environment import GrobidService

        GROBID_SERVICE = GrobidService()
        GROBID_SERVICE.check_grobid_availability()

        # https://github.com/kermitt2/grobid/issues/837
        r = requests.post(
            GrobidService.GROBID_URL + "/api/processHeaderDocument",
            headers={"Accept": "application/x-bibtex"},
            params={"consolidateHeader": "1"},
            files=dict(input=open(file, "rb"), encoding="utf8"),
        )

        if 200 == r.status_code:
            search_records_dict = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                load_str=r.text
            )
            return search_records_dict.values()

        if 500 == r.status_code:
            self.REVIEW_MANAGER.report_logger.error(
                f"Not a readable pdf file: {file.name}"
            )
            self.REVIEW_MANAGER.logger.error(f"Not a readable pdf file: {file.name}")
            self.REVIEW_MANAGER.report_logger.debug(f"Grobid: {r.text}")
            self.REVIEW_MANAGER.logger.debug(f"Grobid: {r.text}")
            return []

        self.REVIEW_MANAGER.report_logger.debug(f"Status: {r.status_code}")
        self.REVIEW_MANAGER.logger.debug(f"Status: {r.status_code}")
        self.REVIEW_MANAGER.report_logger.debug(f"Response: {r.text}")
        self.REVIEW_MANAGER.logger.debug(f"Response: {r.text}")
        return []

    def __pdfRefs2bib(self, *, file: Path) -> typing.List[dict]:
        from colrev_core.environment import GrobidService

        GROBID_SERVICE = GrobidService()
        GROBID_SERVICE.check_grobid_availability()

        r = requests.post(
            GrobidService.GROBID_URL + "/api/processReferences",
            files=dict(input=open(file, "rb"), encoding="utf8"),
            data={"consolidateHeader": "0", "consolidateCitations": "1"},
            headers={"Accept": "application/x-bibtex"},
        )
        if 200 == r.status_code:
            search_records_dict = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                load_str=r.text
            )
            search_records = search_records_dict.values()

            # Use lpad to maintain the sort order (easier to catch errors)
            for rec in search_records:
                rec["ID"] = rec.get("ID", "").rjust(3, "0")

            return search_records
        if 500 == r.status_code:
            self.REVIEW_MANAGER.report_logger.error(
                f"Not a readable pdf file: {file.name}"
            )
            self.REVIEW_MANAGER.logger.error(f"Not a readable pdf file: {file.name}")
            self.REVIEW_MANAGER.report_logger.debug(f"Grobid: {r.text}")
            self.REVIEW_MANAGER.logger.debug(f"Grobid: {r.text}")
            return []

        self.REVIEW_MANAGER.report_logger.debug(f"Status: {r.status_code}")
        self.REVIEW_MANAGER.logger.debug(f"Status: {r.status_code}")
        self.REVIEW_MANAGER.report_logger.debug(f"Response: {r.text}")
        self.REVIEW_MANAGER.logger.debug(f"Response: {r.text}")
        return []

    def __drop_empty_fields(self, *, records: typing.List[dict]) -> typing.List[dict]:
        records = [{k: v for k, v in r.items() if v is not None} for r in records]
        records = [{k: v for k, v in r.items() if v != "nan"} for r in records]
        return records

    def __set_incremental_IDs(self, *, records: typing.List[dict]) -> typing.List[dict]:
        # if IDs to set for some records
        if 0 != len([r for r in records if "ID" not in r]):
            for i, record in enumerate(records):
                if "ID" not in record:
                    if "UT_(Unique_WOS_ID)" in record:
                        record["ID"] = record["UT_(Unique_WOS_ID)"].replace(":", "_")
                    else:
                        record["ID"] = f"{i+1}".rjust(10, "0")
        return records

    def __fix_keys(self, *, records: typing.List[dict]) -> typing.List[dict]:
        for record in records:
            record = {
                re.sub("[0-9a-zA-Z_]+", "1", k.replace(" ", "_")): v
                for k, v in record.items()
            }
        return records

    def validate_file_formats(self) -> None:
        search_files = self.get_search_files()
        for sfp in search_files:
            if not any(
                sfp.suffix == f".{ext}" for ext in self.conversion_scripts.keys()
            ):
                if not sfp.suffix == ".bib":
                    raise UnsupportedImportFormatError(sfp)
        return None

    def __convert_to_bib(self, *, sfpath: Path) -> Path:
        from colrev_core.environment import GrobidService

        corresponding_bib_file = sfpath.with_suffix(".bib")

        if corresponding_bib_file.is_file():
            return corresponding_bib_file

        if not any(
            sfpath.suffix == f".{ext}" for ext in self.conversion_scripts.keys()
        ):
            raise UnsupportedImportFormatError(sfpath)

        filetype = sfpath.suffix.replace(".", "")
        if "pdf" == filetype:
            if str(sfpath).endswith("_ref_list.pdf"):
                filetype = "pdf_refs"

        if sfpath.suffix in [".pdf", ".md"]:
            self.REVIEW_MANAGER.logger.info("Start grobid")
            GROBID_SERVICE = GrobidService()
            GROBID_SERVICE.start()

        if filetype in self.conversion_scripts.keys():
            self.REVIEW_MANAGER.report_logger.info(f"Loading {filetype}: {sfpath.name}")
            self.REVIEW_MANAGER.logger.info(f"Loading {filetype}: {sfpath.name}")

            try:
                cur_tag = (
                    docker.from_env().images.get("zotero/translation-server").tags[0]
                )
                self.REVIEW_MANAGER.report_logger.info(
                    f"Running docker container created from {cur_tag}"
                )
                self.REVIEW_MANAGER.logger.info(
                    f"Running docker container created from {cur_tag}"
                )
            except docker.errors.ImageNotFound:
                pass

            self.REVIEW_MANAGER.logger.debug(
                f"Called {self.conversion_scripts[filetype].__name__}({sfpath})"
            )
            records = self.conversion_scripts[filetype](file=sfpath)

            records = self.__fix_keys(records=records)
            records = self.__set_incremental_IDs(records=records)

            records = self.__drop_empty_fields(records=records)

            if len(records) == 0:
                self.REVIEW_MANAGER.report_logger.error("No records loaded")
                self.REVIEW_MANAGER.logger.error("No records loaded")
                return corresponding_bib_file

            if corresponding_bib_file != str(sfpath) and sfpath.suffix != ".bib":
                if not corresponding_bib_file.is_file():
                    self.REVIEW_MANAGER.logger.info(
                        f"Loaded {len(records)} " f"records from {sfpath.name}"
                    )
                    records_dict = {r["ID"]: r for r in records}
                    self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict_to_file(
                        records=records_dict, save_path=corresponding_bib_file
                    )

        else:
            self.REVIEW_MANAGER.report_logger.info(
                f"Filetype not recognized: {sfpath.name}"
            )
            self.REVIEW_MANAGER.logger.info(f"Filetype not recognized: {sfpath.name}")
            return corresponding_bib_file

        return corresponding_bib_file

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

    def __get_currently_imported_origin_list(self) -> list:
        record_header_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_header_list()
        imported_origins = [x["colrev_origin"].split(";") for x in record_header_list]
        imported_origins = list(itertools.chain(*imported_origins))
        return imported_origins

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

    def main(self, *, keep_ids: bool = False, combine_commits=False) -> None:

        saved_args = locals()
        if not keep_ids:
            del saved_args["keep_ids"]

        self.REVIEW_MANAGER.REVIEW_DATASET.check_sources()
        self.REVIEW_MANAGER.REVIEW_DATASET.add_setting_changes()
        for search_file in self.get_search_files():

            corresponding_bib_file = self.__convert_to_bib(sfpath=search_file)
            if not corresponding_bib_file.is_file():
                continue

            imported_origins = self.__get_currently_imported_origin_list()
            len_before = len(imported_origins)

            self.REVIEW_MANAGER.report_logger.info(f"Load {search_file.name}")
            self.REVIEW_MANAGER.logger.info(f"Load {search_file.name}")
            saved_args["file"] = search_file.name

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
            self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(path=str(search_file))
            if not combine_commits:

                self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
                self.REVIEW_MANAGER.create_commit(
                    msg=f"Load {saved_args['file']}", saved_args=saved_args
                )

            imported_origins = self.__get_currently_imported_origin_list()
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
