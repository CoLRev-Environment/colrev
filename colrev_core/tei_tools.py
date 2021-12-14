#!/usr/bin/env python3
import os
import re
import subprocess
import time
from pathlib import Path
from xml.etree.ElementTree import Element

import requests
from lxml import etree

ns = {
    "tei": "{http://www.tei-c.org/ns/1.0}",
    "w3": "{http://www.w3.org/XML/1998/namespace}",
}
nsmap = {
    "tei": "http://www.tei-c.org/ns/1.0",
    "w3": "http://www.w3.org/XML/1998/namespace",
}

GROBID_URL = "http://localhost:8070"


def start_grobid() -> bool:
    r = requests.get(GROBID_URL + "/api/isalive")
    if r.text == "true":
        # print('Docker running')
        return True
    print("Starting grobid service...")
    subprocess.Popen(
        [
            'docker run -t --rm -m "4g" -p 8070:8070 '
            + "-p 8071:8071 lfoppiano/grobid:0.6.2"
        ],
        shell=True,
        stdin=None,
        stdout=open(os.devnull, "wb"),
        stderr=None,
        close_fds=True,
    )
    pass

    i = 0
    while True:
        i += 1
        time.sleep(1)
        r = requests.get(GROBID_URL + "/api/isalive")
        if r.text == "true":
            print("Grobid service alive.")
            return True
        if i > 30:
            break
    return False


def get_paper_title(root: Element) -> str:
    title_text = "NA"
    file_description = root.find(".//" + ns["tei"] + "fileDesc")
    if file_description is not None:
        titleStmt_node = file_description.find(".//" + ns["tei"] + "titleStmt")
        if titleStmt_node is not None:
            title_node = titleStmt_node.find(".//" + ns["tei"] + "title")
            if title_node is not None:
                title_text = title_node.text if title_node.text is not None else "NA"
                title_text = (
                    title_text.replace("(Completed paper)", "")
                    .replace("(Completed-paper)", "")
                    .replace("(Research-in-Progress)", "")
                    .replace("Completed Research Paper", "")
                )
    return title_text


def get_paper_journal(root: Element) -> str:
    journal_name = "NA"
    file_description = root.find(".//" + ns["tei"] + "sourceDesc")
    if file_description:
        if file_description.find(".//" + ns["tei"] + "monogr") is not None:
            journal_node = file_description.find(".//" + ns["tei"] + "monogr")
            if journal_node:
                jtitle_node = journal_node.find(".//" + ns["tei"] + "title")
                if jtitle_node:
                    journal_name = (
                        jtitle_node.text if jtitle_node.text is not None else "NA"
                    )
                    if "NA" != journal_name:
                        words = journal_name.split()
                        if sum(word.isupper() for word in words) / len(words) > 0.8:
                            words = [word.capitalize() for word in words]
                            journal_name = " ".join(words)
    return journal_name


def get_paper_journal_volume(root: Element) -> str:
    volume = "NA"
    file_description = root.find(".//" + ns["tei"] + "sourceDesc")
    if file_description:
        if file_description.find(".//" + ns["tei"] + "monogr") is not None:
            journal_node = file_description.find(".//" + ns["tei"] + "monogr")
            if journal_node:
                imprint_node = journal_node.find(".//" + ns["tei"] + "imprint")
                if imprint_node:
                    vnode = imprint_node.find(
                        ".//" + ns["tei"] + "biblScope[@unit='volume']"
                    )
                    if vnode:
                        volume = vnode.text if vnode.text is not None else "NA"
    return volume


def get_paper_journal_issue(root: Element) -> str:
    issue = "NA"
    file_description = root.find(".//" + ns["tei"] + "sourceDesc")
    if file_description:
        if file_description.find(".//" + ns["tei"] + "monogr") is not None:
            journal_node = file_description.find(".//" + ns["tei"] + "monogr")
            if journal_node:
                imprint_node = journal_node.find(".//" + ns["tei"] + "imprint")
                if imprint_node:
                    issue_node = imprint_node.find(
                        ".//" + ns["tei"] + "biblScope[@unit='issue']"
                    )
                    if issue_node:
                        issue = issue_node.text if issue_node.text is not None else "NA"
    return issue


def get_paper_journal_pages(root: Element) -> str:
    pages = "NA"
    file_description = root.find(".//" + ns["tei"] + "sourceDesc")
    if file_description is not None:
        journal_node = file_description.find(".//" + ns["tei"] + "monogr")
        if journal_node is not None:
            imprint_node = journal_node.find(".//" + ns["tei"] + "imprint")
            if imprint_node is not None:
                page_node = imprint_node.find(
                    ".//" + ns["tei"] + "biblScope[@unit='page']"
                )
                if page_node is not None:
                    if (
                        page_node.get("from") is not None
                        and page_node.get("to") is not None
                    ):
                        pages = (
                            page_node.get("from", "") + "--" + page_node.get("to", "")
                        )
    return pages


def get_paper_year(root: Element) -> str:
    year = "NA"
    file_description = root.find(".//" + ns["tei"] + "sourceDesc")
    if file_description:
        if file_description.find(".//" + ns["tei"] + "monogr") is not None:
            journal_node = file_description.find(".//" + ns["tei"] + "monogr")
            if journal_node:
                imprint_node = journal_node.find(".//" + ns["tei"] + "imprint")
                if imprint_node:
                    date_node = imprint_node.find(".//" + ns["tei"] + "date")
                    if date_node:
                        year = (
                            date_node.get("when", "")
                            if date_node.get("when") is not None
                            else "NA"
                        )
                        year = re.sub(r".*([1-2][0-9]{3}).*", r"\1", year)
    return year


def get_paper_authors(root: Element) -> str:
    author_string = "NA"
    file_description = root.find(".//" + ns["tei"] + "sourceDesc")
    author_list = []

    if file_description:
        if file_description.find(".//" + ns["tei"] + "analytic") is not None:
            analytic_node = file_description.find(".//" + ns["tei"] + "analytic")
            if analytic_node:
                for author_node in analytic_node.iterfind(ns["tei"] + "author"):
                    authorname = ""

                    author_pers_node = author_node.find(ns["tei"] + "persName")
                    if author_pers_node is None:
                        continue
                    surname_node = author_pers_node.find(ns["tei"] + "surname")
                    if surname_node is not None:
                        surname = (
                            surname_node.text if surname_node.text is not None else ""
                        )
                    else:
                        surname = ""

                    forename_node = author_pers_node.find(
                        ns["tei"] + 'forename[@type="first"]'
                    )
                    if forename_node is not None:
                        forename = (
                            forename_node.text if forename_node.text is not None else ""
                        )
                    else:
                        forename = ""

                    if 1 == len(forename):
                        forename = forename + "."

                    middlename_node = author_pers_node.find(
                        ns["tei"] + 'forename[@type="middle"]'
                    )
                    if middlename_node is not None:
                        middlename = (
                            " " + middlename_node.text
                            if middlename_node.text is not None
                            else ""
                        )
                    else:
                        middlename = ""

                    if 1 == len(middlename):
                        middlename = middlename + "."

                    authorname = surname + ", " + forename + middlename
                    if ", " != authorname:
                        author_list.append(authorname)

                for author in author_list:
                    author_string = " and ".join(author)
                author_string = (
                    author_string.replace("\n", " ")
                    .replace("\r", "")
                    .replace("•", "")
                    .replace("+", "")
                    .replace("Dipl.", "")
                    .replace("Prof.", "")
                    .replace("Dr.", "")
                    .replace("&apos", "'")
                    .replace("❚", "")
                    .replace("~", "")
                    .replace("®", "")
                    .replace("|", "")
                )

                author_string = re.sub("^Paper, Short; ", "", author_string)

                # TODO: deduplicate
                if author_string is None:
                    author_string = "NA"
                if "" == author_string.replace(" ", "").replace(",", "").replace(
                    ";", ""
                ):
                    author_string = "NA"
    return author_string


def get_paper_doi(root: Element) -> str:
    doi = "NA"
    file_description = root.find(".//" + ns["tei"] + "sourceDesc")
    if file_description:
        bibl_struct = file_description.find(".//" + ns["tei"] + "biblStruct")
        if bibl_struct:
            dois = bibl_struct.findall(".//" + ns["tei"] + "idno[@type='DOI']")
            for res in dois:
                if res.text:
                    doi = res.text
    return doi


def get_record_from_pdf_tei(filepath: Path) -> dict:

    # Note: we have more control and transparency over the consolidation
    # if we do it in the colrev_core process
    header_data = {"consolidateHeader": "0"}

    r = requests.post(
        GROBID_URL + "/api/processHeaderDocument",
        files=dict(input=open(filepath, "rb")),
        data=header_data,
    )

    status = r.status_code
    if status != 200:
        print(f"error: {r.text}")
        record = {
            "ENTRYTYPE": "misc",
            "error": "GROBID-Extraction failed",
            "error-msg": r.text,
        }

    if status == 200:
        root = etree.fromstring(r.text.encode("utf-8"))
        # print(etree.tostring(root, pretty_print=True).decode("utf-8"))
        record = {
            "ENTRYTYPE": "article",
            "title": get_paper_title(root),
            "author": get_paper_authors(root),
            "journal": get_paper_journal(root),
            "year": get_paper_year(root),
            "volume": get_paper_journal_volume(root),
            "number": get_paper_journal_issue(root),
            "pages": get_paper_journal_pages(root),
            "doi": get_paper_doi(root),
        }

    for k, v in record.items():
        if "file" != k:
            record[k] = v.replace("}", "").replace("{", "")
        else:
            print(f"problem in filename: {k}")

    return record
