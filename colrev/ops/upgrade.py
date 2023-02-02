#!/usr/bin/env python3
"""Upgrades CoLRev projects."""
from __future__ import annotations

import json
import typing
from pathlib import Path
from shutil import copytree
from typing import TYPE_CHECKING

import pandas as pd
import yaml
from tqdm import tqdm

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.operation

if TYPE_CHECKING:
    import colrev.review_manager


# pylint: disable=too-few-public-methods
# pylint: disable=too-many-lines


class Upgrade(colrev.operation.Operation):
    """Upgrade a CoLRev project"""

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.check,
            notify_state_transition_operation=False,
        )
        self.review_manager = review_manager

    def main(self) -> None:
        """Upgrade a CoLRev project (main entrypoint)"""

        last_version, current_version = self.review_manager.get_colrev_versions()

        if "+" in last_version:
            last_version = last_version[: last_version.find("+")]
        if "+" in current_version:
            current_version = current_version[: current_version.find("+")]

        cur_major = current_version[: current_version.rfind(".")]
        next_minor = str(int(current_version[current_version.rfind(".") + 1 :]) + 1)
        upcoming_version = cur_major + "." + next_minor

        # next version should be:
        # ...
        # {'from': '0.4.0', "to": '0.5.0', 'script': __migrate_0_4_0}
        # {'from': '0.5.0', "to": upcoming_version, 'script': __migrate_0_5_0}
        migration_scripts: typing.List[typing.Dict[str, typing.Any]] = [
            {"from": "0.4.0", "to": "0.5.0", "script": self.__migrate_0_4_0},
            {"from": "0.5.0", "to": "0.6.0", "script": self.__migrate_0_5_0},
            {"from": "0.6.0", "to": "0.7.0", "script": self.__migrate_0_6_0},
            {"from": "0.7.0", "to": upcoming_version, "script": self.__migrate_0_7_0},
        ]

        # Start with the first step if the version is older:
        if last_version not in [x["from"] for x in migration_scripts]:
            last_version = "0.4.0"

        while current_version in [x["from"] for x in migration_scripts]:
            self.review_manager.logger.info("Current CoLRev version: %s", last_version)

            migrator = [x for x in migration_scripts if x["from"] == last_version].pop()

            migration_script = migrator["script"]

            self.review_manager.logger.info(
                "Migrating from %s to %s", migrator["from"], migrator["to"]
            )

            updated = migration_script()
            if updated:
                self.review_manager.logger.info("Updated to: %s", last_version)
            else:
                self.review_manager.logger.info("Nothing to do.")
                self.review_manager.logger.info(
                    "If the update notification occurs again, run\n "
                    "git commit -n -m --allow-empty 'update colrev'"
                )

            # Note : the version in the commit message will be set to
            # the current_version immediately. Therefore, use the migrator['to'] field.
            last_version = migrator["to"]

            if last_version == upcoming_version:
                break

        if self.review_manager.dataset.has_changes():
            self.review_manager.create_commit(
                msg=f"Upgrade to CoLRev {upcoming_version}",
            )
            self.__print_release_notes(selected_version=upcoming_version)
        else:
            self.review_manager.logger.info("Nothing to do.")
            self.review_manager.logger.info(
                "If the update notification occurs again, run\n "
                "git commit -n -m --allow-empty 'update colrev'"
            )

    def __print_release_notes(self, *, selected_version: str) -> None:

        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("../CHANGELOG.md")
        )
        active = False
        if filedata:
            for line in filedata.decode("utf-8").split("\n"):
                if selected_version in line:
                    active = True
                    print(f"Release notes v{selected_version}")
                    continue
                if "### [" in line and selected_version not in line:
                    active = False
                if active:
                    print(line)

    def __migrate_0_4_0(self) -> bool:
        # pylint: disable=too-many-statements
        # pylint: disable=too-many-branches

        if not Path("settings.json").is_file():
            filedata = colrev.env.utils.get_package_file_content(
                file_path=Path("template/settings.json")
            )

            if not filedata:
                print("error reading file")
                return False
            settings = json.loads(filedata.decode("utf-8"))
        else:
            with open("settings.json", encoding="utf-8") as file:
                settings = json.load(file)

        old_sources_path = Path("sources.yaml")
        if old_sources_path.is_file():
            if old_sources_path.is_file():
                with open(old_sources_path, encoding="utf-8") as file:
                    sources_df = pd.json_normalize(yaml.safe_load(file))
                    sources = sources_df.to_dict("records")
                    print(sources)
            for source in sources:
                if len(source["search_parameters"]) > 0:
                    if "dblp" == source["search_parameters"][0]["endpoint"]:
                        source["source_identifier"] = "{{dblp_key}}"
                    elif "crossref" == source["search_parameters"][0]["endpoint"]:
                        source[
                            "source_identifier"
                        ] = "https://api.crossref.org/works/{{doi}}"
                    elif "pdfs_directory" == source["search_parameters"][0]["endpoint"]:
                        source["source_identifier"] = "{{file}}"
                    else:
                        source["source_identifier"] = source["search_parameters"][0][
                            "endpoint"
                        ]

                    source["search_parameters"] = source["search_parameters"][0][
                        "params"
                    ]
                else:
                    source["search_parameters"] = ""
                    source["source_identifier"] = source.get("source_url", "")

                if (
                    source["comment"] != source["comment"] or "NA" == source["comment"]
                ):  # NaN
                    source["comment"] = ""

                if "source_url" in source:
                    del source["source_url"]
                if "source_name" in source:
                    del source["source_name"]
                if "last_sync" in source:
                    del source["last_sync"]

            settings["search"]["sources"] = sources

        if any(r["name"] == "exclusion" for r in settings["prep"]["prep_rounds"]):
            e_r = [
                r for r in settings["prep"]["prep_rounds"] if r["name"] == "exclusion"
            ][0]
            if "exclude_predatory_journals" in e_r["scripts"]:
                e_r["scripts"].remove("exclude_predatory_journals")

        for source in settings["search"]["sources"]:
            source["script"] = {"endpoint": "bib_pybtex"}

        settings["prep"]["man_prep_scripts"] = [{"endpoint": "colrev_cli_man_prep"}]
        settings["prescreen"]["scope"] = [{"LanguageScope": ["eng"]}]
        if "plugin" in settings["prescreen"]:
            del settings["prescreen"]["plugin"]
        if "mode" in settings["prescreen"]:
            del settings["prescreen"]["mode"]
        settings["prescreen"]["scripts"] = [
            {"endpoint": "scope_prescreen"},
            {"endpoint": "colrev_cli_prescreen"},
        ]
        if "process" in settings["screen"]:
            del settings["screen"]["process"]
        settings["screen"]["scripts"] = [{"endpoint": "colrev_cli_screen"}]

        settings["pdf_get"]["man_pdf_get_scripts"] = [
            {"endpoint": "colrev_cli_pdf_get_man"}
        ]
        settings["pdf_get"]["scripts"] = [
            {"endpoint": "unpaywall"},
            {"endpoint": "local_index"},
        ]

        settings["pdf_prep"]["scripts"] = [
            {"endpoint": "pdf_check_ocr"},
            {"endpoint": "remove_coverpage"},
            {"endpoint": "remove_last_page"},
            {"endpoint": "validate_pdf_metadata"},
            {"endpoint": "validate_completeness"},
        ]
        settings["pdf_prep"]["man_pdf_prep_scripts"] = [
            {"endpoint": "colrev_cli_pdf_prep_man"}
        ]

        for data_script in settings["data"]["data_format"]:
            if "MANUSCRIPT" == data_script["endpoint"]:
                if "paper_endpoint_version" not in data_script:
                    data_script["paper_endpoint_version"] = "0.1"
            if "STRUCTURED" == data_script["endpoint"]:
                if "structured_data_endpoint_version" not in data_script:
                    data_script["structured_data_endpoint_version"] = "0.1"

        if "curated_metadata" in str(self.review_manager.path):
            git_repo = self.review_manager.dataset.get_repo()
            settings["project"]["curation_url"] = git_repo.remote().url.replace(
                ".git", ""
            )

        if old_sources_path.is_file():
            old_sources_path.unlink()
            self.review_manager.dataset.remove_file_from_git(path=str(old_sources_path))

        if Path("shared_config.ini").is_file():
            Path("shared_config.ini").unlink()
            self.review_manager.dataset.remove_file_from_git(path="shared_config.ini")
        if Path("private_config.ini").is_file():
            Path("private_config.ini").unlink()

        if "curated_metadata" in str(self.review_manager.path):
            settings["project"]["curated_master_data"] = True
            settings["project"]["curated_fields"] = [
                "doi",
                "url",
                "dblp_key",
            ]

        settings["dedupe"]["same_source_merges"] = "prevent"

        if settings["project"]["review_type"] == "NA":
            if "curated_metadata" in str(self.review_manager.path):
                settings["project"]["review_type"] = "curated_master_data"
            else:
                settings["project"]["review_type"] = "literature_review"

        with open("settings.json", "w", encoding="utf-8") as outfile:
            json.dump(settings, outfile, indent=4)

        self.review_manager.settings = self.review_manager.load_settings()
        self.review_manager.save_settings()

        self.review_manager.dataset.add_setting_changes()
        records = self.review_manager.dataset.load_records_dict()
        if len(records.values()) > 0:
            for record in records.values():
                if "manual_duplicate" in record:
                    del record["manual_duplicate"]
                if "manual_non_duplicate" in record:
                    del record["manual_non_duplicate"]
                if "origin" in record:
                    record["colrev_origin"] = record["origin"]
                    del record["origin"]
                if "status" in record:
                    record["colrev_status"] = record["status"]
                    del record["status"]
                if "excl_criteria" in record:
                    record["exclusion_criteria"] = record["excl_criteria"]
                    del record["excl_criteria"]
                if "metadata_source" in record:
                    del record["metadata_source"]

                if "colrev_masterdata" in record:
                    if record["colrev_masterdata"] == "ORIGINAL":
                        del record["colrev_masterdata"]
                    else:
                        record["colrev_masterdata_provenance"] = record[
                            "colrev_masterdata"
                        ]
                        del record["colrev_masterdata"]

                if "curated_metadata" in str(self.review_manager.path):
                    if "colrev_masterdata_provenance" in record:
                        if "CURATED" == record["colrev_masterdata_provenance"]:
                            record["colrev_masterdata_provenance"] = {}
                if "colrev_masterdata_provenance" not in record:
                    record["colrev_masterdata_provenance"] = {}
                if "colrev_data_provenance" not in record:
                    record["colrev_data_provenance"] = {}

                # if "source_url" in record:
                #     record["colrev_masterdata"] = \
                #           "CURATED:" + record["source_url"]
                #     del record["source_url"]
                # else:
                #     record["colrev_masterdata"] = "ORIGINAL"
                # Note : for curated repositories
                # record["colrev_masterdata"] = "CURATED"

            self.review_manager.dataset.save_records_dict(records=records)
            self.review_manager.dataset.add_record_changes()

        colrev.env.utils.retrieve_package_file(
            template_file=Path("template/.pre-commit-config.yaml"),
            target=Path(".pre-commit-config.yaml"),
        )
        self.review_manager.dataset.add_changes(path=Path(".pre-commit-config.yaml"))
        # Note: the order is important in this case.

        return True

    def __migrate_0_5_0(self) -> None:
        # pylint: disable=too-many-statements
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-locals

        def prefix_colrev_built_in(settings_part: dict) -> None:
            for endpoint in settings_part:
                if "colrev_built_in." not in endpoint["endpoint"]:
                    endpoint["endpoint"] = "colrev_built_in." + endpoint["endpoint"]

        with open("settings.json", encoding="utf-8") as file:
            settings = json.load(file)

        if "sources" in settings["search"]:
            for source in settings["search"]["sources"]:
                source["script"] = {"endpoint": "bib_pybtex"}
                if "search" not in source["filename"]:
                    source["filename"] = "search/" + source["filename"]

            if "sources" not in settings:
                settings["sources"] = settings["search"]["sources"]
                del settings["search"]["sources"]

                for source in settings["sources"]:
                    source["search_script"] = source["script"]
                    del source["script"]

                    source["load_conversion_script"] = {"endpoint": "bibtex"}

                    source["source_prep_scripts"] = []
                    if "CROSSREF" == source["source_name"]:
                        source["search_script"] = {"endpoint": "search_crossref"}
                    if "DBLP" == source["source_name"]:
                        source["search_script"] = {"endpoint": "search_dblp"}
                    if "BACKWARD_SEARCH" == source["source_name"]:
                        source["search_script"] = {"endpoint": "backward_search"}
                    if "COLREV_PROJECT" == source["source_name"]:
                        source["search_script"] = {"endpoint": "search_colrev_project"}
                    if "INDEX" == source["source_name"]:
                        source["search_script"] = {"endpoint": "search_local_index"}
                    if "PDFs" == source["source_name"]:
                        source["search_script"] = {"endpoint": "search_pdfs_dir"}
                    if "bib_pybtex" == source["search_script"]["endpoint"]:
                        source["search_script"] = {}

            settings = {
                "project": settings["project"],
                "sources": settings["sources"],
                "search": settings["search"],
                "load": settings["load"],
                "prep": settings["prep"],
                "dedupe": settings["dedupe"],
                "prescreen": settings["prescreen"],
                "pdf_get": settings["pdf_get"],
                "pdf_prep": settings["pdf_prep"],
                "screen": settings["screen"],
                "data": settings["data"],
            }

        if "title" not in settings["project"]:
            settings["project"]["title"] = str(Path.cwd().name)

        if "authors" not in settings["project"]:
            settings["project"]["authors"] = [
                {
                    "name": self.review_manager.committer,
                    "initials": "".join(
                        part[0] for part in self.review_manager.committer.split(" ")
                    ),
                    "email": self.review_manager.email,
                }
            ]

        if "keywords" not in settings["project"]:
            settings["project"]["keywords"] = []
        if "colrev_version" not in settings["project"]:
            settings["project"]["colrev_version"] = "0.5.0"

        if "THREE_AUTHORS_YEAR" == settings["project"]["id_pattern"]:
            settings["project"]["id_pattern"] = "three_authors_year"

        for source in settings["sources"]:
            if "source_name" in source:
                if "PDFs" == source["source_name"]:
                    source["source_name"] = "pdfs_dir"
                source["source_name"] = source["source_name"].lower()
                if "FEED" == source["search_type"]:
                    if "CROSSREF" == source["source_name"]:
                        source["search_type"] = "DB"
                    elif "DBLP" == source["source_name"]:
                        source["search_type"] = "DB"
                    elif "pdfs" == source["source_name"].lower():
                        source["search_type"] = "PDFS"
                    else:
                        source["search_type"] = "DB"

                if "crossref" == source["source_name"].lower():
                    if isinstance(source["search_parameters"], str):
                        jissn = (
                            source["search_parameters"]
                            .replace("SCOPE journal_issn=", "")
                            .strip("'")
                        )
                        source["search_parameters"] = {"scope": {"journal_issn": jissn}}
                elif "dblp" == source["source_name"].lower():
                    if isinstance(source["search_parameters"], str):
                        venue_key, journal_abbreviated = source[
                            "search_parameters"
                        ].split(" AND ")
                        venue_key = venue_key.replace("SCOPE venue_key=", "").strip("'")
                        journal_abbreviated = journal_abbreviated.replace(
                            "journal_abbreviated=", ""
                        ).strip("'")
                        source["search_parameters"] = {
                            "scope": {
                                "venue_key": venue_key,
                                "journal_abbreviated": journal_abbreviated,
                            }
                        }
                elif source["source_name"].lower() in ["pdfs_dir", "pdfs"]:
                    if isinstance(source["search_parameters"], str):
                        param_string = source["search_parameters"]
                        temp = {"scope": {}}  # type: ignore
                        if "sub_dir_pattern" in param_string:
                            param_string, subdir_pattern = param_string.split(
                                "sub_dir_pattern="
                            )
                            param_string = param_string.rstrip(" AND ")
                            subdir_pattern = subdir_pattern.strip("'")
                            temp["scope"]["subdir_pattern"] = subdir_pattern  # type: ignore
                        if "journal" in param_string:
                            param_string, journal = param_string.split("journal=")
                            param_string = param_string.rstrip(" WITH ")
                            journal = journal.strip("'")
                            temp["scope"]["type"] = "journal"  # type: ignore
                            temp["scope"]["journal"] = journal  # type: ignore
                        if "conference" in param_string:
                            param_string, conference = param_string.split("conference=")
                            param_string = param_string.rstrip(" WITH ")
                            conference = conference.strip("'")
                            temp["scope"]["type"] = "conference"  # type: ignore
                            temp["scope"]["conference"] = conference  # type: ignore

                        if "path" in param_string:
                            param_string, path_name = param_string.split("path=")
                            path_name = path_name.strip("'")
                            temp["scope"]["path"] = path_name  # type: ignore
                        source["search_parameters"] = temp

            if "" == source["search_parameters"]:
                source["search_parameters"] = {}

            if "conversion_script" in source:
                source["load_conversion_script"] = source["conversion_script"]
                del source["conversion_script"]
            if "search_script" in source:
                del source["search_script"]
            if "source_prep_scripts" in source:
                del source["source_prep_scripts"]

            if "source_name" in source:
                source["endpoint"] = "colrev_built_in." + source["source_name"]
                del source["source_name"]

                package_endpoint = source["load_conversion_script"]["endpoint"]

                source["load_conversion_package_endpoint"] = {
                    "endpoint": "colrev_built_in." + package_endpoint
                }
                del source["load_conversion_script"]

        for prep_round in settings["prep"]["prep_rounds"]:
            if "scripts" in prep_round:
                prep_round["prep_package_endpoints"] = prep_round["scripts"]
                del prep_round["scripts"]

            prep_round["prep_package_endpoints"] = [
                s
                for s in prep_round["prep_package_endpoints"]
                if s["endpoint"]
                not in ["get_doi_from_sem_scholar", "update_metadata_status"]
            ]

        if "retrieve_forthcoming" not in settings["search"]:
            if "colrev/curated_metadata" in str(self.review_manager.path):
                settings["search"]["retrieve_forthcoming"] = False
            else:
                settings["search"]["retrieve_forthcoming"] = True

        if settings["project"]["review_type"] == "NA":
            if "curated_metadata" in str(self.review_manager.path):
                settings["project"]["review_type"] = "curated_master_data"
            else:
                settings["project"]["review_type"] = "literature_review"

        for prep_round in settings["prep"]["prep_rounds"]:
            prep_round["prep_package_endpoints"] = [
                {"endpoint": s} if "endpoint" not in s and isinstance(str, s) else s
                for s in prep_round["prep_package_endpoints"]
            ]
            prefix_colrev_built_in(prep_round["prep_package_endpoints"])
            # for endpoint in prep_round["prep_package_endpoints"]:
            #     if "colrev_built_in." not in endpoint["endpoint"]:
            #         endpoint["endpoint"] = "colrev_built_in." + endpoint["endpoint"]

        if "man_prep_scripts" in settings["prep"]:
            settings["prep"]["prep_man_package_endpoints"] = settings["prep"][
                "man_prep_scripts"
            ]
            prefix_colrev_built_in(settings["prep"]["prep_man_package_endpoints"])
            del settings["prep"]["man_prep_scripts"]

        if "explanation" not in settings["prescreen"]:
            settings["prescreen"]["explanation"] = ""
        if "scope" in settings["prescreen"]:
            scope_items = settings["prescreen"]["scope"]
            del settings["prescreen"]["scope"]

            if len(scope_items) > 0:

                if "scope_prescreen" not in [
                    s["endpoint"] for s in settings["prescreen"]["scripts"]
                ]:
                    settings["prescreen"].insert(0, {"endpoint": "scope_prescreen"})
                scope_prescreen = [
                    s
                    for s in settings["prescreen"]["scripts"]
                    if s["endpoint"] == "scope_prescreen"
                ][0]
                for elements in scope_items:
                    for scope_key, scope_item in elements.items():
                        scope_prescreen[scope_key] = scope_item

        if "scripts" in settings["prescreen"]:
            settings["prescreen"]["prescreen_package_endpoints"] = settings[
                "prescreen"
            ]["scripts"]
            prefix_colrev_built_in(settings["prescreen"]["prescreen_package_endpoints"])
            del settings["prescreen"]["scripts"]

        if "scripts" in settings["pdf_get"]:
            settings["pdf_get"]["pdf_get_package_endpoints"] = settings["pdf_get"][
                "scripts"
            ]
            prefix_colrev_built_in(settings["pdf_get"]["pdf_get_package_endpoints"])
            del settings["pdf_get"]["scripts"]
        settings["pdf_get"]["pdf_get_package_endpoints"] = [
            s
            for s in settings["pdf_get"]["pdf_get_package_endpoints"]
            if s["endpoint"] != "website_screenshot"
        ]

        if "man_pdf_get_scripts" in settings["pdf_get"]:
            settings["pdf_get"]["pdf_get_man_package_endpoints"] = settings["pdf_get"][
                "man_pdf_get_scripts"
            ]
            prefix_colrev_built_in(settings["pdf_get"]["pdf_get_man_package_endpoints"])
            del settings["pdf_get"]["man_pdf_get_scripts"]

        if "scripts" in settings["pdf_prep"]:
            settings["pdf_prep"]["pdf_prep_package_endpoints"] = settings["pdf_prep"][
                "scripts"
            ]
            prefix_colrev_built_in(settings["pdf_prep"]["pdf_prep_package_endpoints"])
            del settings["pdf_prep"]["scripts"]

        if "man_pdf_prep_scripts" in settings["pdf_prep"]:
            settings["pdf_prep"]["pdf_prep_man_package_endpoints"] = settings[
                "pdf_prep"
            ]["man_pdf_prep_scripts"]
            prefix_colrev_built_in(
                settings["pdf_prep"]["pdf_prep_man_package_endpoints"]
            )
            del settings["pdf_prep"]["man_pdf_prep_scripts"]

        if "scripts" in settings["screen"]:
            settings["screen"]["screen_package_endpoints"] = settings["screen"][
                "scripts"
            ]
            prefix_colrev_built_in(settings["screen"]["screen_package_endpoints"])
            del settings["screen"]["scripts"]

        if "scripts" in settings["data"]:
            settings["data"]["data_package_endpoints"] = settings["data"]["scripts"]
            prefix_colrev_built_in(settings["data"]["data_package_endpoints"])
            del settings["data"]["scripts"]

        if settings["screen"]["criteria"] == []:
            settings["screen"]["criteria"] = {}

        if "scripts" in settings["dedupe"]:
            settings["dedupe"]["dedupe_package_endpoints"] = settings["dedupe"][
                "scripts"
            ]
            prefix_colrev_built_in(settings["dedupe"]["dedupe_package_endpoints"])
            del settings["dedupe"]["scripts"]

        if "rename_pdfs" not in settings["pdf_get"]:
            settings["pdf_get"]["rename_pdfs"] = True

        if "keep_backup_of_pdfs" not in settings["pdf_prep"]:
            settings["pdf_prep"]["keep_backup_of_pdfs"] = True

        if "pdf_required_for_screen_and_synthesis" not in settings["pdf_get"]:
            settings["pdf_get"]["pdf_required_for_screen_and_synthesis"] = True

        if "data_format" in settings["data"]:
            data_scripts = settings["data"]["data_format"]
            del settings["data"]["data_format"]
            settings["data"]["scripts"] = data_scripts

        with open("settings.json", "w", encoding="utf-8") as outfile:
            json.dump(settings, outfile, indent=4)

        self.review_manager.settings = self.review_manager.load_settings()
        self.review_manager.save_settings()
        self.review_manager.dataset.add_setting_changes()

        records = self.review_manager.dataset.load_records_dict()
        if len(records.values()) > 0:
            for record in records.values():
                if "file" in record:
                    if "pdfs" == record["file"][:4]:
                        record["file"] = "data/" + record["file"]

                if "exclusion_criteria" in record:
                    record["screening_criteria"] = (
                        record["exclusion_criteria"]
                        .replace("=no", "=in")
                        .replace("=yes", "=out")
                    )
                    del record["exclusion_criteria"]

            self.review_manager.dataset.save_records_dict(records=records)
            self.review_manager.dataset.add_record_changes()

        for bib_file in self.review_manager.search_dir.glob("*.bib"):
            colrev.env.utils.inplace_change(
                filename=bib_file, old_string="{pdfs/", new_string="{data/pdfs/"
            )
            self.review_manager.dataset.add_changes(
                path=bib_file.relative_to(self.review_manager.path)
            )

        colrev.env.utils.retrieve_package_file(
            template_file=Path("template/.pre-commit-config.yaml"),
            target=Path(".pre-commit-config.yaml"),
        )
        self.review_manager.dataset.add_changes(path=Path(".pre-commit-config.yaml"))

        Path("report.log").unlink(missing_ok=True)

        colrev.env.utils.inplace_change(
            filename=Path(".gitignore"),
            old_string="private_config.ini\n",
            new_string="",
        )
        colrev.env.utils.inplace_change(
            filename=Path(".gitignore"), old_string="data.csv\n", new_string=".tei\n"
        )
        colrev.env.utils.inplace_change(
            filename=Path("settings.json"),
            old_string='"filename": "search',
            new_string='"filename": "data/search',
        )
        for _ in range(0, 5):
            colrev.env.utils.inplace_change(
                filename=Path(".gitignore"),
                old_string="data/data/pdfs\n",
                new_string="data/pdfs\n",
            )
        colrev.env.utils.inplace_change(
            filename=Path(".gitignore"),
            old_string="\npdfs\n",
            new_string="\ndata/pdfs\n",
        )
        self.review_manager.dataset.add_changes(path=Path(".gitignore"))
        self.review_manager.dataset.add_changes(path=Path("settings.json"))

        pdf_dir_old = Path("pdfs")
        pdf_dir_new = Path("data/pdfs")
        if pdf_dir_old.is_dir():
            if pdf_dir_old.is_symlink():
                if not any(pdf_dir_new.iterdir()):
                    pdf_dir_new.rmdir()
                if not pdf_dir_new.is_dir():
                    original_dir = pdf_dir_old.resolve()
                    pdf_dir_new.symlink_to(original_dir, target_is_directory=True)
                    pdf_dir_old.unlink()

        dedupe_dir = Path("dedupe")
        dedupe_dir_new = Path("data/dedupe")
        if dedupe_dir.is_dir():
            copytree(
                dedupe_dir,
                dedupe_dir_new,
                dirs_exist_ok=True,
            )

        print("Manually run \n")
        print(
            "git branch -D backup\n"
            "rm -d -r .git/refs/original\n"
            "git branch backup\n"
            "git filter-branch --tree-filter 'if [ -f records.bib ]; \\n"
            "then mkdir -p data && mv records.bib data/records.bib; fi' HEAD\n"
            "rm -d -r .git/refs/original\n\n\n"
            "git branch -D backup\n"
            "rm -d -r .git/refs/original\n"
            "git branch backup \n"
            "git filter-branch --tree-filter 'if [ -d search ]; \\n"
            "then mkdir -p data/search && mv search/* data/search; fi' HEAD\n"
            "rm -d -r .git/refs/original\n"
        )

        # git branch backup
        # git filter-branch --tree-filter 'if [ -f references.bib ];
        # then mv references.bib records.bib; fi' HEAD
        # rm -d -r .git/refs/original
        # # DO NOT REPLACE IN SETTINGS.json (or in records.bib/references.bib/...)
        # (some search sources may be named "references.bib")
        # git filter-branch --tree-filter
        # "find . \( -name **.md -o -name .pre-commit-config.yaml \)
        # -exec sed -i -e \ 's/references.bib/records.bib/g' {} \;"

    def __migrate_0_6_0(self) -> None:
        # pylint: disable=too-many-statements
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-locals

        if not Path("settings.json").is_file():
            filedata = colrev.env.utils.get_package_file_content(
                file_path=Path("template/settings.json")
            )

            if not filedata:
                print("error reading file")
                return
            settings = json.loads(filedata.decode("utf-8"))
        else:
            with open("settings.json", encoding="utf-8") as file:
                settings = json.load(file)

        for source in settings["sources"]:
            if source["endpoint"] == "colrev_built_in.pdfs_dir":
                if "scope" in source["search_parameters"]:
                    if "path" in source["search_parameters"]["scope"]:
                        if source["search_parameters"]["scope"]["path"] == "pdfs":
                            source["search_parameters"]["scope"]["path"] = "data/pdfs"

        if "curation_url" in settings["project"]:
            if settings["project"]["curation_url"] is not None:
                records = self.review_manager.dataset.load_records_dict()
                example_record = {
                    "ENTRYTYPE": "article",
                    "journal": "TODO",
                    "volume": True,
                    "number": True,
                }
                min_date = 3000
                for record in records.values():
                    if record[
                        "colrev_status"
                    ] in colrev.record.RecordState.get_post_x_states(
                        state=colrev.record.RecordState.md_processed
                    ):
                        example_record = record
                    if record.get("year", "3000").isdigit():
                        if int(record.get("year", "3000")) < min_date:
                            min_date = int(record["year"])
                if min_date == 3000:
                    min_date = 1900

                curation_endpoint = {
                    "endpoint": "colrev_built_in.colrev_curation",
                    "curation_url": settings["project"]["curation_url"],
                    "curated_masterdata": settings["project"].get(
                        "curated_masterdata", False
                    ),
                    "masterdata_restrictions": {
                        min_date: {
                            "ENTRYTYPE": example_record["ENTRYTYPE"],
                            "volume": bool("volume" in example_record),
                            "number": bool("number" in example_record),
                        }
                    },
                    "curated_fields": settings["project"].get("curated_fields", []),
                }
                if "journal" in example_record:
                    curation_endpoint["masterdata_restrictions"][min_date][
                        "journal"
                    ] = example_record["journal"]
                if "booktitle" in example_record:
                    curation_endpoint["masterdata_restrictions"][min_date][
                        "booktitle"
                    ] = example_record["booktitle"]

                settings["data"]["data_package_endpoints"].append(curation_endpoint)
            del settings["project"]["curation_url"]
            del settings["project"]["curated_masterdata"]
            del settings["project"]["curated_fields"]
            self.review_manager.logger.info(
                "If masterdata_restrictions changed over time, "
                "the settings need to be adapted manually."
            )

        if "curated_metadata" in str(self.review_manager.path):
            for prep_round in settings["prep"]["prep_rounds"]:
                prep_round["prep_package_endpoints"] = [
                    s
                    for s in prep_round["prep_package_endpoints"]
                    if s["endpoint"]
                    not in [
                        "colrev_built_in.prep_curated",
                        "colrev_built_in.get_doi_from_urls",
                        "colrev_built_in.get_masterdata_from_doi",
                        "colrev_built_in.get_masterdata_from_crossref",
                        "colrev_built_in.get_masterdata_from_dblp",
                        "colrev_built_in.get_masterdata_from_open_library",
                        "colrev_built_in.get_year_from_vol_iss_jour_crossref",
                        "colrev_built_in.get_record_from_local_index",
                        "colrev_built_in.get_year_from_vol_iss_jour_crossref",
                    ]
                ]
                if "exclusion" == prep_round["name"]:
                    if "colrev_built_in.exclude_complementary_materials" not in [
                        p["endpoint"] for p in prep_round["prep_package_endpoints"]
                    ]:
                        prep_round["prep_package_endpoints"].append(
                            {
                                "endpoint": "colrev_built_in.exclude_complementary_materials"
                            }
                        )

        for search_source in settings["sources"]:
            if "source_identifier" in search_source:
                del search_source["source_identifier"]

        if "curated_metadata" in str(self.review_manager.path):
            settings["prep"]["prep_rounds"] = [
                {
                    "name": "prep",
                    "similarity": 0.8,
                    "prep_package_endpoints": [
                        {"endpoint": "colrev_built_in.resolve_crossrefs"},
                        {"endpoint": "colrev_built_in.source_specific_prep"},
                        {"endpoint": "colrev_built_in.exclude_non_latin_alphabets"},
                        {"endpoint": "colrev_built_in.exclude_collections"},
                        {"endpoint": "colrev_built_in.exclude_complementary_materials"},
                        {"endpoint": "colrev_built_in.exclude_languages"},
                        {"endpoint": "colrev_built_in.remove_urls_with_500_errors"},
                        {"endpoint": "colrev_built_in.remove_broken_ids"},
                        {"endpoint": "colrev_built_in.global_ids_consistency_check"},
                        {"endpoint": "colrev_built_in.get_doi_from_urls"},
                        {"endpoint": "colrev_built_in.get_year_from_vol_iss_jour"},
                    ],
                }
            ]
        else:
            settings["prep"]["prep_rounds"] = [
                {
                    "name": "prep",
                    "similarity": 0.8,
                    "prep_package_endpoints": [
                        {"endpoint": "colrev_built_in.resolve_crossrefs"},
                        {"endpoint": "colrev_built_in.source_specific_prep"},
                        {"endpoint": "colrev_built_in.exclude_non_latin_alphabets"},
                        {"endpoint": "colrev_built_in.exclude_collections"},
                        {"endpoint": "colrev_built_in.exclude_complementary_materials"},
                        {"endpoint": "colrev_built_in.get_masterdata_from_local_index"},
                        {"endpoint": "colrev_built_in.exclude_languages"},
                        {"endpoint": "colrev_built_in.remove_urls_with_500_errors"},
                        {"endpoint": "colrev_built_in.remove_broken_ids"},
                        {"endpoint": "colrev_built_in.global_ids_consistency_check"},
                        {"endpoint": "colrev_built_in.get_doi_from_urls"},
                        {"endpoint": "colrev_built_in.get_year_from_vol_iss_jour"},
                        {"endpoint": "colrev_built_in.get_masterdata_from_crossref"},
                        {"endpoint": "colrev_built_in.get_masterdata_from_europe_pmc"},
                        {"endpoint": "colrev_built_in.get_masterdata_from_dblp"},
                        {
                            "endpoint": "colrev_built_in.get_masterdata_from_open_library"
                        },
                    ],
                }
            ]

        with open("settings.json", "w", encoding="utf-8") as outfile:
            json.dump(settings, outfile, indent=4)

        colrev.env.utils.inplace_change(
            filename=Path("settings.json"),
            old_string='"get_year_from_vol_iss_jour_crossref"',
            new_string='"get_year_from_vol_iss_jour"',
        )

        self.review_manager.dataset.add_changes(path=Path("settings.json"))

        self.review_manager.settings = self.review_manager.load_settings()

        prep_operation = self.review_manager.get_prep_operation(
            retrieval_similarity=0.9
        )

        self.review_manager.logger.info("Create/link local-index metadata")
        # pylint: disable=import-outside-toplevel
        import colrev.ops.built_in.search_sources.local_index as local_index_connector

        local_index_source = local_index_connector.LocalIndexSearchSource(
            source_operation=prep_operation
        )
        records = self.review_manager.dataset.load_records_dict()
        if not self.review_manager.settings.is_curated_masterdata_repo():
            for record_dict in tqdm(records.values()):
                if "CURATED" not in record_dict.get("colrev_masterdata_provenance", {}):
                    pass
                if not any(
                    o.startswith("md_local_index.bib")
                    for o in record_dict["colrev_origin"]
                ):
                    prev_status = record_dict["colrev_status"]

                    local_index_source.get_masterdata(
                        prep_operation=prep_operation,
                        record=colrev.record.Record(data=record_dict),
                    )
                    record_dict["colrev_status"] = prev_status

        self.review_manager.dataset.save_records_dict(records=records)

        local_index = self.review_manager.get_local_index()
        for search_source in self.review_manager.settings.sources:
            if search_source.endpoint != "colrev_built_in.local_index":
                continue
            curation_recs = self.review_manager.dataset.load_records_dict(
                file_path=search_source.filename
            )
            for record_id in list(curation_recs.keys()):
                if "curation_ID" not in curation_recs[record_id]:
                    try:
                        retrieved_record_dict = local_index.retrieve(
                            record_dict=curation_recs[record_id], include_file=False
                        )
                        del retrieved_record_dict["colrev_status"]
                        curation_recs[record_id] = retrieved_record_dict
                    except colrev_exceptions.RecordNotInIndexException:
                        continue
            self.review_manager.dataset.save_records_dict_to_file(
                records=curation_recs, save_path=search_source.filename
            )
            self.review_manager.dataset.add_changes(path=search_source.filename)

        if any(
            "colrev_built_in.get_masterdata_from_crossref" == x["endpoint"]
            for r in self.review_manager.settings.prep.prep_rounds
            for x in r.prep_package_endpoints
        ):
            # pylint: disable=import-outside-toplevel
            import colrev.ops.built_in.search_sources.crossref as crossref_connector

            crossref_source = crossref_connector.CrossrefSearchSource(
                source_operation=prep_operation
            )

            self.review_manager.logger.info("Create/link crossref metadata")
            for record_dict in tqdm(records.values()):
                # for masterdata-curated repositories:
                # record_dict["colrev_origin"] = [
                #     o for o in record_dict["colrev_origin"] if not o.startswith("CROSSREF")
                # ]
                if "doi" in record_dict:
                    if not any(
                        o.startswith("md_crossref.bib/")
                        for o in record_dict["colrev_origin"]
                    ):
                        prev_status = record_dict["colrev_status"]
                        crossref_source.get_masterdata(
                            prep_operation=prep_operation,
                            record=colrev.record.Record(data=record_dict),
                        )
                        if (
                            colrev.record.RecordState.md_prepared
                            == record_dict["colrev_status"]
                        ):
                            record_dict["colrev_status"] = prev_status

        for record_dict in records.values():
            if "colrev_id" in record_dict:
                del record_dict["colrev_id"]
            if self.review_manager.settings.is_curated_masterdata_repo():
                if "cited_by" in record_dict:
                    record = colrev.record.Record(data=record_dict)
                    record.remove_field(key="cited_by")

        self.review_manager.dataset.save_records_dict(records=records)

        self.review_manager.update_status_yaml()

        for bib_file in self.review_manager.DATA_DIR_RELATIVE.glob("**/*.bib"):
            colrev.env.utils.inplace_change(
                filename=bib_file,
                old_string="CURATED:https://github.com/geritwagner",
                new_string="CURATED:https://github.com/CoLRev-curations",
            )
            self.review_manager.dataset.add_changes(path=bib_file)

    def __migrate_0_7_0(self) -> None:
        pass


if __name__ == "__main__":
    pass
