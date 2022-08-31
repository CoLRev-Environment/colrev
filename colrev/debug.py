import collections
import logging
import pprint
from pathlib import Path  # noqa F401

import pandas as pd

import colrev.record
import colrev.review_manager

logger = logging.getLogger("colrev")
pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)


def debug_load() -> None:

    # Records that are not imported (after running load)
    # Debugging: get all imported records, their origins
    # then compare them to the original search_files

    review_manager = colrev.review_manager.ReviewManager()
    load_operation = review_manager.get_load_operation()

    # rec_header_lis = loader.review_manager.dataset.get_record_header_list()
    # origin_list = [x['colrev_origin'] for x in rec_header_lis]

    # search_files = loader.get_search_files(restrict=["bib"])

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

    records = load_operation.review_manager.dataset.set_ids(
        records, selected_IDs=[x["ID"] for x in records]
    )
    print(records)


def debug_pdf_get():

    review_manager = colrev.review_manager.ReviewManager()

    record = {
        "ENTRYTYPE": "article",
        "ID": "GuoLiuNault2021",
        "colrev_origin": "MISQ.bib/0000000826",
        "colrev_status": colrev.record.RecordState.md_imported,
        "author": "Guo, Hong and Liu, Yipeng and Nault, Barrie R.",
        "file": "pdfs/GuoLiuNault2021.pdf",
        "journal": "MIS Quarterly",
        "number": "1",
        "title": "Provisioning Interoperable Disaster Management Systems",
        "volume": "45",
        "year": "2021",
        "doi": " 10.25300/MISQ/2020/14947",
    }
    print(record)
    pdf_retrieval_operation = review_manager.get_pdf_get_operation()
    print(pdf_retrieval_operation)


def debug_data():

    review_manager = colrev.review_manager.ReviewManager()

    data_operation = review_manager.get_data_operation()
    records = data_operation.review_manager.dataset.load_records_dict()
    included = data_operation.get_record_ids_for_synthesis(records)
    print(included)


def debug_tei_tools(param) -> None:

    review_manager = colrev.review_manager.ReviewManager()
    grobid_service = review_manager.get_grobid_service()

    logger.debug("Start grobid")
    grobid_service.start()
    logger.debug("Started grobid")

    filepath = Path(param)
    tei = review_manager.get_tei(pdf_path=filepath)
    res = tei.get_metadata()
    print(res)


def debug_pdf_prep():

    # from pdfminer.pdfdocument import PDFDocument
    # from pdfminer.pdfinterp import resolve1
    # from pdfminer.pdfparser import PDFParser
    # records = review_manager.load_records_dict()
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
        "colrev_status": colrev.record.RecordState.pdf_imported,
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
    print(record)


def get_non_unique_colrev_pdf_ids() -> None:

    review_manager = colrev.review_manager.ReviewManager()
    records = review_manager.dataset.load_records_dict()

    colrev_pdf_ids = [
        x["colrev_pdf_id"].split(":")[1]
        for x in records.values()
        if "colrev_pdf_id" in x
    ]
    colrev_pdf_ids = [
        item for item, count in collections.Counter(colrev_pdf_ids).items() if count > 1
    ]
    cpid_df = pd.DataFrame(colrev_pdf_ids, columns=["colrev_pdf_ids"])

    cpid_df.to_csv("colrev_pdf_ids.csv", index=False)
    return cpid_df


def debug_local_index(param):
    review_manager = colrev.review_manager.ReviewManager()

    # pylint: disable=no-member
    local_index = review_manager.get_local_index()

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
    record = local_index.retrieve(record=record)
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


def corrections():
    # pylint: disable=import-outside-toplevel

    from colrev.process import CheckProcess

    review_manager = colrev.review_manager.ReviewManager()
    CheckProcess(review_manager=review_manager)
    review_manager.dataset.check_corrections_of_curated_records()


def main(operation: str, param):

    operations = {
        "load": debug_load,
        "pdf_get": debug_pdf_get,
        "pdf_prep": debug_pdf_prep,
        "data": debug_data,
        "local_index": debug_local_index,
        "tei": debug_tei_tools,
        "corrections": corrections,
    }

    func = operations.get(operation, lambda: "not implemented")
    func(param)  # type: ignore

    # remove_needs_manual_preparation_records()

    # get_non_unique_colrev_pdf_ids()


if __name__ == "__main__":
    pass
