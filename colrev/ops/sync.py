#! /usr/bin/env python
"""Synchronize records into a non-CoLRev project."""
import logging
import re
import typing
from pathlib import Path

import pybtex.errors
from pybtex.database.input import bibtex

import colrev.dataset
import colrev.env.local_index
import colrev.record
import colrev.ui_cli.cli_colors as colors


class Sync:
    """Synchronize records into a non-CoLRev repository"""

    cited_papers: list

    def __init__(self) -> None:
        self.records_to_import: typing.List[colrev.record.Record] = []
        self.non_unique_for_import: typing.List[typing.Dict] = []

        self.logger = self.__setup_logger(level=logging.DEBUG)

    def __setup_logger(self, *, level: int = logging.INFO) -> logging.Logger:
        """Setup the sync logger"""
        # pylint: disable=duplicate-code

        # for logger debugging:
        # from logging_tree import printout
        # printout()
        logger = logging.getLogger(f"colrev{str(Path.cwd()).replace('/', '_')}")
        logger.setLevel(level)

        if logger.handlers:
            for handler in logger.handlers:
                logger.removeHandler(handler)

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        handler.setLevel(level)

        logger.addHandler(handler)
        logger.propagate = False

        return logger

    def __get_cited_papers_citation_keys(self) -> list:
        if Path("paper.md").is_file():
            paper_md = Path("paper.md")
        if Path("data/paper.md").is_file():
            paper_md = Path("data/paper.md")
        elif Path("review.md").is_file():
            paper_md = Path("review.md")
        rst_files = list(Path.cwd().rglob("*.rst"))

        citation_keys = []
        if paper_md.is_file():
            self.logger.info("Load cited references from paper.md")
            content = paper_md.read_text(encoding="utf-8")
            res = re.findall(r"(^|\s|\[|;)(@[a-zA-Z0-9_]+)+", content)
            citation_keys = list({r[1].replace("@", "") for r in res})
            if "fig" in citation_keys:
                citation_keys.remove("fig")
            self.logger.info("Citations in paper.md: %s", len(citation_keys))
            self.cited_papers = citation_keys

        elif len(rst_files) > 0:
            self.logger.info("Load cited references from *.rst")
            for rst_file in rst_files:
                content = rst_file.read_text()
                res = re.findall(r":cite:p:`(.*)`", content)
                cited = [c for cit_group in res for c in cit_group.split(",")]
                citation_keys.extend(cited)

            citation_keys = list(set(citation_keys))
            self.logger.info("Citations in *.rst: %s", len(citation_keys))
            self.cited_papers = citation_keys

        else:
            print("Not found paper.md or *.rst")
        return citation_keys

    def get_cited_papers(self) -> None:
        """Get the cited papers"""

        citation_keys = self.__get_cited_papers_citation_keys()

        ids_in_bib = self.__get_ids_in_paper()
        self.logger.info("References in bib: %s", len(ids_in_bib))

        local_index = colrev.env.local_index.LocalIndex()
        for citation_key in citation_keys:
            if citation_key in ids_in_bib:
                continue

            if Path(f"{citation_key}.pdf").is_file():
                print("TODO - prefer!")
                # continue if found/extracted

            returned_records = local_index.search(
                query=f"citation_key='{citation_key}'"
            )

            if 0 == len(returned_records):
                self.logger.info("Not found: %s", citation_key)
            elif 1 == len(returned_records):
                if returned_records[0].data["ID"] in [
                    r.data["ID"] for r in self.records_to_import
                ]:
                    continue
                self.records_to_import.append(returned_records[0])
            else:
                listed_item: typing.Dict[str, typing.List] = {citation_key: []}
                for returned_record in returned_records:  # type: ignore
                    listed_item[citation_key].append(returned_record)
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

    def add_to_records_to_import(self, *, record: colrev.record.Record) -> None:
        """Add a record to the records_to_import list"""
        if record.data["ID"] not in [r.data["ID"] for r in self.records_to_import]:
            self.records_to_import.append(record)

    def __save_to_bib(self, *, records: dict, save_path: Path) -> None:
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
                        if record_dict[ordered_field] == "":
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
        """Add records to the bibliography"""

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
            if record_to_import.data["ID"] not in available_ids:
                record_to_import = colrev.record.Record(
                    data={
                        k: v
                        for k, v in record_to_import.data.items()
                        if k not in colrev.record.Record.provenance_keys
                    }
                )
                records.append(record_to_import.get_data())
                available_ids.append(record_to_import.data["ID"])
                added.append(record_to_import)

        if len(added) > 0:
            self.logger.info("Loaded:")
            print()
            for added_record in added:
                added_record.print_citation_format()
            print()

            self.logger.info(
                "%s Loaded %s papers%s", colors.GREEN, len(added), colors.END
            )

        records_dict = {r["ID"]: r for r in records if r["ID"] in self.cited_papers}

        self.__save_to_bib(records=records_dict, save_path=references_file)


if __name__ == "__main__":
    pass
