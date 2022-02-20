#! /usr/bin/env python
import binascii
import hashlib
import os
import re
import typing
import unicodedata
from pathlib import Path

import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from nameparser import HumanName
from thefuzz import fuzz
from tqdm import tqdm

from colrev_core.process import CheckProcess
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.process import RecordState
from colrev_core.review_manager import ReviewManager


class LocalIndex(Process):

    global_keys = ["ID", "doi", "dblp_key", "pdf_hash", "file"]
    max_len_sha256 = 2 ** 256

    local_index_path = Path.home().joinpath(".colrev")
    rind_path = local_index_path / Path(".record_index/")
    gind_path = local_index_path / Path(".gid_index/")
    dind_path = local_index_path / Path(".d_index/")
    toc_path = local_index_path / Path(".toc_index/")
    jind_path = local_index_path / Path(".j_index/")
    wos_j_abbrev = local_index_path / Path(".wos_abbrev_table.csv")

    def __init__(self, REVIEW_MANAGER):
        from git.exc import NoSuchPathError
        from git.exc import InvalidGitRepositoryError

        super().__init__(
            REVIEW_MANAGER, ProcessType.explore, notify_state_transition_process=False
        )

        self.local_registry = self.REVIEW_MANAGER.load_local_registry()

        self.local_repos = []
        for source in [x for x in self.local_registry]:
            try:
                cp_REVIEW_MANAGER = ReviewManager(path_str=source["source_url"])
                CheckProcess(cp_REVIEW_MANAGER)  # to notify
                shared_url = ""
                git_repo = cp_REVIEW_MANAGER.REVIEW_DATASET.get_repo()
                for remote in git_repo.remotes:
                    if remote.url:
                        shared_url = remote.url
                repo = {
                    "source_url": source["source_url"],
                    "source_link": shared_url.rstrip(".git"),
                }
                self.local_repos.append(repo)
            except (NoSuchPathError, InvalidGitRepositoryError):
                pass

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
        title_str = re.sub("[^0-9a-zA-Z]+", " ", record.get("title", ""))
        srep = self.__robust_append(srep, title_str)
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
        plaintext_number += 10
        plaintext_number = plaintext_number % self.max_len_sha256

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

    def __get_toc_index_file(self, hash: str) -> Path:
        return self.local_index_path / Path(f".toc_index/{hash[:2]}/{hash[2:]}.txt")

    def __store_record(self, record: dict, index_fpath: Path) -> None:
        index_fpath.parents[0].mkdir(exist_ok=True, parents=True)

        # Casting to string (in particular the RecordState Enum)
        record = {k: str(v) for k, v in record.items()}

        index_record_db = BibDatabase()
        index_record_db.entries = [record]
        bibtex_str = bibtexparser.dumps(
            index_record_db, self.REVIEW_MANAGER.REVIEW_DATASET.get_bibtex_writer()
        )
        with open(index_fpath, "w") as out:
            out.write(bibtex_str)
        return

    def __retrieve_from_index_based_on_hash(self, hash: str) -> dict:
        record_fp = self.__get_record_index_file(hash)
        if not record_fp.is_file():
            raise RecordNotInIndexException
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

    def __retrieve_from_toc_index_based_on_hash(self, hash: str) -> list:
        toc_fpath = self.__get_toc_index_file(hash)
        res = toc_fpath.read_text().splitlines()
        return res

    def __amend_toc(self, index_fpath: Path, string_repr: str) -> None:
        with open(index_fpath, "a") as out:
            out.write(f"{string_repr}\n")
        return

    def __amend_record(self, hash: str, record: dict) -> None:

        index_fpath = self.__get_record_index_file(hash)
        saved_record = self.__retrieve_from_index_based_on_hash(hash)
        # TODO: check key and increment hash if necessary?

        # Casting to string (in particular the RecordState Enum)
        record = {k: str(v) for k, v in record.items()}

        # amend saved record
        for k, v in record.items():
            if k in saved_record:
                continue
            saved_record[k] = v

        index_record_db = BibDatabase()
        index_record_db.entries = [saved_record]
        bibtex_str = bibtexparser.dumps(index_record_db)
        with open(index_fpath, "w") as out:
            out.write(bibtex_str)

        return

    def __record_index(self, record: dict) -> None:
        hash = self.__get_record_hash(record)
        index_fpath = self.__get_record_index_file(hash)
        string_representation = self.__get_string_representation(record)
        record["hash_string_representation"] = string_representation

        try:
            dupl: typing.List[str] = []
            # check if the record is already indexed (based on gid/d)
            retrieved_record = self.retrieve_record_from_index(record)

            # if the string_representations are not identical: add to d_index
            if not self.__get_string_representation(
                retrieved_record
            ) == self.__get_string_representation(record):
                self.__append_if_duplicate_repr(dupl, record, retrieved_record)
            # Note: we need the hash of retrieved_record (different from record)
            self.__amend_record(self.__get_record_hash(retrieved_record), record)
            return
        except RecordNotInIndexException:
            pass

        while True:
            if not index_fpath.is_file():
                self.__store_record(record, index_fpath)
                break
            else:
                saved_record = self.__retrieve_from_index_based_on_hash(hash)
                if string_representation == saved_record.get(
                    "hash_string_representation", ""
                ):
                    # ok - no collision, update the record
                    # Note : do not update (the record from the first repository
                    # should take precedence - reset the index to update)
                    self.__amend_record(hash, record)
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

                if "file" == global_key:
                    record["file"] = str(Path(record["file"]).resolve())
                    if not Path(record["file"]).is_file():
                        if Path(record["source_url"] + "/" + record["file"]).is_file():
                            record["file"] = record["source_url"] + "/" + record["file"]
                        else:
                            print(f'File not available for gid index: {record["file"]}')
                            continue

                # print(f"{global_key}={record[global_key]}")

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

    def __get_toc_key(self, record: dict) -> str:
        toc_key = "NA"
        if "article" == record["ENTRYTYPE"]:
            toc_key = f"toc_key={record.get('journal', '').lower()}"
            if "volume" in record:
                toc_key = toc_key + f"|{record['volume']}"
            if "number" in record:
                toc_key = toc_key + f"|{record['number']}"
        elif "inproceedings" == record["ENTRYTYPE"]:
            toc_key = (
                f"toc_key={record.get('booktitle', '').lower()}"
                + f"|{record.get('year', '')}"
            )

        return toc_key

    def __toc_index(self, record) -> None:

        if "article" == record.get("ENTRYTYPE", ""):
            # Note : records are md_prepared, i.e., complete

            toc_key = self.__get_toc_key(record)
            if "NA" == toc_key:
                return

            # print(toc_key)
            hash = hashlib.sha256(toc_key.encode("utf-8")).hexdigest()
            index_fpath = self.__get_toc_index_file(hash)
            record_string_repr = self.__get_string_representation(record)
            while True:
                if not index_fpath.is_file():
                    index_fpath.parents[0].mkdir(exist_ok=True, parents=True)
                    index_fpath.write_text(f"{toc_key}\n{record_string_repr}\n")
                    break
                else:
                    res = self.__retrieve_from_toc_index_based_on_hash(hash)
                    saved_toc_key = res[0]
                    saved_toc_content = res[1:]
                    if saved_toc_key == toc_key:
                        # ok - no collision, update the record
                        # Note : do not update (the record from the first repository
                        #  should take precedence - reset the index to update)
                        if record_string_repr not in saved_toc_content:
                            self.__amend_toc(index_fpath, record_string_repr)
                        break
                    else:
                        # to handle the collision:
                        print(f"Collision: {hash}")
                        hash = self.__increment_hash(hash)
                        index_fpath = self.__get_toc_index_file(hash)

        if "inproceedings" == record.get("ENTRYTYPE", ""):
            # Note : records are md_prepared, i.e., complete

            toc_key = self.__get_toc_key(record)
            if "NA" == toc_key:
                return

            hash = hashlib.sha256(toc_key.encode("utf-8")).hexdigest()
            index_fpath = self.__get_toc_index_file(hash)
            record_string_repr = self.__get_string_representation(record)

            while True:
                if not index_fpath.is_file():
                    index_fpath.parents[0].mkdir(exist_ok=True, parents=True)
                    index_fpath.write_text(f"{toc_key}\n{record_string_repr}\n")
                    break
                else:
                    res = self.__retrieve_from_toc_index_based_on_hash(hash)
                    saved_toc_key = res[0]
                    saved_toc_content = res[1:]
                    if saved_toc_key == toc_key:
                        # ok - no collision, update the record
                        # Note : do not update (the record from the first repository
                        #  should take precedence - reset the index to update)
                        if record_string_repr not in saved_toc_content:
                            self.__amend_toc(index_fpath, record_string_repr)
                        break
                    else:
                        # to handle the collision:
                        print(f"Collision: {hash}")
                        hash = self.__increment_hash(hash)
                        index_fpath = self.__get_toc_index_file(hash)

        return

    def __append_j_variation(
        self, j_variations: list, origin_record: dict, record: dict
    ) -> list:

        if "journal" not in origin_record or "journal" not in record:
            return j_variations
        else:
            if origin_record["journal"] != record["journal"]:
                j_variations.append([origin_record["journal"], record["journal"]])

        return j_variations

    def __append_if_duplicate_repr(
        self, non_identical_representations: list, origin_record: dict, record: dict
    ) -> list:

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

        if all(required_field in origin_record for required_field in required_fields):
            orig_repr = self.__get_string_representation(origin_record)
            main_repr = self.__get_string_representation(record)
            if orig_repr != main_repr:
                non_identical_representations.append([orig_repr, main_repr])

        return non_identical_representations

    def __add_to_d_index(self, non_identical_representations: list) -> None:
        non_identical_representations = [
            list(x) for x in {tuple(x) for x in non_identical_representations}
        ]
        if len(non_identical_representations) > 0:

            for (
                non_identical_representation,
                orig_record_string,
            ) in non_identical_representations:
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

    def __d_index(self, records: typing.List[dict]) -> None:

        from colrev_core.prep import Preparation

        # Note: preparation notifies of preparation processs...
        PREPARATION = Preparation(
            self.REVIEW_MANAGER, notify_state_transition_process=False
        )

        try:
            search_path = Path(records[0]["source_url"] + "/search/")
        except IndexError:
            pass
            return

        self.logger.info(f"Create d_index for {search_path.parent}")

        # records = [x for x in records if x['ID'] == 'BenbasatZmud1999']

        # Note : records are at least md_processed.
        duplicate_repr_list = []
        for record in records:
            for orig in record["origin"].split(";"):
                duplicate_repr_list.append(
                    {
                        "origin_source": orig.split("/")[0],
                        "origin_id": orig.split("/")[1],
                        "record": record,
                    }
                )
        if len(duplicate_repr_list) == 0:
            return

        origin_sources = list({x["origin_source"] for x in duplicate_repr_list})
        non_identical_representations: typing.List[list] = []
        j_variations: typing.List[list] = []
        for origin_source in origin_sources:
            os_fp = search_path / Path(origin_source)
            if not os_fp.is_file():
                print(f"source not fount {os_fp}")
            else:
                with open(os_fp) as target_db:
                    bib_db = BibTexParser(
                        customization=convert_to_unicode,
                        ignore_nonstandard_types=False,
                        common_strings=True,
                    ).parse_file(target_db, partial=True)

                    origin_source_records = bib_db.entries
                for duplicate_repr in duplicate_repr_list:
                    record = duplicate_repr["record"]
                    origin_record_list = [
                        x
                        for x in origin_source_records
                        if x["ID"] == duplicate_repr["origin_id"]
                    ]
                    if len(origin_record_list) == 0:
                        continue
                    origin_record = origin_record_list.pop()
                    non_identical_representations = self.__append_if_duplicate_repr(
                        non_identical_representations, origin_record, record
                    )
                    j_variations = self.__append_j_variation(
                        j_variations, origin_record, record
                    )

        # also include the doi/dblp representations
        for record in tqdm(records):
            if "doi" in record:
                unprepared_record = PREPARATION.get_md_from_doi(record.copy())
                non_identical_representations = self.__append_if_duplicate_repr(
                    non_identical_representations, unprepared_record, record
                )
                j_variations = self.__append_j_variation(
                    j_variations, unprepared_record, record
                )

            if "dblp_key" in record:
                unprepared_record = PREPARATION.get_md_from_dblp(record.copy())
                non_identical_representations = self.__append_if_duplicate_repr(
                    non_identical_representations, unprepared_record, record
                )
                j_variations = self.__append_j_variation(
                    j_variations, unprepared_record, record
                )
        # print(j_variations)
        # 2. add representations to index
        self.__add_to_d_index(non_identical_representations)

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
        retrieved_record = self.__retrieve_from_index_based_on_hash(
            hashlib.sha256(associated_original.encode("utf-8")).hexdigest()
        )
        return self.__prep_record_for_return(retrieved_record)

    def __retrieve_from_gid_index(self, record: dict) -> dict:
        """Convenience function to retrieve a record based on a global ID"""

        string_representation = ""
        retrieved = False
        for k, v in record.items():
            if k not in self.global_keys or "ID" == k:
                continue

            gid = f"{k}={v}"
            hash = hashlib.sha256(gid.encode("utf-8")).hexdigest()
            # Note: catch exceptions to make sure that all global IDs are considered
            try:
                while True:
                    (
                        saved_gid,
                        string_representation,
                    ) = self.__retrieve_from_gid_index_based_on_hash(hash)
                    if saved_gid == gid:
                        # ok - no collision,
                        retrieved = True
                        break
                    else:
                        # to handle the collision:
                        hash = self.__increment_hash(hash)
            except FileNotFoundError:
                pass

        if not retrieved:
            raise RecordNotInIndexException

        indexed_record = self.__retrieve_from_index_based_on_hash(
            hashlib.sha256(string_representation.encode("utf-8")).hexdigest()
        )
        return indexed_record

    def __prep_record_for_return(self, record: dict) -> dict:
        from colrev_core.process import RecordState

        if "hash_string_representation" in record:
            del record["hash_string_representation"]
        # del retrieved_record['source_url']
        if "file" in record:
            if not Path(record["file"]).is_file():
                dir_path = Path(record["source_url"]) / Path(record["file"])
                if dir_path.is_file():
                    record["file"] = str(dir_path)
                pdf_dir_path = (
                    Path(record["source_url"])
                    / self.REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"]
                    / Path(record["file"])
                )
                if pdf_dir_path.is_file():
                    record["file"] = str(pdf_dir_path)

        if "manual_non_duplicate" in record:
            del record["manual_non_duplicate"]
        record["status"] = RecordState.md_prepared
        return record

    def __download_resources(self) -> None:
        import requests

        if not self.wos_j_abbrev.is_file():
            url = "https://su.figshare.com/ndownloader/files/5212423"
            r = requests.get(url, allow_redirects=True)
            open(self.wos_j_abbrev, "wb").write(r.content)
        return

    def index_records(self) -> None:
        import shutil

        self.logger.info("Called LocalIndex")

        self.logger.info("Reset record_index, gid_index, d_index")
        if self.rind_path.is_dir():
            shutil.rmtree(self.rind_path)
        if self.gind_path.is_dir():
            shutil.rmtree(self.gind_path)
        if self.dind_path.is_dir():
            shutil.rmtree(self.dind_path)
        if self.jind_path.is_dir():
            shutil.rmtree(self.jind_path)
        if self.toc_path.is_dir():
            shutil.rmtree(self.toc_path)

        # TODO: add web of science abbreviations (only when they are unique!?)
        # self.__download_resources()

        for source_url in [x["source_url"] for x in self.local_registry]:
            if not Path(source_url).is_dir():
                print(f"Warning {source_url} not a directory")
                continue
            os.chdir(source_url)
            self.logger.info(f"Index records from {source_url}")

            # get ReviewManager for project (after chdir)
            REVIEW_MANAGER = ReviewManager(path_str=str(source_url))
            CHECK_PROCESS = CheckProcess(REVIEW_MANAGER)

            if not CHECK_PROCESS.REVIEW_MANAGER.paths["MAIN_REFERENCES"].is_file():
                continue

            records = CHECK_PROCESS.REVIEW_MANAGER.REVIEW_DATASET.load_records()
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
                # Note: if the pdf_hash has not been checked,
                # we cannot use it for retrieval or preparation.
                if record["status"] not in [
                    RecordState.pdf_prepared,
                    RecordState.rev_excluded,
                    RecordState.rev_included,
                    RecordState.rev_synthesized,
                ]:
                    if "pdf_hash" in record:
                        del record["pdf_hash"]

                del record["status"]

                self.__record_index(record)
                self.__gid_index(record)
                self.__toc_index(record)

            self.__d_index(records)

        return

    def retrieve_record_from_toc_index(
        self, record: dict, similarity_threshold: float
    ) -> dict:
        toc_key = self.__get_toc_key(record)

        hash = hashlib.sha256(toc_key.encode("utf-8")).hexdigest()
        index_fpath = self.__get_toc_index_file(hash)
        record_string_repr = self.__get_string_representation(record)

        saved_toc_record_str_reprs = []
        while True:
            if not index_fpath.is_file():
                break
            else:
                res = self.__retrieve_from_toc_index_based_on_hash(hash)
                saved_toc_key = res[0]
                if saved_toc_key == toc_key:
                    saved_toc_record_str_reprs = res[1:]
                    break
                else:
                    # to handle the collision:
                    print(f"Collision: {hash}")
                    hash = self.__increment_hash(hash)
                    index_fpath = self.__get_toc_index_file(hash)

        if len(saved_toc_record_str_reprs) > 0:
            sim_list = []
            for saved_toc_record_str_repr in saved_toc_record_str_reprs:
                # Note : using a simpler similarity measure
                # because the publication outlet parameters are already identical
                sv = fuzz.ratio(record_string_repr, saved_toc_record_str_repr) / 100
                sim_list.append(sv)

            if max(sim_list) > similarity_threshold:
                saved_toc_record_str_repr = saved_toc_record_str_reprs[
                    sim_list.index(max(sim_list))
                ]

                hash = hashlib.sha256(
                    saved_toc_record_str_repr.encode("utf-8")
                ).hexdigest()
                record = self.__retrieve_from_index_based_on_hash(hash)

                return self.__prep_record_for_return(record)

        return record

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
            self.REVIEW_MANAGER.logger.debug("Retrieved from g_id index")
            return self.__prep_record_for_return(retrieved_record)

        # 2. Try the record index
        string_representation_record = self.__get_string_representation(record)
        hash = self.__get_record_hash(record)
        while True:
            try:
                retrieved_record = self.__retrieve_from_index_based_on_hash(hash)
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
            self.REVIEW_MANAGER.logger.debug("Retrieved from record index")
            return self.__prep_record_for_return(retrieved_record)

        # 3. Try the duplicate representation index
        if not retrieved_record:
            try:
                retrieved_record = self.__retrieve_record_from_d_index(record)
            except FileNotFoundError:
                pass

        if not retrieved_record:
            raise RecordNotInIndexException(record.get("ID", "no-key"))

        self.REVIEW_MANAGER.logger.debug("Retrieved from d index")
        return self.__prep_record_for_return(retrieved_record)

    def set_source_url_link(self, record: dict) -> dict:
        if "source_url" in record:
            for local_repo in self.local_repos:
                if local_repo["source_url"] == record["source_url"]:
                    record["source_url"] = local_repo["source_link"]

        return record

    def set_source_path(self, record: dict) -> dict:
        if "source_url" in record:
            for local_repo in self.local_repos:
                if local_repo["source_link"] == record["source_url"]:
                    record["source_url"] = local_repo["source_url"]

        return record

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
        except RecordNotInIndexException:
            pass
            return "unknown"

        return "unknown"

    def analyze(self, threshold: float = 0.95) -> None:
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
        df = df.sort_values(by=["similarity", "fname"])
        df.to_csv("changes.csv", index=False)
        print("Exported changes.csv")

        pdf_hashes = []
        for r_file in self.rind_path.rglob("*.bib"):

            with open(r_file) as f:
                while True:
                    line = f.readline()
                    if not line:
                        break
                    if "pdf_hash" in line[:9]:
                        pdf_hashes.append(line[line.find("{") + 1 : line.rfind("}")])

        import collections

        pdf_hashes_dupes = [
            item for item, count in collections.Counter(pdf_hashes).items() if count > 1
        ]

        with open("non-unique-pdf-hashes.txt", "w") as o:
            o.write("\n".join(pdf_hashes_dupes))
        print("Export non-unique-pdf-hashes.txt")
        return


class Curations:

    curations_path = Path.home().joinpath(".colrev/curated_metadata")

    def __init__(self):
        pass

    def install_curated_resource(self, curated_resource: str) -> bool:
        import git

        # check if url else return False
        # validators.url(curated_resource)
        if "http" not in curated_resource:
            curated_resource = "https://github.com/" + curated_resource
        self.curations_path.mkdir(exist_ok=True, parents=True)
        repo_dir = self.curations_path / Path(curated_resource.split("/")[-1])
        if repo_dir.is_dir():
            print(f"Repo already exists ({repo_dir})")
            return False
        print(f"Download curated resource from {curated_resource}")
        git.Repo.clone_from(curated_resource, repo_dir)
        REVIEW_MANAGER = ReviewManager(path_str=str(repo_dir))
        REVIEW_MANAGER.register_repo()

        return True


class RecordNotInIndexException(Exception):
    def __init__(self, id: str = None):
        if id is not None:
            self.message = f"Record not in index ({id})"
        else:
            self.message = "Record not in index"
        super().__init__(self.message)


if __name__ == "__main__":
    pass
