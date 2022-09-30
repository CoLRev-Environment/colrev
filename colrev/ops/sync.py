#! /usr/bin/env python
"""Synchronize records into a non-CoLRev project."""
import json
import re
import typing
from pathlib import Path

import pybtex.errors
from pybtex.database.input import bibtex

import colrev.dataset
import colrev.env.local_index
import colrev.record


class Sync:

    cited_papers: list

    def __init__(self) -> None:
        self.records_to_import: typing.List[typing.Dict] = []
        self.non_unique_for_import: typing.List[typing.Dict] = []

    def __get_cited_papers_citation_keys(self) -> list:
        if Path("paper.md").is_file():
            paper_md = Path("paper.md")
        if Path("data/paper.md").is_file():
            paper_md = Path("data/paper.md")
        elif Path("review.md"):
            paper_md = Path("review.md")
        rst_files = list(Path.cwd().rglob("*.rst"))

        citation_keys = []
        if paper_md.is_file():
            print("Loading cited references from paper.md")
            content = paper_md.read_text(encoding="utf-8")
            res = re.findall(r"(^|\s|\[|;)(@[a-zA-Z0-9_]+)+", content)
            citation_keys = list({r[1].replace("@", "") for r in res})
            citation_keys.remove("fig")
            print(f"Citations in paper.md: {len(citation_keys)}")
            self.cited_papers = citation_keys

        elif len(rst_files) > 0:
            print("Loading cited references from *.rst")
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
        return citation_keys

    def get_cited_papers(self) -> None:

        citation_keys = self.__get_cited_papers_citation_keys()

        ids_in_bib = self.__get_ids_in_paper()
        print(f"References in bib: {len(ids_in_bib)}")

        for citation_key in citation_keys:
            if citation_key in ids_in_bib:
                continue

            if Path(f"{citation_key}.pdf").is_file():
                print("TODO - prefer!")
                # continue if found/extracted

            local_index = colrev.env.local_index.LocalIndex()

            query = json.dumps({"query": {"match_phrase": {"ID": citation_key}}})
            res = local_index.open_search.search(
                index=local_index.RECORD_INDEX, body=query
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
                record_to_import = local_index.prep_record_for_return(
                    record_dict=record_to_import, include_file=False
                )

                self.records_to_import.append(record_to_import)
            else:
                # print(f'Multiple hits for {citation_key}')
                listed_item: typing.Dict[str, typing.List] = {citation_key: []}
                for item in res["hits"]["hits"]:  # type: ignore
                    listed_item[citation_key].append(item["_source"])
                self.non_unique_for_import.append(listed_item)

    def __get_ids_in_paper(self) -> typing.List:

        pybtex.errors.set_strict_mode(False)

        if Path("references.bib").is_file():
            parser = bibtex.Parser()
            bib_data = parser.parse_file(str(Path("references.bib")))
            records = colrev.dataset.Dataset.parse_records_dict(
                records_dict=bib_data.entries
            )

        else:
            records = {}

        return list(records.keys())

    def get_non_unique(self) -> list:
        return self.non_unique_for_import

    def add_to_records_to_import(self, *, record: dict) -> None:
        if record["ID"] not in [r["ID"] for r in self.records_to_import]:
            self.records_to_import.append(record)

    def save_to_bib(self, *, records: dict, save_path: Path) -> None:

        # pylint: disable=duplicate-code

        def parse_bibtex_str(*, recs_dict_in: dict) -> str:
            def format_field(field: str, value: str) -> str:
                padd = " " * max(0, 28 - len(field))
                return f",\n   {field} {padd} = {{{value}}}"

            bibtex_str = ""

            first = True
            for record_id, record_dict in recs_dict_in.items():
                if not first:
                    bibtex_str += "\n"
                first = False

                bibtex_str += f"@{record_dict['ENTRYTYPE']}{{{record_id}"

                field_order = [
                    "doi",
                    "dblp_key",
                    "sem_scholar_id",
                    "wos_accession_number",
                    "author",
                    "booktitle",
                    "journal",
                    "title",
                    "year",
                    "volume",
                    "number",
                    "pages",
                    "editor",
                ]

                for ordered_field in field_order:
                    if ordered_field in record_dict:
                        if "" == record_dict[ordered_field]:
                            continue
                        if isinstance(record_dict[ordered_field], (list, dict)):
                            continue
                        bibtex_str += format_field(
                            ordered_field, record_dict[ordered_field]
                        )

                for key, value in record_dict.items():
                    if key in field_order + ["ID", "ENTRYTYPE"]:
                        continue
                    if isinstance(key, (list, dict)):
                        continue

                    bibtex_str += format_field(key, value)

                bibtex_str += ",\n}\n"

            return bibtex_str

        bibtex_str = parse_bibtex_str(recs_dict_in=records)

        with open(save_path, "w", encoding="utf-8") as out:
            out.write(bibtex_str)

    def add_to_bib(self) -> None:

        pybtex.errors.set_strict_mode(False)

        references_file = Path("references.bib")
        if not references_file.is_file():
            records = []
        else:

            parser = bibtex.Parser()
            bib_data = parser.parse_file(str(references_file))
            records = list(
                colrev.dataset.Dataset.parse_records_dict(
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
            for record_dict in added:
                colrev.record.Record(data=record_dict).print_citation_format()

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

        self.save_to_bib(records=records_dict, save_path=references_file)


if __name__ == "__main__":
    pass
