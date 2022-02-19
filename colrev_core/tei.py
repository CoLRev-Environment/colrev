#!/usr/bin/env python3
import re
import time
from pathlib import Path

import requests
from lxml import etree

from colrev_core import grobid_client
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.process import RecordState


class TEI(Process):
    ns = {
        "tei": "{http://www.tei-c.org/ns/1.0}",
        "w3": "{http://www.w3.org/XML/1998/namespace}",
    }
    nsmap = {
        "tei": "http://www.tei-c.org/ns/1.0",
        "w3": "http://www.w3.org/XML/1998/namespace",
    }

    GROBID_URL = "http://localhost:8070"

    def __init__(
        self,
        REVIEW_MANAGER,
        pdf_path: Path = None,
        tei_path: Path = None,
        notify_state_transition_process: bool = True,
    ):
        """Creates a TEI file
        modes of operation:
        - pdf_path: create TEI and temporarily store in self.data
        - pfd_path and tei_path: create TEI and save in tei_path
        - tei_path: read TEI from file
        """
        super().__init__(
            REVIEW_MANAGER,
            ProcessType.data,
            notify_state_transition_process=notify_state_transition_process,
        )

        assert pdf_path is not None or tei_path is not None
        if pdf_path is not None:
            assert pdf_path.is_file()
            self.pdf_path = pdf_path
        if tei_path is not None:
            assert tei_path.is_file()
            self.tei_path = tei_path

        if pdf_path is not None:
            # Note: we have more control and transparency over the consolidation
            # if we do it in the colrev_core process
            options = {}
            options["consolidateHeader"] = "0"
            options["consolidateCitations"] = "0"
            r = requests.post(
                grobid_client.get_grobid_url() + "/api/processFulltextDocument",
                files={"input": open(str(pdf_path), "rb")},
                data=options,
            )

            # Possible extension: get header only (should be more efficient)
            # r = requests.post(
            #     self.GROBID_URL + "/api/processHeaderDocument",
            #     files=dict(input=open(filepath, "rb")),
            #     data=header_data,
            # )

            if r.status_code != 200:
                raise TEI_Exception()

            if b"[TIMEOUT]" in r.content:
                raise TEI_TimeoutException()

            self.root = etree.fromstring(r.content)

            if tei_path is not None:
                with open(tei_path, "wb") as tf:
                    tf.write(r.content)

                # Note : reopen/write to prevent format changes in the enhancement
                with open(tei_path, "rb") as tf:
                    xml_fstring = tf.read()
                self.root = etree.fromstring(xml_fstring)

                tree = etree.ElementTree(self.root)
                tree.write(tei_path, pretty_print=True, encoding="utf-8")
        elif tei_path is not None:
            with open(tei_path) as ts:
                xml_string = ts.read()
            if "[BAD_INPUT_DATA]" in xml_string[:100]:
                raise TEI_Exception()
            self.root = etree.fromstring(xml_string)

    def check_precondition(self) -> None:
        return

    def start_grobid(self) -> bool:
        import os
        import subprocess

        r = requests.get(self.GROBID_URL + "/api/isalive")
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
            r = requests.get(self.GROBID_URL + "/api/isalive")
            if r.text == "true":
                print("Grobid service alive.")
                return True
            if i > 30:
                break
        return False

    def __get_paper_title(self) -> str:
        title_text = "NA"
        file_description = self.root.find(".//" + self.ns["tei"] + "fileDesc")
        if file_description is not None:
            titleStmt_node = file_description.find(".//" + self.ns["tei"] + "titleStmt")
            if titleStmt_node is not None:
                title_node = titleStmt_node.find(".//" + self.ns["tei"] + "title")
                if title_node is not None:
                    title_text = (
                        title_node.text if title_node.text is not None else "NA"
                    )
                    title_text = (
                        title_text.replace("(Completed paper)", "")
                        .replace("(Completed-paper)", "")
                        .replace("(Research-in-Progress)", "")
                        .replace("Completed Research Paper", "")
                    )
        return title_text

    def __get_paper_journal(self) -> str:
        journal_name = "NA"
        file_description = self.root.find(".//" + self.ns["tei"] + "sourceDesc")
        if file_description is not None:
            if file_description.find(".//" + self.ns["tei"] + "monogr") is not None:
                journal_node = file_description.find(".//" + self.ns["tei"] + "monogr")
                if journal_node is not None:
                    jtitle_node = journal_node.find(".//" + self.ns["tei"] + "title")
                    if jtitle_node is not None:
                        journal_name = (
                            jtitle_node.text if jtitle_node.text is not None else "NA"
                        )
                        if "NA" != journal_name:
                            words = journal_name.split()
                            if sum(word.isupper() for word in words) / len(words) > 0.8:
                                words = [word.capitalize() for word in words]
                                journal_name = " ".join(words)
        return journal_name

    def __get_paper_journal_volume(self) -> str:
        volume = "NA"
        file_description = self.root.find(".//" + self.ns["tei"] + "sourceDesc")
        if file_description is not None:
            if file_description.find(".//" + self.ns["tei"] + "monogr") is not None:
                journal_node = file_description.find(".//" + self.ns["tei"] + "monogr")
                if journal_node is not None:
                    imprint_node = journal_node.find(".//" + self.ns["tei"] + "imprint")
                    if imprint_node is not None:
                        vnode = imprint_node.find(
                            ".//" + self.ns["tei"] + "biblScope[@unit='volume']"
                        )
                        if vnode is not None:
                            volume = vnode.text if vnode.text is not None else "NA"
        return volume

    def __get_paper_journal_issue(self) -> str:
        issue = "NA"
        file_description = self.root.find(".//" + self.ns["tei"] + "sourceDesc")
        if file_description is not None:
            if file_description.find(".//" + self.ns["tei"] + "monogr") is not None:
                journal_node = file_description.find(".//" + self.ns["tei"] + "monogr")
                if journal_node is not None:
                    imprint_node = journal_node.find(".//" + self.ns["tei"] + "imprint")
                    if imprint_node is not None:
                        issue_node = imprint_node.find(
                            ".//" + self.ns["tei"] + "biblScope[@unit='issue']"
                        )
                        if issue_node is not None:
                            issue = (
                                issue_node.text if issue_node.text is not None else "NA"
                            )
        return issue

    def __get_paper_journal_pages(self) -> str:
        pages = "NA"
        file_description = self.root.find(".//" + self.ns["tei"] + "sourceDesc")
        if file_description is not None:
            journal_node = file_description.find(".//" + self.ns["tei"] + "monogr")
            if journal_node is not None:
                imprint_node = journal_node.find(".//" + self.ns["tei"] + "imprint")
                if imprint_node is not None:
                    page_node = imprint_node.find(
                        ".//" + self.ns["tei"] + "biblScope[@unit='page']"
                    )
                    if page_node is not None:
                        if (
                            page_node.get("from") is not None
                            and page_node.get("to") is not None
                        ):
                            pages = (
                                page_node.get("from", "")
                                + "--"
                                + page_node.get("to", "")
                            )
        return pages

    def __get_paper_year(self) -> str:
        year = "NA"
        file_description = self.root.find(".//" + self.ns["tei"] + "sourceDesc")
        if file_description is not None:
            if file_description.find(".//" + self.ns["tei"] + "monogr") is not None:
                journal_node = file_description.find(".//" + self.ns["tei"] + "monogr")
                if journal_node is not None:
                    imprint_node = journal_node.find(".//" + self.ns["tei"] + "imprint")
                    if imprint_node is not None:
                        date_node = imprint_node.find(".//" + self.ns["tei"] + "date")
                        if date_node is not None:
                            year = (
                                date_node.get("when", "")
                                if date_node.get("when") is not None
                                else "NA"
                            )
                            year = re.sub(r".*([1-2][0-9]{3}).*", r"\1", year)
        return year

    def get_author_name_from_node(self, author_node) -> str:
        authorname = ""

        author_pers_node = author_node.find(self.ns["tei"] + "persName")
        if author_pers_node is None:
            return authorname
        surname_node = author_pers_node.find(self.ns["tei"] + "surname")
        if surname_node is not None:
            surname = surname_node.text if surname_node.text is not None else ""
        else:
            surname = ""

        forename_node = author_pers_node.find(
            self.ns["tei"] + 'forename[@type="first"]'
        )
        if forename_node is not None:
            forename = forename_node.text if forename_node.text is not None else ""
        else:
            forename = ""

        if 1 == len(forename):
            forename = forename + "."

        middlename_node = author_pers_node.find(
            self.ns["tei"] + 'forename[@type="middle"]'
        )
        if middlename_node is not None:
            middlename = (
                " " + middlename_node.text if middlename_node.text is not None else ""
            )
        else:
            middlename = ""

        if 1 == len(middlename):
            middlename = middlename + "."

        authorname = surname + ", " + forename + middlename

        authorname = (
            authorname.replace("\n", " ")
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

        authorname = re.sub("^Paper, Short; ", "", authorname)
        return authorname

    def __get_paper_authors(self) -> str:
        author_string = "NA"
        file_description = self.root.find(".//" + self.ns["tei"] + "sourceDesc")
        author_list = []

        if file_description is not None:
            if file_description.find(".//" + self.ns["tei"] + "analytic") is not None:
                analytic_node = file_description.find(
                    ".//" + self.ns["tei"] + "analytic"
                )
                if analytic_node is not None:
                    for author_node in analytic_node.iterfind(
                        self.ns["tei"] + "author"
                    ):

                        authorname = self.get_author_name_from_node(author_node)
                        if authorname in ["Paper, Short"]:
                            continue
                        if ", " != authorname and "" != authorname:
                            author_list.append(authorname)

                    author_string = " and ".join(author_list)

                    # TODO: deduplicate
                    if author_string is None:
                        author_string = "NA"
                    if "" == author_string.replace(" ", "").replace(",", "").replace(
                        ";", ""
                    ):
                        author_string = "NA"
        return author_string

    def __get_paper_doi(self) -> str:
        doi = "NA"
        file_description = self.root.find(".//" + self.ns["tei"] + "sourceDesc")
        if file_description is not None:
            bibl_struct = file_description.find(".//" + self.ns["tei"] + "biblStruct")
            if bibl_struct is not None:
                dois = bibl_struct.findall(".//" + self.ns["tei"] + "idno[@type='DOI']")
                for res in dois:
                    if res.text is not None:
                        doi = res.text
        return doi

    def get_metadata(self) -> dict:

        record = {
            "ENTRYTYPE": "article",
            "title": self.__get_paper_title(),
            "author": self.__get_paper_authors(),
            "journal": self.__get_paper_journal(),
            "year": self.__get_paper_year(),
            "volume": self.__get_paper_journal_volume(),
            "number": self.__get_paper_journal_issue(),
            "pages": self.__get_paper_journal_pages(),
            "doi": self.__get_paper_doi(),
        }

        for k, v in record.items():
            if "file" != k:
                record[k] = v.replace("}", "").replace("{", "").rstrip("\\")
            else:
                print(f"problem in filename: {k}")

        return record

    # (individual) bibliography-reference elements  ----------------------------

    def __get_reference_bibliography_id(self, reference) -> str:
        if "ID" in reference.attrib:
            return reference.attrib["ID"]
        else:
            return ""

    def __get_reference_bibliography_tei_id(self, reference) -> str:
        return reference.attrib[self.ns["w3"] + "id"]

    def __get_reference_author_string(self, reference) -> str:
        author_list = []
        if reference.find(self.ns["tei"] + "analytic") is not None:
            authors_node = reference.find(self.ns["tei"] + "analytic")
        elif reference.find(self.ns["tei"] + "monogr") is not None:
            authors_node = reference.find(self.ns["tei"] + "monogr")

        for author_node in authors_node.iterfind(self.ns["tei"] + "author"):

            authorname = self.get_author_name_from_node(author_node)

            if ", " != authorname and "" != authorname:
                author_list.append(authorname)

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

        # TODO: deduplicate
        if author_string is None:
            author_string = "NA"
        if "" == author_string.replace(" ", "").replace(",", "").replace(";", ""):
            author_string = "NA"
        return author_string

    def __get_reference_title_string(self, reference) -> str:
        title_string = ""
        if reference.find(self.ns["tei"] + "analytic") is not None:
            title = reference.find(self.ns["tei"] + "analytic").find(
                self.ns["tei"] + "title"
            )
        elif reference.find(self.ns["tei"] + "monogr") is not None:
            title = reference.find(self.ns["tei"] + "monogr").find(
                self.ns["tei"] + "title"
            )
        if title is None:
            title_string = "NA"
        else:
            title_string = title.text
        return title_string

    def __get_reference_year_string(self, reference) -> str:
        year_string = ""
        if reference.find(self.ns["tei"] + "monogr") is not None:
            year = (
                reference.find(self.ns["tei"] + "monogr")
                .find(self.ns["tei"] + "imprint")
                .find(self.ns["tei"] + "date")
            )
        elif reference.find(self.ns["tei"] + "analytic") is not None:
            year = (
                reference.find(self.ns["tei"] + "analytic")
                .find(self.ns["tei"] + "imprint")
                .find(self.ns["tei"] + "date")
            )

        if year is not None:
            for name, value in sorted(year.items()):
                if name == "when":
                    year_string = value
                else:
                    year_string = "NA"
        else:
            year_string = "NA"
        return year_string

    def __get_reference_page_string(self, reference) -> str:
        page_string = ""

        if reference.find(self.ns["tei"] + "monogr") is not None:
            page_list = (
                reference.find(self.ns["tei"] + "monogr")
                .find(self.ns["tei"] + "imprint")
                .findall(self.ns["tei"] + "biblScope[@unit='page']")
            )
        elif reference.find(self.ns["tei"] + "analytic") is not None:
            page_list = (
                reference.find(self.ns["tei"] + "analytic")
                .find(self.ns["tei"] + "imprint")
                .findall(self.ns["tei"] + "biblScope[@unit='page']")
            )

        for page in page_list:
            if page is not None:
                for name, value in sorted(page.items()):
                    if name == "from":
                        page_string += value
                    if name == "to":
                        page_string += "--" + value
            else:
                page_string = "NA"

        return page_string

    def __get_reference_number_string(self, reference) -> str:
        number_string = ""

        if reference.find(self.ns["tei"] + "monogr") is not None:
            number_list = (
                reference.find(self.ns["tei"] + "monogr")
                .find(self.ns["tei"] + "imprint")
                .findall(self.ns["tei"] + "biblScope[@unit='issue']")
            )
        elif reference.find(self.ns["tei"] + "analytic") is not None:
            number_list = (
                reference.find(self.ns["tei"] + "analytic")
                .find(self.ns["tei"] + "imprint")
                .findall(self.ns["tei"] + "biblScope[@unit='issue']")
            )

        for number in number_list:
            if number is not None:
                number_string = number.text
            else:
                number_string = "NA"

        return number_string

    def __get_reference_volume_string(self, reference) -> str:
        volume_string = ""

        if reference.find(self.ns["tei"] + "monogr") is not None:
            volume_list = (
                reference.find(self.ns["tei"] + "monogr")
                .find(self.ns["tei"] + "imprint")
                .findall(self.ns["tei"] + "biblScope[@unit='volume']")
            )
        elif reference.find(self.ns["tei"] + "analytic") is not None:
            volume_list = (
                reference.find(self.ns["tei"] + "analytic")
                .find(self.ns["tei"] + "imprint")
                .findall(self.ns["tei"] + "biblScope[@unit='volume']")
            )

        for volume in volume_list:
            if volume is not None:
                volume_string = volume.text
            else:
                volume_string = "NA"

        return volume_string

    def __get_reference_journal_string(self, reference) -> str:
        journal_title = ""
        if reference.find(self.ns["tei"] + "monogr") is not None:
            journal_title = (
                reference.find(self.ns["tei"] + "monogr")
                .find(self.ns["tei"] + "title")
                .text
            )
        if journal_title is None:
            journal_title = ""
        return journal_title

    def get_bibliography(self):
        from lxml.etree import XMLSyntaxError

        bibliographies = self.root.iter(self.ns["tei"] + "listBibl")
        tei_bib_db = []
        for bibliography in bibliographies:
            for reference in bibliography:
                try:
                    ref_rec = {
                        "ID": self.__get_reference_bibliography_id(reference),
                        "tei_id": self.__get_reference_bibliography_tei_id(reference),
                        "author": self.__get_reference_author_string(reference),
                        "title": self.__get_reference_title_string(reference),
                        "year": self.__get_reference_year_string(reference),
                        "journal": self.__get_reference_journal_string(reference),
                        "volume": self.__get_reference_volume_string(reference),
                        "number": self.__get_reference_number_string(reference),
                        "pages": self.__get_reference_page_string(reference),
                    }
                except XMLSyntaxError:
                    pass
                    continue

                ref_rec = {k: v for k, v in ref_rec.items() if v is not None}
                # print(ref_rec)
                tei_bib_db.append(ref_rec)

        return tei_bib_db

    def mark_references(self, records):
        from colrev_core import dedupe

        tei_records = self.get_bibliography(self.root)
        for record in tei_records:
            if "title" not in record:
                continue

            max_sim = 0.9
            max_sim_record = {}
            for local_record in records:
                if local_record["status"] not in [
                    RecordState.rev_included,
                    RecordState.rev_synthesized,
                ]:
                    continue
                rec_sim = dedupe.get_record_similarity(
                    record.copy(), local_record.copy()
                )
                if rec_sim > max_sim:
                    max_sim_record = local_record
                    max_sim = rec_sim
            if len(max_sim_record) == 0:
                continue

            # Record found: mark in tei
            bibliography = self.root.find(".//" + self.ns["tei"] + "listBibl")
            # mark reference in bibliography
            for ref in bibliography:
                if ref.get(self.ns["w3"] + "id") == record["tei_id"]:
                    ref.set("ID", max_sim_record["ID"])
            # mark reference in in-text citations
            for reference in self.root.iter(self.ns["tei"] + "ref"):
                if "target" in reference.keys():
                    if reference.get("target") == f"#{record['tei_id']}":
                        reference.set("ID", max_sim_record["ID"])

            # if settings file available: dedupe_io match agains records

        if self.tei_path:
            tree = etree.ElementTree(self.root)
            tree.write(str(self.tei_path), pretty_print=True, encoding="utf-8")

        return self.root


class TEI_TimeoutException(Exception):
    pass


class TEI_Exception(Exception):
    pass


if __name__ == "__main__":
    pass
