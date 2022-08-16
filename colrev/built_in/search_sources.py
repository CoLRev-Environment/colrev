#! /usr/bin/env python
from dataclasses import asdict

import zope.interface
from dacite import from_dict

import colrev.process
import colrev.record

# TODO
# IEEEXplore
# JSTOR
# CINAHL
# Psychinfo

# VirtualHealthLibrary
# BielefeldAcademicSearchEngine

# paywalled:
# EbscoHost
# ProQuest
# ScienceDirect
# OVID

# challenging:
# ClinicalTrialsGov (no bibliographic data?!)

# AMiner
# arXiv
# CiteSeerX
# DirectoryOfOpenAccessJournals
# EducationResourcesInformationCenter
# SemanticScholar
# SpringerLinks
# WorldCat
# WorldWideScience


# Heurisitics:
# TODO : we should consider all records
# (e.g., the first record with url=ais... may be misleading)
# TBD: applying heuristics before bibtex-conversion?
# -> test bibtex conversion before? (otherwise: abort import/warn?)
# TODO : deal with misleading file extensions.


def apply_field_mapping(
    *, RECORD: colrev.record.PrepRecord, mapping: dict
) -> colrev.record.PrepRecord:
    """Convenience function for the prep scripts"""

    mapping = {k.lower(): v.lower() for k, v in mapping.items()}
    prior_keys = list(RECORD.data.keys())
    # Note : warning: do not create a new dict.
    for key in prior_keys:
        if key.lower() in mapping:
            RECORD.rename_field(key=key, new_key=mapping[key.lower()])

    return RECORD


def drop_fields(
    *, RECORD: colrev.record.PrepRecord, drop=list
) -> colrev.record.PrepRecord:
    """Convenience function for the prep scripts"""

    for key_to_drop in drop:
        RECORD.remove_field(key=key_to_drop)
    return RECORD


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class AISeLibrarySearchSource:
    source_identifier = "https://aisel.aisnet.org/"

    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev.process.DefaultSettings, data=SETTINGS
        )

    def heuristic(self, filename, data):
        result = {"confidence": 0, "source_identifier": self.source_identifier}
        nr_ais_links = data.count("https://aisel.aisnet.org/")
        if nr_ais_links > 0:
            # for the enl file:
            if nr_ais_links >= data.count("%U "):
                result["confidence"] = 0.7
                result["conversion_script"] = {"endpoint": "bibutils"}
                new_filename = filename.with_suffix(".enl")
                print(
                    f"\033[92mRenaming to {new_filename} "
                    "(because the format is .enl, not .txt.)\033[0m"
                )
                filename.rename(new_filename)
                result["filename"] = new_filename
                return result
            # for the bib file:
            if nr_ais_links == data.count("\n}"):
                result["confidence"] = 0.7
                return result

        return result

    def prepare(self, RECORD):
        ais_mapping: dict = {}
        RECORD = apply_field_mapping(RECORD=RECORD, mapping=ais_mapping)

        # Note : simple heuristic
        # but at the moment, AISeLibrary only indexes articles and conference papers
        if (
            RECORD.data.get("volume", "UNKNOWN") != "UNKNOWN"
            or RECORD.data.get("number", "UNKNOWN") != "UNKNOWN"
        ) and not any(
            x in RECORD.data.get("journal", "")
            for x in [
                "HICSS",
                "ICIS",
                "ECIS",
                "AMCIS",
                "Proceedings",
                "All Sprouts Content",
            ]
        ):
            RECORD.data["ENTRYTYPE"] = "article"
            if "journal" not in RECORD.data and "booktitle" in RECORD.data:
                RECORD.rename_field(key="booktitle", new_key="journal")
            if (
                "journal" not in RECORD.data
                and "title" in RECORD.data
                and "chapter" in RECORD.data
            ):
                RECORD.rename_field(key="title", new_key="journal")
                RECORD.rename_field(key="chapter", new_key="title")
                RECORD.remove_field(key="publisher")

        else:
            RECORD.data["ENTRYTYPE"] = "inproceedings"
            RECORD.remove_field(key="publisher")
            if RECORD.data.get("volume", "") == "UNKNOWN":
                RECORD.remove_field(key="volume")
            if RECORD.data.get("number", "") == "UNKNOWN":
                RECORD.remove_field(key="number")

            if (
                "booktitle" not in RECORD.data
                and "title" in RECORD.data
                and "chapter" in RECORD.data
            ):

                RECORD.rename_field(key="title", new_key="booktitle")
                RECORD.rename_field(key="chapter", new_key="title")

            if "journal" in RECORD.data and "booktitle" not in RECORD.data:
                RECORD.rename_field(key="journal", new_key="booktitle")

            if RECORD.data.get("booktitle", "") in [
                "Research-in-Progress Papers",
                "Research Papers",
            ]:
                if "https://aisel.aisnet.org/ecis" in RECORD.data.get("url", ""):
                    RECORD.update_field(
                        key="booktitle", value="ECIS", source="prep_ais_source"
                    )

        if RECORD.data.get("journal", "") == "Management Information Systems Quarterly":
            RECORD.update_field(
                key="journal", value="MIS Quarterly", source="prep_ais_source"
            )

        if "inproceedings" == RECORD.data["ENTRYTYPE"]:
            if "ICIS" in RECORD.data["booktitle"]:
                RECORD.update_field(
                    key="booktitle",
                    value="International Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "PACIS" in RECORD.data["booktitle"]:
                RECORD.update_field(
                    key="booktitle",
                    value="Pacific-Asia Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "ECIS" in RECORD.data["booktitle"]:
                RECORD.update_field(
                    key="booktitle",
                    value="European Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "AMCIS" in RECORD.data["booktitle"]:
                RECORD.update_field(
                    key="booktitle",
                    value="Americas Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "HICSS" in RECORD.data["booktitle"]:
                RECORD.update_field(
                    key="booktitle",
                    value="Hawaii International Conference on System Sciences",
                    source="prep_ais_source",
                )
            if "MCIS" in RECORD.data["booktitle"]:
                RECORD.update_field(
                    key="booktitle",
                    value="Mediterranean Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "ACIS" in RECORD.data["booktitle"]:
                RECORD.update_field(
                    key="booktitle",
                    value="Australasian Conference on Information Systems",
                    source="prep_ais_source",
                )

        if "abstract" in RECORD.data:
            if "N/A" == RECORD.data["abstract"]:
                RECORD.remove_field(key="abstract")
        if "author" in RECORD.data:
            RECORD.update_field(
                key="author",
                value=RECORD.data["author"].replace("\n", " "),
                source="prep_ais_source",
                keep_source_if_equal=True,
            )

        return RECORD


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class GoogleScholarSearchSource:
    source_identifier = "https://scholar.google.com/"

    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev.process.DefaultSettings, data=SETTINGS
        )

    def heuristic(self, filename, data):
        result = {"confidence": 0, "source_identifier": self.source_identifier}
        if "related = {https://scholar.google.com/scholar?q=relat" in data:
            result["confidence"] = 0.7
            return result
        return result

    def prepare(self, RECORD):

        return RECORD


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class WebOfScienceSearchSource:
    source_identifier = (
        "https://www.webofscience.com/wos/woscc/full-record/" + "{{unique-id}}"
    )

    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev.process.DefaultSettings, data=SETTINGS
        )

    def heuristic(self, filename, data):

        result = {"confidence": 0, "source_identifier": self.source_identifier}

        if "Unique-ID = {WOS:" in data:
            result["confidence"] = 0.7
            return result
        if "UT_(Unique_WOS_ID) = {WOS:" in data:
            result["confidence"] = 0.7
            return result
        if "@article{ WOS:" in data:
            result["confidence"] = 1.0
            return result

        return result

    def prepare(self, RECORD):

        return RECORD


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class ScopusSearchSource:
    source_identifier = "{{url}}"

    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev.process.DefaultSettings, data=SETTINGS
        )

    def heuristic(self, filename, data):
        result = {"confidence": 0, "source_identifier": self.source_identifier}
        if "source={Scopus}," in data:
            result["confidence"] = 1.0
            return result
        return result

    def prepare(self, RECORD):

        if "document_type" in RECORD.data:
            if RECORD.data["document_type"] == "Conference Paper":
                RECORD.data["ENTRYTYPE"] = "inproceedings"
                if "journal" in RECORD.data:
                    RECORD.rename_field(key="journal", new_key="booktitle")
            elif RECORD.data["document_type"] == "Conference Review":
                RECORD.data["ENTRYTYPE"] = "proceedings"
                if "journal" in RECORD.data:
                    RECORD.rename_field(key="journal", new_key="booktitle")

            elif RECORD.data["document_type"] == "Article":
                RECORD.data["ENTRYTYPE"] = "article"

            RECORD.remove_field(key="document_type")

        if "Start_Page" in RECORD.data and "End_Page" in RECORD.data:
            if RECORD.data["Start_Page"] != "nan" and RECORD.data["End_Page"] != "nan":
                RECORD.data["pages"] = (
                    RECORD.data["Start_Page"] + "--" + RECORD.data["End_Page"]
                )
                RECORD.data["pages"] = RECORD.data["pages"].replace(".0", "")
                RECORD.remove_field(key="Start_Page")
                RECORD.remove_field(key="End_Page")

        if "note" in RECORD.data:
            if "cited By " in RECORD.data["note"]:
                RECORD.rename_field(key="note", new_key="cited_by")
                RECORD.data["cited_by"] = RECORD.data["cited_by"].replace(
                    "cited By ", ""
                )

        if "author" in RECORD.data:
            RECORD.data["author"] = RECORD.data["author"].replace("; ", " and ")

        drop = ["source"]
        for field_to_drop in drop:
            RECORD.remove_field(key=field_to_drop)

        return RECORD


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class ACMDigitalLibrary:
    # Note : the ID contains the doi
    source_identifier = "https://dl.acm.org/doi/{{ID}}"

    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev.process.DefaultSettings, data=SETTINGS
        )

    def heuristic(self, filename, data):
        result = {"confidence": 0, "source_identifier": self.source_identifier}

        # Simple heuristic:
        if "publisher = {Association for Computing Machinery}," in data:
            result["confidence"] = 0.7
            return result
        # We may also check whether the ID=doi=url
        return result

    def prepare(self, RECORD):
        # TODO (if any)
        return RECORD


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class PubMed:

    source_identifier = "https://pubmed.ncbi.nlm.nih.gov/{{pmid}}"

    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev.process.DefaultSettings, data=SETTINGS
        )

    def heuristic(self, filename, data):
        result = {"confidence": 0, "source_identifier": self.source_identifier}

        # Simple heuristic:
        if "PMID,Title,Authors,Citation,First Author,Journal/Book," in data:
            result["confidence"] = 1.0
            return result
        if "PMID- " in data:
            result["confidence"] = 0.7
            return result

        return result

    def prepare(self, RECORD):
        if "language" in RECORD.data:
            RECORD.data["language"] = RECORD.data["language"].replace("eng", "en")

        if "first_author" in RECORD.data:
            RECORD.remove_field(key="first_author")
        if "journal/book" in RECORD.data:
            RECORD.rename_field(key="journal/book", new_key="journal")
        if "UNKNOWN" == RECORD.data.get("author") and "authors" in RECORD.data:
            RECORD.remove_field(key="author")
            RECORD.rename_field(key="authors", new_key="author")

        if "UNKNOWN" == RECORD.data.get("year"):
            RECORD.remove_field(key="year")
            if "publication_year" in RECORD.data:
                RECORD.rename_field(key="publication_year", new_key="year")

        if "author" in RECORD.data:
            RECORD.data["author"] = colrev.record.PrepRecord.format_author_field(
                input_string=RECORD.data["author"]
            )

        # TBD: how to distinguish other types?
        RECORD.change_ENTRYTYPE(NEW_ENTRYTYPE="article")
        RECORD.import_provenance(source_identifier=self.source_identifier)

        return RECORD


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class WileyOnlineLibrary:

    source_identifier = "{{url}}"

    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev.process.DefaultSettings, data=SETTINGS
        )

    def heuristic(self, filename, data):
        result = {"confidence": 0, "source_identifier": self.source_identifier}

        # Simple heuristic:
        if "eprint = {https://onlinelibrary.wiley.com/doi/pdf/" in data:
            result["confidence"] = 0.7
            return result

        return result

    def prepare(self, RECORD):
        # TODO (if any)
        return RECORD


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class DBLP:

    source_identifier = "{{biburl}}"

    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev.process.DefaultSettings, data=SETTINGS
        )

    def heuristic(self, filename, data):
        result = {"confidence": 0, "source_identifier": self.source_identifier}
        # Simple heuristic:
        if "bibsource = {dblp computer scienc" in data:
            result["confidence"] = 1.0
            return result
        return result

    def prepare(self, RECORD):
        # TODO (if any)
        return RECORD


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class TransportResearchInternationalDocumentation:

    source_identifier = "{{biburl}}"

    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev.process.DefaultSettings, data=SETTINGS
        )

    def heuristic(self, filename, data):
        result = {"confidence": 0, "source_identifier": self.source_identifier}
        # Simple heuristic:
        if "UR  - https://trid.trb.org/view/" in data:
            result["confidence"] = 0.9
            return result
        return result

    def prepare(self, RECORD):
        # TODO (if any)
        return RECORD


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class PDFSearchSource:
    source_identifier = "{{file}}"

    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev.process.DefaultSettings, data=SETTINGS
        )

    def heuristic(self, filename, data):
        result = {"confidence": 0, "source_identifier": self.source_identifier}
        # Note : quick fix (passing the PDFSearchSource settings)
        BSWH = BackwardSearchSearchSource(SETTINGS=asdict(self.SETTINGS))
        if filename.suffix == ".pdf" and not BSWH.heuristic(
            filename=filename, data=data
        ):
            result["confidence"] = 1.0
            return result

        return result

    def prepare(self, RECORD):

        return RECORD


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class BackwardSearchSearchSource:
    source_identifier = "{{cited_by_file}} (references)"

    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev.process.DefaultSettings, data=SETTINGS
        )

    def heuristic(self, filename, data):
        result = {"confidence": 0, "source_identifier": self.source_identifier}
        if str(filename).endswith("_ref_list.pdf"):
            result["confidence"] = 1.0
            return result
        return result

    def prepare(self, RECORD):

        return RECORD
