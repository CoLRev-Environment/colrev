#! /usr/bin/env python
import csv
import itertools
import pkgutil
import re
import tempfile
import typing
from collections import Counter
from pathlib import Path

import pandas as pd
import requests
from urllib3.exceptions import ProtocolError

from colrev_core import grobid_client
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import RecordState
from colrev_core.tei import TEI
from colrev_core.tei import TEI_TimeoutException


class Data(Process):
    """Class supporting structured and unstructured
    data extraction, analysis and synthesis"""

    __PAD = 0
    NEW_RECORD_SOURCE_TAG = "<!-- NEW_RECORD_SOURCE -->"
    """Tag for appending new records in paper.md

    In the paper.md, the IDs of new records marked for synthesis
    will be appended after this tag.

    If IDs are moved to other parts of the manuscript,
    the corresponding record will be marked as rev_synthesized."""

    def __init__(self, REVIEW_MANAGER, notify_state_transition_process=True):

        super().__init__(
            REVIEW_MANAGER,
            ProcessType.data,
            notify_state_transition_process=notify_state_transition_process,
        )

    @classmethod
    def get_record_ids_for_synthesis(cls, records: typing.Dict) -> list:
        return [
            ID
            for ID, record in records.items()
            if record["colrev_status"]
            in [RecordState.rev_included, RecordState.rev_synthesized]
        ]

    def get_data_page_missing(self, PAPER: Path, record_id_list: list) -> list:
        available = []
        with open(PAPER) as f:
            line = f.read()
            for record in record_id_list:
                if record in line:
                    available.append(record)

        return list(set(record_id_list) - set(available))

    def get_to_synthesize_in_manuscript(
        self, PAPER: Path, records_for_synthesis: list
    ) -> list:
        in_manuscript_to_synthesize = []
        if PAPER.is_file():
            with open(PAPER) as f:
                for line in f:
                    if self.NEW_RECORD_SOURCE_TAG in line:
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

    def get_synthesized_ids(self, records: typing.Dict, PAPER: Path) -> list:

        record_ids_for_synthesis = self.get_record_ids_for_synthesis(records)

        in_manuscript_to_synthesize = self.get_to_synthesize_in_manuscript(
            PAPER, record_ids_for_synthesis
        )
        # Assuming that all records have been added to the PAPER before
        synthesized_ids = [
            x for x in record_ids_for_synthesis if x not in in_manuscript_to_synthesize
        ]

        return synthesized_ids

    def get_data_extracted(self, DATA: Path, records_for_data_extraction: list) -> list:
        data_extracted = []
        data_df = pd.read_csv(DATA)

        for record in records_for_data_extraction:
            drec = data_df.loc[data_df["ID"] == record]
            if 1 == drec.shape[0]:
                if "TODO" not in drec.iloc[0].tolist():
                    data_extracted.append(drec.loc[drec.index[0], "ID"])

        data_extracted = [x for x in data_extracted if x in records_for_data_extraction]
        return data_extracted

    def get_structured_data_extracted(self, records: typing.Dict, DATA: Path) -> list:

        if not DATA.is_file():
            return []

        records_for_data_extraction = [
            ID
            for ID, record in records.items()
            if record["colrev_status"]
            in [RecordState.rev_included, RecordState.rev_synthesized]
        ]

        data_extracted = self.get_data_extracted(DATA, records_for_data_extraction)
        data_extracted = [x for x in data_extracted if x in records_for_data_extraction]
        return data_extracted

    def add_missing_records_to_manuscript(
        self, PAPER: Path, missing_records: list
    ) -> None:
        temp = tempfile.NamedTemporaryFile()
        PAPER.rename(temp.name)
        with open(temp.name) as reader, open(PAPER, "w") as writer:
            appended, completed = False, False
            line = reader.readline()
            while line != "":
                if self.NEW_RECORD_SOURCE_TAG in line:
                    if "_Records to synthesize" not in line:
                        line = "_Records to synthesize_:" + line + "\n"
                        writer.write(line)
                    else:
                        writer.write(line)
                        writer.write("\n")

                    for missing_record in missing_records:
                        writer.write(missing_record)
                        self.REVIEW_MANAGER.report_logger.info(
                            f" {missing_record}".ljust(self.__PAD, " ")
                            + f" added to {PAPER.name}"
                        )

                        self.REVIEW_MANAGER.logger.info(
                            f" {missing_record}".ljust(self.__PAD, " ")
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
                    f"Marker {self.NEW_RECORD_SOURCE_TAG} not found in "
                    + f"{PAPER.name}. Adding records at the end of "
                    + "the document."
                )
                self.REVIEW_MANAGER.report_logger.warning(msg)
                self.REVIEW_MANAGER.logger.warning(msg)

                if line != "\n":
                    writer.write("\n")
                marker = f"{self.NEW_RECORD_SOURCE_TAG}_Records to synthesize_:\n\n"
                writer.write(marker)
                for missing_record in missing_records:
                    writer.write(missing_record)
                    self.REVIEW_MANAGER.report_logger.info(
                        f" {missing_record}".ljust(self.__PAD, " ") + " added"
                    )
                    self.REVIEW_MANAGER.logger.info(
                        f" {missing_record}".ljust(self.__PAD, " ") + " added"
                    )

        return

    def authorship_heuristic(self) -> str:
        git_repo = self.REVIEW_MANAGER.REVIEW_DATASET.get_repo()
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

    def __inplace_change(
        self, filename: Path, old_string: str, new_string: str
    ) -> None:
        with open(filename) as f:
            s = f.read()
            if old_string not in s:
                self.REVIEW_MANAGER.logger.info(
                    f'"{old_string}" not found in {filename}.'
                )
                return
        with open(filename, "w") as f:
            s = s.replace(old_string, new_string)
            f.write(s)
        return

    def update_manuscript(self, records: typing.Dict, included: list) -> typing.Dict:

        PAPER = self.REVIEW_MANAGER.paths["PAPER"]
        PAPER_RELATIVE = self.REVIEW_MANAGER.paths["PAPER_RELATIVE"]

        if not PAPER.is_file():
            missing_records = included

            self.REVIEW_MANAGER.report_logger.info("Creating manuscript")
            self.REVIEW_MANAGER.logger.info("Creating manuscript")

            title = "Manuscript template"
            readme_file = self.REVIEW_MANAGER.paths["README"]
            if readme_file.is_file():
                with open(readme_file) as f:
                    title = f.readline()
                    title = title.replace("# ", "").replace("\n", "")

            author = self.authorship_heuristic()

            PAPER_resource_path = Path("template/") / PAPER_RELATIVE
            self.retrieve_package_file(PAPER_resource_path, PAPER)
            self.__inplace_change(PAPER, "{{project_title}}", title)
            self.__inplace_change(PAPER, "{{author}}", author)
            self.REVIEW_MANAGER.logger.info(
                f"Please update title and authors in {PAPER.name}"
            )

        self.REVIEW_MANAGER.report_logger.info("Updating manuscript")
        self.REVIEW_MANAGER.logger.info("Updating manuscript")
        missing_records = self.get_data_page_missing(PAPER, included)
        missing_records = sorted(missing_records)
        self.REVIEW_MANAGER.logger.debug(f"missing_records: {missing_records}")

        if 0 == len(missing_records):
            self.REVIEW_MANAGER.report_logger.info(
                f"All records included in {PAPER.name}"
            )
            self.REVIEW_MANAGER.logger.info(f"All records included in {PAPER.name}")
        else:
            self.add_missing_records_to_manuscript(
                PAPER,
                ["\n- @" + missing_record + "\n" for missing_record in missing_records],
            )
            nr_records_added = len(missing_records)
            self.REVIEW_MANAGER.report_logger.info(
                f"{nr_records_added} records added to {PAPER.name}"
            )
            self.REVIEW_MANAGER.logger.info(
                f"{nr_records_added} records added to {PAPER.name}"
            )

        return records

    def update_structured_data(
        self, records: typing.Dict, included: list
    ) -> typing.Dict:

        DATA = self.REVIEW_MANAGER.paths["DATA"]

        if not DATA.is_file():
            included = self.get_record_ids_for_synthesis(records)

            coding_dimensions_str = input(
                "\n\nEnter columns for data extraction (comma-separted)"
            )
            coding_dimensions = coding_dimensions_str.replace(" ", "_").split(",")

            data = []
            for included_id in included:
                item = [[included_id], ["TODO"] * len(coding_dimensions)]
                data.append(list(itertools.chain(*item)))

            data_df = pd.DataFrame(data, columns=["ID"] + coding_dimensions)
            data_df.sort_values(by=["ID"], inplace=True)

            data_df.to_csv(DATA, index=False, quoting=csv.QUOTE_ALL)

        else:

            nr_records_added = 0

            data_df = pd.read_csv(DATA, dtype=str)

            for record_id in included:
                # skip when already available
                if 0 < len(data_df[data_df["ID"].str.startswith(record_id)]):
                    continue

                add_record = pd.DataFrame({"ID": [record_id]})
                add_record = add_record.reindex(
                    columns=data_df.columns, fill_value="TODO"
                )
                data_df = pd.concat([data_df, add_record], axis=0, ignore_index=True)
                nr_records_added = nr_records_added + 1

            data_df.sort_values(by=["ID"], inplace=True)

            data_df.to_csv(DATA, index=False, quoting=csv.QUOTE_ALL)

            self.REVIEW_MANAGER.report_logger.info(
                f"{nr_records_added} records added ({DATA})"
            )
            self.REVIEW_MANAGER.logger.info(
                f"{nr_records_added} records added ({DATA})"
            )

        return records

    def update_tei(
        self, records: typing.Dict, included: typing.List[dict]
    ) -> typing.Dict:
        from lxml import etree
        from lxml.etree import XMLSyntaxError

        # from p_tqdm import p_map
        from colrev_core.tei import TEI_Exception

        grobid_client.start_grobid()

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
                    TEI(pdf_path=pdf_path, tei_path=tei_path)

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

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records)
        if self.REVIEW_MANAGER.REVIEW_DATASET.has_changes():
            self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
            self.REVIEW_MANAGER.create_commit("Create TEIs")

        # Enhance TEIs (link local IDs)
        for record in records.values():
            self.REVIEW_MANAGER.logger.info(f"Enhance TEI for {record['ID']}")
            if "tei_file" in record:

                tei_path = Path(record["tei_file"])
                try:
                    TEI_INSTANCE = TEI(self.REVIEW_MANAGER, tei_path=tei_path)
                    TEI_INSTANCE.mark_references(records.values())
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

        self.REVIEW_MANAGER.create_commit("Enhance TEIs")

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

    def retrieve_default_word_template(self) -> str:
        template_name = "APA-7.docx"

        filedata = pkgutil.get_data(__name__, str(Path("template/APA-7.docx")))
        if filedata:
            with open(Path(template_name), "wb") as file:
                file.write(filedata)

        self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(template_name)
        return template_name

    def retrieve_default_csl(self) -> str:
        csl_link = (
            "https://raw.githubusercontent.com/"
            + "citation-style-language/styles/master/apa.csl"
        )
        r = requests.get(csl_link, allow_redirects=True)
        open(Path(csl_link).name, "wb").write(r.content)
        csl = Path(csl_link).name
        return csl

    def add_data_endpoint(self, data_endpoint) -> None:

        self.REVIEW_MANAGER.settings.data.data_format.append(data_endpoint)
        self.REVIEW_MANAGER.save_settings()

        return

    def main(self) -> None:

        saved_args = locals()

        data_endpoints = self.REVIEW_MANAGER.settings.data.data_format
        if 0 == len(data_endpoints):
            raise NoDataEndpointsRegistered()

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        self.__PAD = min((max(len(ID) for ID in records.keys()) + 2), 35)

        included = self.get_record_ids_for_synthesis(records)
        if 0 == len(included):
            self.REVIEW_MANAGER.report_logger.info(
                "No records included yet (use colrev_core screen)"
            )
            self.REVIEW_MANAGER.logger.info(
                "No records included yet (use colrev_core screen)"
            )

        else:
            for DATA_FORMAT in data_endpoints:
                if "TEI" == DATA_FORMAT.endpoint:
                    records = self.update_tei(records, included)
                    self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records)
                    self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
                if "MANUSCRIPT" == DATA_FORMAT.endpoint:
                    records = self.update_manuscript(records, included)
                    self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
                        self.REVIEW_MANAGER.paths["PAPER_RELATIVE"]
                    )
                if "STRUCTURED" == DATA_FORMAT.endpoint:
                    records = self.update_structured_data(records, included)
                    self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
                        self.REVIEW_MANAGER.paths["DATA_RELATIVE"]
                    )

            self.update_synthesized_status()

            if "y" == input("Create commit (y/n)?"):
                self.REVIEW_MANAGER.create_commit(
                    "Data and synthesis", manual_author=True, saved_args=saved_args
                )

        return

    def check_new_record_source_tag(self) -> None:
        PAPER = self.REVIEW_MANAGER.paths["PAPER"]
        with open(PAPER) as f:
            for line in f:
                if self.NEW_RECORD_SOURCE_TAG in line:
                    return
        raise ManuscriptRecordSourceTagError(
            f"Did not find {self.NEW_RECORD_SOURCE_TAG} tag in {PAPER}"
        )

    def update_synthesized_status(self) -> typing.Dict:
        from colrev_core.process import CheckProcess

        CHECK_PROCESS = CheckProcess(self.REVIEW_MANAGER)
        records = CHECK_PROCESS.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        PAPER = self.REVIEW_MANAGER.paths["PAPER"]
        DATA = self.REVIEW_MANAGER.paths["DATA"]

        synthesized_in_manuscript = self.get_synthesized_ids(records, PAPER)
        structured_data_extracted = self.get_structured_data_extracted(records, DATA)

        DATA_FORMATS = self.REVIEW_MANAGER.settings.data.data_format
        for ID, record in records.items():
            if (
                "MANUSCRIPT" in [e.endpoint for e in DATA_FORMATS]
                and ID not in synthesized_in_manuscript
            ):
                continue
            if (
                "STRUCTURED" in [e.endpoint for e in DATA_FORMATS]
                and ID not in structured_data_extracted
            ):
                continue

            record.update(colrev_status=RecordState.rev_synthesized)
            self.REVIEW_MANAGER.report_logger.info(
                f" {ID}".ljust(self.__PAD, " ") + "set colrev_status to synthesized"
            )
            self.REVIEW_MANAGER.logger.info(
                f" {ID}".ljust(self.__PAD, " ") + "set colrev_status to synthesized"
            )

        CHECK_PROCESS.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records)
        CHECK_PROCESS.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return records

    def retrieve_package_file(self, template_file: Path, target: Path) -> None:
        filedata = pkgutil.get_data(__name__, str(template_file))
        if filedata:
            with open(target, "w") as file:
                file.write(filedata.decode("utf-8"))
        return

    def __prep_references(self, records) -> pd.DataFrame:
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

    def __prep_observations(
        self, references: dict, records: typing.Dict
    ) -> pd.DataFrame:

        included_papers = [
            ID
            for ID, record in records.items()
            if record["colrev_status"]
            in [RecordState.rev_synthesized, RecordState.rev_included]
        ]
        observations = references[references["ID"].isin(included_papers)].copy()
        observations.loc[:, "year"] = observations.loc[:, "year"].astype(int)
        missing_outlet = observations[observations["outlet"].isnull()]["ID"].tolist()
        if len(missing_outlet) > 0:
            self.REVIEW_MANAGER.logger.info(f"No outlet: {missing_outlet}")
        return observations

    def profile(self) -> None:

        self.REVIEW_MANAGER.logger.info("Create sample profile")

        # RED = "\033[91m"
        # END = "\033[0m"
        # if not status.get_completeness_condition():
        #     self.REVIEW_MANAGER.logger.warning(
        #  f"{RED}Sample not completely processed!{END}")

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        output_dir = self.REVIEW_MANAGER.path / Path("output")
        output_dir.mkdir(exist_ok=True)

        references = self.__prep_references(records.values())
        observations = self.__prep_observations(references, records)

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
