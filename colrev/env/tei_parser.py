#! /usr/bin/env python
"""Service parsing metadata from PDFs/TEIs (created by GROBID)."""
from __future__ import annotations

import re
import typing
from pathlib import Path

import requests
from lxml import etree
from lxml.etree import XMLSyntaxError  # nosec

import colrev.env.grobid_service
import colrev.exceptions as colrev_exceptions
import colrev.record.record
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import RecordState

# xpath alternative:
# tree.xpath("//tei:sourceDesc/tei:biblStruct/tei:monogr/tei:idno",
# namespaces={"tei": "http://www.tei-c.org/ns/1.0"})
# abstract_node =tree.xpath("//tei:profileDesc/tei:abstract",
# namespaces={"tei": "http://www.tei-c.org/ns/1.0"})
# etree.tostring(abstract_node[0]).decode("utf-8")

if typing.TYPE_CHECKING:  # pragma: no cover
    from xml.etree.ElementTree import Element  # nosec


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
        pdf_path: typing.Optional[Path] = None,
        tei_path: typing.Optional[Path] = None,
    ):
        """Creates a TEI file
        modes of operation:
        - pdf_path: create TEI and temporarily store in self.data
        - pfd_path and tei_path: create TEI and save in tei_path
        - tei_path: read TEI from file
        """
        # pylint: disable=consider-using-with
        assert pdf_path is not None or tei_path is not None
        if pdf_path is not None:
            if pdf_path.is_symlink():  # pragma: no cover
                pdf_path = pdf_path.resolve()
        self.pdf_path = pdf_path
        self.tei_path = tei_path
        if pdf_path is not None and not pdf_path.is_file():
            raise FileNotFoundError

        load_from_tei = False
        if tei_path is not None:
            if tei_path.is_file():
                load_from_tei = True

        if pdf_path is not None and not load_from_tei:
            # TODO / TBD:
            # Do not run in continuous-integration environment
            # if not self.review_manager.in_ci_environment():
            grobid_service = colrev.env.grobid_service.GrobidService()
            grobid_service.start()
            self._create_tei()

        elif tei_path is not None:
            self.root = self._read_from_tei()  # type: ignore

    def _read_from_tei(self):  # type: ignore
        """Read a TEI from file"""
        with open(self.tei_path, "rb") as data:
            xslt_content = data.read()

        if b"[BAD_INPUT_DATA]" in xslt_content[:100]:
            raise colrev_exceptions.TEIException()

        return etree.XML(xslt_content)

    def _create_tei(self) -> None:
        """Create the TEI (based on GROBID)"""
        grobid_service = colrev.env.grobid_service.GrobidService()
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

            if ret.status_code != 200:  # pragma: no cover
                raise colrev_exceptions.TEIException()

            if b"[TIMEOUT]" in ret.content:  # pragma: no cover
                raise colrev_exceptions.TEITimeoutException()

            self.root = etree.fromstring(ret.content)

            if self.tei_path is not None:
                self.tei_path.parent.mkdir(exist_ok=True, parents=True)
                with open(self.tei_path, "wb") as file:
                    file.write(ret.content)

                # Note : reopen/write to prevent format changes in the enhancement
                with open(self.tei_path, "rb") as file:
                    xml_fstring = file.read()
                self.root = etree.fromstring(xml_fstring)

                tree = etree.ElementTree(self.root)
                tree.write(str(self.tei_path), encoding="utf-8")
        except requests.exceptions.ConnectionError as exc:  # pragma: no cover
            print(exc)
            print(str(self.pdf_path))
            raise colrev_exceptions.TEITimeoutException() from exc

    def get_tei_str(self) -> str:
        """Get the TEI string"""
        try:
            etree.register_namespace("tei", "http://www.tei-c.org/ns/1.0")
            return etree.tostring(self.root).decode("utf-8")
        except XMLSyntaxError as exc:  # pragma: no cover
            raise colrev_exceptions.TEIException from exc

    def get_grobid_version(self) -> str:
        """Get the GROBID version used for TEI creation"""
        grobid_version = ""
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

    def _parse_author_dict(self, *, author_pers_node: Element) -> dict:
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
            author_dict["middlename"] = middlename
        else:
            middlename = ""

        return author_dict

    def _get_author_name_from_node(self, *, author_node: Element) -> str:
        authorname = ""

        author_pers_node = author_node.find(self.ns["tei"] + "persName")
        if author_pers_node is None:
            return authorname

        author_dict = self._parse_author_dict(author_pers_node=author_pers_node)

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

    def _get_paper_doi(self, reference: Element) -> str:
        doi = ""
        dois = reference.findall(".//" + self.ns["tei"] + "idno[@type='DOI']")
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

        abstract_text = ""
        profile_description = self.root.find(".//" + self.ns["tei"] + "profileDesc")
        if profile_description is not None:
            abstract_node = profile_description.find(
                ".//" + self.ns["tei"] + "abstract"
            )
            html_str = etree.tostring(abstract_node).decode("utf-8")
            abstract_text = cleanhtml(html_str)
        abstract_text = abstract_text.lstrip().rstrip()
        return abstract_text

    def get_metadata(self) -> dict:
        """Get the metadata of the PDF (title, author, ...) as a dict"""

        reference = self.root.find(".//" + self.ns["tei"] + "sourceDesc").find(
            ".//" + self.ns["tei"] + "biblStruct"
        )
        record = self._get_dict_from_reference(reference)

        if Fields.TITLE in record:
            record[Fields.TITLE] = (
                record[Fields.TITLE]
                .replace("(Completed paper)", "")
                .replace("(Completed-paper)", "")
                .replace("(Research-in-Progress)", "")
                .replace("Completed Research Paper", "")
            )

        for key, value in record.items():
            if key != Fields.FILE:
                record[key] = value.replace("}", "").replace("{", "").rstrip("\\")

        record = {k: v for k, v in record.items() if v != ""}
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

                        author_dict = self._parse_author_dict(
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

    # reference elements  ----------------------------

    def _get_reference_bibliography_tei_id(self, reference: Element) -> str:
        tei_id = ""
        try:
            tei_id = reference.attrib[self.ns["w3"] + "id"]
        except KeyError:
            pass
        return tei_id

    def _get_reference_author_string(self, reference: Element) -> str:
        author_list = []
        if reference.find(self.ns["tei"] + "analytic") is not None:
            authors_node = reference.find(self.ns["tei"] + "analytic")
        elif reference.find(self.ns["tei"] + "monogr") is not None:
            authors_node = reference.find(self.ns["tei"] + "monogr")
        else:
            return ""

        if authors_node is not None:
            for author_node in authors_node.iterfind(self.ns["tei"] + "author"):
                authorname = self._get_author_name_from_node(author_node=author_node)

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
        return author_string

    def _get_reference_title_string(self, reference: Element) -> str:
        title_string = ""
        title = None
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

    def _get_reference_year_string(self, reference: Element) -> str:
        year_string = ""
        year = None
        if reference.find(self.ns["tei"] + "monogr") is not None:
            monogr_node = reference.find(self.ns["tei"] + "monogr")
            if monogr_node is not None:
                imprint_node = monogr_node.find(self.ns["tei"] + "imprint")
                if imprint_node is not None:
                    year = imprint_node.find(self.ns["tei"] + "date")

        if year is not None:
            for name, value in sorted(year.items()):
                year_string = value if (name == "when") else ""

        match = re.match(r"\d{4}", year_string)
        year_string = match.group(0) if match else year_string
        return year_string

    def _get_reference_page_string(self, reference: Element) -> str:
        page_string = ""
        page_list = []

        if reference.find(self.ns["tei"] + "monogr") is not None:
            monogr_node = reference.find(self.ns["tei"] + "monogr")
            if monogr_node is not None:
                imprint_node = monogr_node.find(self.ns["tei"] + "imprint")
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

        return page_string

    def _get_reference_number_string(self, reference: Element) -> str:
        number_string = ""
        number_list = []

        if reference.find(self.ns["tei"] + "monogr") is not None:
            monogr_node = reference.find(self.ns["tei"] + "monogr")
            if monogr_node is not None:
                imprint_node = monogr_node.find(self.ns["tei"] + "imprint")
                if imprint_node is not None:
                    number_list = imprint_node.findall(
                        self.ns["tei"] + "biblScope[@unit='issue']"
                    )

        for number in number_list:
            if number.text is not None:
                number_string = number.text

        return number_string

    def _get_reference_volume_string(self, reference: Element) -> str:
        volume_string = ""
        volume_list = []

        if reference.find(self.ns["tei"] + "monogr") is not None:
            monogr_node = reference.find(self.ns["tei"] + "monogr")
            if monogr_node is not None:
                imprint_node = monogr_node.find(self.ns["tei"] + "imprint")
                if imprint_node is not None:
                    volume_list = imprint_node.findall(
                        self.ns["tei"] + "biblScope[@unit='volume']"
                    )

        for volume in volume_list:
            if volume.text is not None:
                volume_string = volume.text

        return volume_string

    def _get_reference_monograph_string(self, reference: Element) -> str:
        journal_title = ""
        if reference.find(self.ns["tei"] + "monogr") is not None:
            monogr_node = reference.find(self.ns["tei"] + "monogr")
            if monogr_node is not None:
                monogr_title = monogr_node.find(self.ns["tei"] + "title")
                if monogr_title is not None:
                    if monogr_title.text is not None:
                        journal_title = monogr_title.text

        return journal_title

    # pylint: disable=too-many-nested-blocks
    def _get_entrytype(self, reference: Element) -> str:
        entrytype = ENTRYTYPES.MISC
        if reference.find(self.ns["tei"] + "monogr") is not None:
            monogr_node = reference.find(self.ns["tei"] + "monogr")
            if monogr_node is not None:
                meeting_node = monogr_node.find(self.ns["tei"] + "meeting")

                if meeting_node is not None:
                    entrytype = ENTRYTYPES.INPROCEEDINGS
                else:
                    title_node = monogr_node.find(self.ns["tei"] + "title")
                    if title_node is not None:
                        if title_node.text is not None:
                            if any(
                                x in title_node.text.lower()
                                for x in [
                                    "conference",
                                    "proceedings",
                                    "symposium",
                                    "meeting",
                                ]
                            ):
                                entrytype = ENTRYTYPES.INPROCEEDINGS
                                return entrytype

                        if title_node.get("level", "") == "j":
                            entrytype = ENTRYTYPES.ARTICLE
                        elif title_node.get("level", "") in ["m", "s"]:
                            entrytype = ENTRYTYPES.BOOK
        return entrytype

    def _get_tei_id_count(self, *, tei_id: str) -> int:
        count = 0

        for reference in self.root.iter(self.ns["tei"] + "ref"):
            if "target" in reference.keys():
                if reference.get("target") == f"#{tei_id}":
                    count += 1

        return count

    def _get_dict_from_reference(self, reference: Element) -> dict:
        entrytype = self._get_entrytype(reference)
        tei_id = self._get_reference_bibliography_tei_id(reference)

        ground_dict = {
            Fields.ID: tei_id,
            Fields.TEI_ID: tei_id,
            Fields.AUTHOR: self._get_reference_author_string(reference),
            Fields.TITLE: self._get_reference_title_string(reference),
            Fields.YEAR: self._get_reference_year_string(reference),
            Fields.PAGES: self._get_reference_page_string(reference),
            Fields.DOI: self._get_paper_doi(reference),
        }

        if entrytype == ENTRYTYPES.ARTICLE:
            ref_rec = {
                Fields.ENTRYTYPE: entrytype,
                Fields.JOURNAL: self._get_reference_monograph_string(reference),
                Fields.VOLUME: self._get_reference_volume_string(reference),
                Fields.NUMBER: self._get_reference_number_string(reference),
            }
        elif entrytype == ENTRYTYPES.BOOK:
            ref_rec = {
                Fields.ENTRYTYPE: entrytype,
                Fields.TITLE: self._get_reference_monograph_string(reference),
            }
        elif entrytype == ENTRYTYPES.INPROCEEDINGS:
            ref_rec = {
                Fields.ENTRYTYPE: entrytype,
                Fields.BOOKTITLE: self._get_reference_monograph_string(reference),
            }
        else:
            ref_rec = {
                Fields.ENTRYTYPE: ENTRYTYPES.MISC,
            }
        ref_rec = {**ground_dict, **ref_rec}

        ref_rec = {k: v for k, v in ref_rec.items() if v != ""}
        return ref_rec

    def get_references(self, *, add_intext_citation_count: bool = False) -> list:
        """Get the bibliography (references section) as a list of record dicts"""
        # Note : could also allow top-10 % of most frequent in-text citations

        #  https://epidoc.stoa.org/gl/latest/ref-title.html

        bibliographies = self.root.iter(self.ns["tei"] + "listBibl")
        tei_bib_db = []
        for bibliography in bibliographies:
            for reference in bibliography:
                ref_rec = self._get_dict_from_reference(reference)

                if add_intext_citation_count:
                    nr_citations = self._get_tei_id_count(tei_id=ref_rec[Fields.ID])
                    ref_rec[Fields.NR_INTEXT_CITATIONS] = nr_citations  # type: ignore

                tei_bib_db.append(ref_rec)

        return tei_bib_db

    def get_citations_per_section(self) -> dict:
        """Get a dict of section-names and list-of-citations"""
        section_citations = {}
        parent_map = {c: p for p in self.root.iter() for c in p}
        sections = self.root.iter(f'{self.ns["tei"]}head')
        for section in sections:
            section_name = section.text
            if section_name is not None:
                parent = parent_map[section]
                citation_nodes = parent.findall(f'.//{self.ns["tei"]}ref')
                citations = [
                    x.get("target", "").replace("#", "")
                    for x in citation_nodes
                    if x.get("type", "") == "bibr"
                ]
                citations = list(filter(lambda a: a != "", citations))
                if len(citations) > 0:
                    section_citations[section_name.lower()] = citations
        return section_citations

    def mark_references(self, *, records: dict):  # type: ignore
        """Mark references with the additional record ID"""

        tei_records = self.get_references()
        for record_dict in tei_records:
            if Fields.TITLE not in record_dict:
                continue

            max_sim = 0.9
            max_sim_record = {}
            for local_record_dict in records.values():
                if local_record_dict[Fields.STATUS] not in [
                    RecordState.rev_included,
                    RecordState.rev_synthesized,
                ]:
                    continue
                rec_sim = colrev.record.record.Record.get_record_similarity(
                    colrev.record.record.Record(record_dict),
                    colrev.record.record.Record(local_record_dict),
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
                if ref.get(f'{self.ns["w3"]}id') == record_dict[Fields.TEI_ID]:
                    ref.set(Fields.ID, max_sim_record[Fields.ID])
            # mark reference in in-text citations
            for reference in self.root.iter(f'{self.ns["tei"]}ref'):
                if "target" in reference.keys():
                    if reference.get("target") == f"#{record_dict['tei_id']}":
                        reference.set(Fields.ID, max_sim_record[Fields.ID])

            # if settings file available: dedupe_io match agains records

        if self.tei_path:
            tree = etree.ElementTree(self.root)
            tree.write(str(self.tei_path))

        return self.root
