#! /usr/bin/env python
import itertools
import re
import shutil
import string
import typing
from pathlib import Path

import bibtexparser
import pandas as pd
import requests
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from yaml import safe_load

import docker
from colrev_core import grobid_client
from colrev_core import load_custom
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.process import RecordState


class Loader(Process):
    def __init__(
        self,
        REVIEW_MANAGER,
        keep_ids,
        notify=True,
        notify_state_transition_process=True,
    ):

        super().__init__(
            REVIEW_MANAGER,
            ProcessType.load,
            fun=self.main,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.keep_ids = keep_ids

        self.conversion_scripts = {
            "ris": self.__ris2bib,
            "enl": self.__end2bib,
            "end": self.__end2bib,
            "txt": self.__txt2bib,
            "md": self.__txt2bib,
            "csv": self.__csv2bib,
            "xlsx": self.__xlsx2bib,
            "xls": self.__xlsx2bib,
            "pdf": self.__pdf2bib,
            "pdf_refs": self.__pdfRefs2bib,
        }

    def get_search_files(self, restrict: list = None) -> typing.List[Path]:
        """ "Retrieve search files"""

        supported_extensions = [
            "bib",
            "ris",
            "enl",
            "end",
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
            for f_ in [search_dir.glob(f"*.{e}") for e in supported_extensions]
            for f in f_
        ]

        return files

    def __getbib(self, file: Path) -> typing.List[dict]:
        with open(file) as bibtex_file:
            contents = bibtex_file.read()
            bib_r = re.compile(r"@.*{.*,", re.M)
            if len(re.findall(bib_r, contents)) == 0:
                self.logger.error(f"Not a bib file? {file.name}")
                db = None
            if "Early Access Date" in contents:
                raise BibFileFormatError(
                    f"Replace Early Access Date in bibfile before loading! {file.name}"
                )

        with open(file) as bibtex_file:
            db = BibTexParser(
                customization=convert_to_unicode,
                ignore_nonstandard_types=True,
                common_strings=True,
            ).parse_file(bibtex_file, partial=True)

        return db.entries

    def __load_records(self, filepath: Path) -> list:

        search_records = self.__getbib(filepath)

        self.logger.debug(f"Loaded {filepath.name} with {len(search_records)} records")

        if len(search_records) == 0:
            return []

        nr_in_bib = self.__get_nr_in_bib(filepath)
        if len(search_records) < nr_in_bib:
            self.logger.error("broken bib file (not imported all records)")
            with open(filepath) as f:
                line = f.readline()
                while line:
                    if "@" in line[:3]:
                        ID = line[line.find("{") + 1 : line.rfind(",")]
                        if ID not in [x["ID"] for x in search_records]:
                            self.logger.error(f"{ID} not imported")
                    line = f.readline()

        search_records = self.__unify_field_names(search_records, filepath.name)

        record_list = []
        for record in search_records:
            record.update(origin=f"{filepath.name}/{record['ID']}")

            # Drop empty fields
            record = {k: v for k, v in record.items() if v}

            if "status" not in record:
                record.update(status=RecordState.md_retrieved)
            elif record["status"] in [
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
                record["status"] = RecordState.md_prepared

            if "doi" in record:
                record.update(
                    doi=record["doi"].replace("http://dx.doi.org/", "").upper()
                )
                # https://www.crossref.org/blog/dois-and-matching-regular-expressions/
                d = re.match(r"^10.\d{4}/", record["doi"])
                if not d:
                    del record["doi"]

            self.logger.debug(
                f'append record {record["ID"]} ' f"\n{self.pp.pformat(record)}\n\n"
            )
            record_list.append(record)

        return record_list

    def __import_record(self, record: dict) -> dict:

        self.logger.debug(
            f'import_record {record["ID"]}: \n{self.pp.pformat(record)}\n\n'
        )

        if RecordState.md_retrieved != record["status"]:
            return record

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

        record.update(metadata_source="ORIGINAL")
        record.update(status=RecordState.md_imported)

        return record

    def apply_source_heuristics(
        self, new_record: dict, sfp: Path, original: Path
    ) -> dict:
        """Apply heuristics to identify source"""
        if str(original).endswith("_ref_list.bib"):
            new_record["source_name"] = "PDF reference section"
        if original.suffix == ".pdf":
            new_record["source_name"] = "PDF"
        data = ""
        # TODO : tbd: how we deal with misleading file extensions.
        try:
            data = original.read_text()
        except UnicodeDecodeError:
            pass
        for source in [x for x in load_custom.scripts if "heuristic" in x]:
            if source["heuristic"](original, data):
                new_record["source_name"] = source["source_name"]
                break

        return new_record

    def append_sources(self, new_record: dict):
        """Append sources"""
        sources = self.REVIEW_MANAGER.REVIEW_DATASET.load_sources()
        sources.append(new_record)
        self.logger.debug(
            f"Added infos to {self.REVIEW_MANAGER.paths['SOURCES']}:"
            f" \n{self.pp.pformat(new_record)}"
        )
        self.REVIEW_MANAGER.REVIEW_DATASET.save_sources(sources)
        return sources

    def __bibutils_convert(self, script: str, data: str) -> str:

        if "xml2bib" == script:
            script = script + " -b -w -sk "
        else:
            script = script + " -i unicode "

        client = docker.APIClient()
        try:
            container = client.create_container("bibutils", script, stdin_open=True)
        except docker.errors.ImageNotFound:
            self.logger.info("Docker image not found")
            pass
            return ""

        sock = client.attach_socket(
            container, params={"stdin": 1, "stdout": 1, "stderr": 1, "stream": 1}
        )
        client.start(container)

        sock._sock.send(data.encode())
        sock._sock.close()
        sock.close()

        client.wait(container)
        stdout = client.logs(container, stderr=False).decode()
        client.remove_container(container)

        return stdout

    def __ris2bib(self, file: Path) -> typing.List[dict]:
        with open(file) as reader:
            data = reader.read(4096)
        if "TY  - " not in data:
            self.logger.error(f"Error: Not a ris file? {file.name}")
            return []

        with open(file) as reader:
            data = reader.read()

        data = self.__bibutils_convert("ris2xml", data)
        data = self.__bibutils_convert("xml2bib", data)
        parser = BibTexParser(customization=convert_to_unicode)
        db = bibtexparser.loads(data, parser=parser)
        return db.entries

    def __end2bib(self, file: Path) -> typing.List[dict]:
        with open(file) as reader:
            data = reader.read(4096)
        if "%T " not in data:
            self.logger.error(f"Error: Not an end file? {file.name}")
            return []

        with open(file) as reader:
            data = reader.read()

        data = self.__bibutils_convert("end2xml", data)
        data = self.__bibutils_convert("xml2bib", data)
        parser = BibTexParser(customization=convert_to_unicode)
        db = bibtexparser.loads(data, parser=parser)
        return db.entries

    def __txt2bib(self, file: Path) -> typing.List[dict]:
        grobid_client.check_grobid_availability()
        with open(file) as f:
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
                grobid_client.get_grobid_url() + "/api/processCitation",
                data=options,
                headers={"Accept": "application/x-bibtex"},
            )
            ind += 1
            data = data + "\n" + r.text.replace("{-1,", "{" + str(ind) + ",")

        parser = BibTexParser(customization=convert_to_unicode)
        db = bibtexparser.loads(data, parser=parser)
        return db.entries

    def __preprocess_records(self, data: list) -> list:
        for x in data:
            # TODO: more sophisticated setting of ENTRYTYPE, ID is needed.
            # could also use simple numbers as IDs...
            x["ENTRYTYPE"] = "article"
            if "citation_key" in x.keys():
                x["ID"] = x.pop("citation_key")
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

    def __csv2bib(self, file: Path) -> typing.List[dict]:
        try:
            data = pd.read_csv(file)
        except pd.errors.ParserError:
            self.logger.error(f"Error: Not a csv file? {file.name}")
            pass
            return []
        data.columns = data.columns.str.replace(" ", "_")
        data.columns = data.columns.str.replace("-", "_")
        data = data.to_dict("records")
        data = self.__preprocess_records(data)

        return data

    def __xlsx2bib(self, file: Path) -> typing.List[dict]:
        try:
            data = pd.read_excel(file, dtype=str)  # dtype=str to avoid type casting
        except pd.errors.ParserError:
            self.logger.error(f"Error: Not an xlsx file: {file.name}")
            pass
            return []
        data.columns = data.columns.str.replace(" ", "_")
        data.columns = data.columns.str.replace("-", "_")
        data = data.to_dict("records")
        data = self.__preprocess_records(data)

        return data

    def __move_to_pdf_dir(self, filepath: Path) -> Path:
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
        grobid_client.check_grobid_availability()

        # https://github.com/kermitt2/grobid/issues/837
        r = requests.post(
            grobid_client.get_grobid_url() + "/api/processHeaderDocument",
            headers={"Accept": "application/x-bibtex"},
            params={"consolidateHeader": "1"},
            files=dict(input=open(file, "rb")),
        )

        if 200 == r.status_code:
            parser = BibTexParser(customization=convert_to_unicode)
            db = bibtexparser.loads(r.text, parser=parser)
            return db.entries
        if 500 == r.status_code:
            self.report_logger.error(f"Not a readable pdf file: {file.name}")
            self.logger.error(f"Not a readable pdf file: {file.name}")
            self.report_logger.debug(f"Grobid: {r.text}")
            self.logger.debug(f"Grobid: {r.text}")
            return []

        self.report_logger.debug(f"Status: {r.status_code}")
        self.logger.debug(f"Status: {r.status_code}")
        self.report_logger.debug(f"Response: {r.text}")
        self.logger.debug(f"Response: {r.text}")
        return []

    def __pdfRefs2bib(self, file: Path) -> typing.List[dict]:
        grobid_client.check_grobid_availability()

        r = requests.post(
            grobid_client.get_grobid_url() + "/api/processReferences",
            files=dict(input=open(file, "rb")),
            data={"consolidateHeader": "0", "consolidateCitations": "1"},
            headers={"Accept": "application/x-bibtex"},
        )
        if 200 == r.status_code:
            parser = BibTexParser(customization=convert_to_unicode)
            db = bibtexparser.loads(r.text, parser=parser)
            # Use lpad to maintain the sort order (easier to catch errors)
            for rec in db.entries:
                rec["ID"] = rec.get("ID", "").rjust(3, "0")
            return db.entries
        if 500 == r.status_code:
            self.report_logger.error(f"Not a readable pdf file: {file.name}")
            self.logger.error(f"Not a readable pdf file: {file.name}")
            self.report_logger.debug(f"Grobid: {r.text}")
            self.logger.debug(f"Grobid: {r.text}")
            return []

        self.report_logger.debug(f"Status: {r.status_code}")
        self.logger.debug(f"Status: {r.status_code}")
        self.report_logger.debug(f"Response: {r.text}")
        self.logger.debug(f"Response: {r.text}")
        return []

    def __unify_field_names(
        self, records: typing.List[dict], sfp: str
    ) -> typing.List[dict]:

        SOURCES = self.REVIEW_MANAGER.paths["SOURCES"]
        source_name = "NA"
        with open(SOURCES) as f:
            sources_df = pd.json_normalize(safe_load(f))
            sources = sources_df.to_dict("records")
            if sfp in [x["filename"] for x in sources]:
                source_name = [
                    x["source_name"] for x in sources if sfp == x["filename"]
                ].pop()

        # Note : field name corrections etc. that should be fixed before the preparation
        # stages should be source-specific (in the load_custom.scripts):
        # Note : if we do not unify (at least author/year), the IDs of imported records
        # will be AnonymousNoYear a,b,c,d,....
        if source_name != "NA":
            if source_name in [x["source_name"] for x in load_custom.scripts]:
                source_details = [
                    x for x in load_custom.scripts if source_name == x["source_name"]
                ].pop()
                if "load_script" in source_details:
                    records = source_details["load_script"](records)

        return records

    def __drop_empty_fields(self, records: typing.List[dict]) -> typing.List[dict]:
        records = [{k: v for k, v in r.items() if v is not None} for r in records]
        records = [{k: v for k, v in r.items() if v != "nan"} for r in records]
        return records

    def __set_incremental_IDs(self, records: typing.List[dict]) -> typing.List[dict]:
        # if IDs to set for some records
        if 0 != len([r for r in records if "ID" not in r]):
            for i, record in enumerate(records):
                if "ID" not in record:
                    if "UT_(Unique_WOS_ID)" in record:
                        record["ID"] = record["UT_(Unique_WOS_ID)"].replace(":", "_")
                    else:
                        record["ID"] = f"{i+1}".rjust(10, "0")
        return records

    def __fix_keys(self, records: typing.List[dict]) -> typing.List[dict]:
        for record in records:
            record = {
                re.sub("[0-9a-zA-Z_]+", "1", k.replace(" ", "_")): v
                for k, v in record.items()
            }
        return records

    def __validate_file_formats(self) -> None:
        search_files = self.get_search_files()
        for sfp in search_files:
            if not any(
                sfp.suffix == f".{ext}" for ext in self.conversion_scripts.keys()
            ):
                if not sfp.suffix == ".bib":
                    raise UnsupportedImportFormatError(sfp)
        return None

    def __convert_to_bib(self, sfpath: Path) -> Path:

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

        if ".pdf" == sfpath.suffix or ".txt" == sfpath.suffix or ".md" == sfpath.suffix:
            grobid_client.start_grobid()

        if filetype in self.conversion_scripts.keys():
            self.report_logger.info(f"Loading {filetype}: {sfpath.name}")
            self.logger.info(f"Loading {filetype}: {sfpath.name}")

            cur_tag = docker.from_env().images.get("bibutils").tags[0]
            self.report_logger.info(f"Running docker container created from {cur_tag}")
            self.logger.info(f"Running docker container created from {cur_tag}")

            self.logger.debug(
                f"Called {self.conversion_scripts[filetype].__name__}({sfpath})"
            )
            records = self.conversion_scripts[filetype](sfpath)

            records = self.__fix_keys(records)
            records = self.__set_incremental_IDs(records)

            records = self.__unify_field_names(records, corresponding_bib_file.name)
            records = self.__drop_empty_fields(records)

            if len(records) == 0:
                self.report_logger.error("No records loaded")
                self.logger.error("No records loaded")
                return corresponding_bib_file

            if corresponding_bib_file != str(sfpath) and sfpath.suffix != ".bib":
                if not corresponding_bib_file.is_file():
                    self.logger.info(
                        f"Loaded {len(records)} " f"records from {sfpath.name}"
                    )
                    db = BibDatabase()
                    db.entries = records
                    with open(corresponding_bib_file, "w") as fi:
                        fi.write(bibtexparser.dumps(db))
        else:
            self.report_logger.info(f"Filetype not recognized: {sfpath.name}")
            self.logger.info(f"Filetype not recognized: {sfpath.name}")
            return corresponding_bib_file

        return corresponding_bib_file

    def get_unique_id(self, ID: str, ID_list: typing.List[str]) -> str:

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
        self, filename: Path, old_string: str, new_string: str
    ) -> None:
        new_file_lines = []
        with open(filename) as f:
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
        with open(filename, "w") as f:
            for s in new_file_lines:
                f.write(s)
        return

    def resolve_non_unique_IDs(self, corresponding_bib_file: Path) -> None:

        with open(corresponding_bib_file) as bibtex_file:
            db = BibTexParser(
                customization=convert_to_unicode,
                ignore_nonstandard_types=True,
                common_strings=True,
            ).parse_file(bibtex_file, partial=True)

        IDs_to_update = []
        current_IDs = [x["ID"] for x in db.entries]
        for record in db.entries:
            if len([x for x in current_IDs if x == record["ID"]]) > 1:
                new_id = self.get_unique_id(record["ID"], current_IDs)
                IDs_to_update.append([record["ID"], new_id])
                current_IDs.append(new_id)

        if len(IDs_to_update) > 0:
            self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(str(corresponding_bib_file))
            self.REVIEW_MANAGER.create_commit(
                f"Save original search file: {corresponding_bib_file.name}"
            )

            for old_id, new_id in IDs_to_update:
                self.logger.info(
                    f"Resolve ID to ensure unique origins: {old_id} -> {new_id}"
                )
                self.report_logger.info(
                    f"Resolve ID to ensure unique origins: {old_id} -> {new_id}"
                )
                self.__inplace_change_second(
                    corresponding_bib_file, f"{old_id},", f"{new_id},"
                )
            # with open(corresponding_bib_file, "w") as fi:
            #     fi.write(bibtexparser.dumps(db))
            self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(str(corresponding_bib_file))
            self.REVIEW_MANAGER.create_commit(
                f"Resolve non-unique IDs in {corresponding_bib_file.name}"
            )

        return

    def __add_sources(self) -> None:
        self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
            str(self.REVIEW_MANAGER.paths["SOURCES_RELATIVE"])
        )
        return

    def __get_currently_imported_origin_list(self) -> list:
        record_header_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_header_list()
        imported_origins = [x[1].split(";") for x in record_header_list]
        imported_origins = list(itertools.chain(*imported_origins))
        return imported_origins

    def __get_nr_in_bib(self, file_path: Path) -> int:

        number_in_bib = 0
        with open(file_path) as f:
            line = f.readline()
            while line:
                # Note: the '﻿' occured in some bibtex files
                # (e.g., Publish or Perish exports)
                if "@" in line[:3]:
                    if "@comment" not in line[:10].lower():
                        number_in_bib += 1
                line = f.readline()

        return number_in_bib

    def main(self, keep_ids: bool = False) -> None:

        saved_args = locals()
        if not keep_ids:
            del saved_args["keep_ids"]

        self.REVIEW_MANAGER.REVIEW_DATASET.check_sources()
        self.__add_sources()
        for search_file in self.get_search_files():

            corresponding_bib_file = self.__convert_to_bib(search_file)
            if not corresponding_bib_file.is_file():
                continue

            imported_origins = self.__get_currently_imported_origin_list()
            len_before = len(imported_origins)

            self.report_logger.info(f"Load {search_file.name}")
            self.logger.info(f"Load {search_file.name}")
            saved_args["file"] = search_file.name

            self.resolve_non_unique_IDs(corresponding_bib_file)

            search_records = self.__load_records(corresponding_bib_file)
            nr_search_recs = len(search_records)

            nr_in_bib = self.__get_nr_in_bib(corresponding_bib_file)
            if nr_in_bib != nr_search_recs:
                self.logger.error(f"ERROR in bib file:  {corresponding_bib_file}")

            search_records = [
                x for x in search_records if x["origin"] not in imported_origins
            ]
            to_import = len(search_records)
            if 0 == to_import:
                continue

            for sr in search_records:
                sr = self.__import_record(sr)

            self.logger.info("Save records to references.bib")
            records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records(init=True)
            records += search_records
            self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)

            # TBD: does the following create errors!?
            # REVIEW_MANAGER.save_record_list_by_ID(search_records, append_new=True)

            if not keep_ids:
                self.logger.info("Set IDs")
                records = self.REVIEW_MANAGER.REVIEW_DATASET.set_IDs(
                    records, selected_IDs=[x["ID"] for x in search_records]
                )

            self.logger.info("Add changes and create commit")
            self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
                str(self.REVIEW_MANAGER.paths["SOURCES"])
            )
            self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(str(corresponding_bib_file))
            self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(str(search_file))

            self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
            self.REVIEW_MANAGER.create_commit(
                f"Load {saved_args['file']}", saved_args=saved_args
            )

            imported_origins = self.__get_currently_imported_origin_list()
            len_after = len(imported_origins)
            imported = len_after - len_before

            if imported != to_import:
                self.logger.error(
                    f"PROBLEM: delta: {to_import - imported} "
                    "records missing (negative: too much)"
                )
                self.logger.error(f"len_before: {len_before}")
                self.logger.error(f"Records not yet imported: {to_import}")
                self.logger.error(f"len_after: {len_after}")
                self.logger.error([x["ID"] for x in search_records])

            print("\n")

        return

    def run(self):
        self.REVIEW_MANAGER.run_process(self, self.keep_ids)


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


if __name__ == "__main__":
    pass
