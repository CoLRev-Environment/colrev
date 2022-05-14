#! /usr/bin/env python
import re
import typing
from pathlib import Path

import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.customization import convert_to_unicode

from colrev_core.environment import LocalIndex


class Sync:

    colrev_path = Path.home().joinpath("colrev")
    registry = "registry.yaml"

    paths = {"REGISTRY": colrev_path.joinpath(registry)}

    os_db = "opensearchproject/opensearch-dashboards:1.3.0"

    docker_images = {
        "lfoppiano/grobid": "lfoppiano/grobid:0.7.0",
        "pandoc/ubuntu-latex": "pandoc/ubuntu-latex:2.14",
        "jbarlow83/ocrmypdf": "jbarlow83/ocrmypdf:v13.3.0",
        "zotero/translation-server": "zotero/translation-server:2.0.4",
        "opensearchproject/opensearch": "opensearchproject/opensearch:1.3.0",
        "opensearchproject/opensearch-dashboards": os_db,
    }

    def __init__(self):
        self.records_to_import = []
        self.non_unique_for_import = []

    def get_cited_papers(self) -> None:
        import json

        paper_md = Path("paper.md")
        rst_files = list(Path.cwd().rglob("*.rst"))

        IDs_in_bib = self.get_IDs_in_paper()
        print(f"References in bib: {len(IDs_in_bib)}")

        if paper_md.is_file():
            print("Loading cited references from paper.md")
            content = paper_md.read_text()
            res = re.findall(r"(^|\s|\[|;)(@[a-zA-Z0-9_]+)+", content)
            citation_keys = list({r[1].replace("@", "") for r in res})
            print(f"Citations in paper.md: {len(citation_keys)}")
            self.cited_papers = citation_keys

        elif len(rst_files) > 0:
            print("Loading cited references from *.rst")
            citation_keys = []
            for rst_file in rst_files:
                content = rst_file.read_text()
                res = re.findall(r":cite:p:`(.*)`", content)
                cited = [c for cit_group in res for c in cit_group.split(",")]
                citation_keys.extend(cited)

            citation_keys = list(set(citation_keys))
            print(f"Citations in *.rst: {len(citation_keys)}")
            self.cited_papers = citation_keys

        else:
            print("Not found paper.md or *.rst")
            return

        for citation_key in citation_keys:
            if citation_key in IDs_in_bib:
                continue

            self.LOCAL_INDEX = LocalIndex()

            query = json.dumps({"query": {"match_phrase": {"ID": citation_key}}})
            res = self.LOCAL_INDEX.os.search(
                index=self.LOCAL_INDEX.RECORD_INDEX, body=query
            )

            nr_hits = len(res["hits"]["hits"])  # type: ignore
            if 0 == nr_hits:
                print(f"Not found: {citation_key}")
            elif 1 == nr_hits:
                record_to_import = res["hits"]["hits"][0]["_source"]  # type: ignore
                if record_to_import["ID"] in [r["ID"] for r in self.records_to_import]:
                    continue
                record_to_import = {k: str(v) for k, v in record_to_import.items()}
                record_to_import = {
                    k: v for k, v in record_to_import.items() if "None" != v
                }
                record_to_import = self.LOCAL_INDEX.prep_record_for_return(
                    record_to_import, include_file=False
                )

                self.records_to_import.append(record_to_import)
            else:
                # print(f'Multiple hits for {citation_key}')
                listed_item: typing.Dict[str, typing.List] = {citation_key: []}
                for item in res["hits"]["hits"]:  # type: ignore
                    listed_item[citation_key].append(item["_source"])
                self.non_unique_for_import.append(listed_item)

        return

    def get_IDs_in_paper(self) -> typing.List:

        references_file = Path("references.bib")
        if not references_file.is_file():
            feed_db = BibDatabase()
            records = []
        else:
            with open(references_file) as bibtex_file:
                feed_db = BibTexParser(
                    customization=convert_to_unicode,
                    ignore_nonstandard_types=True,
                    common_strings=True,
                ).parse_file(bibtex_file, partial=True)
                records = feed_db.entries

        return [r["ID"] for r in records]

    def get_non_unique(self) -> list:
        return self.non_unique_for_import

    def add_to_records_to_import(self, record: dict) -> None:
        if record["ID"] not in [r["ID"] for r in self.records_to_import]:
            self.records_to_import.append(record)
        return

    def format_ref(self, v) -> str:
        formatted_ref = (
            f"{v.get('author', '')} ({v.get('year', '')}) "
            + f"{v.get('title', '')}. "
            + f"{v.get('journal', '')}{v.get('booktitle', '')}, "
            + f"{v.get('volume', '')} ({v.get('number', '')})"
        )
        return formatted_ref

    def add_to_bib(self) -> None:

        references_file = Path("references.bib")
        if not references_file.is_file():
            feed_db = BibDatabase()
            records = []
        else:
            with open(references_file) as bibtex_file:
                feed_db = BibTexParser(
                    customization=convert_to_unicode,
                    ignore_nonstandard_types=True,
                    common_strings=True,
                ).parse_file(bibtex_file, partial=True)
                records = feed_db.entries

        available_ids = [r["ID"] for r in records]
        added = []
        for record_to_import in self.records_to_import:
            if record_to_import["ID"] not in available_ids:
                records.append(record_to_import)
                available_ids.append(record_to_import["ID"])
                added.append(record_to_import)

        if len(added) > 0:
            print("Loaded:")
            for element in added:
                print(" - " + self.format_ref(element))

            print(f"Loaded {len(added)} papers")

        # Casting to string (in particular the RecordState Enum)
        records = [
            {
                k: str(v)
                for k, v in record.items()
                if k
                in [
                    "ID",
                    "ENTRYTYPE",
                    "author",
                    "title",
                    "year",
                    "journal",
                    "doi",
                    "booktitle",
                    "chapter",
                    "volume",
                    "number",
                    "pages",
                    "publisher",
                ]
            }
            for record in records
        ]

        records = [r for r in records if r["ID"] in self.cited_papers]

        records.sort(key=lambda x: x["ID"])

        feed_db.entries = records
        with open(references_file, "w") as fi:
            fi.write(bibtexparser.dumps(feed_db, self.__get_bibtex_writer()))

        return

    def __get_bibtex_writer(self) -> BibTexWriter:

        writer = BibTexWriter()
        writer.contents = ["entries", "comments"]
        writer.display_order = [
            "doi",
            "dblp_key",
            "author",
            "booktitle",
            "journal",
            "title",
            "year",
            "editor",
            "number",
            "pages",
            "series",
            "volume",
            "abstract",
            "book-author",
            "book-group-author",
        ]

        # Note : use this sort order to ensure that the latest entries will be
        # appended at the end and in the same order when rerunning the feed:
        writer.order_entries_by = "ID"
        writer.add_trailing_comma = True
        writer.align_values = True
        writer.indent = "  "
        return writer


if __name__ == "__main__":
    pass
