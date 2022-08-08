#! /usr/bin/env python
import json
import re
import typing
from pathlib import Path

import pybtex.errors
from pybtex.database.input import bibtex

import colrev_core.environment
import colrev_core.record
import colrev_core.review_dataset


class Sync:
    def __init__(self):
        self.records_to_import = []
        self.non_unique_for_import = []

    def get_cited_papers(self) -> None:

        if Path("paper.md").is_file():
            paper_md = Path("paper.md")
        elif Path("review.md"):
            paper_md = Path("review.md")
        rst_files = list(Path.cwd().rglob("*.rst"))

        IDs_in_bib = self.get_IDs_in_paper()
        print(f"References in bib: {len(IDs_in_bib)}")

        if paper_md.is_file():
            print("Loading cited references from paper.md")
            content = paper_md.read_text(encoding="utf-8")
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

            if Path(f"{citation_key}.pdf").is_file():
                print("TODO - prefer!")
                # continue if found/extracted

            self.LOCAL_INDEX = colrev_core.environment.LocalIndex()

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
                    record=record_to_import, include_file=False
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

        pybtex.errors.set_strict_mode(False)

        references_file = Path("references.bib")
        if not references_file.is_file():
            records = {}
        else:

            parser = bibtex.Parser()
            bib_data = parser.parse_file(str(references_file))
            records = colrev_core.review_dataset.ReviewDataset.parse_records_dict(
                records_dict=bib_data.entries
            )

        return list(records.keys())

    def get_non_unique(self) -> list:
        return self.non_unique_for_import

    def add_to_records_to_import(self, record: dict) -> None:
        if record["ID"] not in [r["ID"] for r in self.records_to_import]:
            self.records_to_import.append(record)

    def add_to_bib(self) -> None:

        pybtex.errors.set_strict_mode(False)

        references_file = Path("references.bib")
        if not references_file.is_file():
            records = []
        else:

            parser = bibtex.Parser()
            bib_data = parser.parse_file(str(references_file))
            records = list(
                colrev_core.review_dataset.ReviewDataset.parse_records_dict(
                    records_dict=bib_data.entries
                ).values()
            )

        available_ids = [r["ID"] for r in records]
        added = []
        for record_to_import in self.records_to_import:
            if record_to_import["ID"] not in available_ids:
                records.append(record_to_import)
                available_ids.append(record_to_import["ID"])
                added.append(record_to_import)

        if len(added) > 0:
            print("Loaded:")
            for record in added:
                colrev_core.record.Record(data=record).print_citation_format()

            print(f"Loaded {len(added)} papers")

        records = [
            {
                k: v
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

        records_dict = {r["ID"]: r for r in records if r["ID"] in self.cited_papers}

        colrev_core.review_dataset.ReviewDataset.save_records_dict_to_file(
            records=records_dict, save_path=references_file
        )


if __name__ == "__main__":
    pass
