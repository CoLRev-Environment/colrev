#! /usr/bin/env python
from dataclasses import asdict
from pathlib import Path

import zope.interface
from dacite import from_dict

import colrev.cli_colors as colors
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
    *, record: colrev.record.PrepRecord, mapping: dict
) -> colrev.record.PrepRecord:
    """Convenience function for the prep scripts"""

    mapping = {k.lower(): v.lower() for k, v in mapping.items()}
    prior_keys = list(record.data.keys())
    # Note : warning: do not create a new dict.
    for key in prior_keys:
        if key.lower() in mapping:
            record.rename_field(key=key, new_key=mapping[key.lower()])

    return record


def drop_fields(
    *, record: colrev.record.PrepRecord, drop=list
) -> colrev.record.PrepRecord:
    """Convenience function for the prep scripts"""

    for key_to_drop in drop:
        record.remove_field(key=key_to_drop)
    return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class AISeLibrarySearchSource:
    source_identifier = "https://aisel.aisnet.org/"

    def __init__(self, *, settings: dict) -> None:
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def heuristic(self, filename: Path, data: str) -> dict:
        result = {"confidence": 0, "source_identifier": self.source_identifier}
        nr_ais_links = data.count("https://aisel.aisnet.org/")
        if nr_ais_links > 0:
            # for the enl file:
            if nr_ais_links >= data.count("%U "):
                result["confidence"] = 0.7
                result["conversion_script"] = {"endpoint": "bibutils"}
                new_filename = filename.with_suffix(".enl")
                print(
                    f"{colors.GREEN}Renaming to {new_filename} "
                    f"(because the format is .enl, not .txt.){colors.END}"
                )
                filename.rename(new_filename)
                result["filename"] = new_filename
                return result
            # for the bib file:
            if nr_ais_links == data.count("\n}"):
                result["confidence"] = 0.7
                return result

        return result

    def prepare(self, record: colrev.record.PrepRecord) -> colrev.record.Record:
        ais_mapping: dict = {}
        record = apply_field_mapping(record=record, mapping=ais_mapping)

        # Note : simple heuristic
        # but at the moment, AISeLibrary only indexes articles and conference papers
        if (
            record.data.get("volume", "UNKNOWN") != "UNKNOWN"
            or record.data.get("number", "UNKNOWN") != "UNKNOWN"
        ) and not any(
            x in record.data.get("journal", "")
            for x in [
                "HICSS",
                "ICIS",
                "ECIS",
                "AMCIS",
                "Proceedings",
                "All Sprouts Content",
            ]
        ):
            record.data["ENTRYTYPE"] = "article"
            if "journal" not in record.data and "booktitle" in record.data:
                record.rename_field(key="booktitle", new_key="journal")
            if (
                "journal" not in record.data
                and "title" in record.data
                and "chapter" in record.data
            ):
                record.rename_field(key="title", new_key="journal")
                record.rename_field(key="chapter", new_key="title")
                record.remove_field(key="publisher")

        else:
            record.data["ENTRYTYPE"] = "inproceedings"
            record.remove_field(key="publisher")
            if record.data.get("volume", "") == "UNKNOWN":
                record.remove_field(key="volume")
            if record.data.get("number", "") == "UNKNOWN":
                record.remove_field(key="number")

            if (
                "booktitle" not in record.data
                and "title" in record.data
                and "chapter" in record.data
            ):

                record.rename_field(key="title", new_key="booktitle")
                record.rename_field(key="chapter", new_key="title")

            if "journal" in record.data and "booktitle" not in record.data:
                record.rename_field(key="journal", new_key="booktitle")

            if record.data.get("booktitle", "") in [
                "Research-in-Progress Papers",
                "Research Papers",
            ]:
                if "https://aisel.aisnet.org/ecis" in record.data.get("url", ""):
                    record.update_field(
                        key="booktitle", value="ECIS", source="prep_ais_source"
                    )

        if record.data.get("journal", "") == "Management Information Systems Quarterly":
            record.update_field(
                key="journal", value="MIS Quarterly", source="prep_ais_source"
            )

        if "inproceedings" == record.data["ENTRYTYPE"]:
            if "ICIS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="International Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "PACIS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="Pacific-Asia Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "ECIS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="European Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "AMCIS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="Americas Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "HICSS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="Hawaii International Conference on System Sciences",
                    source="prep_ais_source",
                )
            if "MCIS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="Mediterranean Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "ACIS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="Australasian Conference on Information Systems",
                    source="prep_ais_source",
                )

        if "abstract" in record.data:
            if "N/A" == record.data["abstract"]:
                record.remove_field(key="abstract")
        if "author" in record.data:
            record.update_field(
                key="author",
                value=record.data["author"].replace("\n", " "),
                source="prep_ais_source",
                keep_source_if_equal=True,
            )

        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class GoogleScholarSearchSource:
    source_identifier = "https://scholar.google.com/"

    def __init__(self, *, settings: dict) -> None:
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def heuristic(
        self, filename: Path, data: str  # pylint: disable=unused-argument
    ) -> dict:
        result = {"confidence": 0, "source_identifier": self.source_identifier}
        if "related = {https://scholar.google.com/scholar?q=relat" in data:
            result["confidence"] = 0.7
            return result
        return result

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class WebOfScienceSearchSource:
    source_identifier = (
        "https://www.webofscience.com/wos/woscc/full-record/" + "{{unique-id}}"
    )

    def __init__(self, *, settings: dict) -> None:
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def heuristic(
        self, filename: Path, data: str  # pylint: disable=unused-argument
    ) -> dict:

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

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class ScopusSearchSource:
    source_identifier = "{{url}}"

    def __init__(self, *, settings: dict) -> None:
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def heuristic(
        self, filename: Path, data: str  # pylint: disable=unused-argument
    ) -> dict:
        result = {"confidence": 0, "source_identifier": self.source_identifier}
        if "source={Scopus}," in data:
            result["confidence"] = 1.0
            return result
        return result

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        if "document_type" in record.data:
            if record.data["document_type"] == "Conference Paper":
                record.data["ENTRYTYPE"] = "inproceedings"
                if "journal" in record.data:
                    record.rename_field(key="journal", new_key="booktitle")
            elif record.data["document_type"] == "Conference Review":
                record.data["ENTRYTYPE"] = "proceedings"
                if "journal" in record.data:
                    record.rename_field(key="journal", new_key="booktitle")

            elif record.data["document_type"] == "Article":
                record.data["ENTRYTYPE"] = "article"

            record.remove_field(key="document_type")

        if "Start_Page" in record.data and "End_Page" in record.data:
            if record.data["Start_Page"] != "nan" and record.data["End_Page"] != "nan":
                record.data["pages"] = (
                    record.data["Start_Page"] + "--" + record.data["End_Page"]
                )
                record.data["pages"] = record.data["pages"].replace(".0", "")
                record.remove_field(key="Start_Page")
                record.remove_field(key="End_Page")

        if "note" in record.data:
            if "cited By " in record.data["note"]:
                record.rename_field(key="note", new_key="cited_by")
                record.data["cited_by"] = record.data["cited_by"].replace(
                    "cited By ", ""
                )

        if "author" in record.data:
            record.data["author"] = record.data["author"].replace("; ", " and ")

        drop = ["source"]
        for field_to_drop in drop:
            record.remove_field(key=field_to_drop)

        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class ACMDigitalLibrary:
    # Note : the ID contains the doi
    source_identifier = "https://dl.acm.org/doi/{{ID}}"

    def __init__(self, *, settings: dict) -> None:
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def heuristic(
        self, filename: Path, data: str  # pylint: disable=unused-argument
    ) -> dict:
        result = {"confidence": 0, "source_identifier": self.source_identifier}

        # Simple heuristic:
        if "publisher = {Association for Computing Machinery}," in data:
            result["confidence"] = 0.7
            return result
        # We may also check whether the ID=doi=url
        return result

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:
        # TODO (if any)
        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class PubMed:

    source_identifier = "https://pubmed.ncbi.nlm.nih.gov/{{pmid}}"

    def __init__(self, *, settings: dict) -> None:
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def heuristic(
        self, filename: Path, data: str  # pylint: disable=unused-argument
    ) -> dict:
        result = {"confidence": 0, "source_identifier": self.source_identifier}

        # Simple heuristic:
        if "PMID,Title,Authors,Citation,First Author,Journal/Book," in data:
            result["confidence"] = 1.0
            return result
        if "PMID- " in data:
            result["confidence"] = 0.7
            return result

        return result

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:
        if "language" in record.data:
            record.data["language"] = record.data["language"].replace("eng", "en")

        if "first_author" in record.data:
            record.remove_field(key="first_author")
        if "journal/book" in record.data:
            record.rename_field(key="journal/book", new_key="journal")
        if "UNKNOWN" == record.data.get("author") and "authors" in record.data:
            record.remove_field(key="author")
            record.rename_field(key="authors", new_key="author")

        if "UNKNOWN" == record.data.get("year"):
            record.remove_field(key="year")
            if "publication_year" in record.data:
                record.rename_field(key="publication_year", new_key="year")

        if "author" in record.data:
            record.data["author"] = colrev.record.PrepRecord.format_author_field(
                input_string=record.data["author"]
            )

        # TBD: how to distinguish other types?
        record.change_entrytype(new_entrytype="article")
        record.import_provenance(source_identifier=self.source_identifier)

        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class WileyOnlineLibrary:

    source_identifier = "{{url}}"

    def __init__(self, *, settings: dict) -> None:
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def heuristic(
        self, filename: Path, data: str  # pylint: disable=unused-argument
    ) -> dict:
        result = {"confidence": 0, "source_identifier": self.source_identifier}

        # Simple heuristic:
        if "eprint = {https://onlinelibrary.wiley.com/doi/pdf/" in data:
            result["confidence"] = 0.7
            return result

        return result

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:
        # TODO (if any)
        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class DBLP:

    source_identifier = "{{biburl}}"

    def __init__(self, *, settings: dict) -> None:
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def heuristic(
        self, filename: Path, data: str  # pylint: disable=unused-argument
    ) -> dict:
        result = {"confidence": 0, "source_identifier": self.source_identifier}
        # Simple heuristic:
        if "bibsource = {dblp computer scienc" in data:
            result["confidence"] = 1.0
            return result
        return result

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:
        # TODO (if any)
        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class TransportResearchInternationalDocumentation:

    source_identifier = "{{biburl}}"

    def __init__(self, *, settings: dict) -> None:
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def heuristic(
        self, filename: Path, data: str  # pylint: disable=unused-argument
    ) -> dict:
        result = {"confidence": 0, "source_identifier": self.source_identifier}
        # Simple heuristic:
        if "UR  - https://trid.trb.org/view/" in data:
            result["confidence"] = 0.9
            return result
        return result

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:
        # TODO (if any)
        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class PDFSearchSource:
    source_identifier = "{{file}}"

    def __init__(self, *, settings: dict) -> None:
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def heuristic(self, filename: Path, data: str) -> dict:
        result = {"confidence": 0, "source_identifier": self.source_identifier}
        # Note : quick fix (passing the PDFSearchSource settings)
        backward_search_source = BackwardSearchSearchSource(
            settings=asdict(self.settings)
        )
        if filename.suffix == ".pdf" and not backward_search_source.heuristic(
            filename=filename, data=data
        ):
            result["confidence"] = 1.0
            return result

        return result

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        return record


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class BackwardSearchSearchSource:
    source_identifier = "{{cited_by_file}} (references)"

    def __init__(self, *, settings: dict) -> None:
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def heuristic(
        self, filename: Path, data: str  # pylint: disable=unused-argument
    ) -> dict:
        result = {"confidence": 0, "source_identifier": self.source_identifier}
        if str(filename).endswith("_ref_list.pdf"):
            result["confidence"] = 1.0
            return result
        return result

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        return record
