#!/usr/bin/env python3
import os
import re
import subprocess
import time

import requests

ns = {
    "tei": "{http://www.tei-c.org/ns/1.0}",
    "w3": "{http://www.w3.org/XML/1998/namespace}",
}
nsmap = {
    "tei": "http://www.tei-c.org/ns/1.0",
    "w3": "http://www.w3.org/XML/1998/namespace",
}

GROBID_URL = "http://localhost:8070"


def start_grobid():
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


def get_paper_title(root):
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


def get_paper_journal(root):
    journal_name = "NA"
    file_description = root.find(".//" + ns["tei"] + "sourceDesc")
    if file_description.find(".//" + ns["tei"] + "monogr") is not None:
        journal_node = file_description.find(".//" + ns["tei"] + "monogr")
    jtitle_node = journal_node.find(".//" + ns["tei"] + "title")
    if jtitle_node is not None:
        journal_name = jtitle_node.text if jtitle_node.text is not None else "NA"
        if "NA" != journal_name:
            words = journal_name.split()
            if sum(word.isupper() for word in words) / len(words) > 0.8:
                words = [word.capitalize() for word in words]
                journal_name = " ".join(words)
    return journal_name


def get_paper_journal_volume(root):
    volume = "NA"
    file_description = root.find(".//" + ns["tei"] + "sourceDesc")
    if file_description.find(".//" + ns["tei"] + "monogr") is not None:
        journal_node = file_description.find(".//" + ns["tei"] + "monogr")
        if journal_node is not None:
            imprint_node = journal_node.find(".//" + ns["tei"] + "imprint")
            if imprint_node is not None:
                vnode = imprint_node.find(
                    ".//" + ns["tei"] + "biblScope[@unit='volume']"
                )
                if vnode is not None:
                    volume = vnode.text if vnode.text is not None else "NA"
    return volume


def get_paper_journal_issue(root):
    issue = "NA"
    file_description = root.find(".//" + ns["tei"] + "sourceDesc")
    if file_description.find(".//" + ns["tei"] + "monogr") is not None:
        journal_node = file_description.find(".//" + ns["tei"] + "monogr")
        if journal_node is not None:
            imprint_node = journal_node.find(".//" + ns["tei"] + "imprint")
            if imprint_node is not None:
                issue_node = imprint_node.find(
                    ".//" + ns["tei"] + "biblScope[@unit='issue']"
                )
                if issue_node is not None:
                    issue = issue_node.text if issue_node.text is not None else "NA"
    return issue


def get_paper_journal_pages(root):
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
                        pages = page_node.get("from") + "--" + page_node.get("to")
    return pages


def get_paper_year(root):
    year = "NA"
    file_description = root.find(".//" + ns["tei"] + "sourceDesc")
    if file_description.find(".//" + ns["tei"] + "monogr") is not None:
        journal_node = file_description.find(".//" + ns["tei"] + "monogr")
        imprint_node = journal_node.find(".//" + ns["tei"] + "imprint")
        if imprint_node is not None:
            date_node = imprint_node.find(".//" + ns["tei"] + "date")
            if date_node is not None:
                year = (
                    date_node.get("when") if date_node.get("when") is not None else "NA"
                )
                year = re.sub(r".*([1-2][0-9]{3}).*", r"\1", year)
    return year


def get_paper_authors(root):
    author_string = "NA"
    file_description = root.find(".//" + ns["tei"] + "sourceDesc")
    author_list = []
    author_node = ""

    if file_description.find(".//" + ns["tei"] + "analytic") is not None:
        author_node = file_description.find(".//" + ns["tei"] + "analytic")

    for author in author_node.iterfind(ns["tei"] + "author"):
        authorname = ""

        author_pers_node = author.find(ns["tei"] + "persName")
        if author_pers_node is None:
            continue
        surname_node = author_pers_node.find(ns["tei"] + "surname")
        if surname_node is not None:
            surname = surname_node.text if surname_node.text is not None else ""
        else:
            surname = ""

        forename_node = author_pers_node.find(ns["tei"] + 'forename[@type="first"]')
        if forename_node is not None:
            forename = forename_node.text if forename_node.text is not None else ""
        else:
            forename = ""

        if 1 == len(forename):
            forename = forename + "."

        middlename_node = author_pers_node.find(ns["tei"] + 'forename[@type="middle"]')
        if middlename_node is not None:
            middlename = (
                " " + middlename_node.text if middlename_node.text is not None else ""
            )
        else:
            middlename = ""

        if 1 == len(middlename):
            middlename = middlename + "."

        authorname = surname + ", " + forename + middlename
        if ", " != authorname:
            author_list.append(authorname)

    for author in author_list:
        author_string = " and ".join(author_list)
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
    if "" == author_string.replace(" ", "").replace(",", "").replace(";", ""):
        author_string = "NA"
    return author_string

    return "NA"


def get_paper_doi(root):
    doi = "NA"
    file_description = root.find(".//" + ns["tei"] + "sourceDesc")
    bibl_struct = file_description.find(".//" + ns["tei"] + "biblStruct")
    dois = bibl_struct.findall(".//" + ns["tei"] + "idno[@type='DOI']")
    for res in dois:
        doi = res.text
    return doi
