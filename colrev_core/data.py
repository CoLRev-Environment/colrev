#! /usr/bin/env python
import csv
import importlib
import itertools
import pkgutil
import re
import sys
import tempfile
import typing
from collections import Counter
from pathlib import Path

import pandas as pd
import requests
import zope.interface
from urllib3.exceptions import ProtocolError
from zope.interface.verify import verifyObject

from colrev_core.environment import GrobidService
from colrev_core.environment import TEI_TimeoutException
from colrev_core.environment import TEIParser
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import RecordState


class DataEndpoint(zope.interface.Interface):
    def get_default_setup(self) -> dict:
        return {}

    def update_data(
        REVIEW_MANAGER, records: dict, synthesized_record_status_matrix: dict
    ) -> None:
        pass

    def update_record_status_matrix(
        REVIEW_MANAGER, synthesized_record_status_matrix, endpoint_identifier
    ) -> None:
        pass


@zope.interface.implementer(DataEndpoint)
class ManuscriptEndpoint:

    NEW_RECORD_SOURCE_TAG = "<!-- NEW_RECORD_SOURCE -->"
    """Tag for appending new records in paper.md

    In the paper.md, the IDs of new records marked for synthesis
    will be appended after this tag.

    If IDs are moved to other parts of the manuscript,
    the corresponding record will be marked as rev_synthesized."""

    @classmethod
    def get_default_setup(cls):

        manuscript_endpoint_details = {
            "endpoint": "MANUSCRIPT",
            "paper_endpoint_version": "0.1",
            "word_template": cls.retrieve_default_word_template(),
            "csl_style": cls.retrieve_default_csl(),
        }

        return manuscript_endpoint_details

    @classmethod
    def retrieve_default_word_template(cls) -> str:
        template_name = "APA-7.docx"

        filedata = pkgutil.get_data(__name__, str(Path("template/APA-7.docx")))
        if filedata:
            with open(Path(template_name), "wb") as file:
                file.write(filedata)

        return template_name

    @classmethod
    def retrieve_default_csl(cls) -> str:
        csl_link = (
            "https://raw.githubusercontent.com/"
            + "citation-style-language/styles/master/apa.csl"
        )
        r = requests.get(csl_link, allow_redirects=True)
        open(Path(csl_link).name, "wb").write(r.content)
        csl = Path(csl_link).name
        return csl

    @classmethod
    def check_new_record_source_tag(cls, REVIEW_MANAGER) -> None:
        PAPER = REVIEW_MANAGER.paths["PAPER"]
        with open(PAPER) as f:
            for line in f:
                if cls.NEW_RECORD_SOURCE_TAG in line:
                    return
        raise ManuscriptRecordSourceTagError(
            f"Did not find {cls.NEW_RECORD_SOURCE_TAG} tag in {PAPER}"
        )

    @classmethod
    def update_manuscript(
        cls,
        REVIEW_MANAGER,
        records: typing.Dict,
        synthesized_record_status_matrix: dict,
    ) -> typing.Dict:
        def inplace_change(filename: Path, old_string: str, new_string: str) -> None:
            with open(filename) as f:
                s = f.read()
                if old_string not in s:
                    REVIEW_MANAGER.logger.info(
                        f'"{old_string}" not found in {filename}.'
                    )
                    return
            with open(filename, "w") as f:
                s = s.replace(old_string, new_string)
                f.write(s)
            return

        def authorship_heuristic() -> str:
            git_repo = REVIEW_MANAGER.REVIEW_DATASET.get_repo()
            commits_list = list(git_repo.iter_commits())
            commits_authors = []
            for commit in commits_list:
                committer = git_repo.git.show("-s", "--format=%cn", commit.hexsha)
                if "GitHub" == committer:
                    continue
                commits_authors.append(committer)
                # author = git_repo.git.show("-s", "--format=%an", commit.hexsha)
                # mail = git_repo.git.show("-s", "--format=%ae", commit.hexsha)
            author = ", ".join(dict(Counter(commits_authors)))
            return author

        def get_data_page_missing(PAPER: Path, record_id_list: list) -> list:
            available = []
            with open(PAPER) as f:
                line = f.read()
                for record in record_id_list:
                    if record in line:
                        available.append(record)

            return list(set(record_id_list) - set(available))

        PAPER = REVIEW_MANAGER.paths["PAPER"]
        PAPER_RELATIVE = REVIEW_MANAGER.paths["PAPER_RELATIVE"]

        def retrieve_package_file(template_file: Path, target: Path) -> None:
            filedata = pkgutil.get_data(__name__, str(template_file))
            if filedata:
                with open(target, "w") as file:
                    file.write(filedata.decode("utf-8"))
            return

        def add_missing_records_to_manuscript(
            *, REVIEW_MANAGER, PAPER: Path, missing_records: list
        ):
            temp = tempfile.NamedTemporaryFile()
            PAPER.rename(temp.name)
            with open(temp.name) as reader, open(PAPER, "w") as writer:
                appended, completed = False, False
                line = reader.readline()
                while line != "":
                    if cls.NEW_RECORD_SOURCE_TAG in line:
                        if "_Records to synthesize" not in line:
                            line = "_Records to synthesize_:" + line + "\n"
                            writer.write(line)
                        else:
                            writer.write(line)
                            writer.write("\n")

                        for missing_record in missing_records:
                            writer.write(missing_record)
                            REVIEW_MANAGER.report_logger.info(
                                # f" {missing_record}".ljust(self.__PAD, " ")
                                f" {missing_record}"
                                + f" added to {PAPER.name}"
                            )

                            REVIEW_MANAGER.logger.info(
                                # f" {missing_record}".ljust(self.__PAD, " ")
                                f" {missing_record}"
                                + f" added to {PAPER.name}"
                            )

                        # skip empty lines between to connect lists
                        line = reader.readline()
                        if "\n" != line:
                            writer.write(line)

                        appended = True

                    elif appended and not completed:
                        if "- @" == line[:3]:
                            writer.write(line)
                        else:
                            if "\n" != line:
                                writer.write("\n")
                            writer.write(line)
                            completed = True
                    else:
                        writer.write(line)
                    line = reader.readline()

                if not appended:
                    msg = (
                        f"Marker {cls.NEW_RECORD_SOURCE_TAG} not found in "
                        + f"{PAPER.name}. Adding records at the end of "
                        + "the document."
                    )
                    REVIEW_MANAGER.report_logger.warning(msg)
                    REVIEW_MANAGER.logger.warning(msg)

                    if line != "\n":
                        writer.write("\n")
                    marker = f"{cls.NEW_RECORD_SOURCE_TAG}_Records to synthesize_:\n\n"
                    writer.write(marker)
                    for missing_record in missing_records:
                        writer.write(missing_record)
                        REVIEW_MANAGER.report_logger.info(
                            # f" {missing_record}".ljust(self.__PAD, " ") + " added"
                            f" {missing_record} added"
                        )
                        REVIEW_MANAGER.logger.info(
                            # f" {missing_record}".ljust(self.__PAD, " ") + " added"
                            f" {missing_record} added"
                        )

            return

        if not PAPER.is_file():
            # missing_records = synthesized_record_status_matrix.keys()

            REVIEW_MANAGER.report_logger.info("Creating manuscript")
            REVIEW_MANAGER.logger.info("Creating manuscript")

            title = "Manuscript template"
            readme_file = REVIEW_MANAGER.paths["README"]
            if readme_file.is_file():
                with open(readme_file) as f:
                    title = f.readline()
                    title = title.replace("# ", "").replace("\n", "")

            author = authorship_heuristic()

            PAPER_resource_path = Path("template/") / PAPER_RELATIVE
            retrieve_package_file(PAPER_resource_path, PAPER)
            inplace_change(PAPER, "{{project_title}}", title)
            inplace_change(PAPER, "{{author}}", author)
            REVIEW_MANAGER.logger.info(
                f"Please update title and authors in {PAPER.name}"
            )

        REVIEW_MANAGER.report_logger.info("Updating manuscript")
        REVIEW_MANAGER.logger.info("Updating manuscript")
        missing_records = get_data_page_missing(
            PAPER, list(synthesized_record_status_matrix.keys())
        )
        missing_records = sorted(missing_records)
        REVIEW_MANAGER.logger.debug(f"missing_records: {missing_records}")

        if 0 == len(missing_records):
            REVIEW_MANAGER.report_logger.info(f"All records included in {PAPER.name}")
            REVIEW_MANAGER.logger.info(f"All records included in {PAPER.name}")
        else:
            add_missing_records_to_manuscript(
                REVIEW_MANAGER=REVIEW_MANAGER,
                PAPER=PAPER,
                missing_records=[
                    "\n- @" + missing_record + "\n"
                    for missing_record in missing_records
                ],
            )
            nr_records_added = len(missing_records)
            REVIEW_MANAGER.report_logger.info(
                f"{nr_records_added} records added to {PAPER.name}"
            )
            REVIEW_MANAGER.logger.info(
                f"{nr_records_added} records added to {PAPER.name}"
            )

        REVIEW_MANAGER.REVIEW_DATASET.add_changes(
            path=REVIEW_MANAGER.paths["PAPER_RELATIVE"]
        )

        return records

    @classmethod
    def update_data(
        cls, REVIEW_MANAGER, records: dict, synthesized_record_status_matrix: dict
    ):
        # Update manuscript
        records = cls.update_manuscript(
            REVIEW_MANAGER, records, synthesized_record_status_matrix
        )

        return

    @classmethod
    def update_record_status_matrix(
        cls, REVIEW_MANAGER, synthesized_record_status_matrix, endpoint_identifier
    ):
        def get_to_synthesize_in_manuscript(
            PAPER: Path, records_for_synthesis: list
        ) -> list:
            in_manuscript_to_synthesize = []
            if PAPER.is_file():
                with open(PAPER) as f:
                    for line in f:
                        if cls.NEW_RECORD_SOURCE_TAG in line:
                            while line != "":
                                line = f.readline()
                                if re.search(r"- @.*", line):
                                    ID = re.findall(r"- @(.*)$", line)
                                    in_manuscript_to_synthesize.append(ID[0])
                                    if line == "\n":
                                        break

                in_manuscript_to_synthesize = [
                    x for x in in_manuscript_to_synthesize if x in records_for_synthesis
                ]
            else:
                in_manuscript_to_synthesize = records_for_synthesis
            return in_manuscript_to_synthesize

        def get_synthesized_ids_paper(
            PAPER: Path, synthesized_record_status_matrix
        ) -> list:

            in_manuscript_to_synthesize = get_to_synthesize_in_manuscript(
                PAPER, list(synthesized_record_status_matrix.keys())
            )
            # Assuming that all records have been added to the PAPER before
            synthesized_ids = [
                x
                for x in list(synthesized_record_status_matrix.keys())
                if x not in in_manuscript_to_synthesize
            ]

            return synthesized_ids

        # Update status / synthesized_record_status_matrix
        synthesized_in_manuscript = get_synthesized_ids_paper(
            REVIEW_MANAGER.paths["PAPER"],
            synthesized_record_status_matrix,
        )
        for syn_ID in synthesized_in_manuscript:
            if syn_ID in synthesized_record_status_matrix:
                synthesized_record_status_matrix[syn_ID][endpoint_identifier] = True
            else:
                print(f"Error: {syn_ID} not int {synthesized_in_manuscript}")
        return


@zope.interface.implementer(DataEndpoint)
class StructuredDataEndpoint:
    @classmethod
    def get_default_setup(cls):
        structured_endpoint_details = {
            "endpoint": "STRUCTURED",
            "structured_data_endpoint_version": "0.1",
            "fields": [
                {
                    "name": "field name",
                    "explanation": "explanation",
                    "data_type": "data type",
                }
            ],
        }
        return structured_endpoint_details

    @classmethod
    def update_data(
        cls, REVIEW_MANAGER, records: dict, synthesized_record_status_matrix: dict
    ):
        def update_structured_data(
            REVIEW_MANAGER,
            synthesized_record_status_matrix: dict,
        ) -> typing.Dict:

            DATA = REVIEW_MANAGER.paths["DATA"]

            if not DATA.is_file():

                coding_dimensions_str = input(
                    "\n\nEnter columns for data extraction (comma-separted)"
                )
                coding_dimensions = coding_dimensions_str.replace(" ", "_").split(",")

                data = []
                for included_id in list(synthesized_record_status_matrix.keys()):
                    item = [[included_id], ["TODO"] * len(coding_dimensions)]
                    data.append(list(itertools.chain(*item)))

                data_df = pd.DataFrame(data, columns=["ID"] + coding_dimensions)
                data_df.sort_values(by=["ID"], inplace=True)

                data_df.to_csv(DATA, index=False, quoting=csv.QUOTE_ALL)

            else:

                nr_records_added = 0

                data_df = pd.read_csv(DATA, dtype=str)

                for record_id in list(synthesized_record_status_matrix.keys()):
                    # skip when already available
                    if 0 < len(data_df[data_df["ID"].str.startswith(record_id)]):
                        continue

                    add_record = pd.DataFrame({"ID": [record_id]})
                    add_record = add_record.reindex(
                        columns=data_df.columns, fill_value="TODO"
                    )
                    data_df = pd.concat(
                        [data_df, add_record], axis=0, ignore_index=True
                    )
                    nr_records_added = nr_records_added + 1

                data_df.sort_values(by=["ID"], inplace=True)

                data_df.to_csv(DATA, index=False, quoting=csv.QUOTE_ALL)

                REVIEW_MANAGER.report_logger.info(
                    f"{nr_records_added} records added ({DATA})"
                )
                REVIEW_MANAGER.logger.info(f"{nr_records_added} records added ({DATA})")

            return records

        records = update_structured_data(
            REVIEW_MANAGER, synthesized_record_status_matrix
        )

        REVIEW_MANAGER.REVIEW_DATASET.add_changes(
            path=REVIEW_MANAGER.paths["DATA_RELATIVE"]
        )
        return

    @classmethod
    def update_record_status_matrix(
        cls, REVIEW_MANAGER, synthesized_record_status_matrix, endpoint_identifier
    ):
        def get_data_extracted(DATA: Path, records_for_data_extraction: list) -> list:
            data_extracted = []
            data_df = pd.read_csv(DATA)

            for record in records_for_data_extraction:
                drec = data_df.loc[data_df["ID"] == record]
                if 1 == drec.shape[0]:
                    if "TODO" not in drec.iloc[0].tolist():
                        data_extracted.append(drec.loc[drec.index[0], "ID"])

            data_extracted = [
                x for x in data_extracted if x in records_for_data_extraction
            ]
            return data_extracted

        def get_structured_data_extracted(
            synthesized_record_status_matrix: typing.Dict, DATA: Path
        ) -> list:

            if not DATA.is_file():
                return []

            data_extracted = get_data_extracted(
                DATA, list(synthesized_record_status_matrix.keys())
            )
            data_extracted = [
                x
                for x in data_extracted
                if x in list(synthesized_record_status_matrix.keys())
            ]
            return data_extracted

        DATA = REVIEW_MANAGER.paths["DATA"]
        structured_data_extracted = get_structured_data_extracted(
            synthesized_record_status_matrix, DATA
        )

        for syn_ID in structured_data_extracted:
            if syn_ID in synthesized_record_status_matrix:
                synthesized_record_status_matrix[syn_ID][endpoint_identifier] = True
            else:
                print(f"Error: {syn_ID} not int " f"{synthesized_record_status_matrix}")
        return


@zope.interface.implementer(DataEndpoint)
class EndnoteEndpoint:
    @classmethod
    def get_default_setup(cls):
        endnote_endpoint_details = {
            "endpoint": "ENDNOTE",
            "endnote_data_endpoint_version": "0.1",
            "config": {
                "path": "data/endnote",
            },
        }
        return endnote_endpoint_details

    @classmethod
    def update_data(
        cls, REVIEW_MANAGER, records: dict, synthesized_record_status_matrix: dict
    ):

        from colrev_core import load as cc_load
        from colrev_core.review_dataset import ReviewDataset

        def zotero_conversion(data):
            import requests
            import json

            from colrev_core.environment import ZoteroTranslationService

            ZOTERO_TRANSLATION_SERVICE = ZoteroTranslationService()
            ZOTERO_TRANSLATION_SERVICE.start_zotero_translators()

            headers = {"Content-type": "text/plain"}
            r = requests.post(
                "http://127.0.0.1:1969/import",
                headers=headers,
                files={"file": str.encode(data)},
            )
            headers = {"Content-type": "application/json"}
            if "No suitable translators found" == r.content.decode("utf-8"):
                raise cc_load.ImportException(
                    "Zotero translators: No suitable import translators found"
                )

            try:
                zotero_format = json.loads(r.content)
                et = requests.post(
                    "http://127.0.0.1:1969/export?format=refer",
                    headers=headers,
                    json=zotero_format,
                )

            except Exception as e:
                pass
                raise cc_load.ImportException(f"Zotero import translators failed ({e})")

            return et.content

        endpoint_path = Path("data/endnote")
        endpoint_path.mkdir(exist_ok=True, parents=True)

        if not any(Path(endpoint_path).iterdir()):
            REVIEW_MANAGER.logger.info("Export all")
            export_filepath = endpoint_path / Path("export_part1.enl")

            selected_records = {
                ID: r
                for ID, r in records.items()
                if r["colrev_status"]
                in [RecordState.rev_included, RecordState.rev_synthesized]
            }

            data = ReviewDataset.parse_bibtex_str(recs_dict_in=selected_records)

            enl_data = zotero_conversion(data)

            with open(export_filepath, "w") as w:
                w.write(enl_data.decode("utf-8"))
            REVIEW_MANAGER.REVIEW_DATASET.add_changes(path=str(export_filepath))

        else:

            enl_files = endpoint_path.glob("*.enl")
            file_numbers = []
            exported_IDs = []
            for enl_file in enl_files:
                file_numbers.append(int(re.findall(r"\d+", str(enl_file.name))[0]))
                with open(enl_file) as ef:
                    for line in ef:
                        if "%F" == line[:2]:
                            ID = line[3:].lstrip().rstrip()
                            exported_IDs.append(ID)

            REVIEW_MANAGER.logger.info(
                "IDs that have already been exported (in the other export files):"
                f" {exported_IDs}"
            )

            selected_records = {
                ID: r
                for ID, r in records.items()
                if r["colrev_status"]
                in [RecordState.rev_included, RecordState.rev_synthesized]
            }

            if len(selected_records) > 0:

                data = ReviewDataset.parse_bibtex_str(recs_dict_in=selected_records)

                enl_data = zotero_conversion(data)

                next_file_number = str(max(file_numbers) + 1)
                export_filepath = endpoint_path / Path(
                    f"export_part{next_file_number}.enl"
                )
                print(export_filepath)
                with open(export_filepath, "w") as w:
                    w.write(enl_data.decode("utf-8"))
                REVIEW_MANAGER.REVIEW_DATASET.add_changes(path=str(export_filepath))

            else:
                REVIEW_MANAGER.logger.info("No additional records to export")

        return

    @classmethod
    def update_record_status_matrix(
        cls, REVIEW_MANAGER, synthesized_record_status_matrix, endpoint_identifier
    ):
        # Note : automatically set all to True / synthesized
        for syn_ID in list(synthesized_record_status_matrix.keys()):
            synthesized_record_status_matrix[syn_ID][endpoint_identifier] = True

        return


@zope.interface.implementer(DataEndpoint)
class PRISMAEndpoint:
    @classmethod
    def get_default_setup(cls):
        prisma_endpoint_details = {
            "endpoint": "PRISMA",
            "prisma_data_endpoint_version": "0.1",
        }
        return prisma_endpoint_details

    @classmethod
    def update_data(
        cls, REVIEW_MANAGER, records: dict, synthesized_record_status_matrix: dict
    ):

        from colrev_core.status import Status
        import os

        def retrieve_package_file(template_file: Path, target: Path) -> None:
            filedata = pkgutil.get_data(__name__, str(template_file))
            if filedata:
                with open(target, "w") as file:
                    file.write(filedata.decode("utf-8"))
            return

        PRISMA_resource_path = Path("template/") / Path("PRISMA.csv")
        PRISMA_path = Path("data/PRISMA.csv")
        PRISMA_path.parent.mkdir(exist_ok=True, parents=True)

        if PRISMA_path.is_file():
            os.remove(PRISMA_path)
        retrieve_package_file(PRISMA_resource_path, PRISMA_path)

        STATUS = Status(REVIEW_MANAGER=REVIEW_MANAGER)
        stat = STATUS.get_status_freq()
        # print(stat)

        prisma_data = pd.read_csv(PRISMA_path)
        prisma_data["ind"] = prisma_data["data"]
        prisma_data.set_index("ind", inplace=True)
        prisma_data.loc["database_results", "n"] = stat["colrev_status"]["overall"][
            "md_retrieved"
        ]
        prisma_data.loc["duplicates", "n"] = stat["colrev_status"]["currently"][
            "md_duplicates_removed"
        ]
        prisma_data.loc["records_screened", "n"] = stat["colrev_status"]["overall"][
            "rev_prescreen"
        ]
        prisma_data.loc["records_excluded", "n"] = stat["colrev_status"]["overall"][
            "rev_excluded"
        ]
        prisma_data.loc["dbr_assessed", "n"] = stat["colrev_status"]["overall"][
            "rev_screen"
        ]
        prisma_data.loc["new_studies", "n"] = stat["colrev_status"]["overall"][
            "rev_included"
        ]
        prisma_data.loc["dbr_notretrieved_reports", "n"] = stat["colrev_status"][
            "overall"
        ]["pdf_not_available"]
        prisma_data.loc["dbr_sought_reports", "n"] = stat["colrev_status"]["overall"][
            "rev_prescreen_included"
        ]

        exclusion_stats = []
        for c, v in stat["colrev_status"]["currently"]["exclusion"].items():
            exclusion_stats.append(f"Reason {c}, {v}")
        prisma_data.loc["dbr_excluded", "n"] = "; ".join(exclusion_stats)

        prisma_data.to_csv(PRISMA_path, index=False)
        print(f"Exported {PRISMA_path}")
        print(
            "Diagrams can be created online "
            "at https://estech.shinyapps.io/prisma_flowdiagram/"
        )

        if not stat["completeness_condition"]:
            print("Warning: review not (yet) complete")

        return

    @classmethod
    def update_record_status_matrix(
        cls, REVIEW_MANAGER, synthesized_record_status_matrix, endpoint_identifier
    ):

        # Note : automatically set all to True / synthesized
        for syn_ID in list(synthesized_record_status_matrix.keys()):
            synthesized_record_status_matrix[syn_ID][endpoint_identifier] = True

        return


@zope.interface.implementer(DataEndpoint)
class ZettlrEndpoint:

    NEW_RECORD_SOURCE_TAG = "<!-- NEW_RECORD_SOURCE -->"

    @classmethod
    def get_default_setup(cls):
        zettlr_endpoint_details = {
            "endpoint": "ZETTLR",
            "zettlr_endpoint_version": "0.1",
            "config": {},
        }
        return zettlr_endpoint_details

    @classmethod
    def update_data(
        cls, REVIEW_MANAGER, records: dict, synthesized_record_status_matrix: dict
    ):
        from colrev_core.data import Data
        import configparser
        import datetime

        REVIEW_MANAGER.logger.info("Export to zettlr endpoint")

        endpoint_path = REVIEW_MANAGER.path / Path("data/zettlr")

        # TODO : check if a main-zettlr file exists.

        def get_zettlr_missing(endpoint_path, included):
            in_zettelkasten = []

            for md_file in endpoint_path.glob("*.md"):
                with open(md_file) as f:
                    line = f.readline()
                    while line:
                        if "title:" in line:
                            id = line[line.find('"') + 1 : line.rfind('"')]
                            in_zettelkasten.append(id)
                        line = f.readline()

            return [x for x in included if x not in in_zettelkasten]

        def retrieve_package_file(template_file: Path, target: Path) -> None:
            filedata = pkgutil.get_data(__name__, str(template_file))
            if filedata:
                with open(target, "w") as file:
                    file.write(filedata.decode("utf-8"))
            return

        def inplace_change(filename: Path, old_string: str, new_string: str) -> None:
            with open(filename) as f:
                s = f.read()
                if old_string not in s:
                    REVIEW_MANAGER.logger.info(
                        f'"{old_string}" not found in {filename}.'
                    )
                    return
            with open(filename, "w") as f:
                s = s.replace(old_string, new_string)
                f.write(s)
            return

        def add_missing_records_to_manuscript(
            *, REVIEW_MANAGER, PAPER: Path, missing_records: list
        ):
            temp = tempfile.NamedTemporaryFile()
            PAPER.rename(temp.name)
            with open(temp.name) as reader, open(PAPER, "w") as writer:
                appended, completed = False, False
                line = reader.readline()
                while line != "":
                    if cls.NEW_RECORD_SOURCE_TAG in line:
                        if "_Records to synthesize" not in line:
                            line = "_Records to synthesize_:" + line + "\n"
                            writer.write(line)
                        else:
                            writer.write(line)
                            writer.write("\n")

                        for missing_record in missing_records:
                            writer.write(missing_record)
                            REVIEW_MANAGER.report_logger.info(
                                # f" {missing_record}".ljust(self.__PAD, " ")
                                f" {missing_record}"
                                + f" added to {PAPER.name}"
                            )

                            REVIEW_MANAGER.logger.info(
                                # f" {missing_record}".ljust(self.__PAD, " ")
                                f" {missing_record}"
                                + f" added to {PAPER.name}"
                            )

                        # skip empty lines between to connect lists
                        line = reader.readline()
                        if "\n" != line:
                            writer.write(line)

                        appended = True

                    elif appended and not completed:
                        if "- @" == line[:3]:
                            writer.write(line)
                        else:
                            if "\n" != line:
                                writer.write("\n")
                            writer.write(line)
                            completed = True
                    else:
                        writer.write(line)
                    line = reader.readline()

                if not appended:
                    msg = (
                        f"Marker {cls.NEW_RECORD_SOURCE_TAG} not found in "
                        + f"{PAPER.name}. Adding records at the end of "
                        + "the document."
                    )
                    REVIEW_MANAGER.report_logger.warning(msg)
                    REVIEW_MANAGER.logger.warning(msg)

                    if line != "\n":
                        writer.write("\n")
                    marker = f"{cls.NEW_RECORD_SOURCE_TAG}_Records to synthesize_:\n\n"
                    writer.write(marker)
                    for missing_record in missing_records:
                        writer.write(missing_record)
                        REVIEW_MANAGER.report_logger.info(
                            # f" {missing_record}".ljust(self.__PAD, " ") + " added"
                            f" {missing_record} added"
                        )
                        REVIEW_MANAGER.logger.info(
                            # f" {missing_record}".ljust(self.__PAD, " ") + " added"
                            f" {missing_record} added"
                        )

            return

        zettlr_config_path = endpoint_path / Path(".zettlr_config.ini")
        currentDT = datetime.datetime.now()
        if zettlr_config_path.is_file():
            zettlr_config = configparser.ConfigParser()
            zettlr_config.read(zettlr_config_path)
            ZETTLR_path = endpoint_path / Path(zettlr_config.get("general", "main"))

        else:

            unique_timestamp = currentDT + datetime.timedelta(seconds=3)
            ZETTLR_resource_path = Path("template/zettlr/") / Path("zettlr.md")
            fname = Path(unique_timestamp.strftime("%Y%m%d%H%M%S") + ".md")
            ZETTLR_path = endpoint_path / fname

            zettlr_config = configparser.ConfigParser()
            zettlr_config.add_section("general")
            zettlr_config["general"]["main"] = str(fname)
            with open(zettlr_config_path, "w") as configfile:
                zettlr_config.write(configfile)
            REVIEW_MANAGER.REVIEW_DATASET.add_changes(path=str(zettlr_config_path))

            retrieve_package_file(ZETTLR_resource_path, ZETTLR_path)
            title = "PROJECT_NAME"
            readme_file = REVIEW_MANAGER.paths["README"]
            if readme_file.is_file():
                with open(readme_file) as f:
                    title = f.readline()
                    title = title.replace("# ", "").replace("\n", "")

            inplace_change(ZETTLR_path, "{{project_title}}", title)
            # author = authorship_heuristic(REVIEW_MANAGER)
            REVIEW_MANAGER.create_commit(msg="Add zettlr endpoint")

        records_dict = REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        included = Data.get_record_ids_for_synthesis(records_dict)

        missing_records = get_zettlr_missing(endpoint_path, included)

        if len(missing_records) == 0:
            print("All records included. Nothing to export.")
        else:
            print(missing_records)

            missing_records = sorted(missing_records)
            missing_record_fields = []
            for i, missing_record in enumerate(missing_records):
                unique_timestamp = currentDT - datetime.timedelta(seconds=i)
                missing_record_fields.append(
                    [unique_timestamp.strftime("%Y%m%d%H%M%S") + ".md", missing_record]
                )

            add_missing_records_to_manuscript(
                REVIEW_MANAGER=REVIEW_MANAGER,
                PAPER=ZETTLR_path,
                missing_records=[
                    "\n- [[" + i + "]] @" + r + "\n" for i, r in missing_record_fields
                ],
            )

            REVIEW_MANAGER.REVIEW_DATASET.add_changes(path=str(ZETTLR_path))

            ZETTLR_resource_path = Path("template/zettlr/") / Path("zettlr_bib_item.md")

            for missing_record_field in missing_record_fields:
                id, r = missing_record_field
                print(id + r)
                ZETTLR_path = endpoint_path / Path(id)

                retrieve_package_file(ZETTLR_resource_path, ZETTLR_path)
                inplace_change(ZETTLR_path, "{{project_name}}", r)
                with ZETTLR_path.open("a") as f:
                    f.write(f"\n\n@{r}\n")

                REVIEW_MANAGER.REVIEW_DATASET.add_changes(path=str(ZETTLR_path))

            REVIEW_MANAGER.create_commit(msg="Setup zettlr")

            print("TODO: recommend zettlr/snippest, adding tags")

        return

    @classmethod
    def update_record_status_matrix(
        cls, REVIEW_MANAGER, synthesized_record_status_matrix, endpoint_identifier
    ):
        # TODO : not yet implemented!
        # TODO : records mentioned after the NEW_RECORD_SOURCE tag are not synthesized.

        # Note : automatically set all to True / synthesized
        for syn_ID in list(synthesized_record_status_matrix.keys()):
            synthesized_record_status_matrix[syn_ID][endpoint_identifier] = True

        return


# @zope.interface.implementer(DataEndpoint)
# class NAMEEndpoint:

#     TODO : add to settings.json
#     TODO : add to Data - self.data_endpoints:

#    @classmethod
#    def get_default_setup(cls):
#        XXX_endpoint_details = {
#            "endpoint": "XXX",
#            "XXX_version": "0.1",
#            "config": {},
#        }
#        return XXX_endpoint_details

#     @classmethod
#     def update_data(
#         cls, REVIEW_MANAGER, records: dict, synthesized_record_status_matrix: dict
#     ):

#         return

#     @classmethod
#     def update_record_status_matrix(
#         cls, REVIEW_MANAGER, synthesized_record_status_matrix, endpoint_identifier
#     ):

#         return


class Data(Process):
    """Class supporting structured and unstructured
    data extraction, analysis and synthesis"""

    __PAD = 0

    def __init__(self, REVIEW_MANAGER, notify_state_transition_process=True):

        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            type=ProcessType.data,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.data_endpoints: typing.Dict[str, typing.Dict[str, typing.Any]] = {
            "MANUSCRIPT": {
                "endpoint": ManuscriptEndpoint,
            },
            "STRUCTURED": {
                "endpoint": StructuredDataEndpoint,
            },
            "ENDNOTE": {
                "endpoint": EndnoteEndpoint,
            },
            "PRISMA": {
                "endpoint": PRISMAEndpoint,
            },
            "ZETTLR": {
                "endpoint": ZettlrEndpoint,
            },
        }

        list_custom_scripts = [
            s.endpoint
            for s in REVIEW_MANAGER.settings.data.data_format
            if s.endpoint not in self.data_endpoints
            and Path(s.endpoint + ".py").is_file()
        ]
        sys.path.append(".")  # to import custom scripts from the project dir
        for plugin_script in list_custom_scripts:
            custom_data_script = importlib.import_module(plugin_script, ".").CustomData
            verifyObject(DataEndpoint, custom_data_script())
            self.data_endpoints[plugin_script] = {"endpoint": custom_data_script}

        # TODO : test the module data_scripts
        list_module_scripts = [
            s.endpoint
            for s in REVIEW_MANAGER.settings.data.data_format
            if s.endpoint not in self.data_endpoints
            and not Path(s.endpoint + ".py").is_file()
        ]
        for plugin_script in list_module_scripts:
            try:
                custom_data_script = importlib.import_module(plugin_script).CustomData
                verifyObject(DataEndpoint, custom_data_script())
                self.data_endpoints[plugin_script] = {"endpoint": custom_data_script}
            except ModuleNotFoundError:
                pass
                # raise MissingDependencyError
                print(
                    "Dependency data_script " + f"{plugin_script} not found. "
                    "Please install it\n  pip install "
                    f"{plugin_script}"
                )

    @classmethod
    def get_record_ids_for_synthesis(cls, records: typing.Dict) -> list:
        return [
            ID
            for ID, record in records.items()
            if record["colrev_status"]
            in [RecordState.rev_included, RecordState.rev_synthesized]
        ]

    def update_tei(
        self, records: typing.Dict, included: typing.List[dict]
    ) -> typing.Dict:
        from lxml import etree
        from lxml.etree import XMLSyntaxError

        # from p_tqdm import p_map
        from colrev_core.environment import TEI_Exception

        GROBID_SERVICE = GrobidService()
        GROBID_SERVICE.start()

        def create_tei(record: dict) -> None:
            if "file" not in record:
                return
            if "tei_file" not in record:
                self.REVIEW_MANAGER.logger.info(f"Get tei for {record['ID']}")
                pdf_path = self.REVIEW_MANAGER.path / record["file"]
                if not Path(pdf_path).is_file():
                    print(f"file not available: {record['file']}")
                    return

                tei_path = Path("tei") / Path(record["ID"] + ".tei.xml")
                tei_path.parents[0].mkdir(exist_ok=True)
                if tei_path.is_file():
                    record["tei_file"] = str(tei_path)
                    return

                try:
                    TEIParser(pdf_path=pdf_path, tei_path=tei_path)

                    if tei_path.is_file():
                        record["tei_file"] = str(tei_path)

                except (
                    etree.XMLSyntaxError,
                    ProtocolError,
                    requests.exceptions.ConnectionError,
                    TEI_TimeoutException,
                    TEI_Exception,
                ):
                    if "tei_file" in record:
                        del record["tei_file"]
                    pass
            return

        for record in records.values():
            create_tei(record)
        # p_map(create_tei, records, num_cpus=6)

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        if self.REVIEW_MANAGER.REVIEW_DATASET.has_changes():
            self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
            self.REVIEW_MANAGER.create_commit(msg="Create TEIs")

        # Enhance TEIs (link local IDs)
        for record in records.values():
            self.REVIEW_MANAGER.logger.info(f"Enhance TEI for {record['ID']}")
            if "tei_file" in record:

                tei_path = Path(record["tei_file"])
                try:
                    TEI_INSTANCE = TEIParser(self.REVIEW_MANAGER, tei_path=tei_path)
                    TEI_INSTANCE.mark_references(records=records.values())
                except XMLSyntaxError:
                    pass
                    continue

                # ns = {
                #     "tei": "{http://www.tei-c.org/ns/1.0}",
                #     "w3": "{http://www.w3.org/XML/1998/namespace}",
                # }
                # theories = ['actornetwork theory', 'structuration theory']
                # for paragraph in root.iter(ns['tei'] + 'p'):
                #     # print(paragraph.text.lower())
                #     for theory in theories:
                #         # if theory in ''.join(paragraph.itertext()):
                #         if theory in paragraph.text:
                #             paragraph.text = \
                #               paragraph.text.replace(theory,
                #                           f'<theory>{theory}</theory>')

                # if tei_path.is_file():
                #     git_repo.index.add([str(tei_path)])

        self.REVIEW_MANAGER.create_commit(msg="Enhance TEIs")

        return records

    def reading_heuristics(self):

        enlit_list = []
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        for relevant_record_id in self.get_record_ids_for_synthesis(records):
            enlit_status = str(records[relevant_record_id]["colrev_status"])
            enlit_status = enlit_status.replace("rev_included", "").replace(
                "rev_synthesized", "synthesized"
            )
            enlit_list.append(
                {
                    "ID": relevant_record_id,
                    "score": 0,
                    "score_intensity": 0,
                    "colrev_status": enlit_status,
                }
            )

        tei_path = self.REVIEW_MANAGER.paths["REPO_DIR"] / Path("tei")
        required_records_ids = self.get_record_ids_for_synthesis(records)
        missing = [
            x
            for x in list(tei_path.glob("*.tei.xml"))
            if not any(i in x for i in required_records_ids)
        ]
        if len(missing) > 0:
            print(f"Records with missing tei file: {missing}")

        for tei_file in tei_path.glob("*.tei.xml"):
            data = tei_file.read_text()
            for enlit_item in enlit_list:
                ID_string = f'ID="{enlit_item["ID"]}"'
                if ID_string in data:
                    enlit_item["score"] += 1
                enlit_item["score_intensity"] += data.count(ID_string)

        enlit_list = sorted(enlit_list, key=lambda d: d["score"], reverse=True)

        return enlit_list

    def profile(self) -> None:

        self.REVIEW_MANAGER.logger.info("Create sample profile")

        def prep_references(records) -> pd.DataFrame:
            for record in records:
                record["outlet"] = record.get("journal", record.get("booktitle", "NA"))

            references = pd.DataFrame.from_dict(records)

            required_cols = [
                "ID",
                "ENTRYTYPE",
                "author",
                "title",
                "journal",
                "booktitle",
                "outlet",
                "year",
                "volume",
                "number",
                "pages",
                "doi",
            ]
            available_cols = references.columns.intersection(set(required_cols))
            cols = [x for x in required_cols if x in available_cols]
            references = references[cols]
            return references

        def prep_observations(references: dict, records: typing.Dict) -> pd.DataFrame:

            included_papers = [
                ID
                for ID, record in records.items()
                if record["colrev_status"]
                in [RecordState.rev_synthesized, RecordState.rev_included]
            ]
            observations = references[references["ID"].isin(included_papers)].copy()
            observations.loc[:, "year"] = observations.loc[:, "year"].astype(int)
            missing_outlet = observations[observations["outlet"].isnull()][
                "ID"
            ].tolist()
            if len(missing_outlet) > 0:
                self.REVIEW_MANAGER.logger.info(f"No outlet: {missing_outlet}")
            return observations

        # RED = "\033[91m"
        # END = "\033[0m"
        # if not status.get_completeness_condition():
        #     self.REVIEW_MANAGER.logger.warning(
        #  f"{RED}Sample not completely processed!{END}")

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        output_dir = self.REVIEW_MANAGER.path / Path("output")
        output_dir.mkdir(exist_ok=True)

        references = prep_references(records.values())
        observations = prep_observations(references, records)

        if observations.empty:
            self.REVIEW_MANAGER.logger.info("No sample/observations available")
            return

        self.REVIEW_MANAGER.logger.info("Generate output/sample.csv")
        observations.to_csv(output_dir / Path("sample.csv"), index=False)

        tabulated = pd.pivot_table(
            observations[["outlet", "year"]],
            index=["outlet"],
            columns=["year"],
            aggfunc=len,
            fill_value=0,
            margins=True,
        )
        # Fill missing years with 0 columns
        years = range(
            min(e for e in tabulated.columns if isinstance(e, int)),
            max(e for e in tabulated.columns if isinstance(e, int)) + 1,
        )
        for year in years:
            if year not in tabulated.columns:
                tabulated[year] = 0
        nc = list(years)
        nc.extend(["All"])  # type: ignore
        tabulated = tabulated[nc]

        self.REVIEW_MANAGER.logger.info("Generate profile output/journals_years.csv")
        tabulated.to_csv(output_dir / Path("journals_years.csv"))

        tabulated = pd.pivot_table(
            observations[["ENTRYTYPE", "year"]],
            index=["ENTRYTYPE"],
            columns=["year"],
            aggfunc=len,
            fill_value=0,
            margins=True,
        )
        self.REVIEW_MANAGER.logger.info("Generate output/ENTRYTYPES.csv")
        tabulated.to_csv(output_dir / Path("ENTRYTYPES.csv"))

        self.REVIEW_MANAGER.logger.info(f"Files are available in {output_dir.name}")

        return

    def add_data_endpoint(self, data_endpoint) -> None:

        self.REVIEW_MANAGER.settings.data.data_format.append(data_endpoint)
        self.REVIEW_MANAGER.save_settings()

        return

    def main(self, pre_commit_hook=False) -> dict:

        if pre_commit_hook:
            self.verbose = False
            # TODO : use self.verbose in the update scripts of data endpoints
        else:
            self.verbose = True

        saved_args = locals()

        if 0 == len(self.REVIEW_MANAGER.settings.data.data_format):
            raise NoDataEndpointsRegistered()

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        if 0 == len(records):
            return {"ask_to_commit": False}

        self.__PAD = min((max(len(ID) for ID in records.keys()) + 2), 35)

        included = self.get_record_ids_for_synthesis(records)
        if 0 == len(included):
            if self.verbose:
                self.REVIEW_MANAGER.report_logger.info(
                    "No records included yet (use colrev_core screen)"
                )
                self.REVIEW_MANAGER.logger.info(
                    "No records included yet (use colrev_core screen)"
                )

        else:

            from colrev_core.process import CheckProcess

            CHECK_PROCESS = CheckProcess(REVIEW_MANAGER=self.REVIEW_MANAGER)
            # TBD: do we assume that records are not changed by the processes?
            records = CHECK_PROCESS.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

            # synthesized_record_status_matrix (paper IDs x endpoint):
            # each endpoint sets synthesized = True/False
            # and if a paper has synthesized=True in all fields,
            # its overall status is set to synthesized
            # Some endpoints may always set synthesized
            default_row = {
                df.endpoint: False
                for df in self.REVIEW_MANAGER.settings.data.data_format
            }
            synthesized_record_status_matrix = {
                ID: default_row.copy() for ID in included
            }

            if self.verbose:
                self.REVIEW_MANAGER.pp.pprint(synthesized_record_status_matrix)

            # TODO : include paper.md / data.csv as arguments of the data endpoint
            # not the review_manager? (but: the other scripts/checks may rely
            # on the review_manager/path variables....)

            for DATA_FORMAT in self.REVIEW_MANAGER.settings.data.data_format:

                if DATA_FORMAT.endpoint not in list(self.data_endpoints.keys()):
                    if self.verbose:
                        print(f"Error: endpoint not available: {DATA_FORMAT}")
                    continue

                endpoint = self.data_endpoints[DATA_FORMAT.endpoint]

                ENDPOINT = endpoint["endpoint"]()
                ENDPOINT.update_data(
                    self.REVIEW_MANAGER, records, synthesized_record_status_matrix
                )
                ENDPOINT.update_record_status_matrix(
                    self.REVIEW_MANAGER,
                    synthesized_record_status_matrix,
                    DATA_FORMAT.endpoint,
                )

                if self.verbose:
                    print(f"updated {endpoint}")

                # if "TEI" == DATA_FORMAT.endpoint:
                #     records = self.update_tei(records, included)
                #     self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
                #     self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

            for ID, individual_status_dict in synthesized_record_status_matrix.items():
                if all(x for x in individual_status_dict.values()):
                    records[ID].update(colrev_status=RecordState.rev_synthesized)
                    if self.verbose:
                        self.REVIEW_MANAGER.report_logger.info(
                            f" {ID}".ljust(self.__PAD, " ")
                            + "set colrev_status to synthesized"
                        )
                        self.REVIEW_MANAGER.logger.info(
                            f" {ID}".ljust(self.__PAD, " ")
                            + "set colrev_status to synthesized"
                        )
                else:
                    records[ID].update(colrev_status=RecordState.rev_included)

            if self.verbose:
                self.REVIEW_MANAGER.pp.pprint(synthesized_record_status_matrix)

            CHECK_PROCESS.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(
                records=records
            )
            CHECK_PROCESS.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

            return {"ask_to_commit": True}
        return {"ask_to_commit": False}

    def setup_custom_script(self) -> None:
        import pkgutil
        from colrev_core.settings import CustomDataFormat

        filedata = pkgutil.get_data(__name__, "template/custom_data_script.py")
        if filedata:
            with open("custom_data_script.py", "w") as file:
                file.write(filedata.decode("utf-8"))

        self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(path="custom_data_script.py")

        NEW_DATA_ENDPOINT = CustomDataFormat(
            endpoint="custom_data_script", custom_data_format_version="0.1", config={}
        )

        self.REVIEW_MANAGER.settings.data.data_format.append(NEW_DATA_ENDPOINT)
        self.REVIEW_MANAGER.save_settings()

        return


class NoDataEndpointsRegistered(Exception):
    """No data endpoints (data_format field) registered in settings.json"""

    def __init__(self):
        super().__init__(
            "No data endpoints (data_format field) registered in settings.json"
        )


class ManuscriptRecordSourceTagError(Exception):
    """NEW_RECORD_SOURCE_TAG not found in paper.md"""

    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


if __name__ == "__main__":
    pass
