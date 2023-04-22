#! /usr/bin/env python
"""SearchSource: LocalIndex"""
from __future__ import annotations

import difflib
import typing
import webbrowser
from copy import deepcopy
from dataclasses import dataclass
from multiprocessing import Lock
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import git
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.search
import colrev.record
import colrev.ui_cli.cli_colors as colors

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class LocalIndexSearchSource(JsonSchemaMixin):
    """Performs a search in the LocalIndex"""

    # pylint: disable=too-many-instance-attributes
    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "curation_ID"
    search_type = colrev.settings.SearchType.OTHER
    api_search_supported = True
    ci_supported: bool = True
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "LocalIndex"
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/local_index.md"
    )
    __local_index_md_filename = Path("data/search/md_curated.bib")

    essential_md_keys = [
        "title",
        "author",
        "journal",
        "year",
        "booktitle",
        "number",
        "volume",
        "issue",
        "author",
        "doi",
        "dblp_key",
        "url",
    ]

    def __init__(
        self,
        *,
        source_operation: colrev.operation.Operation,
        settings: Optional[dict] = None,
    ) -> None:
        if settings:
            # LocalIndex as a search_source
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )

        else:
            # LocalIndex as an md-prep source
            li_md_source_l = [
                s
                for s in source_operation.review_manager.settings.sources
                if s.filename == self.__local_index_md_filename
            ]
            if li_md_source_l:
                self.search_source = li_md_source_l[0]
            else:
                self.search_source = colrev.settings.SearchSource(
                    endpoint="colrev.local_index",
                    filename=self.__local_index_md_filename,
                    search_type=colrev.settings.SearchType.OTHER,
                    search_parameters={},
                    load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
                    comment="",
                )

            self.local_index_lock = Lock()

        self.origin_prefix = self.search_source.get_origin_prefix()

        self.local_index = source_operation.review_manager.get_local_index()
        self.review_manager = source_operation.review_manager

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
        )

        # if "query" not in source.search_parameters:
        # Note :  for md-sources, there is no query parameter.
        #     raise colrev_exceptions.InvalidQueryException(
        #         f"Source missing query search_parameter ({source.filename})"
        #     )

        if "query" in source.search_parameters:
            pass
            # if "simple_query_string" in source.search_parameters["query"]:
            #     if "query" in source.search_parameters["query"]["simple_query_string"]:
            #         pass
            #     else:
            #         raise colrev_exceptions.InvalidQueryException(
            #             "Source missing query/simple_query_string/query "
            #             f"search_parameter ({source.filename})"
            #         )

            # elif "url" in source.search_parameters["query"]:
            #     pass
            # # else:
            #     raise colrev_exceptions.InvalidQueryException(
            #         f"Source missing query/query search_parameter ({source.filename})"
            #     )

        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )

    def __retrieve_from_index(self) -> typing.List[dict]:
        params = self.search_source.search_parameters
        query = params["query"]

        returned_records = self.local_index.search(query=query)

        records_to_import = [r.get_data() for r in returned_records]
        records_to_import = [r for r in records_to_import if r]
        keys_to_drop = [
            "colrev_status",
            "colrev_origin",
            "screening_criteria",
        ]
        for record_dict in records_to_import:
            record_dict = {
                key: value
                for key, value in record_dict.items()
                if key not in keys_to_drop
            }

        return records_to_import

    def __run_md_search_update(
        self,
        *,
        search_operation: colrev.ops.search.Search,
        local_index_feed: colrev.ops.search.GeneralOriginFeed,
    ) -> None:
        records = search_operation.review_manager.dataset.load_records_dict()

        nr_changed = 0
        for feed_record_dict_id in list(local_index_feed.feed_records.keys()):
            feed_record_dict = local_index_feed.feed_records[feed_record_dict_id]
            feed_record = colrev.record.Record(data=feed_record_dict)

            try:
                retrieved_record_dict = self.local_index.retrieve(
                    record_dict=feed_record.get_data(), include_file=False
                )

                local_index_feed.set_id(record_dict=retrieved_record_dict)
            except (
                colrev_exceptions.RecordNotInIndexException,
                colrev_exceptions.NotFeedIdentifiableException,
            ):
                continue

            prev_record_dict_version = {}
            if retrieved_record_dict["ID"] in local_index_feed.feed_records:
                prev_record_dict_version = local_index_feed.feed_records[
                    retrieved_record_dict["ID"]
                ]

            local_index_feed.add_record(
                record=colrev.record.Record(data=retrieved_record_dict)
            )

            changed = search_operation.update_existing_record(
                records=records,
                record_dict=retrieved_record_dict,
                prev_record_dict_version=prev_record_dict_version,
                source=self.search_source,
                update_time_variant_fields=True,
            )
            # Note : changed refers to the data/records.bib.
            # Records that are not yet imported do not count.
            if changed:
                nr_changed += 1

        if nr_changed > 0:
            self.review_manager.logger.info(
                f"{colors.GREEN}Updated {nr_changed} "
                f"records based on LocalIndex{colors.END}"
            )
        else:
            if records:
                self.review_manager.logger.info(
                    f"{colors.GREEN}Records (data/records.bib) "
                    f"up-to-date with LocalIndex{colors.END}"
                )

        local_index_feed.save_feed_file()
        search_operation.review_manager.dataset.save_records_dict(records=records)
        search_operation.review_manager.dataset.add_record_changes()

    def __run_parameter_search(
        self,
        *,
        search_operation: colrev.ops.search.Search,
        local_index_feed: colrev.ops.search.GeneralOriginFeed,
        rerun: bool,
    ) -> None:
        records = search_operation.review_manager.dataset.load_records_dict()

        nr_retrieved, nr_changed = 0, 0

        for retrieved_record_dict in self.__retrieve_from_index():
            try:
                local_index_feed.set_id(record_dict=retrieved_record_dict)
            except colrev_exceptions.NotFeedIdentifiableException:
                continue

            prev_record_dict_version = {}
            if retrieved_record_dict["ID"] in local_index_feed.feed_records:
                prev_record_dict_version = local_index_feed.feed_records[
                    retrieved_record_dict["ID"]
                ]

            added = local_index_feed.add_record(
                record=colrev.record.Record(data=retrieved_record_dict)
            )
            if added:
                nr_retrieved += 1

            else:
                changed = search_operation.update_existing_record(
                    records=records,
                    record_dict=retrieved_record_dict,
                    prev_record_dict_version=prev_record_dict_version,
                    source=self.search_source,
                    update_time_variant_fields=rerun,
                )
                if changed:
                    nr_changed += 1

        local_index_feed.save_feed_file()

        if nr_retrieved > 0:
            search_operation.review_manager.logger.info(
                f"{colors.GREEN}Retrieved {nr_retrieved} records {colors.END}"
            )

        if nr_changed > 0:
            self.review_manager.logger.info(
                f"{colors.GREEN}Updated {nr_changed} "
                f"records based on LocalIndex{colors.END}"
            )
        else:
            if records:
                self.review_manager.logger.info(
                    f"{colors.GREEN}Records (data/records.bib) "
                    f"up-to-date with LocalIndex{colors.END}"
                )

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of local-index"""

        local_index_feed = self.search_source.get_feed(
            review_manager=search_operation.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        if self.search_source.is_md_source() or self.search_source.is_quasi_md_source():
            self.__run_md_search_update(
                search_operation=search_operation,
                local_index_feed=local_index_feed,
            )

        else:
            self.__run_parameter_search(
                search_operation=search_operation,
                local_index_feed=local_index_feed,
                rerun=rerun,
            )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for local-index"""

        result = {"confidence": 0.0}
        if "curation_ID" in data:
            result["confidence"] = 1.0

        return result

    @classmethod
    def add_endpoint(
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> typing.Optional[colrev.settings.SearchSource]:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        if query.startswith("local_index:"):
            query = query.replace("local_index:", "")

            filename = search_operation.get_unique_filename(
                file_path_string=f"local_index_{query}".replace("%", "").replace(
                    "'", ""
                )
            )
            add_source = colrev.settings.SearchSource(
                endpoint="colrev.local_index",
                filename=filename,
                search_type=colrev.settings.SearchType.DB,
                search_parameters={"query": query},
                load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
                comment="",
            )
            return add_source

        return None

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for local-index"""

        # Note : to avoid modifying the feed-records
        records = deepcopy(records)

        for record_dict in records.values():
            curation_url = record_dict["curation_ID"].split("#")[0]
            record_dict["colrev_masterdata_provenance"] = {
                "CURATED": {"source": curation_url, "note": ""}
            }
            record = colrev.record.Record(data=record_dict)
            record.set_status(target_state=colrev.record.RecordState.md_prepared)
            del curation_url

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for local-index"""

        return record

    def __add_cpid(self, *, record: colrev.record.Record) -> bool:
        # To enable retrieval based on colrev_pdf_id (as part of the global_ids)
        if "file" in record.data and "colrev_pdf_id" not in record.data:
            pdf_path = Path(self.review_manager.path / Path(record.data["file"]))
            if pdf_path.is_file():
                try:
                    record.data.update(
                        colrev_pdf_id=colrev.record.Record.get_colrev_pdf_id(
                            pdf_path=pdf_path,
                        )
                    )
                    return True
                except colrev_exceptions.PDFHashError:
                    pass
        return False

    def __set_not_in_toc_info(
        self, *, record: colrev.record.Record, toc_key: str
    ) -> None:
        record.set_status(
            target_state=colrev.record.RecordState.md_needs_manual_preparation
        )
        if "journal" in record.data:
            record.add_masterdata_provenance_note(
                key="journal", note=f"record_not_in_toc {toc_key}"
            )
        elif "booktitle" in record.data:
            record.add_masterdata_provenance_note(
                key="booktitle", note=f"record_not_in_toc {toc_key}"
            )

    def __retrieve_record_from_local_index(
        self,
        *,
        record: colrev.record.Record,
        added_colrev_pdf_id: bool,
        retrieval_similarity: float,
    ) -> colrev.record.Record:
        retrieved_record_dict = {}
        try:
            retrieved_record_dict = self.local_index.retrieve(
                record_dict=record.get_data(), include_file=False
            )
        except (
            colrev_exceptions.RecordNotInIndexException,
            colrev_exceptions.NotEnoughDataToIdentifyException,
        ):
            try:
                # Search within the table-of-content in local_index
                retrieved_record_dict = self.local_index.retrieve_from_toc(
                    record_dict=record.data,
                    similarity_threshold=retrieval_similarity,
                    include_file=False,
                )
            except colrev_exceptions.RecordNotInTOCException as exc:
                self.__set_not_in_toc_info(record=record, toc_key=exc.toc_key)
                return record

            except colrev_exceptions.RecordNotInIndexException:
                try:
                    # Search across table-of-contents in local_index
                    retrieved_record_dict = self.local_index.retrieve_from_toc(
                        record_dict=record.data,
                        similarity_threshold=retrieval_similarity,
                        include_file=False,
                        search_across_tocs=True,
                    )
                except colrev_exceptions.RecordNotInTOCException as exc:
                    self.__set_not_in_toc_info(record=record, toc_key=exc.toc_key)
                    return record
                except (colrev_exceptions.RecordNotInIndexException,):
                    return record
            except colrev_exceptions.NotTOCIdentifiableException:
                return record
        finally:
            if added_colrev_pdf_id:
                del record.data["colrev_pdf_id"]

        if "colrev_status" in retrieved_record_dict:
            del retrieved_record_dict["colrev_status"]

        return colrev.record.PrepRecord(data=retrieved_record_dict)

    def __store_retrieved_record_in_feed(
        self,
        *,
        record: colrev.record.Record,
        default_source: str,
        prep_operation: colrev.ops.prep.Prep,
    ) -> None:
        try:
            # lock: to prevent different records from having the same origin
            self.local_index_lock.acquire(timeout=60)

            # Note : need to reload file because the object is not shared between processes
            local_index_feed = self.search_source.get_feed(
                review_manager=self.review_manager,
                source_identifier=self.source_identifier,
                update_only=False,
            )

            local_index_feed.set_id(record_dict=record.data)
            local_index_feed.add_record(record=record)

            record.remove_field(key="curation_ID")
            record.merge(
                merging_record=record,
                default_source=default_source,
            )
            record.set_status(target_state=colrev.record.RecordState.md_prepared)
            if record.data.get("prescreen_exclusion", "NA") == "retracted":
                record.prescreen_exclude(reason="retracted")

            git_repo = self.review_manager.dataset.get_repo()
            cur_project_source_paths = [str(self.review_manager.path)]
            for remote in git_repo.remotes:
                if remote.url:
                    shared_url = remote.url
                    shared_url = shared_url.rstrip(".git")
                    cur_project_source_paths.append(shared_url)
                    break

            try:
                local_index_feed.save_feed_file()
                # extend fields_to_keep (to retrieve all fields from the index)
                for key in record.data.keys():
                    if key not in prep_operation.fields_to_keep:
                        prep_operation.fields_to_keep.append(key)

            except OSError:
                pass

            self.local_index_lock.release()

        except (
            colrev_exceptions.InvalidMerge,
            colrev_exceptions.NotFeedIdentifiableException,
        ):
            self.local_index_lock.release()

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.Record:
        """Retrieve masterdata from LocalIndex based on similarity with the record provided"""

        if any(self.origin_prefix in o for o in record.data["colrev_origin"]):
            # Already linked to a local-index record
            return record

        # add colrev_pdf_id
        added_colrev_pdf_id = self.__add_cpid(record=record)

        retrieved_record = self.__retrieve_record_from_local_index(
            record=record,
            added_colrev_pdf_id=added_colrev_pdf_id,
            retrieval_similarity=prep_operation.retrieval_similarity,
        )

        # restriction: if we don't restrict to CURATED,
        # we may have to rethink the LocalIndexSearchFeed.set_ids()
        if "CURATED" not in retrieved_record.data.get(
            "colrev_masterdata_provenance", ""
        ):
            return record

        default_source = "LOCAL_INDEX"
        if "colrev_masterdata_provenance" in retrieved_record.data:
            if "CURATED" in retrieved_record.data["colrev_masterdata_provenance"]:
                default_source = retrieved_record.data["colrev_masterdata_provenance"][
                    "CURATED"
                ]["source"]

        self.__store_retrieved_record_in_feed(
            record=retrieved_record,
            default_source=default_source,
            prep_operation=prep_operation,
        )

        return record

    def __get_local_base_repos(self, *, change_itemsets: list) -> dict:
        base_repos = []
        for item in change_itemsets:
            if "CURATED" in item["original_record"].get(
                "colrev_masterdata_provenance", {}
            ):
                repo_path = item["original_record"]["colrev_masterdata_provenance"][
                    "CURATED"
                ]["source"]
                assert "#" not in repo_path
                # otherwise: strip the ID at the end if we add an ID...
                base_repos.append(repo_path)

        base_repos = list(set(base_repos))

        environment_manager = colrev.env.environment_manager.EnvironmentManager()

        local_base_repos = {
            x["repo_source_url"]: x["repo_source_path"]
            for x in environment_manager.load_environment_registry()
            if x["repo_source_url"] in base_repos
        }
        return local_base_repos

    def apply_correction(self, *, change_itemsets: list) -> None:
        """Apply a correction by opening a pull request in the original repository"""

        # pylint: disable=too-many-branches

        local_base_repos = self.__get_local_base_repos(change_itemsets=change_itemsets)

        def print_diff(change: tuple) -> str:
            diff = difflib.Differ()
            letters = list(diff.compare(change[1], change[0]))
            for i, letter in enumerate(letters):
                if letter.startswith("  "):
                    letters[i] = letters[i][-1]
                elif letter.startswith("+ "):
                    letters[i] = f"{colors.RED}" + letters[i][-1] + f"{colors.END}"
                elif letter.startswith("- "):
                    letters[i] = f"{colors.GREEN}" + letters[i][-1] + f"{colors.END}"
            res = "".join(letters).replace("\n", " ")
            return res

        for local_base_repo in local_base_repos:
            validated_changes = []
            print()
            self.review_manager.logger.info(f"Base repository: {local_base_repo}")
            for item in change_itemsets:
                repo_path = "NA"
                if "CURATED" in item["original_record"].get(
                    "colrev_masterdata_provenance", {}
                ):
                    repo_path = item["original_record"]["colrev_masterdata_provenance"][
                        "CURATED"
                    ]["source"]
                    assert "#" not in repo_path
                    # otherwise: strip the ID at the end if we add an ID...

                if repo_path != local_base_repo:
                    continue

                # self.review_manager.p_printer.pprint(item["original_record"])
                colrev.record.Record(
                    data=item["original_record"]
                ).print_citation_format()
                for change_item in item["changes"]:
                    if change_item[0] == "change":
                        edit_type, field, values = change_item
                        if field == "colrev_id":
                            continue
                        prefix = f"{edit_type} {field}"
                        print(
                            f"{prefix}"
                            + " " * max(len(prefix), 30 - len(prefix))
                            + f": {values[0]}"
                        )
                        print(
                            " " * max(len(prefix), 30)
                            + f"  {colors.ORANGE}{values[1]}{colors.END}"
                        )
                        print(
                            " " * max(len(prefix), 30)
                            + f"  {print_diff((values[0], values[1]))}"
                        )

                    elif change_item[0] == "add":
                        edit_type, field, values = change_item
                        prefix = f"{edit_type} {values[0][0]}"
                        print(
                            prefix
                            + " " * max(len(prefix), 30 - len(prefix))
                            + f": {colors.GREEN}{values[0][1]}{colors.END}"
                        )
                    else:
                        self.review_manager.p_printer.pprint(change_item)
                validated_changes.append(item)

            response = ""
            while True:
                response = input("\nConfirm changes? (y/n)")
                if response in ["y", "n"]:
                    break

            if response == "y":
                self.__apply_correction(
                    source_url=local_base_repos[repo_path],
                    change_list=validated_changes,
                )
            elif response == "n":
                if input("Discard all corrections (y/n)?") == "y":
                    for validated_change in validated_changes:
                        Path(validated_change["file"]).unlink()

    def __apply_corrections_precondition(
        self, *, check_operation: colrev.operation.Operation, source_url: str
    ) -> bool:
        git_repo = check_operation.review_manager.dataset.get_repo()

        if git_repo.is_dirty():
            msg = f"Repo not clean ({source_url}): commit or stash before updating records"
            raise colrev_exceptions.CorrectionPreconditionException(msg)

        if check_operation.review_manager.dataset.behind_remote():
            origin = git_repo.remotes.origin
            origin.pull()
            if not check_operation.review_manager.dataset.behind_remote():
                self.review_manager.logger.info("Pulled changes")
            else:
                self.review_manager.logger.error(
                    "Repo behind remote. Pull first to avoid conflicts.\n"
                    "colrev env --pull"
                )
                return False

        return True

    def __retrieve_by_colrev_id(
        self, *, indexed_record_dict: dict, records: list[dict]
    ) -> dict:
        indexed_record = colrev.record.Record(data=indexed_record_dict)

        if "colrev_id" in indexed_record.data:
            cid_to_retrieve = indexed_record.get_colrev_id()
        else:
            cid_to_retrieve = [indexed_record.create_colrev_id()]

        record_l = [
            x
            for x in records
            if any(
                cid in colrev.record.Record(data=x).get_colrev_id()
                for cid in cid_to_retrieve
            )
        ]
        if len(record_l) != 1:
            raise colrev_exceptions.RecordNotInRepoException
        return record_l[0]

    def __retrieve_record_for_correction(
        self,
        *,
        records: dict,
        change_item: dict,
    ) -> dict:
        original_record = change_item["original_record"]

        local_index_feed = self.search_source.get_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=True,
        )

        try:
            md_curated_origin_id = [
                x for x in original_record["colrev_origin"] if "md_curated.bib/" in x
            ][0].replace("md_curated.bib/", "")
            curation_origin_record = local_index_feed.feed_records[md_curated_origin_id]
            curation_id = curation_origin_record["curation_ID"]
            curation_id = curation_id[curation_id.find("#") + 1 :]
            return records[curation_id]
        except KeyError:
            pass

        try:
            record_dict = self.__retrieve_by_colrev_id(
                indexed_record_dict=original_record,
                records=list(records.values()),
            )
            return record_dict
        except colrev_exceptions.RecordNotInRepoException:
            matching_doi_rec_l = [
                r
                for r in records.values()
                if original_record.get("doi", "NDOI") == r.get("doi", "NA")
            ]
            if len(matching_doi_rec_l) == 1:
                record_dict = matching_doi_rec_l[0]
                return record_dict

            matching_url_rec_l = [
                r
                for r in records.values()
                if original_record.get("url", "NURL") == r.get("url", "NA")
            ]
            if len(matching_url_rec_l) == 1:
                record_dict = matching_url_rec_l[0]
                return record_dict

        self.review_manager.logger.error(
            f'{colors.RED}Record not found: {original_record["ID"]}{colors.END}'
        )
        raise colrev_exceptions.RecordNotInIndexException()

    def __create_correction_branch(
        self, *, git_repo: git.Repo, record_dict: dict
    ) -> str:
        record_branch_name = record_dict["ID"]
        counter = 1
        new_record_branch_name = record_branch_name
        while new_record_branch_name in [ref.name for ref in git_repo.references]:
            new_record_branch_name = f"{record_branch_name}_{counter}"
            counter += 1

        record_branch_name = new_record_branch_name
        git_repo.git.branch(record_branch_name)
        return record_branch_name

    def __apply_record_correction(
        self,
        *,
        check_operation: colrev.operation.Operation,
        records: dict,
        record_dict: dict,
        change_item: dict,
    ) -> None:
        for edit_type, key, change in list(change_item["changes"]):
            # Note : by retricting changes to self.essential_md_keys,
            # we also prevent changes in
            # "colrev_status", "colrev_origin", "file"

            # Note: the most important thing is to update the metadata.

            if edit_type == "change":
                if key not in self.essential_md_keys:
                    continue
                record_dict[key] = change[1]
            if edit_type == "add":
                key = change[0][0]
                value = change[0][1]
                if key not in self.essential_md_keys:
                    continue
                record_dict[key] = value
            # gh_issue https://github.com/CoLRev-Environment/colrev/issues/63
            # deal with remove/merge

        check_operation.review_manager.dataset.save_records_dict(records=records)
        check_operation.review_manager.dataset.add_record_changes()
        check_operation.review_manager.create_commit(
            msg=f"Update {record_dict['ID']}", script_call="colrev push"
        )

    def __push_corrections_and_reset_branch(
        self,
        *,
        git_repo: git.Repo,
        record_branch_name: str,
        prev_branch_name: str,
        source_url: str,
    ) -> None:
        git_repo.remotes.origin.push(
            refspec=f"{record_branch_name}:{record_branch_name}"
        )
        self.review_manager.logger.info("Pushed corrections")

        for head in git_repo.heads:
            if head.name == prev_branch_name:
                head.checkout()

        git_repo = git.Git(source_url)
        git_repo.execute(["git", "branch", "-D", record_branch_name])

        self.review_manager.logger.info("Removed local corrections branch")

    def __reset_record_after_correction(
        self, *, record_dict: dict, rec_for_reset: dict, change_item: dict
    ) -> None:
        # reset the record - each branch should have changes for one record
        # Note : modify dict (do not replace it) - otherwise changes will not be
        # part of the records.
        for key, value in rec_for_reset.items():
            record_dict[key] = value
        keys_added = [
            key for key in record_dict.keys() if key not in rec_for_reset.keys()
        ]
        for key in keys_added:
            del record_dict[key]

        if Path(change_item["file"]).is_file():
            Path(change_item["file"]).unlink()

    def __apply_change_item_correction(
        self,
        *,
        check_operation: colrev.operation.Operation,
        source_url: str,
        change_list: list,
    ) -> bool:
        # pylint: disable=too-many-locals

        git_repo = check_operation.review_manager.dataset.get_repo()
        records = check_operation.review_manager.dataset.load_records_dict()

        success = False
        pull_request_msgs = []
        pull_request_links = []
        for change_item in change_list:
            try:
                record_dict = self.__retrieve_record_for_correction(
                    records=records,
                    change_item=change_item,
                )
                if not record_dict:
                    continue

                record_branch_name = self.__create_correction_branch(
                    git_repo=git_repo, record_dict=record_dict
                )
                prev_branch_name = git_repo.active_branch.name

                remote = git_repo.remote()
                for head in git_repo.heads:
                    if head.name == record_branch_name:
                        head.checkout()

                rec_for_reset = record_dict.copy()

                self.__apply_record_correction(
                    check_operation=check_operation,
                    records=records,
                    record_dict=record_dict,
                    change_item=change_item,
                )

                self.__push_corrections_and_reset_branch(
                    git_repo=git_repo,
                    record_branch_name=record_branch_name,
                    prev_branch_name=prev_branch_name,
                    source_url=source_url,
                )

                self.__reset_record_after_correction(
                    record_dict=record_dict,
                    rec_for_reset=rec_for_reset,
                    change_item=change_item,
                )

                host = urlparse(remote.url).hostname
                if host and host.endswith("github.com"):
                    link = (
                        str(remote.url).rstrip(".git")
                        + "/compare/"
                        + record_branch_name
                    )
                    pull_request_links.append(link)
                    pull_request_msgs.append(
                        "\nTo create a pull request for your changes go "
                        f"to \n{colors.ORANGE}{link}{colors.END}"
                    )
                success = True
            except colrev_exceptions.RecordNotInIndexException:
                pass

        for pull_request_msg in pull_request_msgs:
            print(pull_request_msg)
        for pull_request_link in pull_request_links:
            webbrowser.open(pull_request_link, new=2)

        # https://github.com/geritwagner/information_systems_papers/compare/update?expand=1
        # gh_issue https://github.com/CoLRev-Environment/colrev/issues/63
        # handle cases where update branch already exists
        return success

    def __apply_correction(self, *, source_url: str, change_list: list) -> None:
        """Apply a (list of) corrections"""

        # TBD: other modes of accepting changes?
        # e.g., only-metadata, no-changes, all(including optional fields)
        check_review_manager = self.review_manager.get_review_manager(
            path_str=source_url
        )
        check_operation = colrev.operation.CheckOperation(
            review_manager=check_review_manager
        )

        if check_review_manager.dataset.behind_remote():
            git_repo = check_review_manager.dataset.get_repo()
            origin = git_repo.remotes.origin
            self.review_manager.logger.info(
                f"Pull project changes from {git_repo.remotes.origin}"
            )
            res = origin.pull()
            self.review_manager.logger.info(res)

        try:
            if not self.__apply_corrections_precondition(
                check_operation=check_operation, source_url=source_url
            ):
                return
        except colrev_exceptions.CorrectionPreconditionException as exc:
            print(exc)
            return

        check_review_manager.logger.info(
            "Precondition for correction (pull-request) checked."
        )

        success = self.__apply_change_item_correction(
            check_operation=check_operation,
            source_url=source_url,
            change_list=change_list,
        )

        if success:
            print(
                f"\n{colors.GREEN}Thank you for supporting other researchers "
                f"by sharing your corrections ❤{colors.END}\n"
            )


if __name__ == "__main__":
    pass
