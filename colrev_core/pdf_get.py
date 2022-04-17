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
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import RecordState
from colrev_core.tei import TEI


class PDF_Retrieval(Process):
    def __init__(
        self,
        REVIEW_MANAGER,
        notify_state_transition_process: bool = True,
    ):

        super().__init__(
            REVIEW_MANAGER,
            ProcessType.pdf_get,
            fun=self.main,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.EMAIL = self.REVIEW_MANAGER.config["EMAIL"]
        self.CPUS = self.REVIEW_MANAGER.config["CPUS"]

        self.PDF_DIRECTORY = self.REVIEW_MANAGER.paths["PDF_DIRECTORY"]
        self.PDF_DIRECTORY.mkdir(exist_ok=True)

    def copy_pdfs_to_repo(self) -> None:
        self.REVIEW_MANAGER.logger.info("Copy PDFs to dir")
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        for record in records.values():
            if "file" in record:
                fpath = Path(record["file"])
                if fpath.is_symlink():
                    new_fpath = fpath.absolute()
                    linked_file = fpath.resolve()
                    if linked_file.is_file():
                        fpath.unlink()
                        shutil.copyfile(linked_file, new_fpath)
                if new_fpath.is_file():
                    self.REVIEW_MANAGER.logger.warning(
                        f'No need to copy PDF - already exits ({record["ID"]})'
                    )

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
                        record.update(colrev_status=RecordState.rev_prescreen_included)
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

        LOCAL_INDEX = LocalIndex()
        try:
            retrieved_record = LOCAL_INDEX.retrieve(record, include_file=True)
            # self.REVIEW_MANAGER.pp.pprint(retrieved_record)
        except RecordNotInIndexException:
            pass
            return record

        if "file" in retrieved_record:
            record["file"] = retrieved_record["file"]
            self.REVIEW_MANAGER.REVIEW_DATASET.import_file(record)

        return record

    def retrieve_pdf(self, item: dict) -> dict:
        record = item["record"]

        if str(RecordState.rev_prescreen_included) != str(record["colrev_status"]):
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
                record.update(colrev_status=RecordState.pdf_imported)
            else:
                record.update(colrev_status=RecordState.pdf_needs_manual_retrieval)

        return record

    def get_colrev_pdf_id(self, path: Path) -> str:
        cpid1 = "cpid1:" + str(
            imagehash.average_hash(
                convert_from_path(path, first_page=1, last_page=1)[0],
                hash_size=32,
            )
        )
        return cpid1

    def relink_files(self) -> None:
        from bibtexparser.bparser import BibTexParser
        from bibtexparser.customization import convert_to_unicode
        import bibtexparser

        def relink_pdf_files(records):

            # Relink files in source file
            sources = self.REVIEW_MANAGER.REVIEW_DATASET.load_sources()
            feeds = [x for x in sources if "FEED" == x["search_type"]]
            feed_filename = ""
            feed_filepath = ""
            source_records = []
            for feed in feeds:
                if "pdfs_directory" == feed["search_parameters"][0]["endpoint"]:
                    feed_filepath = Path("search/" + feed["filename"])
                    if feed_filepath.is_file():
                        feed_filename = feed["filename"]
                        with open(Path("search/" + feed["filename"])) as target_db:
                            bib_db = BibTexParser(
                                customization=convert_to_unicode,
                                ignore_nonstandard_types=False,
                                common_strings=True,
                            ).parse_file(target_db, partial=True)

                        source_records = bib_db.entries

            self.REVIEW_MANAGER.logger.info("Calculate colrev_pdf_ids")
            pdf_candidates = {
                pdf_candidate.relative_to(
                    self.REVIEW_MANAGER.path
                ): self.get_colrev_pdf_id(pdf_candidate)
                for pdf_candidate in list(Path("pdfs").glob("**/*.pdf"))
            }

            for record in records.values():
                if "file" not in record:
                    continue

                # Note: we check the source_records based on the cpids
                # in the record because cpids are not stored in the source_record
                # (pdf hashes may change after import/preparation)
                source_rec = {}
                if feed_filename != "":
                    source_origin_l = [
                        o
                        for o in record["colrev_origin"].split(";")
                        if feed_filename in o
                    ]
                    if len(source_origin_l) == 1:
                        source_origin = source_origin_l[0]
                        source_origin = source_origin.replace(f"{feed_filename}/", "")
                        source_rec_l = [
                            s for s in source_records if s["ID"] == source_origin
                        ]
                        if len(source_rec_l) == 1:
                            source_rec = source_rec_l[0]

                if source_rec:
                    if (self.REVIEW_MANAGER.path / Path(record["file"])).is_file() and (
                        self.REVIEW_MANAGER.path / Path(source_rec["file"])
                    ).is_file():
                        continue
                else:
                    if (self.REVIEW_MANAGER.path / Path(record["file"])).is_file():
                        continue

                self.REVIEW_MANAGER.logger.info(record["ID"])

                for pdf_candidate, cpid in pdf_candidates.items():
                    if record.get("colrev_pdf_id", "") == cpid:
                        record["file"] = str(pdf_candidate)
                        source_rec["file"] = str(pdf_candidate)

                        self.REVIEW_MANAGER.logger.info(
                            f"Found and linked PDF: {pdf_candidate}"
                        )

                        break

            if len(source_records) > 0:
                bib_db.entries = source_records
                bibtex_str = bibtexparser.dumps(
                    bib_db, self.REVIEW_MANAGER.REVIEW_DATASET.get_bibtex_writer()
                )

                with open(feed_filepath, "w") as out:
                    out.write(bibtex_str)

            if feed_filepath != "":
                self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(str(feed_filepath))
            return records

        self.REVIEW_MANAGER.logger.info(
            "Checking PDFs in same directory to reassig when the cpid is identical"
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        records = relink_pdf_files(records)

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records)

        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        self.REVIEW_MANAGER.create_commit("Relink PDFs")

        return

    def check_existing_unlinked_pdfs(
        self,
        records: typing.Dict,
    ) -> typing.Dict:
        from glob import glob
        from colrev_core.record import Record

        linked_pdfs = [
            str(Path(x["file"]).resolve()) for x in records.values() if "file" in x
        ]

        pdf_files = glob(
            str(self.REVIEW_MANAGER.paths["PDF_DIRECTORY"]) + "/**.pdf", recursive=True
        )
        unlinked_pdfs = [Path(x) for x in pdf_files if x not in linked_pdfs]

        if len(unlinked_pdfs) == 0:
            return records

        self.REVIEW_MANAGER.report_logger.info(
            "Starting GROBID service to extract metadata from PDFs"
        )
        self.REVIEW_MANAGER.logger.info(
            "Starting GROBID service to extract metadata from PDFs"
        )
        grobid_client.start_grobid()
        for file in unlinked_pdfs:
            if file.stem not in records.keys():

                TEI_INSTANCE = TEI(pdf_path=file)
                pdf_record = TEI_INSTANCE.get_metadata()

                if "error" in pdf_record:
                    continue

                max_similarity = 0.0
                max_sim_record = None
                for record in records.values():
                    sim = Record.get_record_similarity(
                        Record(pdf_record), Record(record.copy())
                    )
                    if sim > max_similarity:
                        max_similarity = sim
                        max_sim_record = record
                if max_sim_record:
                    if max_similarity > 0.5:
                        if RecordState.pdf_prepared == max_sim_record["colrev_status"]:
                            continue

                        max_sim_record.update(file=str(file))
                        max_sim_record.update(colrev_status=RecordState.pdf_imported)

                        self.REVIEW_MANAGER.report_logger.info(
                            "linked unlinked pdf:" f" {file.name}"
                        )
                        self.REVIEW_MANAGER.logger.info(
                            "linked unlinked pdf:" f" {file.name}"
                        )
                        # max_sim_record = \
                        #     pdf_prep.validate_pdf_metadata(max_sim_record)
                        # colrev_status = max_sim_record['colrev_status']
                        # if RecordState.pdf_needs_manual_preparation == colrev_status:
                        #     # revert?

        return records

    def rename_pdfs(self) -> None:
        self.REVIEW_MANAGER.logger.info("Rename PDFs")

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        for record in records.values():
            if "file" not in record:
                continue

            file = Path(record["file"])
            new_filename = self.REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"] / Path(
                f"{record['ID']}.pdf"
            )
            if str(file) == str(new_filename):
                continue

            if file.is_file():
                file.rename(new_filename)
                record["file"] = str(new_filename)
                self.REVIEW_MANAGER.logger.info(f"rename {file.name} > {new_filename}")
            if file.is_symlink():
                os.rename(str(file), str(new_filename))
                record["file"] = str(new_filename)
                self.REVIEW_MANAGER.logger.info(f"rename {file.name} > {new_filename}")

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return

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
            conditions=[{"colrev_status": RecordState.rev_prescreen_included}],
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

    def __set_status_if_file_linked(self, records: typing.Dict) -> typing.Dict:

        for record in records.values():
            if record["colrev_status"] == RecordState.rev_prescreen_included:
                if "file" in record:
                    if any(
                        Path(fpath).is_file() for fpath in record["file"].split(";")
                    ):
                        record["colrev_status"] = RecordState.pdf_imported
                        self.REVIEW_MANAGER.logger.info(
                            f'Set colrev_status to pdf_imported for {record["ID"]}'
                        )
                    else:
                        print(
                            "Warning: record with file field but no existing PDF "
                            f'({record["ID"]}: {record["file"]}'
                        )
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return records

    def main(self) -> None:

        saved_args = locals()

        # TODO : download if there is a fulltext link in the record

        self.REVIEW_MANAGER.report_logger.info("Get PDFs")
        self.REVIEW_MANAGER.logger.info("Get PDFs")

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
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

            # Note: rename should be after copy.
            # Note : do not pass records as an argument.
            self.rename_pdfs()

            self.REVIEW_MANAGER.create_commit("Get PDFs", saved_args=saved_args)

        if i == 1:
            self.REVIEW_MANAGER.logger.info("No additional pdfs to retrieve")

        return


if __name__ == "__main__":
    pass
