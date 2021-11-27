#! /usr/bin/env python
import itertools
import logging
import multiprocessing as mp
import os
import pprint
import re
import shutil
from datetime import datetime
from itertools import chain

import bibtexparser
import git
import pandas as pd
import requests
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

import docker
from review_template import grobid_client
from review_template import repo_setup
from review_template import utils

logging.getLogger("bibtexparser").setLevel(logging.CRITICAL)

SEARCH_DETAILS = repo_setup.paths["SEARCH_DETAILS"]
MAIN_REFERENCES = repo_setup.paths["MAIN_REFERENCES"]
BATCH_SIZE = repo_setup.config["BATCH_SIZE"]
pp = pprint.PrettyPrinter(indent=4, width=140)

search_type_opts = ["DB", "TOC", "BACK_CIT", "FORW_CIT", "LOCAL_PAPER_INDEX", "OTHER"]


def get_search_files(restrict: list = None) -> None:

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

    files = []
    search_dir = os.path.join(os.getcwd(), "search/")
    files = [
        os.path.join(search_dir, x)
        for x in os.listdir(search_dir)
        if any(x.endswith(ext) for ext in supported_extensions)
    ]
    return files


def get_imported_record_links() -> list:

    imported_record_links = []
    try:
        imported_record_links = pd.read_csv("imported_record_links.csv", header=None)
        imported_record_links = imported_record_links[
            imported_record_links.columns[0]
        ].tolist()
    except pd.errors.EmptyDataError:
        # ok if no search results have been imported before
        if not os.path.exists(MAIN_REFERENCES):
            pass

    return imported_record_links


def load_records(filepath: str) -> list:

    imported_record_links = get_imported_record_links()

    search_db = getbib(filepath)

    logging.debug(f"Loaded {filepath} with {len(search_db.entries)} records")

    if search_db is None:
        return []

    search_file = os.path.basename(filepath)
    record_list = []
    for record in search_db.entries:
        record["origin"] = search_file + "/" + record["ID"]
        if record["origin"] in imported_record_links:
            logging.debug(f'skipped record {record["ID"]} (already imported)')
            continue

        # Drop empty fields
        record = {k: v for k, v in record.items() if v}

        record.update(rev_status="retrieved")
        record.update(md_status="retrieved")
        logging.debug(f'append record {record["ID"]} ' f"\n{pp.pformat(record)}\n\n")
        record_list.append(record)

    logging.debug(f"Thereof {len(record_list)} new records (not yet imported)")

    return record_list


def save_imported_record_links(bib_db: BibDatabase) -> None:
    imported_record_links = [
        x["origin"].split(";") for x in bib_db.entries if "origin" in x
    ]
    imported_record_links = list(itertools.chain(*imported_record_links))

    with open("imported_record_links.csv", "a") as fd:
        for el in imported_record_links:
            fd.write(el + "\n")
    return


def import_record(record: dict) -> dict:

    logging.debug(f'import_record {record["ID"]}: \n{pp.pformat(record)}\n\n')

    if "retrieved" != record["md_status"]:
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

    record.update(md_status="imported")

    return record


def source_heuristics(search_file: str) -> str:
    if search_file.endswith("_ref_list.bib"):
        return "PDF reference section"
    if search_file.endswith(".pdf"):
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

    return None


def append_search_details(new_record: dict) -> None:
    search_details = utils.load_search_details()
    search_details.append(new_record)
    logging.debug(f"Added infos to {SEARCH_DETAILS}:" f" \n{pp.pformat(new_record)}")
    utils.save_search_details(search_details)
    return


def rename_search_files(search_files: list) -> list:
    ret_list = []

    search_details = utils.load_search_details()
    search_dir = os.path.join(os.getcwd(), "search/")
    index_paths = [os.path.join(search_dir, x["filename"]) for x in search_details]

    date_regex = r"^\d{4}-\d{2}-\d{2}"
    for search_file in search_files:
        if (
            re.search(date_regex, os.path.basename(search_file))
            or search_file in index_paths
        ):
            ret_list.append(search_file)
        else:
            new_filename = os.path.join(
                os.path.dirname(search_file),
                datetime.today().strftime("%Y-%m-%d-")
                + os.path.basename(search_file).replace(" ", "_"),
            )
            os.rename(search_file, new_filename)
            ret_list.append(new_filename)
    return ret_list


class SearchDetailsMissingError(Exception):
    def __init__(
        self,
        search_results_path,
    ):
        self.search_results_path = search_results_path
        self.message = (
            "Search results path "
            + f"({os.path.basename(self.search_results_path)}) "
            + "is not in search_details.yaml"
        )
        super().__init__(self.message)


def check_search_details(search_files: list):
    search_details = utils.load_search_details()
    for search_file in search_files:
        if os.path.basename(search_file) not in [x["filename"] for x in search_details]:
            raise SearchDetailsMissingError(search_file)
    return


def load_all_records() -> list:

    bib_db = utils.load_main_refs(mod_check=True, init=True)
    save_imported_record_links(bib_db)

    search_files = get_search_files()
    if any(".pdf" in x for x in search_files) or any(".txt" in x for x in search_files):
        grobid_client.start_grobid()
    search_files = rename_search_files(search_files)
    # Note: after the search_result_file (non-bib formats) has been loaded
    # for the first time, we save a corresponding bib_file, which allows for
    # more efficient status checking, tracing, and validation.
    # This also applies to the pipeline_validation_hooks and is particularly
    # relevant for pdf sources that require long processing times.
    convert_to_bib(search_files)

    search_files = get_search_files(restrict=["bib"])
    logging.debug(f"Search_files (bib, after conversion): {search_files}")
    check_search_details(search_files)

    load_pool = mp.Pool(repo_setup.config["CPUS"])
    additional_records = load_pool.map(load_records, search_files)
    len_lists = [len(additional_record) for additional_record in additional_records]
    logging.debug(f"Length of additional_records lists: {len_lists}")
    load_pool.close()
    load_pool.join()

    additional_records = list(chain(bib_db.entries, *additional_records))

    if os.path.exists("imported_record_links.csv"):
        os.remove("imported_record_links.csv")

    return additional_records


def bibutils_convert(script: str, data: str) -> str:

    assert script in ["ris2xml", "end2xml", "endx2xml", "isi2xml", "med2xml", "xml2bib"]

    if "xml2bib" == script:
        script = script + " -b -w -sk "
    else:
        script = script + " -i unicode "

    if isinstance(data, str):
        data = data.encode()

    client = docker.APIClient()
    try:
        cur_tag = docker.from_env().images.get("bibutils").tags[0]
        logging.info(f"Running docker container created from {cur_tag}")
        container = client.create_container("bibutils", script, stdin_open=True)
    except docker.errors.ImageNotFound:
        logging.info("Docker image not found")
        return ""
        pass

    sock = client.attach_socket(
        container, params={"stdin": 1, "stdout": 1, "stderr": 1, "stream": 1}
    )
    client.start(container)

    sock._sock.send(data)
    sock._sock.close()
    sock.close()

    client.wait(container)
    # status = client.wait(container)
    # status_code = status['StatusCode']
    stdout = client.logs(container, stderr=False).decode()
    # stderr = client.logs(container, stdout=False).decode()

    client.remove_container(container)

    # logging.debug('Exit: {}'.format(status_code))
    # logging.debug('log stdout: {}'.format(stdout))
    # logging.debug('log stderr: {}'.format(stderr))

    # TODO: else: raise error!

    return stdout


def getbib(file: str) -> BibDatabase:
    with open(file) as bibtex_file:
        contents = bibtex_file.read()
        bib_r = re.compile(r"^@.*{.*,", re.M)
        if len(re.findall(bib_r, contents)) == 0:
            logging.error(f"Not a bib file? {os.path.basename(file)}")
            db = None
        if "Early Access Date" in contents:
            logging.error(
                "Replace Early Access Date in bibfile before "
                f"loading! {os.path.basename(file)}"
            )
            return None

    with open(file) as bibtex_file:
        db = BibTexParser(
            customization=convert_to_unicode,
            ignore_nonstandard_types=True,
            common_strings=True,
        ).parse_file(bibtex_file, partial=True)

    return db


def ris2bib(file: str) -> BibDatabase:
    with open(file) as reader:
        data = reader.read(4096)
    if "TY  - " not in data:
        logging.error("Error: Not a ris file? " + os.path.basename(file))
        return None

    with open(file) as reader:
        data = reader.read()

    data = bibutils_convert("ris2xml", data)
    data = bibutils_convert("xml2bib", data)
    parser = BibTexParser(customization=convert_to_unicode)
    db = bibtexparser.loads(data, parser=parser)
    return db


def end2bib(file: str) -> BibDatabase:
    with open(file) as reader:
        data = reader.read(4096)
    if "%T " not in data:
        logging.error("Error: Not an end file? " + os.path.basename(file))
        return None

    with open(file) as reader:
        data = reader.read()

    data = bibutils_convert("end2xml", data)
    data = bibutils_convert("xml2bib", data)
    parser = BibTexParser(customization=convert_to_unicode)
    db = bibtexparser.loads(data, parser=parser)
    return db


def txt2bib(file: str) -> BibDatabase:
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


def csv2bib(file: str) -> BibDatabase:
    try:
        data = pd.read_csv(file)
    except pd.errors.ParserError:
        logging.error("Error: Not a csv file? " + os.path.basename(file))
        pass
        return None
    data.columns = data.columns.str.replace(" ", "_")
    data.columns = data.columns.str.replace("-", "_")
    data = data.to_dict("records")
    data = preprocess_records(data)

    db = BibDatabase()
    db.entries = data
    return db


def xlsx2bib(file: str) -> BibDatabase:
    try:
        data = pd.read_excel(file, dtype=str)  # dtype=str to avoid type casting
    except pd.errors.ParserError:
        logging.error("Error: Not an xlsx file: " + os.path.basename(file))
        pass
        return None
    data.columns = data.columns.str.replace(" ", "_")
    data.columns = data.columns.str.replace("-", "_")
    data = data.to_dict("records")
    data = preprocess_records(data)

    db = BibDatabase()
    db.entries = data
    return db


def move_to_pdf_dir(filepath: str) -> str:
    PDF_DIRECTORY = repo_setup.paths["PDF_DIRECTORY"]
    # We should avoid re-extracting data from PDFs repeatedly (e.g., status.py)
    if not os.path.exists(PDF_DIRECTORY):
        os.mkdir(PDF_DIRECTORY)
    new_fp = os.path.join(PDF_DIRECTORY, os.path.basename(filepath))
    shutil.move(filepath, new_fp)
    return new_fp


# curl -v --form input=@./profit.pdf localhost:8070/api/processHeaderDocument
# curl -v --form input=@./thefile.pdf -H "Accept: application/x-bibtex"
# -d "consolidateHeader=0" localhost:8070/api/processHeaderDocument
def pdf2bib(file: str) -> BibDatabase:
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
        logging.error(f"Not a readable pdf file: {os.path.basename(file)}")
        logging.debug(f"Grobid: {r.text}")
        return None

    logging.debug(f"Status: {r.status_code}")
    logging.debug(f"Response: {r.text}")
    return None


def pdfRefs2bib(file: str) -> BibDatabase:
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
        for r in db.entries:
            r["ID"] = r["ID"].rjust(3, "0")
        return db
    if 500 == r.status_code:
        logging.error(f"Not a readable pdf file? {os.path.basename(file)}")
        logging.debug(f"Grobid: {r.text}")
        return None

    logging.debug(f"Status: {r.status_code}")
    logging.debug(f"Response: {r.text}")
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


def set_IDs(db: BibDatabase) -> BibDatabase:

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
            + f"({os.path.basename(self.import_path)}) "
        )
        super().__init__(self.message)


def validate_file_formats() -> None:
    search_files = get_search_files()
    for sfp in search_files:
        if not any(sfp.endswith(ext) for ext in conversion_scripts.keys()):
            if not sfp.endswith(".bib"):
                raise UnsupportedImportFormatError(sfp)
    return None


def convert_to_bib(search_files: list) -> None:

    for sfpath in search_files:
        search_file = os.path.basename(sfpath)
        corresponding_bib_file = sfpath[: sfpath.rfind(".")] + ".bib"

        if os.path.exists(corresponding_bib_file):
            continue

        if not any(sfpath.endswith(ext) for ext in conversion_scripts.keys()):
            raise UnsupportedImportFormatError(sfpath)

        filetype = sfpath[sfpath.rfind(".") + 1 :]
        if "pdf" == filetype:
            if sfpath.endswith("_ref_list.pdf"):
                filetype = "pdf_refs"

        if filetype in conversion_scripts.keys():
            logging.info(f"Loading {filetype}: {search_file}")
            logging.debug(f"Called {conversion_scripts[filetype].__name__}({sfpath})")
            db = conversion_scripts[filetype](sfpath)

            db = fix_keys(db)
            db = set_IDs(db)
            db = unify_field_names(db)
            db = drop_empty_fields(db)

            if db is None:
                logging.error("No records loaded")
                continue
            elif "pdf" == filetype:
                new_fp = move_to_pdf_dir(sfpath)
                new_record = {
                    "filename": os.path.basename(corresponding_bib_file),
                    "search_type": "OTHER",
                    "source_name": "PDF (metadata)",
                    "source_url": new_fp,
                    "search_parameters": "NA",
                    "comment": "Extracted with GROBID",
                }
                append_search_details(new_record)
                repo = git.Repo()
                repo.index.add([new_fp])

            elif "pdf_refs" == filetype:
                new_fp = move_to_pdf_dir(sfpath)
                new_record = {
                    "filename": os.path.basename(corresponding_bib_file),
                    "search_type": "BACK_CIT",
                    "source_name": "PDF backward search",
                    "source_url": new_fp,
                    "search_parameters": "NA",
                    "comment": "Extracted with GROBID",
                }
                append_search_details(new_record)
                repo = git.Repo()
                repo.index.add([new_fp])

            if corresponding_bib_file != sfpath and not ".bib" == sfpath[-4:]:
                new_file_path = sfpath[: sfpath.rfind(".")] + ".bib"
                if not os.path.exists(new_file_path):
                    logging.info(
                        f"Loaded {len(db.entries)} " f"records from {search_file}"
                    )
                    with open(new_file_path, "w") as fi:
                        fi.write(bibtexparser.dumps(db))
        else:
            logging.info("Filetype not recognized: " + search_file)
            continue

    return


class IteratorEx:
    def __init__(self, it):
        self.it = iter(it)
        self.sentinel = object()
        self.nextItem = next(self.it, self.sentinel)
        self.hasNext = self.nextItem is not self.sentinel

    def next(self):
        ret, self.nextItem = self.nextItem, next(self.it, self.sentinel)
        self.hasNext = self.nextItem is not self.sentinel
        return ret

    def __iter__(self):
        while self.hasNext:
            yield self.next()


current_batch_counter = 0
batch_start = 1
batch_end = 0


def processing_condition(record: dict) -> bool:
    global current_batch_counter
    global batch_start
    global batch_end

    # Do not count records that have already been imported
    if "retrieved" != record.get("md_status", "NA"):
        return False

    if 0 == current_batch_counter:
        batch_start = batch_end + 1

    current_batch_counter += 1
    batch_end += 1

    if current_batch_counter >= BATCH_SIZE:
        current_batch_counter = 0
        return True

    return False


def save_imported_files(repo: git.Repo, bib_db: BibDatabase) -> bool:
    if bib_db is None:
        logging.info("No records imported")
        return False

    if 0 == len(bib_db.entries):
        logging.info("No records imported")
        return False

    utils.save_bib_file(bib_db, MAIN_REFERENCES)
    repo.index.add([SEARCH_DETAILS])
    repo.index.add(get_search_files())
    repo.index.add([MAIN_REFERENCES])

    if not repo.is_dirty():
        logging.info("No new records added to MAIN_REFERENCES")
        return False

    return True


def main(repo: git.Repo, keep_ids: bool = False) -> BibDatabase:

    saved_args = locals()
    if not keep_ids:
        del saved_args["keep_ids"]
    global batch_start
    global batch_end

    utils.reset_log()
    logging.info("Import")
    logging.info(f"Batch size: {BATCH_SIZE}")

    bib_db = BibDatabase()
    record_iterator = IteratorEx(load_all_records())
    for record in record_iterator:
        bib_db.entries.append(record)
        if record_iterator.hasNext:
            if not processing_condition(record):
                continue  # keep appending records
        else:
            processing_condition(record)  # updates counters

        if batch_start > 1:
            logging.info("Continuing batch import started earlier")
        if 0 == batch_end:
            logging.info("No new records")
            break
        if 1 == batch_end:
            logging.info("Importing one record")
        if batch_end != 1:
            logging.info(f"Importing records {batch_start} to {batch_end}")

        pool = mp.Pool(repo_setup.config["CPUS"])
        bib_db.entries = pool.map(import_record, bib_db.entries)
        pool.close()
        pool.join()

        if not keep_ids:
            bib_db = utils.set_IDs(bib_db)

        if save_imported_files(repo, bib_db):
            utils.create_commit(repo, "⚙️ Import search results", saved_args)

    bib_db.entries = sorted(bib_db.entries, key=lambda d: d["ID"])

    return bib_db
