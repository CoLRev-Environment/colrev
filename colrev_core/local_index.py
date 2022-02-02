#! /usr/bin/env python
import binascii
import hashlib
import logging
import os
import pprint
import re
import typing
import unicodedata
from pathlib import Path

import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from nameparser import HumanName

from colrev_core.review_manager import Process
from colrev_core.review_manager import ProcessType
from colrev_core.review_manager import RecordState
from colrev_core.review_manager import ReviewManager

pp = pprint.PrettyPrinter(indent=4, width=140)
logger = logging.getLogger("colrev_core")
logger.setLevel(logging.INFO)


class LocalIndex:

    global_keys = ["ID", "doi", "dblp_key", "pdf_hash", "file"]

    def __init__(self):
        self.local_index_path = Path.home().joinpath(".colrev")
        self.rind_path = self.local_index_path / Path(".record_index/")
        self.gind_path = self.local_index_path / Path(".gid_index/")
        self.dind_path = self.local_index_path / Path(".d_index/")

    class RecordNotInIndexException(Exception):
        def __init__(self, id: str = None):
            if id is not None:
                self.message = f"Record not in index ({id})"
            else:
                self.message = "Record not in index"
            super().__init__(self.message)

    def __robust_append(self, string_to_hash: str, to_append: str) -> str:
        to_append = to_append.replace("\n", " ").rstrip().lstrip().replace("–", " ")
        to_append = re.sub(r"[\.\:“”’]", "", to_append)
        to_append = re.sub(r"\s+", " ", to_append)
        to_append = to_append.lower()
        string_to_hash = string_to_hash + "|" + to_append
        return string_to_hash

    def __rmdiacritics(self, char):
        """
        Return the base character of char, by "removing" any
        diacritics like accents or curls and strokes and the like.
        """
        desc = unicodedata.name(char)
        cutoff = desc.find(" WITH ")
        if cutoff != -1:
            desc = desc[:cutoff]
            try:
                char = unicodedata.lookup(desc)
            except KeyError:
                pass  # removing "WITH ..." produced an invalid name
        return char

    def __remove_accents(self, input_str: str) -> str:
        nfkd_form = unicodedata.normalize("NFKD", input_str)
        wo_ac = [
            self.__rmdiacritics(c) for c in nfkd_form if not unicodedata.combining(c)
        ]
        wo_ac_str = "".join(wo_ac)
        return wo_ac_str

    def __get_container_title(self, record: dict) -> str:

        # if multiple container titles are available, they are concatenated
        container_title = ""

        # school as the container title for theses
        if "school" in record:
            container_title += record["school"]
        # for technical reports
        if "institution" in record:
            container_title += record["institution"]
        if "series" in record:
            container_title += record["series"]
        if "booktitle" in record:
            container_title += record["booktitle"]
        if "journal" in record:
            container_title += record["journal"]

        if "url" in record and not any(
            x in record for x in ["journal", "series", "booktitle"]
        ):
            container_title += record["url"]

        return container_title

    def __format_author_field(self, input_string: str) -> str:
        input_string = input_string.replace("\n", " ")
        names = (
            self.__remove_accents(input_string).replace("; ", " and ").split(" and ")
        )
        author_list = []
        for name in names:
            parsed_name = HumanName(name)
            # Note: do not set this as a global constant to preserve consistent
            # creation of hash_ids
            parsed_name.string_format = "{last}, {first} {middle}"
            if len(parsed_name.middle) > 0:
                parsed_name.middle = parsed_name.middle[:1]
            if len(parsed_name.first) > 0:
                parsed_name.first = parsed_name.first[:1]
            if len(parsed_name.nickname) > 0:
                parsed_name.nickname = ""

            if "," not in str(parsed_name):
                author_list.append(str(parsed_name))
                continue
            author_list.append(str(parsed_name))
        return " and ".join(author_list)

    def __get_string_representation(self, record: dict) -> str:

        # TODO raise no-prepared error if status =! md_prepared
        # TODO distinguish ENTRYTYPES?

        srep = ""

        # Including the version of the hash_function prevents cases
        # in which almost all hash_ids are identical (and very few hash_ids change)
        # when updatingthe hash function
        # (this may look like an anomaly and be hard to identify)
        srep = "v0.1"
        author = record.get("author", "")
        srep = self.__robust_append(srep, record["ENTRYTYPE"].lower())
        srep = self.__robust_append(srep, self.__format_author_field(author))
        srep = self.__robust_append(srep, record.get("year", ""))
        srep = self.__robust_append(srep, record.get("title", ""))
        srep = self.__robust_append(srep, self.__get_container_title(record))
        srep = self.__robust_append(srep, record.get("volume", ""))
        srep = self.__robust_append(srep, record.get("number", ""))
        pages = record.get("pages", "")
        srep = self.__robust_append(srep, pages)

        return srep

    def __get_record_hash(self, record: dict) -> str:
        string_to_hash = self.__get_string_representation(record)
        return hashlib.sha256(string_to_hash.encode("utf-8")).hexdigest()

    def __increment_hash(self, hash: str) -> str:

        plaintext = binascii.unhexlify(hash)
        # also, we'll want to know our length later on
        plaintext_length = len(plaintext)
        plaintext_number = int.from_bytes(plaintext, "big")

        # recommendation: do not increment by 1
        # TODO: we have to use modulo in the following line...
        # TBD: what's the max(plaintext)?
        plaintext_number += 10
        new_plaintext = plaintext_number.to_bytes(plaintext_length, "big")
        new_hex = binascii.hexlify(new_plaintext)
        # print(new_hex.decode("utf-8"))

        return new_hex.decode("utf-8")

    def __get_record_index_file(self, hash: str) -> Path:
        return self.local_index_path / Path(f".record_index/{hash[:2]}/{hash[2:]}.bib")

    def __get_global_id_index_file(self, hash: str) -> Path:
        return self.local_index_path / Path(f".gid_index/{hash[:2]}/{hash[2:]}.txt")

    def __get_d_index_file(self, hash: str) -> Path:
        return self.local_index_path / Path(f".d_index/{hash[:2]}/{hash[2:]}.txt")

    def __store_record(self, record: dict, index_fpath: Path) -> None:
        index_fpath.parents[0].mkdir(exist_ok=True, parents=True)

        # Casting to string (in particular the RecordState Enum)
        record = {k: str(v) for k, v in record.items()}

        index_record_db = BibDatabase()
        index_record_db.entries = [record]
        bibtex_str = bibtexparser.dumps(index_record_db)
        with open(index_fpath, "w") as out:
            out.write(bibtex_str)
        return

    def __load_local_registry(self) -> list:
        from yaml import safe_load
        import pandas as pd

        local_colrev_config = Path.home().joinpath(".colrev")
        local_registry = "registry.yaml"
        local_registry_list: typing.List[dict] = []
        local_registry_path = local_colrev_config.joinpath(local_registry)
        if os.path.exists(local_registry_path):
            with open(local_registry_path) as f:
                local_registry_df = pd.json_normalize(safe_load(f))
                local_registry_list = local_registry_df.to_dict("records")
        return local_registry_list

    def __retrieve_from_index(self, hash: str) -> dict:
        record_fp = self.__get_record_index_file(hash)
        with open(record_fp) as target_db:
            bib_db = BibTexParser(
                customization=convert_to_unicode,
                ignore_nonstandard_types=False,
                common_strings=True,
            ).parse_file(target_db, partial=True)
            record = bib_db.entries[0]
        return record

    def __retrieve_from_gid_index_based_on_hash(self, hash: str) -> list:
        gid_fpath = self.__get_global_id_index_file(hash)
        res = gid_fpath.read_text().splitlines()
        return res

    def __retrieve_from_d_index_based_on_hash(self, hash: str) -> list:
        d_fpath = self.__get_d_index_file(hash)
        return d_fpath.read_text().splitlines()

    def __record_index(self, record: dict) -> None:
        hash = self.__get_record_hash(record)
        index_fpath = self.__get_record_index_file(hash)
        string_representation = self.__get_string_representation(record)
        record["hash_string_representation"] = string_representation

        while True:
            if not index_fpath.is_file():
                self.__store_record(record, index_fpath)
                break
            else:
                saved_record = self.__retrieve_from_index(hash)
                if string_representation == saved_record.get(
                    "hash_string_representation", ""
                ):
                    # ok - no collision, update the record
                    # Note : do not update (the record from the first repository
                    # should take precedence - reset the index to update)
                    # store_record(record, index_fpath)
                    break
                else:
                    # to handle the collision:
                    print(f"Collision: {hash}")
                    hash = self.__increment_hash(hash)
                    index_fpath = self.__get_record_index_file(hash)
        return

    def __gid_index(self, record: dict) -> None:

        for global_key in self.global_keys:
            if global_key in record:
                # print(f"{global_key}={record[global_key]}")

                if "file" == global_key:
                    if not Path(record[global_key]).is_file():
                        if Path(
                            record["source_url"] + "/" + record[global_key]
                        ).is_file():
                            record[global_key] = (
                                record["source_url"] + "/" + record[global_key]
                            )
                        else:
                            continue

                gid = f"{global_key}={record[global_key]}"
                hash = hashlib.sha256(gid.encode("utf-8")).hexdigest()
                index_fpath = self.__get_global_id_index_file(hash)
                while True:
                    if not index_fpath.is_file():
                        index_fpath.parents[0].mkdir(exist_ok=True, parents=True)
                        index_fpath.write_text(
                            gid + "\n" + self.__get_string_representation(record)
                        )
                        break
                    else:
                        (
                            saved_gid,
                            string_representation,
                        ) = self.__retrieve_from_gid_index_based_on_hash(hash)
                        if saved_gid == gid:
                            # ok - no collision, update the record
                            # Note : do not update (the record from the first repository
                            #  should take precedence - reset the index to update)
                            break
                        else:
                            # to handle the collision:
                            print(f"Collision: {hash}")
                            hash = self.__increment_hash(hash)
                            index_fpath = self.__get_global_id_index_file(hash)

        return

    def __did_index(self, record: dict) -> None:
        from colrev_core import prep

        # pp.pprint(record)

        # 1. create representations
        orig_record_string = self.__get_string_representation(record)

        required_fields = [
            k
            for k, v in record.items()
            if k
            in [
                "author",
                "title",
                "year",
                "journal",
                "volume",
                "number",
                "pages",
                "booktitle",
            ]
        ]

        unprepared_records = []
        for origin in record["origin"].split(";"):
            origin_file_name, origin_id = origin.split("/")
            orig_file = Path(f"{record['source_url']}/search/{origin_file_name}")

            # TODO: this can be done efficiently...
            if orig_file.is_file():
                with open(orig_file) as target_db:
                    bib_db = BibTexParser(
                        customization=convert_to_unicode,
                        ignore_nonstandard_types=False,
                        common_strings=True,
                    ).parse_file(target_db, partial=True)

                    records = bib_db.entries
                    unprepared_record = [
                        r for r in records if r["ID"] == origin_id
                    ].pop()
            unprepared_records.append(unprepared_record)

        if "doi" in record:
            unprepared_record = prep.get_md_from_doi(record)
            unprepared_records.append(unprepared_record)

        if "dblp_key" in record:
            unprepared_record = prep.get_md_from_dblp(record)
            unprepared_records.append(unprepared_record)

        non_identical_representations = []
        for unprepared_record in unprepared_records:
            if not all(
                required_field in unprepared_record
                for required_field in required_fields
            ):
                continue
            unprpepped_record_string = self.__get_string_representation(
                unprepared_record
            )
            if orig_record_string != unprpepped_record_string:
                non_identical_representations.append(unprpepped_record_string)

        # 2. add representations to index
        non_identical_representations = list(set(non_identical_representations))
        if len(non_identical_representations) > 0:

            for non_identical_representation in non_identical_representations:
                hash = hashlib.sha256(
                    non_identical_representation.encode("utf-8")
                ).hexdigest()
                index_fpath = self.__get_d_index_file(hash)
                while True:
                    if not index_fpath.is_file():
                        index_fpath.parents[0].mkdir(exist_ok=True, parents=True)
                        index_fpath.write_text(
                            non_identical_representation + "\n" + orig_record_string
                        )
                        break
                    else:
                        (
                            saved_dstring,
                            associated_original,
                        ) = self.__retrieve_from_d_index_based_on_hash(hash)
                        if saved_dstring == non_identical_representation:
                            # ok - no collision
                            break
                        else:
                            # to handle the collision:
                            print(f"Collision: {hash}")
                            hash = self.__increment_hash(hash)
                            index_fpath = self.__get_d_index_file(hash)

        return

    def __retrieve_record_from_d_index(self, record: dict) -> dict:

        string_representation_record = self.__get_string_representation(record)
        hash = self.__get_record_hash(record)
        associated_original = ""
        while True:
            (
                saved_dstring,
                associated_original,
            ) = self.__retrieve_from_d_index_based_on_hash(hash)
            if saved_dstring == string_representation_record:
                break
            hash = self.__increment_hash(hash)
        retrieved_record = self.__retrieve_from_index(
            hashlib.sha256(associated_original.encode("utf-8")).hexdigest()
        )
        return self.__prep_record_for_return(retrieved_record)

    def __retrieve_from_gid_index(self, record: dict) -> dict:
        """Convenience function to retrieve a record based on a global ID"""

        string_representation = ""
        for k, v in record.items():
            if k not in self.global_keys:
                continue

            gid = f"{k}={v}"
            hash = hashlib.sha256(gid.encode("utf-8")).hexdigest()
            while True:
                (
                    saved_gid,
                    string_representation,
                ) = self.__retrieve_from_gid_index_based_on_hash(hash)
                if saved_gid == gid:
                    # ok - no collision,
                    break
                else:
                    # to handle the collision:
                    hash = self.__increment_hash(hash)

        indexed_record = self.__retrieve_from_index(
            hashlib.sha256(string_representation.encode("utf-8")).hexdigest()
        )
        return indexed_record

    def __prep_record_for_return(self, record: dict) -> dict:
        from colrev_core.review_manager import RecordState

        if "hash_string_representation" in record:
            del record["hash_string_representation"]
        # del retrieved_record['source_url']
        record["status"] = RecordState.md_prepared
        return record

    def index_records(self) -> None:
        from tqdm import tqdm
        import shutil

        logger.info("Called LocalIndex")

        logger.info("Reset record_index, gid_index, d_index")
        if self.rind_path.is_dir():
            shutil.rmtree(self.rind_path)
        if self.gind_path.is_dir():
            shutil.rmtree(self.gind_path)
        if self.dind_path.is_dir():
            shutil.rmtree(self.dind_path)

        local_registry = self.__load_local_registry()
        for source_url in [x["source_url"] for x in local_registry]:
            os.chdir(source_url)
            logger.info(f"Index records from {source_url}")

            REVIEW_MANAGER = ReviewManager()
            REVIEW_MANAGER.notify(Process(ProcessType.format))

            records = REVIEW_MANAGER.load_records()
            records = [
                r
                for r in records
                if r["status"]
                not in [
                    RecordState.md_retrieved,
                    RecordState.md_imported,
                    RecordState.md_prepared,
                    RecordState.md_needs_manual_preparation,
                ]
            ]

            for record in tqdm(records):
                record["source_url"] = source_url
                if "excl_criteria" in record:
                    del record["excl_criteria"]

                self.__record_index(record)
                self.__gid_index(record)
                self.__did_index(record)

        return

    def retrieve_record_from_index(self, record: dict) -> dict:
        """
        Convenience function to retrieve the indexed record metadata
        based on another record
        """

        retrieved_record: typing.Dict = dict()

        # 1. Try the global-id index
        if not retrieved_record:
            try:
                retrieved_record = self.__retrieve_from_gid_index(record)
            except FileNotFoundError:
                pass

        if retrieved_record:
            print("Retrieved from g_id index")
            return self.__prep_record_for_return(retrieved_record)

        # 2. Try the record index
        string_representation_record = self.__get_string_representation(record)
        hash = self.__get_record_hash(record)
        while True:
            try:
                retrieved_record = self.__retrieve_from_index(hash)
                string_representation_retrieved_record = (
                    self.__get_string_representation(retrieved_record)
                )
                if (
                    string_representation_retrieved_record
                    == string_representation_record
                ):
                    break
                hash = self.__increment_hash(hash)
            except FileNotFoundError:
                pass
                break

        if retrieved_record:
            print("Retrieved from record index")
            return self.__prep_record_for_return(retrieved_record)

        # 3. Try the duplicate representation index
        if not retrieved_record:
            try:
                retrieved_record = self.__retrieve_record_from_d_index(record)
            except FileNotFoundError:
                pass

        if not retrieved_record:
            raise self.RecordNotInIndexException(record.get("ID", "no-key"))

        print("Retrieved from d index")
        return self.__prep_record_for_return(retrieved_record)

    def is_duplicate(self, record1: dict, record2: dict) -> str:
        """Convenience function to check whether two records are a duplicate"""

        # Note : the retrieve_record_from_index also checks the d_index, i.e.,
        # if the IDs and source_urls are identical,
        # record1 and record2 have been mapped to the same record
        # if record1 and record2 in index (and same source_url): return 'no'
        try:
            r1_index = self.retrieve_record_from_index(record1)
            r2_index = self.retrieve_record_from_index(record2)
            if r1_index["source_url"] == r2_index["source_url"]:
                if r1_index["ID"] == r2_index["ID"]:
                    return "yes"
                else:
                    return "no"
        except self.RecordNotInIndexException:
            pass
            return "unknown"

        return "unknown"

    def analyze(self, threshold: float = 0.95) -> None:
        from thefuzz import fuzz
        import pandas as pd

        changes = []
        for d_file in self.dind_path.rglob("*.txt"):
            str1, str2 = d_file.read_text().split("\n")
            similarity = fuzz.ratio(str1, str2) / 100
            if similarity < threshold:
                changes.append(
                    {"similarity": similarity, "str": str1, "fname": str(d_file)}
                )
                changes.append(
                    {"similarity": similarity, "str": str2, "fname": str(d_file)}
                )

        df = pd.DataFrame(changes)
        # df = df.groupby('fname').apply(pd.DataFrame.sort_values, 'similarity')
        # grouped_df = df.groupby('fname')
        # df['similarity'] = grouped_df['similarity'].transform(max)
        # df = df.sort_values('similarity')
        df.to_csv("changes.csv", index=False)
        print("Exported changes.csv")

        return


def main() -> None:


    # LOCAL_INDEX = LocalIndex()

    # To Test retrieval of record:
    # record = {
    #     "ENTRYTYPE": "article",
    #     "author" : "Addis, T. R.",
    #     "journal" : "Journal of Information Technology",
    #     "number" : "1",
    #     "pages" : "38--45",
    #     "title" : "Knowledge for the New Generation Computers",
    #     "volume" : "1",
    #     "year" : "1986"
    # }
    # record = LOCAL_INDEX.retrieve_record_from_index(record)
    # pp.pprint(record)

    # To Test retrieval of global ID
    # record = {
    #     'doi' : '10.17705/1JAIS.00598',
    # }
    # record = LOCAL_INDEX.retrieve_record_from_index(record)
    # pp.pprint(record)

    # To test the duplicate convenience function:
    # record1 = {
    #     "ENTRYTYPE": "article",
    #     "author" : "Addis, T. R.",
    #     "journal" : "Journal of Information Technology",
    #     "number" : "1",
    #     "pages" : "38--45",
    #     "title" : "Knowledge for the New Generation Computers",
    #     "volume" : "1",
    #     "year" : "1986"
    # }
    # record2 = {
    #     "ENTRYTYPE": "article",
    #     "author" : "Majchrzak, Ann and Malhotra, Arvind",
    #     "journal" : "Information Systems Research",
    #     "number" : "4",
    #     "pages" : "685--703",
    #     "title" : "Effect of Knowledge-Sharing Trajectories on " + \
    #                   "Innovative Outcomes in Temporary Online Crowds",
    #     "volume" : "27",
    #     "year" : "2016"
    # }
    # record3 = {
    #     "ENTRYTYPE": "article",
    #     "author" : "Addis, T. R.",
    #     "journal" : "Journal of Technology",
    #     "number" : "1",
    #     "pages" : "38--45",
    #     "title" : "Knowledge for the New Generation Computers",
    #     "volume" : "1",
    #     "year" : "1986"
    # }
    # record3 = {
    #     "ENTRYTYPE": "article",
    #     "author" : "colquitt, j and zapata-phelan, c p",
    #     "journal" : "academy of management journal",
    #     "number" : "6",
    #     "pages" : "1281--1303",
    #     "title" : "trends in theory building and theory testing a " + \
    #           "five-decade study of theacademy of management journal",
    #     "volume" : "50",
    #     "year" : "2007"
    # }
    # record4 = {
    #     "ENTRYTYPE": "article",
    #     "author" : "colquitt, j and zapata-phelan, c p",
    #     "journal" : "academy of management journal",
    #     "number" : "6",
    #     "pages" : "1281--1303",
    #     "title" : "trends in theory building and theory testing a " + \
    #           "five-decade study of the academy of management journal",
    #     "volume" : "50",
    #     "year" : "2007"
    # }
    # print(LOCAL_INDEX.is_duplicate(record1, record2))
    # print(LOCAL_INDEX.is_duplicate(record1, record3))
    # print(LOCAL_INDEX.is_duplicate(record3, record4))

    # To test the duplicate representation function:
    # record3 = LOCAL_INDEX.retrieve_record_from_index(record3)
    # pp.pprint(record3)
    # record4 = LOCAL_INDEX.retrieve_record_from_index(record4)
    # pp.pprint(record4)

    return


if __name__ == "__main__":
    pass
