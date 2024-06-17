#! /usr/bin/env python3
"""Synchronize records into a non-CoLRev project."""
from __future__ import annotations

import logging
import re
import typing
from pathlib import Path

import pybtex.errors

import colrev.dataset
import colrev.env.local_index
import colrev.env.local_index_builder
import colrev.loader.load_utils_formatter
import colrev.ops.check
import colrev.package_manager.package_manager
import colrev.record.record
import colrev.review_manager
import colrev.ui_cli.cli_status_printer
import colrev.ui_cli.cli_validation
import colrev.ui_cli.dedupe_errors
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import FieldSet
from colrev.constants import RecordState
from colrev.writer.write_utils import write_file


class Sync:
    """Synchronize records into a non-CoLRev repository"""

    cited_papers: list
    pre_commit_config = Path(".pre-commit-config.yaml")

    def __init__(self) -> None:
        self.records_to_import: typing.List[colrev.record.record.Record] = []
        self.non_unique_for_import: typing.List[typing.Dict] = []

        self.logger = self._setup_logger(level=logging.DEBUG)
        self.paper_md = self._get_md_file()
        self.load_formatter = colrev.loader.load_utils_formatter.LoadFormatter()

    def add_hook(self) -> None:
        """Add a pre-commit hook for colrev sync"""
        if not Path(".git").is_dir():
            print("Not in a git directory.")
            return
        if not Path("records.bib").is_file() or not Path("paper.md").is_file():
            print("Warning: records.bib or paper.md does not exist.")
            print("Other filenames are not (yet) supported.")
            return

        if self.pre_commit_config.is_file():
            if "colrev-hooks-update" in self.pre_commit_config.read_text(
                encoding="utf-8"
            ):
                print("Hook already registered")
                return

        with open(self.pre_commit_config, "a", encoding="utf-8") as file:
            file.write(
                """\n-   repo: local
        hooks:
        -   id: colrev-hooks-update
            name: "CoLRev ReviewManager: update"
            entry: colrev-hooks-update
            language: python
            stages: [commit]
            files: 'records.bib|paper.md'"""
            )
        print("Added pre-commit hook for colrev sync.")

    def _setup_logger(self, *, level: int = logging.INFO) -> logging.Logger:
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

    def _get_md_file(self) -> Path:
        paper_md = Path("")
        if Path("paper.md").is_file():
            paper_md = Path("paper.md")
        if Path("data/paper.md").is_file():
            paper_md = Path("data/paper.md")
        elif Path("review.md").is_file():
            paper_md = Path("review.md")
        return paper_md

    def _get_cited_papers_citation_keys(self) -> list:
        rst_files = list(Path.cwd().rglob("*.rst"))

        citation_keys = []
        if self.paper_md.is_file():
            self.logger.info("Load cited references from paper.md")
            content = self.paper_md.read_text(encoding="utf-8")
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

    def get_cited_papers_from_source(self, *, src: Path) -> None:
        """Get the cited papers from a source file"""

        citation_keys = self._get_cited_papers_citation_keys()

        ids_in_bib = self._get_ids_in_paper()
        self.logger.info("References in bib: %s", len(ids_in_bib))

        if src.suffix == ".bib":
            refs_in_src = colrev.loader.load_utils.load(
                filename=src,
                logger=self.logger,
            )

        else:
            print("Format not supported")
            return

        for citation_key in citation_keys:
            if citation_key in ids_in_bib:
                continue
            if citation_key not in refs_in_src:
                print(f"{citation_key} not in {src}")
                continue
            self.records_to_import.append(
                colrev.record.record.Record(refs_in_src[citation_key])
            )

    def get_cited_papers(self) -> None:
        """Get the cited papers"""

        citation_keys = self._get_cited_papers_citation_keys()

        ids_in_bib = self._get_ids_in_paper()
        self.logger.info("References in bib: %s", len(ids_in_bib))

        local_index = colrev.env.local_index.LocalIndex()
        for citation_key in citation_keys:
            if citation_key in ids_in_bib + ["tbl"]:
                continue

            if Path(f"{citation_key}.pdf").is_file():
                print("TODO - prefer!")
                # continue if found/extracted

            returned_records = local_index.search(f"citation_key='{citation_key}'")

            if 0 == len(returned_records):
                self.logger.info("Not found: %s", citation_key)
            elif 1 == len(returned_records):
                if returned_records[0].data[Fields.ID] in [
                    r.data[Fields.ID] for r in self.records_to_import
                ]:
                    continue
                self.records_to_import.append(returned_records[0])
            else:
                listed_item: typing.Dict[str, typing.List] = {citation_key: []}
                for returned_record in returned_records:  # type: ignore
                    listed_item[citation_key].append(returned_record)
                self.non_unique_for_import.append(listed_item)

    def _get_ids_in_paper(self) -> typing.List:
        pybtex.errors.set_strict_mode(False)

        if Path("references.bib").is_file():

            records = colrev.loader.load_utils.load(
                filename=Path("references.bib"),
                logger=self.logger,
            )

        else:
            records = {}

        return list(records.keys())

    def add_to_records_to_import(self, record: colrev.record.record.Record) -> None:
        """Add a record to the records_to_import list"""
        if record.data[Fields.ID] not in [
            r.data[Fields.ID] for r in self.records_to_import
        ]:
            self.records_to_import.append(record)

    def add_paper(self, add: str) -> None:
        """Add a paper to the bibliography"""

        local_index = colrev.env.local_index.LocalIndex()

        def parse_record_str(add: str) -> list:
            # DOI: from crossref
            if add.startswith("10."):
                returned_records = local_index.search(f"doi='{add}'")
            else:
                returned_records = local_index.search(f"title LIKE '{add}'")

            return returned_records

        self.get_cited_papers()
        records = parse_record_str(add)

        if len(records) == 0:
            print("not found")
            return

        self.records_to_import = records
        input(self.records_to_import)
        print(records[0].data["ID"])

    def add_to_bib(self) -> None:
        """Add records to the bibliography"""

        if not self.paper_md.is_file():
            return

        if self.paper_md.read_text(encoding="utf-8").startswith("---"):
            self._export_to_bib()

        else:
            # Append to # References if no header (mardown with linked)
            self._append_as_citations()

    def _append_as_citations(self) -> None:
        if "# References" in self.paper_md.read_text(encoding="utf-8"):
            print("Already contains a reference section.")
            return

        with open(self.paper_md, "a", encoding="utf-8") as file:
            file.write("\n# References\n\n")
            ref_list = [
                record_to_import.format_bib_style()
                for record_to_import in self.records_to_import
            ]
            file.write("\n".join(sorted(ref_list)))

    def _export_to_bib(self) -> None:
        pybtex.errors.set_strict_mode(False)

        references_file = Path("references.bib")
        if not references_file.is_file():
            records = []
        else:

            records_dict = colrev.loader.load_utils.load(
                filename=references_file,
                logger=self.logger,
            )
            records = list(records_dict.values())

        available_ids = [r[Fields.ID] for r in records]
        added = []
        for record_to_import in self.records_to_import:
            if record_to_import.data[Fields.ID] not in available_ids:
                record_to_import = colrev.record.record.Record(
                    {
                        k: v
                        for k, v in record_to_import.data.items()
                        if k
                        not in FieldSet.PROVENANCE_KEYS
                        + [Fields.SCREENING_CRITERIA, Fields.PRESCREEN_EXCLUSION]
                        and "." not in k
                    }
                )
                records.append(record_to_import.get_data())
                available_ids.append(record_to_import.data[Fields.ID])
                added.append(record_to_import)

        if len(added) > 0:
            self.logger.info("Loaded:")
            print()
            for added_record in added:
                added_record.print_citation_format()
            print()

            self.logger.info(
                "%s Loaded %s papers%s", Colors.GREEN, len(added), Colors.END
            )

        for record_dict in records:
            record = colrev.record.record.Record(record_dict)
            record.set_status(RecordState.md_retrieved)  # rev_synthesized
            self.load_formatter.run(record)
            del record.data[Fields.STATUS]

        # records_dict = {
        #     r[Fields.ID]: r for r in records if r[Fields.ID] in self.cited_papers
        # }

        records_dict = {r[Fields.ID]: r for r in records}

        write_file(records_dict=records_dict, filename=references_file)


def main() -> None:
    """Sync records from CoLRev environment to non-CoLRev repo"""

    sync_operation = Sync()

    sync_operation.get_cited_papers()

    if len(sync_operation.non_unique_for_import) > 0:
        print("Non-unique keys to resolve:")
        # Resolve non-unique cases
        for case in sync_operation.non_unique_for_import:
            for val in case.values():
                # later: there may be more collisions (v3, v4)
                v_1 = val[0].format_bib_style()
                v_2 = val[1].format_bib_style()

                if v_1.lower() == v_2.lower():
                    sync_operation.add_to_records_to_import(val[0])
                    continue
                print("\n")
                print(f"1: {v_1}")
                print("      " + val[0].data.get("source_url", ""))
                print("")
                print(f"2: {v_2}")
                print("      " + val[1].data.get("source_url", ""))
                user_selection = input("Import version 1 or 2 (or skip)?")
                if user_selection == "1":
                    sync_operation.add_to_records_to_import(val[0])
                    continue
                if user_selection == "2":
                    sync_operation.add_to_records_to_import(val[1])
                    continue

    sync_operation.add_to_bib()


# @click.option(
#     "-a",
#     "--add",
#     help="Paper to add.",
#     required=False,
# )
# @click.option(
#     "--add_hook",
#     is_flag=True,
#     default=False,
#     help="Add a sync pre-commit hook",
# )
# @click.option(
#     "-src",
#     type=click.Path(exists=True),
#     help="Sync selected citations from source file.",
# )

# sync_operation = colrev.review_manager.ReviewManager.get_sync_operation()
# if add_hook:
#     sync_operation.add_hook()
#     return

# if src:
#     sync_operation.get_cited_papers_from_source(src=Path(src))
#     sync_operation.add_to_bib()
#     return

# if add:
#     sync_operation.add_paper(add)
#     sync_operation.add_to_bib()

#     return
