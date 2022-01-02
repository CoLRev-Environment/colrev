#! /usr/bin/env python
import itertools
import logging
import pprint
import re
import shutil
import typing
from pathlib import Path

import bibtexparser
import pandas as pd
import requests
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

import docker
from colrev_core import grobid_client
from colrev_core.review_manager import RecordState
from colrev_core.review_manager import ReviewManager

pp = pprint.PrettyPrinter(indent=4, width=140)

report_logger = logging.getLogger("colrev_core_report")
logger = logging.getLogger("colrev_core")


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


def get_search_files(REVIEW_MANAGER, restrict: list = None) -> typing.List[Path]:

    supported_extensions = [
        "bib",
        "ris",
        "enl",
        "end",
        "txt",
        "csv",
        "txt",
        "xlsx",
        "xls",
        "pdf",
    ]

    if restrict:
        supported_extensions = restrict

    search_dir = REVIEW_MANAGER.paths["SEARCHDIR"]

    if not search_dir.is_dir():
        raise NoSearchResultsAvailableError()

    files = [
        f
        for f_ in [search_dir.glob(f"*.{e}") for e in supported_extensions]
        for f in f_
    ]

    return files


def getbib(file: Path) -> BibDatabase:
    with open(file) as bibtex_file:
        contents = bibtex_file.read()
        bib_r = re.compile(r"@.*{.*,", re.M)
        if len(re.findall(bib_r, contents)) == 0:
            logger.error(f"Not a bib file? {file.name}")
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

    return db


def load_records(filepath: Path) -> list:

    search_db = getbib(filepath)

    logger.debug(f"Loaded {filepath.name} with {len(search_db.entries)} records")

    if search_db is None:
        return []

    from colrev_core import status

    nr_in_bib = status.get_nr_in_bib(filepath)
    if len(search_db.entries) < nr_in_bib:
        logger.error("broken bib file (not imported all records)")
        with open(filepath) as f:
            line = f.readline()
            while line:
                if "@" in line[:3]:
                    ID = line[line.find("{") + 1 : line.rfind(",")]
                    if ID not in [x["ID"] for x in search_db.entries]:
                        logger.error(f"{ID} not imported")
                line = f.readline()

    record_list = []
    for record in search_db.entries:
        record.update(origin=f"{filepath.name}/{record['ID']}")

        # Drop empty fields
        record = {k: v for k, v in record.items() if v}

        record.update(status=RecordState.md_retrieved)
        logger.debug(f'append record {record["ID"]} ' f"\n{pp.pformat(record)}\n\n")
        record_list.append(record)

    return record_list


def import_record(record: dict) -> dict:

    logger.debug(f'import_record {record["ID"]}: \n{pp.pformat(record)}\n\n')

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

    record.update(metadata_source="ORIGINAL")
    record.update(status=RecordState.md_imported)

    return record


def source_heuristics(search_file: Path) -> str:
    if str(search_file).endswith("_ref_list.bib"):
        return "PDF reference section"
    if search_file.suffix == ".pdf":
        return "PDF"
    with open(search_file) as f:
        for line in f.readlines():
            if (
                "bibsource = {dblp computer science"
                + " bibliography, https://dblp.org}"
                in line
            ):
                return "DBLP"
            if "UT_(Unique_WOS_ID) = {WOS:" in line:
                return "WebOfScience"

    return ""


def append_sources(REVIEW_MANAGER, new_record: dict) -> None:
    sources = REVIEW_MANAGER.load_sources()
    sources.append(new_record)
    logger.debug(
        f"Added infos to {REVIEW_MANAGER.paths['SOURCES']}:"
        f" \n{pp.pformat(new_record)}"
    )
    REVIEW_MANAGER.save_sources(sources)
    return


def bibutils_convert(script: str, data: str) -> str:

    if "xml2bib" == script:
        script = script + " -b -w -sk "
    else:
        script = script + " -i unicode "

    client = docker.APIClient()
    try:
        container = client.create_container("bibutils", script, stdin_open=True)
    except docker.errors.ImageNotFound:
        logger.info("Docker image not found")
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


def ris2bib(file: Path) -> BibDatabase:
    with open(file) as reader:
        data = reader.read(4096)
    if "TY  - " not in data:
        logger.error(f"Error: Not a ris file? {file.name}")
        return None

    with open(file) as reader:
        data = reader.read()

    data = bibutils_convert("ris2xml", data)
    data = bibutils_convert("xml2bib", data)
    parser = BibTexParser(customization=convert_to_unicode)
    db = bibtexparser.loads(data, parser=parser)
    return db


def end2bib(file: Path) -> BibDatabase:
    with open(file) as reader:
        data = reader.read(4096)
    if "%T " not in data:
        logger.error(f"Error: Not an end file? {file.name}")
        return None

    with open(file) as reader:
        data = reader.read()

    data = bibutils_convert("end2xml", data)
    data = bibutils_convert("xml2bib", data)
    parser = BibTexParser(customization=convert_to_unicode)
    db = bibtexparser.loads(data, parser=parser)
    return db


def txt2bib(file: Path) -> BibDatabase:
    grobid_client.check_grobid_availability()
    with open(file) as f:
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
    return db


def preprocess_records(data: list) -> list:
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
        if "no Number-of-Cited-References" == x.get("number_of_cited_references", "NA"):
            del x["number_of_cited_references"]
        if "no file" in x.get("file_name", "NA"):
            del x["file_name"]
        if "times_cited" == x.get("times_cited", "NA"):
            del x["times_cited"]

    return data


def csv2bib(file: Path) -> BibDatabase:
    try:
        data = pd.read_csv(file)
    except pd.errors.ParserError:
        logger.error(f"Error: Not a csv file? {file.name}")
        pass
        return None
    data.columns = data.columns.str.replace(" ", "_")
    data.columns = data.columns.str.replace("-", "_")
    data = data.to_dict("records")
    data = preprocess_records(data)

    db = BibDatabase()
    db.entries = data
    return db


def xlsx2bib(file: Path) -> BibDatabase:
    try:
        data = pd.read_excel(file, dtype=str)  # dtype=str to avoid type casting
    except pd.errors.ParserError:
        logger.error(f"Error: Not an xlsx file: {file.name}")
        pass
        return None
    data.columns = data.columns.str.replace(" ", "_")
    data.columns = data.columns.str.replace("-", "_")
    data = data.to_dict("records")
    data = preprocess_records(data)

    db = BibDatabase()
    db.entries = data
    return db


def move_to_pdf_dir(REVIEW_MANAGER, filepath: Path) -> Path:
    PDF_DIRECTORY = REVIEW_MANAGER.paths["PDF_DIRECTORY"]
    # We should avoid re-extracting data from PDFs repeatedly (e.g., status.py)
    Path(PDF_DIRECTORY).mkdir(exist_ok=True)
    new_fp = Path(PDF_DIRECTORY) / filepath.name
    shutil.move(str(filepath), new_fp)
    return new_fp


# curl -v --form input=@./profit.pdf localhost:8070/api/processHeaderDocument
# curl -v --form input=@./thefile.pdf -H "Accept: application/x-bibtex"
# -d "consolidateHeader=0" localhost:8070/api/processHeaderDocument
def pdf2bib(file: Path) -> BibDatabase:
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
        return db
    if 500 == r.status_code:
        report_logger.error(f"Not a readable pdf file: {file.name}")
        logger.error(f"Not a readable pdf file: {file.name}")
        report_logger.debug(f"Grobid: {r.text}")
        logger.debug(f"Grobid: {r.text}")
        return None

    report_logger.debug(f"Status: {r.status_code}")
    logger.debug(f"Status: {r.status_code}")
    report_logger.debug(f"Response: {r.text}")
    logger.debug(f"Response: {r.text}")
    return None


def pdfRefs2bib(file: Path) -> BibDatabase:
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
        return db
    if 500 == r.status_code:
        report_logger.error(f"Not a readable pdf file: {file.name}")
        logger.error(f"Not a readable pdf file: {file.name}")
        report_logger.debug(f"Grobid: {r.text}")
        logger.debug(f"Grobid: {r.text}")
        return None

    report_logger.debug(f"Status: {r.status_code}")
    logger.debug(f"Status: {r.status_code}")
    report_logger.debug(f"Response: {r.text}")
    logger.debug(f"Response: {r.text}")
    return None


def unify_field_names(db: BibDatabase) -> BibDatabase:

    # At some point, this may depend on the source (database)
    # This should be available in the sources.
    # Note : if we do not unify (at least the author/year), the IDs of imported records
    # will be AnonymousNoYear a,b,c,d,....
    for record in db.entries:
        if "Publication_Type" in record:
            if "J" == record["Publication_Type"]:
                record["ENTRYTYPE"] = "article"
            if "C" == record["Publication_Type"]:
                record["ENTRYTYPE"] = "inproceedings"
            del record["Publication_Type"]
        if "Author_Full_Names" in record:
            record["author"] = record["Author_Full_Names"]
            del record["Author_Full_Names"]
        if "Publication_Year" in record:
            record["year"] = record["Publication_Year"]
            # match =re.match(r'([1-3][0-9]{3})', record['year'])
            # if match is not None:
            #     record['year'] = match.group(1)
            del record["Publication_Year"]
        if "Start_Page" in record and "End_Page" in record:
            if record["Start_Page"] != "nan" and record["End_Page"] != "nan":
                record["pages"] = record["Start_Page"] + "--" + record["End_Page"]
                record["pages"] = record["pages"].replace(".0", "")
                del record["Start_Page"]
                del record["End_Page"]

    return db


def drop_empty_fields(db: BibDatabase) -> BibDatabase:
    db.entries = [{k: v for k, v in r.items() if v is not None} for r in db.entries]
    db.entries = [{k: v for k, v in r.items() if v != "nan"} for r in db.entries]
    return db


def set_incremental_IDs(db: BibDatabase) -> BibDatabase:

    if 0 == len([r for r in db.entries if "ID" not in r]):
        # IDs set for all records
        return db

    for i, record in enumerate(db.entries):
        if "ID" not in record:
            if "UT_(Unique_WOS_ID)" in record:
                record["ID"] = record["UT_(Unique_WOS_ID)"].replace(":", "_")
            else:
                record["ID"] = f"{i+1}".rjust(10, "0")

    return db


def fix_keys(db: BibDatabase) -> BibDatabase:
    for record in db.entries:
        record = {
            re.sub("[0-9a-zA-Z_]+", "1", k.replace(" ", "_")): v
            for k, v in record.items()
        }
    return db


conversion_scripts = {
    "ris": ris2bib,
    "enl": end2bib,
    "end": end2bib,
    "txt": txt2bib,
    "csv": csv2bib,
    "xlsx": xlsx2bib,
    "xls": xlsx2bib,
    "pdf": pdf2bib,
    "pdf_refs": pdfRefs2bib,
}


def validate_file_formats(REVIEW_MANAGER) -> None:
    search_files = get_search_files(REVIEW_MANAGER)
    for sfp in search_files:
        if not any(sfp.suffix == f".{ext}" for ext in conversion_scripts.keys()):
            if not sfp.suffix == ".bib":
                raise UnsupportedImportFormatError(sfp)
    return None


def convert_to_bib(REVIEW_MANAGER, sfpath: Path) -> Path:

    corresponding_bib_file = sfpath.with_suffix(".bib")

    if corresponding_bib_file.is_file():
        return corresponding_bib_file

    if not any(sfpath.suffix == f".{ext}" for ext in conversion_scripts.keys()):
        raise UnsupportedImportFormatError(sfpath)

    filetype = sfpath.suffix.replace(".", "")
    if "pdf" == filetype:
        if str(sfpath).endswith("_ref_list.pdf"):
            filetype = "pdf_refs"

    if ".pdf" == sfpath.suffix or ".txt" in sfpath.suffix:
        grobid_client.start_grobid()

    if filetype in conversion_scripts.keys():
        report_logger.info(f"Loading {filetype}: {sfpath.name}")
        logger.info(f"Loading {filetype}: {sfpath.name}")

        cur_tag = docker.from_env().images.get("bibutils").tags[0]
        report_logger.info(f"Running docker container created from {cur_tag}")
        logger.info(f"Running docker container created from {cur_tag}")

        logger.debug(f"Called {conversion_scripts[filetype].__name__}({sfpath})")
        db = conversion_scripts[filetype](sfpath)

        db = fix_keys(db)
        db = set_incremental_IDs(db)
        db = unify_field_names(db)
        db = drop_empty_fields(db)

        git_repo = REVIEW_MANAGER.get_repo()
        if db is None:
            report_logger.error("No records loaded")
            logger.error("No records loaded")
            return corresponding_bib_file

        elif "pdf" == filetype:
            new_fp = move_to_pdf_dir(REVIEW_MANAGER, sfpath)
            new_record = {
                "filename": corresponding_bib_file.name,
                "search_type": "OTHER",
                "source_name": "PDF (metadata)",
                "source_url": new_fp,
                "search_parameters": "NA",
                "comment": "Extracted with GROBID",
            }
            append_sources(REVIEW_MANAGER, new_record)
            git_repo.index.add([new_fp])

        elif "pdf_refs" == filetype:
            new_fp = move_to_pdf_dir(REVIEW_MANAGER, sfpath)
            new_record = {
                "filename": corresponding_bib_file.name,
                "search_type": "BACK_CIT",
                "source_name": "PDF backward search",
                "source_url": new_fp,
                "search_parameters": "NA",
                "comment": "Extracted with GROBID",
            }
            append_sources(REVIEW_MANAGER, new_record)
            git_repo.index.add([new_fp])

        if corresponding_bib_file != str(sfpath) and sfpath.suffix != ".bib":
            if not corresponding_bib_file.is_file():
                logger.info(f"Loaded {len(db.entries)} " f"records from {sfpath.name}")
                with open(corresponding_bib_file, "w") as fi:
                    fi.write(bibtexparser.dumps(db))
    else:
        report_logger.info(f"Filetype not recognized: {sfpath.name}")
        logger.info(f"Filetype not recognized: {sfpath.name}")
        return corresponding_bib_file

    return corresponding_bib_file


def check_sources(REVIEW_MANAGER) -> None:
    from colrev_core import review_manager

    review_manager.check_sources(REVIEW_MANAGER)
    git_repo = REVIEW_MANAGER.get_repo()
    git_repo.index.add([str(REVIEW_MANAGER.paths["SOURCES_RELATIVE"])])
    return


def get_currently_imported_origin_list(REVIEW_MANAGER) -> list:
    record_header_list = REVIEW_MANAGER.get_record_header_list()
    imported_origins = [x[1].split(";") for x in record_header_list]
    imported_origins = list(itertools.chain(*imported_origins))

    return imported_origins


def main(REVIEW_MANAGER: ReviewManager, keep_ids: bool = False) -> None:

    saved_args = locals()
    if not keep_ids:
        del saved_args["keep_ids"]

    check_sources(REVIEW_MANAGER)
    for search_file in get_search_files(REVIEW_MANAGER):

        corresponding_bib_file = convert_to_bib(REVIEW_MANAGER, search_file)
        if not corresponding_bib_file.is_file():
            continue

        imported_origins = get_currently_imported_origin_list(REVIEW_MANAGER)
        len_before = len(imported_origins)

        report_logger.info(f"Load {search_file.name}")
        logger.info(f"Load {search_file.name}")
        saved_args["file"] = search_file.name

        search_records = load_records(corresponding_bib_file)
        to_import = len(search_records)

        from colrev_core import status

        nr_in_bib = status.get_nr_in_bib(corresponding_bib_file)
        if nr_in_bib != to_import:
            print(f"ERROR in bib file:  {corresponding_bib_file}")

        search_records = [
            x for x in search_records if x["origin"] not in imported_origins
        ]
        nr_not_imported = len(search_records)
        if 0 == nr_not_imported:
            continue

        for sr in search_records:
            sr = import_record(sr)

        bib_db = REVIEW_MANAGER.load_bib_db(init=True)
        bib_db.entries += search_records
        REVIEW_MANAGER.save_bib_db(bib_db)

        # TBD: does the following create errors!?
        # REVIEW_MANAGER.save_record_list_by_ID(search_records, append_new=True)

        if not keep_ids:
            bib_db = REVIEW_MANAGER.set_IDs(
                bib_db, selected_IDs=[x["ID"] for x in search_records]
            )

        git_repo = REVIEW_MANAGER.get_repo()
        git_repo.index.add([str(REVIEW_MANAGER.paths["SOURCES"])])
        git_repo.index.add([str(corresponding_bib_file)])
        git_repo.index.add([str(search_file)])
        REVIEW_MANAGER.create_commit(
            f"Import {saved_args['file']}", saved_args=saved_args
        )

        imported_origins = get_currently_imported_origin_list(REVIEW_MANAGER)
        len_after = len(imported_origins)
        imported = len_after - len_before
        if (imported != to_import) or (nr_in_bib != to_import):
            logger.error(
                f"PROBLEM: delta: {to_import - imported} "
                "records missing (negative: too much)"
            )
            logger.error(f"len_before: {len_before}")
            logger.error(f"Loaded {to_import} records")
            logger.error(f"Records not yet imported: {nr_not_imported}")
            logger.error(f"len_after: {len_after}")
            print([x["ID"] for x in search_records])

        print("\n")

    return
