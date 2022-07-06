#! /usr/bin/env python
import typing
from pathlib import Path

import pandas as pd
import requests
from urllib3.exceptions import ProtocolError

from colrev_core.environment import AdapterManager
from colrev_core.environment import GrobidService
from colrev_core.environment import TEI_TimeoutException
from colrev_core.environment import TEIParser
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import RecordState


class Data(Process):
    """Class supporting structured and unstructured
    data extraction, analysis and synthesis"""

    __PAD = 0

    from colrev_core.built_in import data as built_in_data

    built_in_scripts: typing.Dict[str, typing.Dict[str, typing.Any]] = {
        "MANUSCRIPT": {
            "endpoint": built_in_data.ManuscriptEndpoint,
        },
        "STRUCTURED": {
            "endpoint": built_in_data.StructuredDataEndpoint,
        },
        "ENDNOTE": {
            "endpoint": built_in_data.EndnoteEndpoint,
        },
        "PRISMA": {
            "endpoint": built_in_data.PRISMAEndpoint,
        },
        "ZETTLR": {
            "endpoint": built_in_data.ZettlrEndpoint,
        },
    }

    def __init__(self, REVIEW_MANAGER, notify_state_transition_process=True):

        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            type=ProcessType.data,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.data_scripts: typing.Dict[
            str, typing.Dict[str, typing.Any]
        ] = AdapterManager.load_scripts(
            PROCESS=self,
            scripts=[s.endpoint for s in REVIEW_MANAGER.settings.data.data_format],
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
            self.REVIEW_MANAGER.create_commit(
                msg="Create TEIs", script_call="colrev data"
            )

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

        self.REVIEW_MANAGER.create_commit(msg="Enhance TEIs", script_call="colrev data")

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

        no_endpoints_registered = 0 == len(
            self.REVIEW_MANAGER.settings.data.data_format
        )

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        if 0 == len(records):
            return {
                "ask_to_commit": False,
                "no_endpoints_registered": no_endpoints_registered,
            }

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

            # if self.verbose:
            #     self.REVIEW_MANAGER.pp.pprint(synthesized_record_status_matrix)

            # TODO : include paper.md / data.csv as arguments of the data endpoint
            # not the review_manager? (but: the other scripts/checks may rely
            # on the review_manager/path variables....)

            for DATA_FORMAT in self.REVIEW_MANAGER.settings.data.data_format:

                if DATA_FORMAT.endpoint not in list(self.data_scripts.keys()):
                    if self.verbose:
                        print(f"Error: endpoint not available: {DATA_FORMAT}")
                    continue

                endpoint = self.data_scripts[DATA_FORMAT.endpoint]

                ENDPOINT = endpoint["endpoint"]
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

            # if self.verbose:
            #     self.REVIEW_MANAGER.pp.pprint(synthesized_record_status_matrix)

            CHECK_PROCESS.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(
                records=records
            )
            CHECK_PROCESS.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

            return {
                "ask_to_commit": True,
                "no_endpoints_registered": no_endpoints_registered,
            }
        return {
            "ask_to_commit": False,
            "no_endpoints_registered": no_endpoints_registered,
        }

    def setup_custom_script(self) -> None:
        import pkgutil

        filedata = pkgutil.get_data(__name__, "template/custom_data_script.py")
        if filedata:
            with open("custom_data_script.py", "w") as file:
                file.write(filedata.decode("utf-8"))

        self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(path="custom_data_script.py")

        NEW_DATA_ENDPOINT = {"endpoint": "custom_data_script", "config": {}}

        self.REVIEW_MANAGER.settings.data.data_format.append(NEW_DATA_ENDPOINT)
        self.REVIEW_MANAGER.save_settings()

        return


if __name__ == "__main__":
    pass
