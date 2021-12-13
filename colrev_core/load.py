#! /usr/bin/env python
import itertools
import logging
import multiprocessing as mp
import pprint
import re
import shutil
import typing
from itertools import chain
from pathlib import Path

import bibtexparser
import pandas as pd
import requests
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from tqdm.contrib.concurrent import process_map

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


def get_search_files(restrict: list = None) -> typing.List[Path]:

    supported_extensions = [
        "ris",
        "bib",
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

    # TODO: replace by REVIEW_MANAGER.paths['SEARCHDIR']
    search_dir = Path("search")

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
        bib_r = re.compile(r"^@.*{.*,", re.M)
        if len(re.findall(bib_r, contents)) == 0:
            logger.error(f"Not a bib file? {file.name}")
            db = None
        if "Early Access Date" in contents:
            logger.error(
                "Replace Early Access Date in bibfile before " f"loading! {file.name}"
            )
            return None

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

    record_list = []
    for record in search_db.entries:
        record.update(origin=f"{filepath.name}/{record['ID']}")

        # Drop empty fields
        record = {k: v for k, v in record.items() if v}

        record.update(status=RecordState.md_retrieved)
        logger.debug(f'append record {record["ID"]} ' f"\n{pp.pformat(record)}\n\n")
        record_list.append(record)

    logger.debug(f"Thereof {len(record_list)} new records (not yet imported)")

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


def append_search_details(REVIEW_MANAGER, new_record: dict) -> None:
    search_details = REVIEW_MANAGER.load_search_details()
    search_details.append(new_record)
    logger.debug(
        f"Added infos to {REVIEW_MANAGER.paths['SEARCH_DETAILS']}:"
        f" \n{pp.pformat(new_record)}"
    )
    REVIEW_MANAGER.save_search_details(search_details)
    return


def bibutils_convert(script: str, data: str) -> str:

    assert script in ["ris2xml", "end2xml", "endx2xml", "isi2xml", "med2xml", "xml2bib"]

    if "xml2bib" == script:
        script = script + " -b -w -sk "
    else:
        script = script + " -i unicode "

    client = docker.APIClient()
    try:
        cur_tag = docker.from_env().images.get("bibutils").tags[0]
        report_logger.info(f"Running docker container created from {cur_tag}")
        logger.info(f"Running docker container created from {cur_tag}")
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
    # status = client.wait(container)
    # status_code = status['StatusCode']
    stdout = client.logs(container, stderr=False).decode()
    # stderr = client.logs(container, stdout=False).decode()

    client.remove_container(container)

    # logger.debug('Exit: {}'.format(status_code))
    # logger.debug('log stdout: {}'.format(stdout))
    # logger.debug('log stderr: {}'.format(stderr))

    # TODO: else: raise error!

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


def move_to_pdf_dir(filepath: Path) -> Path:
    # TODO: replace by REVIEW_MANAGER.paths['PDF_DIRECTORY']
    PDF_DIRECTORY = "pdfs"
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
    # This should be available in the search_details.
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
    "end": end2bib,
    "txt": txt2bib,
    "csv": csv2bib,
    "xlsx": xlsx2bib,
    "xls": xlsx2bib,
    "pdf": pdf2bib,
    "pdf_refs": pdfRefs2bib,
}


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


def validate_file_formats() -> None:
    search_files = get_search_files()
    for sfp in search_files:
        if not any(sfp.suffix == f".{ext}" for ext in conversion_scripts.keys()):
            if not sfp.suffix == ".bib":
                raise UnsupportedImportFormatError(sfp)
    return None


def convert_to_bib(REVIEW_MANAGER, search_files: list) -> None:

    for sfpath in search_files:
        corresponding_bib_file = sfpath.with_suffix(".bib")

        if corresponding_bib_file.is_file():
            continue

        if not any(sfpath.suffix == f".{ext}" for ext in conversion_scripts.keys()):
            raise UnsupportedImportFormatError(sfpath)

        filetype = sfpath.suffix.replace(".", "")
        if "pdf" == filetype:
            if str(sfpath).endswith("_ref_list.pdf"):
                filetype = "pdf_refs"

        if filetype in conversion_scripts.keys():
            report_logger.info(f"Loading {filetype}: {sfpath.name}")
            logger.info(f"Loading {filetype}: {sfpath.name}")
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
                continue
            elif "pdf" == filetype:
                new_fp = move_to_pdf_dir(sfpath)
                new_record = {
                    "filename": corresponding_bib_file.name,
                    "search_type": "OTHER",
                    "source_name": "PDF (metadata)",
                    "source_url": new_fp,
                    "search_parameters": "NA",
                    "comment": "Extracted with GROBID",
                }
                append_search_details(REVIEW_MANAGER, new_record)
                git_repo.index.add([new_fp])

            elif "pdf_refs" == filetype:
                new_fp = move_to_pdf_dir(sfpath)
                new_record = {
                    "filename": corresponding_bib_file.name,
                    "search_type": "BACK_CIT",
                    "source_name": "PDF backward search",
                    "source_url": new_fp,
                    "search_parameters": "NA",
                    "comment": "Extracted with GROBID",
                }
                append_search_details(REVIEW_MANAGER, new_record)
                git_repo.index.add([new_fp])
            # print(corresponding_bib_file)
            # print(str(sfpath))
            if corresponding_bib_file != str(sfpath) and sfpath.suffix != ".bib":
                if not corresponding_bib_file.is_file():
                    logger.info(
                        f"Loaded {len(db.entries)} " f"records from {sfpath.name}"
                    )
                    with open(corresponding_bib_file, "w") as fi:
                        fi.write(bibtexparser.dumps(db))
        else:
            report_logger.info(f"Filetype not recognized: {sfpath.name}")
            logger.info(f"Filetype not recognized: {sfpath.name}")
            continue

    return


def convert_non_bib_search_files(REVIEW_MANAGER) -> None:
    search_files = get_search_files()
    if any(".pdf" in x.suffix for x in search_files) or any(
        ".txt" in x.suffix for x in search_files
    ):
        grobid_client.start_grobid()

    # Note: after the search_result_file (non-bib formats) has been loaded
    # for the first time, we save a corresponding bib_file, which allows for
    # more efficient status checking, tracing, and validation.
    # This also applies to the colrev_hooks and is particularly
    # relevant for pdf sources that require long processing times.
    convert_to_bib(REVIEW_MANAGER, search_files)
    git_repo = REVIEW_MANAGER.get_repo()
    search_files = get_search_files()
    git_repo.index.add([str(x) for x in search_files])
    return


def order_bib_file(REVIEW_MANAGER) -> None:
    bib_db = REVIEW_MANAGER.load_bib_db()
    bib_db.entries = sorted(bib_db.entries, key=lambda d: d["ID"])
    REVIEW_MANAGER.save_bib_db(bib_db)
    git_repo = REVIEW_MANAGER.get_repo()
    git_repo.index.add([str(REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"])])
    return


def check_search_details(REVIEW_MANAGER) -> None:
    from colrev_core import review_manager

    review_manager.check_search_details(REVIEW_MANAGER)
    git_repo = REVIEW_MANAGER.get_repo()
    git_repo.index.add([str(REVIEW_MANAGER.paths["SEARCH_DETAILS_RELATIVE"])])
    return


def get_data(REVIEW_MANAGER) -> dict:

    record_header_list = REVIEW_MANAGER.get_record_header_list()
    imported_origins = [x[1].split(";") for x in record_header_list]
    imported_origins = list(itertools.chain(*imported_origins))

    search_files = get_search_files(restrict=["bib"])
    load_pool = mp.Pool(REVIEW_MANAGER.config["CPUS"])
    additional_records = load_pool.map(load_records, search_files)
    load_pool.close()
    load_pool.join()

    additional_records = list(chain(*additional_records))

    additional_records = [
        x for x in additional_records if x["origin"] not in imported_origins
    ]

    load_data = {"nr_tasks": len(additional_records), "items": additional_records}
    logger.debug(pp.pformat(load_data))

    return load_data


def batch(iterable, n=1):
    it_len = len(iterable)
    for ndx in range(0, it_len, n):
        yield iterable[ndx : min(ndx + n, it_len)]


def main(REVIEW_MANAGER: ReviewManager, keep_ids: bool = False) -> None:

    saved_args = locals()
    if not keep_ids:
        del saved_args["keep_ids"]

    convert_non_bib_search_files(REVIEW_MANAGER)
    check_search_details(REVIEW_MANAGER)

    logger.info("Import")
    BATCH_SIZE = REVIEW_MANAGER.config["BATCH_SIZE"]
    logger.info(f"Batch size: {BATCH_SIZE}")

    load_data = get_data(REVIEW_MANAGER)

    i = 1
    for load_batch in batch(load_data["items"], BATCH_SIZE):

        logger.info(f"Batch {i}")
        i += 1

        load_batch = process_map(
            import_record, load_batch, max_workers=REVIEW_MANAGER.config["CPUS"]
        )

        REVIEW_MANAGER.save_record_list_by_ID(load_batch, append_new=True)

        if not keep_ids:
            REVIEW_MANAGER.set_IDs(selected_IDs=[x["ID"] for x in load_batch])

        order_bib_file(REVIEW_MANAGER)

        REVIEW_MANAGER.create_commit("Import search results", saved_args=saved_args)

    if 1 == i:
        logger.info("No records to load")

    return
