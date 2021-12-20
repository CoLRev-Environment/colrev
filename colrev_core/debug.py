import configparser
import logging
import pprint
from pathlib import Path  # noqa F401

from colrev_core import review_manager

review_manager.setup_logger(level=logging.DEBUG)
logger = logging.getLogger("colrev_core")
pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)


def set_debug_mode(activate: bool) -> None:

    config_path = Path("private_config.ini")
    private_config = configparser.ConfigParser()
    if config_path.is_file():
        private_config.read(config_path)
    if "general" not in private_config.sections():
        private_config.add_section("general")
    if activate:
        private_config["general"]["debug_mode"] = "yes"
    else:
        private_config["general"]["debug_mode"] = "no"
    with open(config_path, "w") as f:
        private_config.write(f)

    return


def debug_load() -> None:

    # Records that are not imported (after running load)
    # Debugging: get all imported records, their origins
    # then compare them to the original search_files

    from colrev_core.review_manager import ReviewManager, ProcessType, Process
    from colrev_core import load

    REVIEW_MANAGER = ReviewManager()
    REVIEW_MANAGER.notify(Process(ProcessType.explore, str))
    rec_header_lis = REVIEW_MANAGER.get_record_header_list()
    origin_list = [x[1] for x in rec_header_lis]

    search_files = load.get_search_files(restrict=["bib"])

    for search_file in search_files:
        print(search_file)
        sfn = search_file.stem
        search_file_origins = [x for x in origin_list if sfn in x]
        with open(search_file) as f:
            line = f.readline()
            while line:
                if "@" in line[:3]:
                    current_ID = line[line.find("{") + 1 : line.rfind(",")]
                    corresponding_origin = f"{sfn}/{current_ID}"
                    if corresponding_origin not in search_file_origins:
                        print(corresponding_origin)

                line = f.readline()
    return


def debug_prep() -> None:

    from colrev_core import prep
    from colrev_core.review_manager import (
        ReviewManager,
        ProcessType,
        Process,
        RecordState,
    )

    REVIEW_MANAGER = ReviewManager()
    REVIEW_MANAGER.notify(Process(ProcessType.prep, str))

    record = {
        "ENTRYTYPE": "article",
        "ID": "NewmanRobeyNoYear",
        "author": "Newman, Michael and Robey, Daniel",
        "journal": "MIS Quarterly",
        "metadata_source": "ORIGINAL",
        "number": "2",
        "origin": "MISQ.bib/0000000826",
        "status": RecordState.md_imported,
        "title": "A Social Process Model of User-Analyst Relationships",
        "volume": "16",
    }

    pp.pprint(record)
    res = prep.get_md_from_crossref(record)
    # res = prep.get_md_from_urls(record)
    # res = prep.get_md_from_dblp(record)

    pp.pprint(res)

    return


def debug_pdf_get():
    from colrev_core.review_manager import (
        ReviewManager,
        ProcessType,
        Process,
        RecordState,
    )
    from colrev_core import pdf_get

    REVIEW_MANAGER = ReviewManager()
    REVIEW_MANAGER.notify(Process(ProcessType.pdf_get, str))

    record = {
        "ENTRYTYPE": "article",
        "ID": "GuoLiuNault2021",
        "author": "Guo, Hong and Liu, Yipeng and Nault, Barrie R.",
        "file": "pdfs/GuoLiuNault2021.pdf",
        "journal": "MIS Quarterly",
        "metadata_source": "ORIGINAL",
        "number": "1",
        "origin": "MISQ.bib/0000000826",
        "status": RecordState.md_imported,
        "title": "Provisioning Interoperable Disaster Management Systems",
        "volume": "45",
        "year": "2021",
        "doi": " 10.25300/MISQ/2020/14947",
    }

    pdf_get.get_pdf_from_unpaywall(record, REVIEW_MANAGER)

    return


def debug_data():

    from colrev_core.review_manager import ReviewManager, ProcessType, Process
    from colrev_core import data

    REVIEW_MANAGER = ReviewManager()
    REVIEW_MANAGER.notify(Process(ProcessType.data, str))

    bib_db = REVIEW_MANAGER.load_bib_db()
    included = data.get_records_for_synthesis(bib_db)

    data.update_manuscript(REVIEW_MANAGER, bib_db, included)

    return


def debug_tei_tools() -> None:
    from colrev_core import tei_tools, grobid_client

    logger.debug("Start grobid")
    grobid_client.start_grobid()
    logger.debug("Started grobid")

    filepath = Path("/home/user/Webster2002.pdf")
    res = tei_tools.get_record_from_pdf_tei(filepath)
    print(res)
    return


def main():

    # code for debugging ...

    # TODO : helper-function to load entries from any bib-file (based on ID or origin)

    # debug_load()

    # debug_prep()

    # debug_pdf_get()

    # debug_data()

    # debug_tei_tools()

    return
