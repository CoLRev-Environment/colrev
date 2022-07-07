#! /usr/bin/env python
from pathlib import Path

import docker
import zope.interface

from colrev_core.process import LoadEndpoint

# TODO : TBD: what to return when conversion failed? ([]?)


@zope.interface.implementer(LoadEndpoint)
class BibPybtexLoader:

    supported_extensions = ["bib"]

    def load(self, LOADER, SOURCE):

        return


class SpreadsheetLoadUtility:
    @classmethod
    def preprocess_records(cls, *, records: list) -> list:
        ID = 1
        for x in records:
            if "ENTRYTYPE" not in x:
                if "" != x.get("journal", ""):
                    x["ENTRYTYPE"] = "article"
                if "" != x.get("booktitle", ""):
                    x["ENTRYTYPE"] = "inproceedings"
                else:
                    x["ENTRYTYPE"] = "misc"

            if "ID" not in x:
                if "citation_key" in x:
                    x["ID"] = x["citation_key"]
                else:
                    x["ID"] = ID
                    ID += 1

            for k, v in x.items():
                x[k] = str(v)

        for x in records:
            if "no year" == x.get("year", "NA"):
                del x["year"]
            if "no journal" == x.get("journal", "NA"):
                del x["journal"]
            if "no volume" == x.get("volume", "NA"):
                del x["volume"]
            if "no pages" == x.get("pages", "NA"):
                del x["pages"]
            if "no issue" == x.get("issue", "NA"):
                del x["issue"]
            if "no number" == x.get("number", "NA"):
                del x["number"]
            if "no doi" == x.get("doi", "NA"):
                del x["doi"]
            if "no type" == x.get("type", "NA"):
                del x["type"]
            if "author_count" in x:
                del x["author_count"]
            if "no Number-of-Cited-References" == x.get(
                "number_of_cited_references", "NA"
            ):
                del x["number_of_cited_references"]
            if "no file" in x.get("file_name", "NA"):
                del x["file_name"]
            if "times_cited" == x.get("times_cited", "NA"):
                del x["times_cited"]

        return records


@zope.interface.implementer(LoadEndpoint)
class CSVLoader:
    supported_extensions = ["csv"]

    def load(self, LOADER, SOURCE):
        import pandas as pd

        try:
            data = pd.read_csv(SOURCE.filename)
        except pd.errors.ParserError:
            LOADER.REVIEW_MANAGER.logger.error(
                f"Error: Not a csv file? {SOURCE.filename.name}"
            )
            pass
            return []
        data.columns = data.columns.str.replace(" ", "_")
        data.columns = data.columns.str.replace("-", "_")
        records = data.to_dict("records")
        records = SpreadsheetLoadUtility.preprocess_records(records=records)

        LOADER.save_records(
            records=records, corresponding_bib_file=SOURCE.corresponding_bib_file
        )

        return


@zope.interface.implementer(LoadEndpoint)
class ExcelLoader:

    supported_extensions = ["xls", "xlsx"]

    def load(self, LOADER, SOURCE):
        import pandas as pd

        try:
            data = pd.read_excel(
                SOURCE.filename, dtype=str
            )  # dtype=str to avoid type casting
        except pd.errors.ParserError:
            LOADER.REVIEW_MANAGER.logger.error(
                f"Error: Not an xlsx file: {SOURCE.filename.name}"
            )
            pass
            return []
        data.columns = data.columns.str.replace(" ", "_")
        data.columns = data.columns.str.replace("-", "_")
        records = data.to_dict("records")
        records = SpreadsheetLoadUtility.preprocess_records(records=records)

        LOADER.save_records(
            records=records, corresponding_bib_file=SOURCE.corresponding_bib_file
        )

        return


@zope.interface.implementer(LoadEndpoint)
class ZoteroTranslationLoader:

    supported_extensions = ["ris", "rdf", "json", "mods", "xml", "marc", "txt"]

    def __init__(self):
        from colrev_core.environment import ZoteroTranslationService

        self.ZOTERO_TRANSLATION_SERVICE = ZoteroTranslationService()
        self.ZOTERO_TRANSLATION_SERVICE.start_zotero_translators()

    def load(self, LOADER, SOURCE):
        import requests
        from colrev_core.load import ImportException
        import json

        files = {"file": open(SOURCE.filename, "rb")}
        headers = {"Content-type": "text/plain"}
        r = requests.post("http://127.0.0.1:1969/import", headers=headers, files=files)
        headers = {"Content-type": "application/json"}
        if "No suitable translators found" == r.content.decode("utf-8"):
            raise ImportException(
                "Zotero translators: No suitable import translators found"
            )

        try:
            zotero_format = json.loads(r.content)
            et = requests.post(
                "http://127.0.0.1:1969/export?format=bibtex",
                headers=headers,
                json=zotero_format,
            )
            records = LOADER.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                load_str=et.content.decode("utf-8")
            )

        except Exception as e:
            pass
            raise ImportException(f"Zotero import translators failed ({e})")

        LOADER.save_records(
            records=records, corresponding_bib_file=SOURCE.corresponding_bib_file
        )

        return


@zope.interface.implementer(LoadEndpoint)
class MarkdownLoader:

    supported_extensions = ["md"]

    def load(self, LOADER, SOURCE):
        import requests

        from colrev_core.environment import GrobidService

        GROBID_SERVICE = GrobidService()
        GROBID_SERVICE.check_grobid_availability()
        with open(SOURCE.filename, encoding="utf8") as f:
            if SOURCE.filename.suffix == ".md":
                references = [line.rstrip() for line in f if "#" not in line[:2]]
            else:
                references = [line.rstrip() for line in f]

        data = ""
        ind = 0
        for ref in references:
            options = {}
            options["consolidateCitations"] = "1"
            options["citations"] = ref
            r = requests.post(
                GROBID_SERVICE.GROBID_URL + "/api/processCitation",
                data=options,
                headers={"Accept": "application/x-bibtex"},
            )
            ind += 1
            data = data + "\n" + r.text.replace("{-1,", "{" + str(ind) + ",")

        records = LOADER.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(load_str=data)

        LOADER.save_records(
            records=records, corresponding_bib_file=SOURCE.corresponding_bib_file
        )

        return


@zope.interface.implementer(LoadEndpoint)
class BibutilsLoader:

    supported_extensions = ["ris", "end", "enl", "copac", "isi", "med"]

    @classmethod
    def bibutils_convert(cls, script: str, data: str) -> str:

        from colrev_core.load import ImportException

        if "xml2bib" == script:
            script = script + " -b -w -sk "
        else:
            script = script + " -i unicode "

        client = docker.APIClient()
        try:
            container = client.create_container("bibutils", script, stdin_open=True)
        except docker.errors.ImageNotFound:
            raise ImportException("Docker images for bibutils not found")

        sock = client.attach_socket(
            container, params={"stdin": 1, "stdout": 1, "stderr": 1, "stream": 1}
        )
        client.start(container)

        sock._sock.send(data.encode())
        sock._sock.close()
        sock.close()

        client.wait(container)
        stdout = client.logs(container, stderr=False).decode()
        client.remove_container(container)

        return stdout

    def load(self, LOADER, SOURCE):
        from colrev_core.load import ImportException

        with open(SOURCE.filename) as reader:
            data = reader.read()

        filetype = Path(SOURCE.filename).suffix.replace(".", "")

        if filetype in ["enl", "end"]:
            data = self.bibutils_convert("end2xml", data)
        elif filetype in ["copac"]:
            data = self.bibutils_convert("copac2xml", data)
        elif filetype in ["isi"]:
            data = self.bibutils_convert("isi2xml", data)
        elif filetype in ["med"]:
            data = self.bibutils_convert("med2xml", data)
        elif filetype in ["ris"]:
            data = self.bibutils_convert("ris2xml", data)
        else:
            raise ImportException(f"Filetype {filetype} not supported by bibutils")

        data = self.bibutils_convert("xml2bib", data)

        records = LOADER.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(load_str=data)

        LOADER.save_records(
            records=records, corresponding_bib_file=SOURCE.corresponding_bib_file
        )

        return
