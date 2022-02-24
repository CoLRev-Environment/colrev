#! /usr/bin/env python
import json
import os
import shutil
import typing
from pathlib import Path

import imagehash
import requests
from p_tqdm import p_map
from pdf2image import convert_from_path
from pdfminer.high_level import extract_text

from colrev_core import grobid_client
from colrev_core import utils
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.process import RecordState
from colrev_core.tei import TEI


class PDF_Retrieval(Process):
    def __init__(
        self,
        REVIEW_MANAGER,
        copy_to_repo: bool = False,
        rename: bool = False,
        notify_state_transition_process: bool = True,
    ):

        super().__init__(
            REVIEW_MANAGER,
            ProcessType.pdf_get,
            fun=self.main,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.copy_to_repo = copy_to_repo
        self.rename = rename

        self.EMAIL = self.REVIEW_MANAGER.config["EMAIL"]
        self.CPUS = self.REVIEW_MANAGER.config["CPUS"]

        self.PDF_DIRECTORY = self.REVIEW_MANAGER.paths["PDF_DIRECTORY"]
        self.PDF_DIRECTORY.mkdir(exist_ok=True)

    def __copy_pdfs_to_repo(self) -> None:
        self.REVIEW_MANAGER.logger.info("Copy PDFs to dir")
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()

        for record in records:
            if "file" in record:
                fpath = Path(record["file"]).resolve()
                if fpath.is_file() and not str(
                    self.REVIEW_MANAGER.paths["REPO_DIR"]
                ) in str(fpath):
                    new_fpath = self.REVIEW_MANAGER.paths["PDF_DIRECTORY"] / Path(
                        record["ID"] + ".pdf"
                    )
                    if new_fpath.is_file():
                        self.REVIEW_MANAGER.logger.warning(
                            f'PDF cannot be copied - already exits ({record["ID"]})'
                        )
                        continue
                    shutil.copyfile(fpath, new_fpath)
                    record["file"] = str(
                        self.REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"]
                        / Path(record["ID"] + ".pdf")
                    )
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        return

    def __unpaywall(self, doi: str, retry: int = 0, pdfonly: bool = True) -> str:

        url = "https://api.unpaywall.org/v2/{doi}"

        r = requests.get(url, params={"email": self.EMAIL})

        if r.status_code == 404:
            return "NA"

        if r.status_code == 500:
            if retry < 3:
                return self.__unpaywall(doi, retry + 1)
            else:
                return "NA"

        best_loc = None
        try:
            best_loc = r.json()["best_oa_location"]
        except json.decoder.JSONDecodeError:
            return "NA"
        except KeyError:
            return "NA"

        if not r.json()["is_oa"] or best_loc is None:
            return "NA"

        if best_loc["url_for_pdf"] is None and pdfonly is True:
            return "NA"
        else:
            return best_loc["url_for_pdf"]

    def __is_pdf(self, path_to_file: str) -> bool:
        try:
            extract_text(path_to_file)
            return True
        except:  # noqa E722
            return False

    def __get_pdf_from_unpaywall(self, record: dict) -> dict:

        if "doi" not in record:
            return record

        pdf_filepath = self.REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"] / Path(
            f"{record['ID']}.pdf"
        )
        url = self.__unpaywall(record["doi"])
        if "NA" != url:
            if "Invalid/unknown DOI" not in url:
                res = requests.get(
                    url,
                    headers={
                        "User-Agent": "Chrome/51.0.2704.103",
                        "referer": "https://www.doi.org",
                    },
                )
                if 200 == res.status_code:
                    with open(pdf_filepath, "wb") as f:
                        f.write(res.content)
                    if self.__is_pdf(pdf_filepath):
                        self.REVIEW_MANAGER.report_logger.info(
                            "Retrieved pdf (unpaywall):" f" {pdf_filepath.name}"
                        )
                        self.REVIEW_MANAGER.logger.info(
                            "Retrieved pdf (unpaywall):" f" {pdf_filepath.name}"
                        )
                        record.update(file=str(pdf_filepath))
                        record.update(status=RecordState.rev_prescreen_included)
                    else:
                        os.remove(pdf_filepath)
                else:
                    self.REVIEW_MANAGER.logger.info(
                        "Unpaywall retrieval error " f"{res.status_code}/{url}"
                    )
        return record

    def link_pdf(self, record: dict) -> dict:

        PDF_DIRECTORY_RELATIVE = self.REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"]
        pdf_filepath = PDF_DIRECTORY_RELATIVE / Path(f"{record['ID']}.pdf")
        if pdf_filepath.is_file() and str(pdf_filepath) != record.get("file", "NA"):
            record.update(file=str(pdf_filepath))

        return record

    def __get_pdf_from_local_index(self, record: dict) -> dict:
        from colrev_core.environment import LocalIndex, RecordNotInIndexException

        LOCAL_INDEX = LocalIndex(self.REVIEW_MANAGER)
        try:
            retrieved_record = LOCAL_INDEX.retrieve_record_from_index(record)
            # pp.pprint(retrieved_record)
        except RecordNotInIndexException:
            pass
            return record

        if "file" in retrieved_record:
            record["file"] = retrieved_record["file"]

        return record

    def retrieve_pdf(self, item: dict) -> dict:
        record = item["record"]

        if str(RecordState.rev_prescreen_included) != str(record["status"]):
            return record

        retrieval_scripts: typing.List[typing.Dict[str, typing.Any]] = [
            {"script": self.__get_pdf_from_local_index},
            {"script": self.__get_pdf_from_unpaywall},
            {"script": self.link_pdf},
        ]

        for retrieval_script in retrieval_scripts:
            self.REVIEW_MANAGER.report_logger.info(
                f'{retrieval_script["script"].__name__}({record["ID"]}) called'
            )

            record = retrieval_script["script"](record)
            if "file" in record:
                self.REVIEW_MANAGER.report_logger.info(
                    f'{retrieval_script["script"].__name__}'
                    f'({record["ID"]}): retrieved {record["file"]}'
                )
                record.update(status=RecordState.pdf_imported)
            else:
                record.update(status=RecordState.pdf_needs_manual_retrieval)

        return record

    def get_pdf_hash(self, path: Path) -> str:
        return str(
            imagehash.average_hash(
                convert_from_path(path, first_page=0, last_page=1)[0],
                hash_size=32,
            )
        )

    def relink_files(self, ids_with_files_to_relink: typing.List[str]) -> None:
        from tqdm import tqdm

        self.REVIEW_MANAGER.logger.info(
            "Checking PDFs in same directory and reassigning "
            "when pdf_hash is identical"
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()
        for record in records:
            if record["ID"] in ids_with_files_to_relink:
                self.REVIEW_MANAGER.logger.info(record["ID"])
                pdf_path = Path(record["file"]).parent
                for pdf_candidate in tqdm(list(pdf_path.glob("**/*.pdf"))):
                    if record["pdf_hash"] == self.get_pdf_hash(pdf_candidate):
                        record["file"] = str(pdf_candidate)
                        self.REVIEW_MANAGER.logger.info(
                            f"Found and linked PDF: {pdf_candidate}"
                        )
                        break
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return

    def check_existing_unlinked_pdfs(
        self,
        records: typing.List[dict],
    ) -> typing.List[dict]:

        self.REVIEW_MANAGER.report_logger.info(
            "Starting GROBID service to extract metadata from PDFs"
        )
        self.REVIEW_MANAGER.logger.info(
            "Starting GROBID service to extract metadata from PDFs"
        )
        grobid_client.start_grobid()

        IDs = [x["ID"] for x in records]
        linked_pdfs = [Path(x["file"]) for x in records if "file" in x]

        pdf_files = Path(self.REVIEW_MANAGER.paths["PDF_DIRECTORY"]).glob("*.pdf")
        unlinked_pdfs = [x for x in pdf_files if x not in linked_pdfs]

        for file in unlinked_pdfs:
            if file.stem not in IDs:

                TEI_INSTANCE = TEI(self.REVIEW_MANAGER, pdf_path=file)
                pdf_record = TEI_INSTANCE.get_metadata()

                if "error" in pdf_record:
                    continue

                max_similarity = 0.0
                max_sim_record = None
                for record in records:
                    sim = utils.get_record_similarity(pdf_record, record.copy())
                    if sim > max_similarity:
                        max_similarity = sim
                        max_sim_record = record
                if max_sim_record:
                    if max_similarity > 0.5:
                        if RecordState.pdf_prepared == max_sim_record["status"]:
                            continue

                        max_sim_record.update(file=str(file))
                        max_sim_record.update(status=RecordState.pdf_imported)

                        self.REVIEW_MANAGER.report_logger.info(
                            "linked unlinked pdf:" f" {file.name}"
                        )
                        self.REVIEW_MANAGER.logger.info(
                            "linked unlinked pdf:" f" {file.name}"
                        )
                        # max_sim_record = \
                        #     pdf_prep.validate_pdf_metadata(max_sim_record)
                        # status = max_sim_record['status']
                        # if RecordState.pdf_needs_manual_preparation == status:
                        #     # revert?

        return records

    def __rename_pdfs(self, records: typing.List[dict]) -> typing.List[dict]:
        self.REVIEW_MANAGER.logger.info("RENAME PDFs")
        for record in records:
            if "file" in record and record["status"] == RecordState.pdf_imported:
                file = Path(record["file"])
                new_filename = self.REVIEW_MANAGER.paths[
                    "PDF_DIRECTORY_RELATIVE"
                ] / Path(f"{record['ID']}.pdf")
                try:
                    file.rename(new_filename)
                    record["file"] = str(new_filename)
                    self.REVIEW_MANAGER.logger.info(
                        f"rename {file.name} > {new_filename.name}"
                    )
                except FileNotFoundError:
                    self.REVIEW_MANAGER.logger.error(
                        f"Could not rename {record['ID']} - FileNotFoundError"
                    )
                    pass

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return records

    def __get_data(self) -> dict:
        record_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
        nr_tasks = len(
            [
                x
                for x in record_state_list
                if str(RecordState.rev_prescreen_included) == x[1]
            ]
        )

        PAD = min((max(len(x[0]) for x in record_state_list) + 2), 35)
        items = self.REVIEW_MANAGER.REVIEW_DATASET.read_next_record(
            conditions=[{"status": RecordState.rev_prescreen_included}],
        )

        prep_data = {
            "nr_tasks": nr_tasks,
            "PAD": PAD,
            "items": items,
        }
        self.REVIEW_MANAGER.logger.debug(self.REVIEW_MANAGER.pp.pformat(prep_data))
        return prep_data

    def __batch(self, items: typing.List[typing.Dict]):
        n = self.REVIEW_MANAGER.config["BATCH_SIZE"]
        batch = []
        for item in items:
            batch.append(
                {
                    "record": item,
                }
            )
            if len(batch) == n:
                yield batch
                batch = []
        yield batch

    def __set_status_if_file_linked(
        self, records: typing.List[dict]
    ) -> typing.List[dict]:

        for record in records:
            if record["status"] == RecordState.rev_prescreen_included:
                if "file" in record:
                    if any(
                        Path(fpath).is_file() for fpath in record["file"].split(";")
                    ):
                        record["status"] = RecordState.pdf_imported
                        self.REVIEW_MANAGER.logger.info(
                            f'Set status to pdf_imported for {record["ID"]}'
                        )
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return records

    def main(self, copy_to_repo: bool, rename: bool) -> None:

        saved_args = locals()

        print("TODO: download if there is a fulltext link in the record")

        self.REVIEW_MANAGER.report_logger.info("Retrieve PDFs")
        self.REVIEW_MANAGER.logger.info("Retrieve PDFs")

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()
        records = self.__set_status_if_file_linked(records)
        records = self.check_existing_unlinked_pdfs(records)

        pdf_get_data = self.__get_data()
        self.REVIEW_MANAGER.logger.debug(
            f"pdf_get_data: {self.REVIEW_MANAGER.pp.pformat(pdf_get_data)}"
        )

        self.REVIEW_MANAGER.logger.debug(
            self.REVIEW_MANAGER.pp.pformat(pdf_get_data["items"])
        )

        i = 1
        for retrieval_batch in self.__batch(pdf_get_data["items"]):

            print(f"Batch {i}")
            i += 1

            retrieval_batch = p_map(self.retrieve_pdf, retrieval_batch)

            self.REVIEW_MANAGER.REVIEW_DATASET.save_record_list_by_ID(retrieval_batch)

            # Multiprocessing mixes logs of different records.
            # For better readability:
            self.REVIEW_MANAGER.reorder_log([x["ID"] for x in retrieval_batch])

            if copy_to_repo:
                self.__copy_pdfs_to_repo()

            # Note: rename should be after copy.
            if rename:
                records = self.__rename_pdfs(records)

            self.REVIEW_MANAGER.create_commit("Retrieve PDFs", saved_args=saved_args)

        if i == 1:
            self.REVIEW_MANAGER.logger.info("No additional pdfs to retrieve")

        return

    def run(self):
        self.REVIEW_MANAGER.run_process(self, self.copy_to_repo, self.rename)


if __name__ == "__main__":
    pass
