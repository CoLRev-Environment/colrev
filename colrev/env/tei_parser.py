#! /usr/bin/env python
"""Service parsing metadata from PDFs/TEIs (created by GROBID)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
from xml import etree
from xml.etree.ElementTree import Element

import defusedxml
import requests
from defusedxml.ElementTree import fromstring

import colrev.env.grobid_service
import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.record

# xpath alternative:
# tree.xpath("//tei:sourceDesc/tei:biblStruct/tei:monogr/tei:idno",
# namespaces={"tei": "http://www.tei-c.org/ns/1.0"})
# abstract_node =tree.xpath("//tei:profileDesc/tei:abstract",
# namespaces={"tei": "http://www.tei-c.org/ns/1.0"})
# etree.tostring(abstract_node[0]).decode("utf-8")


# defuse std xml lib
defusedxml.defuse_stdlib()


class TEIParser:
    """Environment service for TEI parsing"""

    ns = {
        "tei": "{http://www.tei-c.org/ns/1.0}",
        "w3": "{http://www.w3.org/XML/1998/namespace}",
    }
    nsmap = {
        "tei": "http://www.tei-c.org/ns/1.0",
        "w3": "http://www.w3.org/XML/1998/namespace",
    }

    def __init__(
        self,
        *,
        environment_manager: colrev.env.environment_manager.EnvironmentManager,
        pdf_path: Optional[Path] = None,
        tei_path: Optional[Path] = None,
    ):
        """Creates a TEI file
        modes of operation:
        - pdf_path: create TEI and temporarily store in self.data
        - pfd_path and tei_path: create TEI and save in tei_path
        - tei_path: read TEI from file
        """

        self.environment_manager = environment_manager
        # pylint: disable=consider-using-with
        assert pdf_path is not None or tei_path is not None
        if pdf_path is not None:
            if pdf_path.is_symlink():
                pdf_path = pdf_path.resolve()
        self.pdf_path = pdf_path
        self.tei_path = tei_path
        if pdf_path is not None:
            assert pdf_path.is_file()
        else:
            assert tei_path.is_file()  # type: ignore

        load_from_tei = False
        if tei_path is not None:
            if tei_path.is_file():
                load_from_tei = True

        if pdf_path is not None and not load_from_tei:
            self.__create_tei()

        elif tei_path is not None:
            self.root = self.__read_from_tei()  # type: ignore

    def __read_from_tei(self):  # type: ignore
        """Read a TEI from file"""
        with open(self.tei_path, "rb") as data:
            xslt_content = data.read()

        if b"[BAD_INPUT_DATA]" in xslt_content[:100]:
            raise colrev_exceptions.TEIException()

        return etree.ElementTree.XML(xslt_content)

    def __create_tei(self) -> None:
        """Create the TEI (based on GROBID)"""
        grobid_service = colrev.env.grobid_service.GrobidService(
            environment_manager=self.environment_manager
        )
        grobid_service.start()
        # Note: we have more control and transparency over the consolidation
        # if we do it in the colrev process
        options = {"consolidateHeader": "0", "consolidateCitations": "0"}

        # Note: Grobid offers direct export of Bibtex:
        # r = requests.post(
        #     GROBID_SERVICE.GROBID_URL() + "/api/processHeaderDocument",
        #     headers={"Accept": "application/x-bibtex"},
        # But parsing the metadata from the tei gives us more control of the details

        try:
            # pylint: disable=consider-using-with
            ret = requests.post(
                grobid_service.GROBID_URL + "/api/processFulltextDocument",
                files={"input": open(str(self.pdf_path), "rb")},
                data=options,
                timeout=180,
            )

            # Possible extension: get header only (should be more efficient)
            # r = requests.post(
            #     GrobidService.GROBID_URL + "/api/processHeaderDocument",
            #     files=dict(input=open(filepath, "rb")),
            #     data=header_data,
            # )

            if ret.status_code != 200:
                raise colrev_exceptions.TEIException()

            if b"[TIMEOUT]" in ret.content:
                raise colrev_exceptions.TEITimeoutException()

            self.root = fromstring(ret.content)

            if self.tei_path is not None:
                self.tei_path.parent.mkdir(exist_ok=True, parents=True)
                with open(self.tei_path, "wb") as file:
                    file.write(ret.content)

                # Note : reopen/write to prevent format changes in the enhancement
                with open(self.tei_path, "rb") as file:
                    xml_fstring = file.read()
                self.root = fromstring(xml_fstring)

                tree = etree.ElementTree.ElementTree(self.root)
                tree.write(str(self.tei_path), encoding="utf-8")
        except requests.exceptions.ConnectionError as exc:
            print(exc)
            print(str(self.pdf_path))

    def get_tei_str(self) -> str:
        """Get the TEI string"""
        etree.ElementTree.register_namespace("tei", "http://www.tei-c.org/ns/1.0")
        return etree.ElementTree.tostring(self.root).decode("utf-8")

    def get_grobid_version(self) -> str:
        """Get the GROBID version used for TEI creation"""
        grobid_version = "NA"
        encoding_description = self.root.find(".//" + self.ns["tei"] + "encodingDesc")
        if encoding_description is not None:
            app_info_node = encoding_description.find(
                ".//" + self.ns["tei"] + "appInfo"
            )
            if app_info_node is not None:
                application_node = encoding_description.find(
                    ".//" + self.ns["tei"] + "application"
                )
                if application_node is not None:
                    if application_node.get("version") is not None:
                        grobid_version = application_node.get("version")
        return grobid_version

    def __get_paper_title(self) -> str:
        title_text = "NA"
        file_description = self.root.find(".//" + self.ns["tei"] + "fileDesc")
        if file_description is not None:
            title_stmt_node = file_description.find(
                ".//" + self.ns["tei"] + "titleStmt"
            )
            if title_stmt_node is not None:
                title_node = title_stmt_node.find(".//" + self.ns["tei"] + "title")
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
        # pylint: disable=too-many-nested-blocks
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
                        if journal_name != "NA":
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

    def __parse_author_dict(self, *, author_pers_node: Element) -> dict:
        author_dict = {}
        surname_node = author_pers_node.find(self.ns["tei"] + "surname")
        if surname_node is not None:
            surname = surname_node.text if surname_node.text is not None else ""
            author_dict["surname"] = surname
        else:
            author_dict["surname"] = ""

        forename_node = author_pers_node.find(
            self.ns["tei"] + 'forename[@type="first"]'
        )
        if forename_node is not None:
            forename = forename_node.text if forename_node.text is not None else ""
            if 1 == len(forename):
                forename = forename + "."
            author_dict["forename"] = forename
        else:
            author_dict["forename"] = ""

        middlename_node = author_pers_node.find(
            self.ns["tei"] + 'forename[@type="middle"]'
        )
        if middlename_node is not None:
            middlename = (
                " " + middlename_node.text if middlename_node.text is not None else ""
            )
            if 1 == len(middlename):
                middlename = middlename + "."
            author_dict["middlename"] = middlename
        else:
            middlename = ""

        return author_dict

    def __get_author_name_from_node(self, *, author_node: Element) -> str:
        authorname = ""

        author_pers_node = author_node.find(self.ns["tei"] + "persName")
        if author_pers_node is None:
            return authorname

        author_dict = self.__parse_author_dict(author_pers_node=author_pers_node)

        authorname = author_dict["surname"] + ", " + author_dict["forename"]
        if "middlename" in author_dict:
            authorname += author_dict["middlename"]

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
                        authorname = self.__get_author_name_from_node(
                            author_node=author_node
                        )
                        if authorname in ["Paper, Short"]:
                            continue
                        if authorname not in [", ", ""]:
                            author_list.append(authorname)

                    author_string = " and ".join(author_list)

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

    def get_abstract(self) -> str:
        """Get the abstract"""

        html_tag_regex = re.compile("<.*?>")

        def cleanhtml(raw_html: str) -> str:
            cleantext = re.sub(html_tag_regex, "", raw_html)
            return cleantext

        abstract_text = "NA"
        profile_description = self.root.find(".//" + self.ns["tei"] + "profileDesc")
        if profile_description is not None:
            abstract_node = profile_description.find(
                ".//" + self.ns["tei"] + "abstract"
            )
            html_str = etree.ElementTree.tostring(abstract_node).decode("utf-8")
            abstract_text = cleanhtml(html_str)
        abstract_text = abstract_text.lstrip().rstrip()
        return abstract_text

    def get_metadata(self) -> dict:
        """Get the metadata of the PDF (title, author, ...) as a dict"""

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

        for key, value in record.items():
            if key != "file":
                record[key] = value.replace("}", "").replace("{", "").rstrip("\\")
            else:
                print(f"problem in filename: {key}")

        return record

    def get_paper_keywords(self) -> list:
        """Get hte keywords"""
        keywords = []
        for keyword_list in self.root.iter(self.ns["tei"] + "keywords"):
            for keyword in keyword_list.iter(self.ns["tei"] + "term"):
                keywords.append(keyword.text)
        return keywords

    def get_author_details(self) -> list:
        """Get the author details"""
        author_details = []

        file_description = self.root.find(".//" + self.ns["tei"] + "sourceDesc")

        if file_description is not None:
            if file_description.find(".//" + self.ns["tei"] + "analytic") is not None:
                analytic_node = file_description.find(
                    ".//" + self.ns["tei"] + "analytic"
                )
                if analytic_node is not None:
                    for author_node in analytic_node.iterfind(
                        self.ns["tei"] + "author"
                    ):
                        author_pers_node = author_node.find(self.ns["tei"] + "persName")
                        if author_pers_node is None:
                            continue

                        author_dict = self.__parse_author_dict(
                            author_pers_node=author_pers_node
                        )

                        email_node = author_node.find(self.ns["tei"] + "email")
                        if email_node is not None:
                            author_dict["emai"] = email_node.text

                        orcid_node = author_node.find(
                            self.ns["tei"] + 'idno[@type="ORCID"]'
                        )
                        if orcid_node is not None:
                            orcid = orcid_node.text
                            author_dict["ORCID"] = orcid

                        author_details.append(author_dict)

        return author_details

    # (individual) bibliography-reference elements  ----------------------------

    def __get_reference_bibliography_id(self, *, reference: Element) -> str:
        if "ID" in reference.attrib:
            return reference.attrib["ID"]
        return ""

    def __get_reference_bibliography_tei_id(self, *, reference: Element) -> str:
        return reference.attrib[self.ns["w3"] + "id"]

    def __get_reference_author_string(self, *, reference: Element) -> str:
        author_list = []
        if reference.find(self.ns["tei"] + "analytic") is not None:
            authors_node = reference.find(self.ns["tei"] + "analytic")
        elif reference.find(self.ns["tei"] + "monogr") is not None:
            authors_node = reference.find(self.ns["tei"] + "monogr")

        if authors_node is not None:
            for author_node in authors_node.iterfind(self.ns["tei"] + "author"):
                authorname = self.__get_author_name_from_node(author_node=author_node)

                if authorname not in [", ", ""]:
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

        if author_string is None:
            author_string = "NA"
        if author_string.replace(" ", "").replace(",", "").replace(";", "") == "":
            author_string = "NA"
        return author_string

    def __get_reference_title_string(self, *, reference: Element) -> str:
        title_string = ""
        if reference.find(self.ns["tei"] + "analytic") is not None:
            analytic_node = reference.find(self.ns["tei"] + "analytic")
            if analytic_node is not None:
                title = analytic_node.find(self.ns["tei"] + "title")
        elif reference.find(self.ns["tei"] + "monogr") is not None:
            monogr_node = reference.find(self.ns["tei"] + "monogr")
            if monogr_node is not None:
                title = monogr_node.find(self.ns["tei"] + "title")

        if title is not None:
            if title.text is not None:
                title_string = title.text

        return title_string

    def __get_reference_year_string(self, *, reference: Element) -> str:
        year_string = ""
        if reference.find(self.ns["tei"] + "monogr") is not None:
            monogr_node = reference.find(self.ns["tei"] + "monogr")
            if monogr_node is not None:
                imprint_node = monogr_node.find(self.ns["tei"] + "imprint")
                if imprint_node is not None:
                    year = imprint_node.find(self.ns["tei"] + "date")
        elif reference.find(self.ns["tei"] + "analytic") is not None:
            analytic_node = reference.find(self.ns["tei"] + "analytic")
            if analytic_node is not None:
                imprint_node = analytic_node.find(self.ns["tei"] + "imprint")
                if imprint_node is not None:
                    year = imprint_node.find(self.ns["tei"] + "date")

        if year is not None:
            for name, value in sorted(year.items()):
                year_string = value if (name == "when") else "NA"
        else:
            year_string = "NA"
        return year_string

    def __get_reference_page_string(self, *, reference: Element) -> str:
        page_string = ""

        if reference.find(self.ns["tei"] + "monogr") is not None:
            monogr_node = reference.find(self.ns["tei"] + "monogr")
            if monogr_node is not None:
                imprint_node = monogr_node.find(self.ns["tei"] + "imprint")
                if imprint_node is not None:
                    page_list = imprint_node.findall(
                        self.ns["tei"] + "biblScope[@unit='page']"
                    )
        elif reference.find(self.ns["tei"] + "analytic") is not None:
            analytic_node = reference.find(self.ns["tei"] + "analytic")
            if analytic_node is not None:
                imprint_node = analytic_node.find(self.ns["tei"] + "imprint")
                if imprint_node is not None:
                    page_list = imprint_node.findall(
                        self.ns["tei"] + "biblScope[@unit='page']"
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

    def __get_reference_number_string(self, *, reference: Element) -> str:
        number_string = ""

        if reference.find(self.ns["tei"] + "monogr") is not None:
            monogr_node = reference.find(self.ns["tei"] + "monogr")
            if monogr_node is not None:
                imprint_node = monogr_node.find(self.ns["tei"] + "imprint")
                if imprint_node is not None:
                    number_list = imprint_node.findall(
                        self.ns["tei"] + "biblScope[@unit='issue']"
                    )
        elif reference.find(self.ns["tei"] + "analytic") is not None:
            analytic_node = reference.find(self.ns["tei"] + "analytic")
            if analytic_node is not None:
                imprint_node = analytic_node.find(self.ns["tei"] + "imprint")
                if imprint_node is not None:
                    number_list = imprint_node.findall(
                        self.ns["tei"] + "biblScope[@unit='issue']"
                    )

        for number in number_list:
            if number.text is not None:
                number_string = number.text

        return number_string

    def __get_reference_volume_string(self, *, reference: Element) -> str:
        volume_string = ""

        if reference.find(self.ns["tei"] + "monogr") is not None:
            monogr_node = reference.find(self.ns["tei"] + "monogr")
            if monogr_node is not None:
                imprint_node = monogr_node.find(self.ns["tei"] + "imprint")
                if imprint_node is not None:
                    volume_list = imprint_node.findall(
                        self.ns["tei"] + "biblScope[@unit='volume']"
                    )
        elif reference.find(self.ns["tei"] + "analytic") is not None:
            analytic_node = reference.find(self.ns["tei"] + "analytic")
            if analytic_node is not None:
                imprint_node = analytic_node.find(self.ns["tei"] + "imprint")
                if imprint_node is not None:
                    volume_list = imprint_node.findall(
                        self.ns["tei"] + "biblScope[@unit='volume']"
                    )

        for volume in volume_list:
            if volume.text is not None:
                volume_string = volume.text

        return volume_string

    def __get_reference_journal_string(self, *, reference: Element) -> str:
        journal_title = ""
        if reference.find(self.ns["tei"] + "monogr") is not None:
            monogr_node = reference.find(self.ns["tei"] + "monogr")
            if monogr_node is not None:
                monogr_title = monogr_node.find(self.ns["tei"] + "title")
                if monogr_title is not None:
                    if monogr_title.text is not None:
                        journal_title = monogr_title.text

        return journal_title

    def __get_entrytype(self, *, reference: Element) -> str:
        entrytype = "misc"
        if reference.find(self.ns["tei"] + "monogr") is not None:
            monogr_node = reference.find(self.ns["tei"] + "monogr")
            if monogr_node is not None:
                title_node = monogr_node.find(self.ns["tei"] + "title")
                if title_node is not None:
                    if title_node.get("level", "NA") != "j":
                        entrytype = "book"
                    else:
                        entrytype = "article"
        return entrytype

    def __get_tei_id_count(self, *, tei_id: str) -> int:
        count = 0

        for reference in self.root.iter(self.ns["tei"] + "ref"):
            if "target" in reference.keys():
                if reference.get("target") == f"#{tei_id}":
                    count += 1

        return count

    def get_bibliography(self, *, min_intext_citations: int = 0) -> list:
        """Get the bibliography (references section) as a list of record dicts"""
        # Note : could also allow top-10 % of most frequent in-text citations

        bibliographies = self.root.iter(self.ns["tei"] + "listBibl")
        tei_bib_db = []
        for bibliography in bibliographies:
            for reference in bibliography:
                try:
                    entrytype = self.__get_entrytype(reference=reference)
                    tei_id = self.__get_reference_bibliography_tei_id(
                        reference=reference
                    )

                    if min_intext_citations > 0:
                        if (
                            self.__get_tei_id_count(tei_id=tei_id)
                            < min_intext_citations
                        ):
                            continue

                    if entrytype == "article":
                        ref_rec = {
                            "ID": tei_id,
                            "ENTRYTYPE": entrytype,
                            "tei_id": tei_id,
                            "reference_bibliography_id": self.__get_reference_bibliography_id(
                                reference=reference
                            ),
                            "author": self.__get_reference_author_string(
                                reference=reference
                            ),
                            "title": self.__get_reference_title_string(
                                reference=reference
                            ),
                            "year": self.__get_reference_year_string(
                                reference=reference
                            ),
                            "journal": self.__get_reference_journal_string(
                                reference=reference
                            ),
                            "volume": self.__get_reference_volume_string(
                                reference=reference
                            ),
                            "number": self.__get_reference_number_string(
                                reference=reference
                            ),
                            "pages": self.__get_reference_page_string(
                                reference=reference
                            ),
                        }
                    elif entrytype == "book":
                        ref_rec = {
                            "ID": tei_id,
                            "ENTRYTYPE": entrytype,
                            "tei_id": tei_id,
                            "reference_bibliography_id": self.__get_reference_bibliography_id(
                                reference=reference
                            ),
                            "author": self.__get_reference_author_string(
                                reference=reference
                            ),
                            "title": self.__get_reference_title_string(
                                reference=reference
                            ),
                            "year": self.__get_reference_year_string(
                                reference=reference
                            ),
                        }
                    elif entrytype == "misc":
                        ref_rec = {
                            "ID": tei_id,
                            "ENTRYTYPE": entrytype,
                            "tei_id": tei_id,
                            "reference_bibliography_id": self.__get_reference_bibliography_id(
                                reference=reference
                            ),
                            "author": self.__get_reference_author_string(
                                reference=reference
                            ),
                            "title": self.__get_reference_title_string(
                                reference=reference
                            ),
                        }
                except etree.ElementTree.ParseError:
                    continue

                ref_rec = {k: v for k, v in ref_rec.items() if v is not None}
                # print(ref_rec)
                tei_bib_db.append(ref_rec)

        return tei_bib_db

    def get_citations_per_section(self) -> dict:
        """Get a dict of section-names and list-of-citations"""
        section_citations = {}
        parent_map = {c: p for p in self.root.iter() for c in p}
        sections = self.root.iter(f'{self.ns["tei"]}head')
        for section in sections:
            section_name = section.text
            if section_name is None:
                continue
            parent = parent_map[section]
            citation_nodes = parent.findall(f'.//{self.ns["tei"]}ref')
            citations = [
                x.get("target", "NA").replace("#", "")
                for x in citation_nodes
                if x.get("type", "NA") == "bibr"
            ]
            citations = list(filter(lambda a: a != "NA", citations))
            if len(citations) > 0:
                section_citations[section_name.lower()] = citations
        return section_citations

    def mark_references(self, *, records: dict):  # type: ignore
        """Mark references with the additional record ID"""

        tei_records = self.get_bibliography()
        for record_dict in tei_records:
            if "title" not in record_dict:
                continue

            max_sim = 0.9
            max_sim_record = {}
            for local_record_dict in records.values():
                if local_record_dict["colrev_status"] not in [
                    colrev.record.RecordState.rev_included,
                    colrev.record.RecordState.rev_synthesized,
                ]:
                    continue
                rec_sim = colrev.record.Record.get_record_similarity(
                    record_a=colrev.record.Record(data=record_dict),
                    record_b=colrev.record.Record(data=local_record_dict),
                )
                if rec_sim > max_sim:
                    max_sim_record = local_record_dict
                    max_sim = rec_sim
            if len(max_sim_record) == 0:
                continue

            # Record found: mark in tei
            bibliography = self.root.find(f".//{self.ns['tei']}listBibl")
            # mark reference in bibliography
            for ref in bibliography:
                if ref.get(f'{self.ns["w3"]}id') == record_dict["tei_id"]:
                    ref.set("ID", max_sim_record["ID"])
            # mark reference in in-text citations
            for reference in self.root.iter(f'{self.ns["tei"]}ref'):
                if "target" in reference.keys():
                    if reference.get("target") == f"#{record_dict['tei_id']}":
                        reference.set("ID", max_sim_record["ID"])

            # if settings file available: dedupe_io match agains records

        if self.tei_path:
            tree = etree.ElementTree.ElementTree(self.root)
            tree.write(str(self.tei_path))

        return self.root


if __name__ == "__main__":
    pass
