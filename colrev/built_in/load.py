#! /usr/bin/env python
import json
from pathlib import Path

import docker
import pandas as pd
import requests
import zope.interface
from dacite import from_dict

import colrev.exceptions as colrev_exceptions
import colrev.process


@zope.interface.implementer(colrev.process.LoadEndpoint)
class BibPybtexLoader:

    supported_extensions = ["bib"]

    def __init__(self, *, load, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def load(self, loader, source):
        if source.filename.is_file():
            with open(source.filename, encoding="utf8") as bibtex_file:
                records = loader.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )

            loader.check_bib_file(source, records)


class SpreadsheetLoadUtility:
    @classmethod
    def preprocess_records(cls, *, records: list) -> dict:
        next_id = 1
        for record_dict in records:

            if "ENTRYTYPE" not in record_dict:
                if "" != record_dict.get("journal", ""):
                    record_dict["ENTRYTYPE"] = "article"
                if "" != record_dict.get("booktitle", ""):
                    record_dict["ENTRYTYPE"] = "inproceedings"
                else:
                    record_dict["ENTRYTYPE"] = "misc"

            if "ID" not in record_dict:
                if "citation_key" in record_dict:
                    record_dict["ID"] = record_dict["citation_key"]
                else:
                    record_dict["ID"] = next_id
                    next_id += 1

            for key, value in record_dict.items():
                record_dict[key] = str(value)

            if "authors" in record_dict and "author" not in record_dict:
                record_dict["author"] = record_dict["authors"]
                del record_dict["authors"]
            if "publication_year" in record_dict and "year" not in record_dict:
                record_dict["year"] = record_dict["publication_year"]
                del record_dict["publication_year"]
            # Note: this is a simple heuristic:
            if (
                "journal/book" in record_dict
                and "journal" not in record_dict
                and "doi" in record_dict
            ):
                record_dict["journal"] = record_dict["journal/book"]
                del record_dict["journal/book"]

        if all("ID" in r for r in records):
            records_dict = {r["ID"]: r for r in records}
        else:
            records_dict = {}
            for i, record in enumerate(records):
                records_dict[str(i)] = record

        for r_dict in records_dict.values():
            if "no year" == r_dict.get("year", "NA"):
                del r_dict["year"]
            if "no journal" == r_dict.get("journal", "NA"):
                del r_dict["journal"]
            if "no volume" == r_dict.get("volume", "NA"):
                del r_dict["volume"]
            if "no pages" == r_dict.get("pages", "NA"):
                del r_dict["pages"]
            if "no issue" == r_dict.get("issue", "NA"):
                del r_dict["issue"]
            if "no number" == r_dict.get("number", "NA"):
                del r_dict["number"]
            if "no doi" == r_dict.get("doi", "NA"):
                del r_dict["doi"]
            if "no type" == r_dict.get("type", "NA"):
                del r_dict["type"]
            if "author_count" in r_dict:
                del r_dict["author_count"]
            if "no Number-of-Cited-References" == r_dict.get(
                "number_of_cited_references", "NA"
            ):
                del r_dict["number_of_cited_references"]
            if "no file" in r_dict.get("file_name", "NA"):
                del r_dict["file_name"]
            if "times_cited" == r_dict.get("times_cited", "NA"):
                del r_dict["times_cited"]

        return records_dict


@zope.interface.implementer(colrev.process.LoadEndpoint)
class CSVLoader:
    supported_extensions = ["csv"]

    def __init__(self, *, load, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def load(self, loader, source):

        try:
            data = pd.read_csv(source.filename)
        except pd.errors.ParserError as exc:
            raise colrev_exceptions.ImportException(
                f"Error: Not a csv file? {source.filename.name}"
            ) from exc

        data.columns = data.columns.str.replace(" ", "_")
        data.columns = data.columns.str.replace("-", "_")
        data.columns = data.columns.str.lower()
        records = data.to_dict("records")
        records = SpreadsheetLoadUtility.preprocess_records(records=records)

        loader.check_bib_file(source, records)

        loader.save_records(
            records=records, corresponding_bib_file=source.corresponding_bib_file
        )


@zope.interface.implementer(colrev.process.LoadEndpoint)
class ExcelLoader:

    supported_extensions = ["xls", "xlsx"]

    def __init__(self, *, load, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def load(self, loader, source):

        try:
            data = pd.read_excel(
                source.filename, dtype=str
            )  # dtype=str to avoid type casting
        except pd.errors.ParserError:
            loader.review_manager.logger.error(
                f"Error: Not an xlsx file: {source.filename.name}"
            )
            return
        data.columns = data.columns.str.replace(" ", "_")
        data.columns = data.columns.str.replace("-", "_")
        data.columns = data.columns.str.lower()
        records = data.to_dict("records")
        records = SpreadsheetLoadUtility.preprocess_records(records=records)

        loader.check_bib_file(source, records)

        loader.save_records(
            records=records, corresponding_bib_file=source.corresponding_bib_file
        )


@zope.interface.implementer(colrev.process.LoadEndpoint)
class ZoteroTranslationLoader:

    supported_extensions = ["ris", "rdf", "json", "mods", "xml", "marc", "txt"]

    def __init__(self, *, load, settings):

        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

        self.zotero_translation_service = (
            load.review_manager.get_zotero_translation_service()
        )
        self.zotero_translation_service.start_zotero_translators()

    def load(self, loader, source):

        # pylint: disable=consider-using-with

        files = {"file": open(source.filename, "rb")}
        headers = {"Content-type": "text/plain"}
        ret = requests.post(
            "http://127.0.0.1:1969/import", headers=headers, files=files
        )
        headers = {"Content-type": "application/json"}
        if "No suitable translators found" == ret.content.decode("utf-8"):
            raise colrev_exceptions.ImportException(
                "Zotero translators: No suitable import translators found"
            )

        try:
            zotero_format = json.loads(ret.content)
            ret = requests.post(
                "http://127.0.0.1:1969/export?format=bibtex",
                headers=headers,
                json=zotero_format,
            )
            records = loader.review_manager.dataset.load_records_dict(
                load_str=ret.content.decode("utf-8")
            )

        except Exception as exc:
            raise colrev_exceptions.ImportException(
                f"Zotero import translators failed ({exc})"
            )

        loader.check_bib_file(source, records)

        loader.save_records(
            records=records, corresponding_bib_file=source.corresponding_bib_file
        )


@zope.interface.implementer(colrev.process.LoadEndpoint)
class MarkdownLoader:

    supported_extensions = ["md"]

    def __init__(self, *, load, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def load(self, loader, source):

        grobid_service = loader.review_manager.get_grobid_service()

        grobid_service.check_grobid_availability()
        with open(source.filename, encoding="utf8") as file:
            if source.filename.suffix == ".md":
                references = [line.rstrip() for line in file if "#" not in line[:2]]
            else:
                references = [line.rstrip() for line in file]

        data = ""
        ind = 0
        for ref in references:
            options = {}
            options["consolidateCitations"] = "1"
            options["citations"] = ref
            ret = requests.post(
                grobid_service.GROBID_URL + "/api/processCitation",
                data=options,
                headers={"Accept": "application/x-bibtex"},
            )
            ind += 1
            data = data + "\n" + ret.text.replace("{-1,", "{" + str(ind) + ",")

        records = loader.review_manager.dataset.load_records_dict(load_str=data)

        loader.check_bib_file(source, records)

        loader.save_records(
            records=records, corresponding_bib_file=source.corresponding_bib_file
        )


@zope.interface.implementer(colrev.process.LoadEndpoint)
class BibutilsLoader:

    supported_extensions = ["ris", "end", "enl", "copac", "isi", "med"]

    def __init__(self, *, load, settings):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def load(self, loader, source):
        def bibutils_convert(script: str, data: str) -> str:

            if "xml2bib" == script:
                script = script + " -b -w -sk "
            else:
                script = script + " -i unicode "

            client = docker.APIClient()
            try:
                container = client.create_container("bibutils", script, stdin_open=True)
            except docker.errors.ImageNotFound as exc:
                raise colrev_exceptions.ImportException(
                    "Docker images for bibutils not found"
                ) from exc

            sock = client.attach_socket(
                container, params={"stdin": 1, "stdout": 1, "stderr": 1, "stream": 1}
            )
            client.start(container)

            # pylint: disable=protected-access
            sock._sock.send(data.encode())
            sock._sock.close()
            sock.close()

            client.wait(container)
            stdout = client.logs(container, stderr=False).decode()
            client.remove_container(container)

            return stdout

        with open(source.filename, encoding="utf-8") as reader:
            data = reader.read()

        filetype = Path(source.filename).suffix.replace(".", "")

        if filetype in ["enl", "end"]:
            data = bibutils_convert("end2xml", data)
        elif filetype in ["copac"]:
            data = bibutils_convert("copac2xml", data)
        elif filetype in ["isi"]:
            data = bibutils_convert("isi2xml", data)
        elif filetype in ["med"]:
            data = bibutils_convert("med2xml", data)
        elif filetype in ["ris"]:
            data = bibutils_convert("ris2xml", data)
        else:
            raise colrev_exceptions.ImportException(
                f"Filetype {filetype} not supported by bibutils"
            )

        data = bibutils_convert("xml2bib", data)

        records = loader.review_manager.dataset.load_records_dict(load_str=data)

        loader.check_bib_file(source, records)

        loader.save_records(
            records=records, corresponding_bib_file=source.corresponding_bib_file
        )
