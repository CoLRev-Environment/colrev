import logging
import pprint
from pathlib import Path  # noqa F401

from colrev_core.record import RecordState
from colrev_core.review_manager import ReviewManager

logger = logging.getLogger("colrev_core")
pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)


def debug_load() -> None:

    # Records that are not imported (after running load)
    # Debugging: get all imported records, their origins
    # then compare them to the original search_files

    from colrev_core.load import Loader
    from colrev_core.review_manager import ReviewManager

    REVIEW_MANAGER = ReviewManager()
    LOADER = Loader(REVIEW_MANAGER)

    # rec_header_lis = LOADER.REVIEW_MANAGER.REVIEW_DATASET.get_record_header_list()
    # origin_list = [x[1] for x in rec_header_lis]

    # search_files = LOADER.get_search_files(restrict=["bib"])

    # for search_file in search_files:
    #     print(search_file)
    #     sfn = search_file.stem
    #     search_file_origins = [x for x in origin_list if sfn in x]
    #     with open(search_file, encoding="utf8") as f:
    #         line = f.readline()
    #         while line:
    #             if "@" in line[:3]:
    #                 current_ID = line[line.find("{") + 1 : line.rfind(",")]
    #                 corresponding_origin = f"{sfn}/{current_ID}"
    #                 if corresponding_origin not in search_file_origins:
    #                     print(corresponding_origin)

    #             line = f.readline()

    # To test ID retrieval from local_index
    records = [
        {
            "ENTRYTYPE": "article",
            "ID": "0001",
            "doi": "10.1057/EJIS.2014.41",
            "author": "Bansal, Gaurav and Zahedi, F. Mariam and Gefen, David",
            "journal": "European Journal of Information Systems",
            "title": "The role of privacy assurance mechanisms in building "
            "trust and the moderating role of privacy concern",
            "year": "2015",
            "number": "6",
            "pages": "624--644",
            "volume": "24",
        }
    ]

    records = LOADER.REVIEW_MANAGER.REVIEW_DATASET.set_IDs(
        records, selected_IDs=[x["ID"] for x in records]
    )
    print(records)

    return


def debug_pdf_get():

    from colrev_core.pdf_get import PDF_Retrieval

    record = {
        "ENTRYTYPE": "article",
        "ID": "GuoLiuNault2021",
        "colrev_origin": "MISQ.bib/0000000826",
        "colrev_status": RecordState.md_imported,
        "author": "Guo, Hong and Liu, Yipeng and Nault, Barrie R.",
        "file": "pdfs/GuoLiuNault2021.pdf",
        "journal": "MIS Quarterly",
        "number": "1",
        "title": "Provisioning Interoperable Disaster Management Systems",
        "volume": "45",
        "year": "2021",
        "doi": " 10.25300/MISQ/2020/14947",
    }

    PDF_RETRIEVAL = PDF_Retrieval()
    PDF_RETRIEVAL.get_pdf_from_unpaywall(record)

    return


def debug_data():

    from colrev_core.data import Data

    DATA = Data()
    records = DATA.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
    included = DATA.get_record_ids_for_synthesis(records)

    DATA.update_manuscript(records, included)

    return


def debug_tei_tools(param) -> None:
    from colrev_core.environment import TEIParser
    from colrev_core.environment import GrobidService

    logger.debug("Start grobid")
    GROBID_SERVICE = GrobidService()
    GROBID_SERVICE.start()
    logger.debug("Started grobid")

    filepath = Path(param)
    TEI_INSTANCE = TEIParser(pdf_path=filepath)
    res = TEI_INSTANCE.get_metadata()
    print(res)
    return


def debug_pdf_prep():

    from colrev_core.pdf_prep import PDF_Preparation

    # from pdfminer.pdfdocument import PDFDocument
    # from pdfminer.pdfinterp import resolve1
    # from pdfminer.pdfparser import PDFParser
    # records = REVIEW_MANAGER.load_records_dict()
    # record = records["Johns2006"]
    # with open(record["file"], "rb") as file:
    #     parser = PDFParser(file)
    #     document = PDFDocument(parser)
    #     pages_in_file = resolve1(document.catalog["Pages"])["Count"]
    # text = pdf_prep.extract_text_by_page(record, [pages_in_file - 1])
    # print(text.lower().replace(" ", ""))

    record = {
        "ENTRYTYPE": "article",
        "ID": "GuoLiuNault2021",
        "colrev_origin": "MISQ.bib/0000000826",
        "colrev_status": RecordState.pdf_imported,
        "author": "Bødker, Mads",
        "file": "pdfs/42_1/Hua2018_User Service Innovatio.pdf",
        "journal": "MIS Quarterly",
        "number": "1",
        "title": "Provisioning Interoperable Disaster Management Systems",
        "volume": "45",
        "year": "2021",
        "doi": " 10.25300/MISQ/2020/14947",
        "pages": "165--187",
    }
    # pdf_prep.remove_last_page(record, 40)
    ret = PDF_Preparation.validate_completeness(record, 40)
    print(ret)
    return


def get_non_unique_colrev_pdf_ids() -> None:
    import pandas as pd

    REVIEW_MANAGER = ReviewManager()
    records = REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

    import collections

    colrev_pdf_ids = [
        x["colrev_pdf_id"].split(":")[1]
        for x in records.values()
        if "colrev_pdf_id" in x
    ]
    colrev_pdf_ids = [
        item for item, count in collections.Counter(colrev_pdf_ids).items() if count > 1
    ]
    df = pd.DataFrame(colrev_pdf_ids, columns=["colrev_pdf_ids"])

    df.to_csv("colrev_pdf_ids.csv", index=False)
    return df


def local_index(param):
    from colrev_core.environment import LocalIndex

    LOCAL_INDEX = LocalIndex()
    # To Test retrieval of record:
    record = {
        "ENTRYTYPE": "article",
        "author": "Addis, T. R.",
        "journal": "Journal of Information Technology",
        "number": "1",
        "pages": "38--45",
        "title": "Knowledge for the New Generation Computers",
        "volume": "1",
        "year": "1986",
    }
    record = {
        "ID": "HovorkaRoweMarkusEtAl2019",
        "ENTRYTYPE": "article",
        "doi": "10.17705/1JAIS.00570",
    }
    record = LOCAL_INDEX.retrieve(record)
    pp.pprint(record)

    # To Test retrieval of global ID
    # record = {
    #     'doi' : '10.17705/1JAIS.00598',
    # }
    # record = LOCAL_INDEX.retrieve(record)
    # pp.pprint(record)

    # record = {
    #     "ENTRYTYPE": "article",
    #     "colrev_pdf_id": "cpid1:ffeadde..",
    # }

    # res = LOCAL_INDEX.retrieve(record)
    # print(res)

    # To test the duplicate convenience function:
    # record1 = {
    #     "ENTRYTYPE": "article",
    #     "author" : "Addis, T. R.",
    #     "journal" : "Journal of Information Technology",
    #     "number" : "1",
    #     "pages" : "38--45",
    #     "title" : "Knowledge for the New Generation Computers",
    #     "volume" : "1",
    #     "year" : "1986"
    # }
    # record2 = {
    #     "ENTRYTYPE": "article",
    #     "author" : "Majchrzak, Ann and Malhotra, Arvind",
    #     "journal" : "Information Systems Research",
    #     "number" : "4",
    #     "pages" : "685--703",
    #     "title" : "Effect of Knowledge-Sharing Trajectories on " + \
    #                   "Innovative Outcomes in Temporary Online Crowds",
    #     "volume" : "27",
    #     "year" : "2016"
    # }
    # record3 = {
    #     "ENTRYTYPE": "article",
    #     "author" : "Addis, T. R.",
    #     "journal" : "Journal of Technology",
    #     "number" : "1",
    #     "pages" : "38--45",
    #     "title" : "Knowledge for the New Generation Computers",
    #     "volume" : "1",
    #     "year" : "1986"
    # }
    # record3 = {
    #     "ENTRYTYPE": "article",
    #     "author" : "colquitt, j and zapata-phelan, c p",
    #     "journal" : "academy of management journal",
    #     "number" : "6",
    #     "pages" : "1281--1303",
    #     "title" : "trends in theory building and theory testing a " + \
    #           "five-decade study of theacademy of management journal",
    #     "volume" : "50",
    #     "year" : "2007"
    # }
    # record4 = {
    #     "ENTRYTYPE": "article",
    #     "author" : "colquitt, j and zapata-phelan, c p",
    #     "journal" : "academy of management journal",
    #     "number" : "6",
    #     "pages" : "1281--1303",
    #     "title" : "trends in theory building and theory testing a " + \
    #           "five-decade study of the academy of management journal",
    #     "volume" : "50",
    #     "year" : "2007"
    # }
    # print(LOCAL_INDEX.is_duplicate(record1, record2))
    # print(LOCAL_INDEX.is_duplicate(record1, record3))
    # print(LOCAL_INDEX.is_duplicate(record3, record4))

    # To test the duplicate representation function:
    # record3 = LOCAL_INDEX.retrieve(record3)
    # pp.pprint(record3)
    # record4 = LOCAL_INDEX.retrieve(record4)
    # pp.pprint(record4)

    return


def corrections():
    REVIEW_MANAGER = ReviewManager()

    from colrev_core.process import CheckProcess

    CheckProcess(REVIEW_MANAGER)
    REVIEW_MANAGER.REVIEW_DATASET.check_corrections_of_curated_records()

    return


def main(operation: str, param):

    operations = {
        "load": debug_load,
        "pdf_get": debug_pdf_get,
        "pdf_prep": debug_pdf_prep,
        "data": debug_data,
        "local_index": local_index,
        "tei": debug_tei_tools,
        "corrections": corrections,
    }

    func = operations.get(operation, lambda: "not implemented")
    func(param)  # type: ignore

    # remove_needs_manual_preparation_records()

    # get_non_unique_colrev_pdf_ids()

    return


if __name__ == "__main__":
    pass
