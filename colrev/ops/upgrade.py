#!/usr/bin/env python3
"""Upgrades CoLRev projects."""
from __future__ import annotations

import json
import re
import shutil
import typing
from importlib.metadata import version
from pathlib import Path

import git
import pandas as pd
from tqdm import tqdm
from yaml import safe_load

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.process.operation
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import Filepaths
from colrev.constants import OperationsType
from colrev.constants import RecordState
from colrev.writer.write_utils import to_string

# pylint: disable=too-few-public-methods


class Upgrade(colrev.process.operation.Operation):
    """Upgrade a CoLRev project"""

    repo: git.Repo

    type = OperationsType.check

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
    ) -> None:
        prev_force_mode = review_manager.force_mode
        review_manager.force_mode = True
        super().__init__(
            review_manager=review_manager,
            operations_type=self.type,
            notify_state_transition_operation=False,
        )
        review_manager.force_mode = prev_force_mode
        self.review_manager = review_manager

    def _move_file(self, source: Path, target: Path) -> None:
        target.parent.mkdir(exist_ok=True, parents=True)
        if source.is_file():
            shutil.move(str(source), str(self.review_manager.path / target))
            self.repo.index.remove([str(source)])
            self.repo.index.add([str(target)])

    def _load_settings_dict(self) -> dict:
        settings_path = self.review_manager.paths.settings
        if not settings_path.is_file():
            raise colrev_exceptions.CoLRevException()
        with open(settings_path, encoding="utf-8") as file:
            settings = json.load(file)
        return settings

    def _save_settings(self, settings: dict) -> None:
        with open("settings.json", "w", encoding="utf-8") as outfile:
            json.dump(settings, outfile, indent=4)
        self.repo.index.add(["settings.json"])

    def load_records_dict(self) -> dict:
        """
        Load the records dictionary from a file and parse it using the bibtex parser.

        Returns:
            dict: The loaded records dictionary.
        """
        records = colrev.loader.load_utils.load(
            filename=Path("data/records.bib"),
            logger=self.review_manager.logger,
        )

        return records

    def save_records_dict(self, records: dict) -> None:
        """
        Save the records dictionary to a file and add it to the repository index.

        Args:
            records (dict): The records dictionary to save.
        """
        bibtex_str = to_string(records_dict=records, implementation="bib")
        with open("data/records.bib", "w", encoding="utf-8") as out:
            out.write(bibtex_str + "\n")
        self.repo.index.add(["data/records.bib"])

    def main(self) -> None:
        """Upgrade a CoLRev project (main entrypoint)"""

        try:
            self.repo = git.Repo(str(self.review_manager.path))
            self.repo.iter_commits()
        except ValueError:
            # Git repository has no initial commit
            return

        settings = self._load_settings_dict()
        settings_version_str = settings["project"]["colrev_version"]

        settings_version = CoLRevVersion(settings_version_str)
        # Start with the first step if the version is older:
        settings_version = max(settings_version, CoLRevVersion("0.7.0"))
        installed_colrev_version = CoLRevVersion(version("colrev"))

        # version: indicates from which version on the migration should be applied
        migration_scripts: typing.List[typing.Dict[str, typing.Any]] = [
            {
                "version": CoLRevVersion("0.7.0"),
                "target_version": CoLRevVersion("0.7.1"),
                "script": self._migrate_0_7_0,
                "released": True,
            },
            {
                "version": CoLRevVersion("0.7.1"),
                "target_version": CoLRevVersion("0.8.0"),
                "script": self._migrate_0_7_1,
                "released": True,
            },
            # Note : we may add a flag to update to pre-released versions
            {
                "version": CoLRevVersion("0.8.0"),
                "target_version": CoLRevVersion("0.8.1"),
                "script": self._migrate_0_8_0,
                "released": True,
            },
            {
                "version": CoLRevVersion("0.8.1"),
                "target_version": CoLRevVersion("0.8.2"),
                "script": self._migrate_0_8_1,
                "released": True,
            },
            {
                "version": CoLRevVersion("0.8.2"),
                "target_version": CoLRevVersion("0.8.3"),
                "script": self._migrate_0_8_2,
                "released": True,
            },
            {
                "version": CoLRevVersion("0.8.3"),
                "target_version": CoLRevVersion("0.8.4"),
                "script": self._migrate_0_8_3,
                "released": True,
            },
            {
                "version": CoLRevVersion("0.8.4"),
                "target_version": CoLRevVersion("0.9.0"),
                "script": self._migrate_0_8_4,
                "released": True,
            },
            {
                "version": CoLRevVersion("0.9.0"),
                "target_version": CoLRevVersion("0.9.1"),
                "script": self._migrate_0_9_1,
                "released": True,
            },
            {
                "version": CoLRevVersion("0.9.2"),
                "target_version": CoLRevVersion("0.9.3"),
                "script": self._migrate_0_9_3,
                "released": True,
            },
            {
                "version": CoLRevVersion("0.10.0"),
                "target_version": CoLRevVersion("0.10.1"),
                "script": self._migrate_0_10_1,
                "released": True,
            },
            {
                "version": CoLRevVersion("0.10.1"),
                "target_version": CoLRevVersion("0.10.2"),
                "script": self._migrate_0_10_2,
                "released": True,
            },
            {
                "version": CoLRevVersion("0.10.2"),
                "target_version": CoLRevVersion("0.11.0"),
                "script": self._migrate_0_11_0,
                "released": True,
            },
            {
                "version": CoLRevVersion("0.11.0"),
                "target_version": CoLRevVersion("0.12.0"),
                "script": self._migrate_0_12_0,
                "released": True,
            },
        ]
        print(f"installed_colrev_version: {installed_colrev_version}")
        print(f"settings_version: {settings_version}")
        # Note: we should always update the colrev_version in settings.json because the
        # checker._check_software requires the settings version and
        # the installed version to be identical

        # skipping_versions_before_settings_version = True
        run_migration = False
        while migration_scripts:
            migrator = migration_scripts.pop(0)
            # Activate run_migration for the current settings_version
            if (
                migrator["target_version"] >= settings_version
            ):  # settings_version == migrator["version"] or
                run_migration = True
            if not run_migration:
                continue
            if installed_colrev_version == settings_version and migrator["released"]:
                break

            migration_script = migrator["script"]
            self.review_manager.logger.info(
                "Upgrade to: %s", migrator["target_version"]
            )
            if migrator["released"]:
                self._print_release_notes(selected_version=migrator["target_version"])

            updated = migration_script()
            if not updated:
                continue

        if not run_migration:
            print("migration not run")
            return

        settings = self._load_settings_dict()
        settings["project"]["colrev_version"] = str(installed_colrev_version)
        self._save_settings(settings)

        if self.repo.is_dirty():
            msg = f"Upgrade to CoLRev {installed_colrev_version}"
            if not migrator["released"]:
                msg += " (pre-release)"
            review_manager = colrev.review_manager.ReviewManager()
            review_manager.dataset.create_commit(
                msg=msg,
            )

    def _print_release_notes(self, *, selected_version: CoLRevVersion) -> None:
        filedata = colrev.env.utils.get_package_file_content(
            module="colrev", filename=Path("../CHANGELOG.md")
        )
        active, printed = False, False
        if filedata:
            for line in filedata.decode("utf-8").split("\n"):
                if str(selected_version) in line:
                    active = True
                    print(f"{Colors.ORANGE}Release notes v{selected_version}")
                    continue
                if line.startswith("## "):
                    active = False
                if active:
                    print(line)
                    printed = True
        if not printed:
            print(f"{Colors.ORANGE}No release notes")
        print(f"{Colors.END}")

    def _migrate_0_7_0(self) -> bool:
        pre_commit_contents = Path(".pre-commit-config.yaml").read_text(
            encoding="utf-8"
        )
        if "ci:" not in pre_commit_contents:
            pre_commit_contents = pre_commit_contents.replace(
                "repos:",
                "ci:\n    skip: [colrev-hooks-format, colrev-hooks-check]\n\nrepos:",
            )
            with open(".pre-commit-config.yaml", "w", encoding="utf-8") as file:
                file.write(pre_commit_contents)
        self.repo.index.add([".pre-commit-config.yaml"])
        return self.repo.is_dirty()

    def _migrate_0_7_1(self) -> bool:
        settings_content = (self.review_manager.path / Path("settings.json")).read_text(
            encoding="utf-8"
        )
        settings_content = settings_content.replace("colrev_built_in.", "colrev.")

        with open(Path("settings.json"), "w", encoding="utf-8") as file:
            file.write(settings_content)

        self.repo.index.add(["settings.json"])
        self.review_manager.load_settings()
        if self.review_manager.settings.is_curated_masterdata_repo():
            self.review_manager.settings.project.delay_automated_processing = False
        self.review_manager.save_settings()

        self._move_file(source=Path("data/paper.md"), target=Path("data/data/paper.md"))
        self._move_file(
            source=Path("data/APA-7.docx"), target=Path("data/data/APA-7.docx")
        )
        self._move_file(
            source=Path("data/non_sample_references.bib"),
            target=Path("data/data/non_sample_references.bib"),
        )

        return self.repo.is_dirty()

    def _migrate_0_8_0(self) -> bool:
        Path(".github/workflows/").mkdir(exist_ok=True, parents=True)

        if "colrev/curated_metadata" in str(self.review_manager.path):
            Path(".github/workflows/colrev_update.yml").unlink(missing_ok=True)
            colrev.env.utils.retrieve_package_file(
                template_file=Path("ops/init/colrev_update_curation.yml"),
                target=Path(".github/workflows/colrev_update.yml"),
            )
            self.repo.index.add([".github/workflows/colrev_update.yml"])
        else:
            Path(".github/workflows/colrev_update.yml").unlink(missing_ok=True)
            colrev.env.utils.retrieve_package_file(
                template_file=Path("ops/init/colrev_update.yml"),
                target=Path(".github/workflows/colrev_update.yml"),
            )
            self.repo.index.add([".github/workflows/colrev_update.yml"])

        Path(".github/workflows/pre-commit.yml").unlink(missing_ok=True)
        colrev.env.utils.retrieve_package_file(
            template_file=Path("ops/init/pre-commit.yml"),
            target=Path(".github/workflows/pre-commit.yml"),
        )
        self.repo.index.add([".github/workflows/pre-commit.yml"])
        return self.repo.is_dirty()

    def _migrate_0_8_1(self) -> bool:
        Path(".github/workflows/").mkdir(exist_ok=True, parents=True)
        if "colrev/curated_metadata" in str(self.review_manager.path):
            Path(".github/workflows/colrev_update.yml").unlink(missing_ok=True)
            colrev.env.utils.retrieve_package_file(
                template_file=Path("ops/init/colrev_update_curation.yml"),
                target=Path(".github/workflows/colrev_update.yml"),
            )
            self.repo.index.add([".github/workflows/colrev_update.yml"])
        else:
            Path(".github/workflows/colrev_update.yml").unlink(missing_ok=True)
            colrev.env.utils.retrieve_package_file(
                template_file=Path("ops/init/colrev_update.yml"),
                target=Path(".github/workflows/colrev_update.yml"),
            )
            self.repo.index.add([".github/workflows/colrev_update.yml"])

        settings = self._load_settings_dict()
        settings["project"]["auto_upgrade"] = True
        self._save_settings(settings)

        return self.repo.is_dirty()

    def _migrate_0_8_2(self) -> bool:
        records = self.review_manager.dataset.load_records_dict()

        for record_dict in tqdm(records.values()):
            if "colrev_pdf_id" not in record_dict:
                continue
            if not record_dict["colrev_pdf_id"].startswith("cpid1:"):
                continue
            if not Path(record_dict.get("file", "")).is_file():
                continue

            pdf_path = Path(record_dict["file"])
            colrev_pdf_id = colrev.record.record.Record.get_colrev_pdf_id(pdf_path)
            # pylint: disable=colrev-missed-constant-usage
            record_dict["colrev_pdf_id"] = colrev_pdf_id

        self.review_manager.dataset.save_records_dict(records)

        return self.repo.is_dirty()

    def _migrate_0_8_3(self) -> bool:
        # pylint: disable=too-many-branches
        settings = self._load_settings_dict()
        settings["prep"]["defects_to_ignore"] = []
        if "curated_metadata" in str(self.review_manager.path):
            settings["prep"]["defects_to_ignore"] = [
                "record-not-in-toc",
                "inconsistent-with-url-metadata",
            ]
        else:
            settings["prep"]["defects_to_ignore"] = ["inconsistent-with-url-metadata"]

        for p_round in settings["prep"]["prep_rounds"]:
            p_round["prep_package_endpoints"] = [
                x
                for x in p_round["prep_package_endpoints"]
                if x["endpoint"] != "colrev.global_ids_consistency_check"
            ]
        self._save_settings(settings)
        self.review_manager = colrev.review_manager.ReviewManager(
            path_str=str(self.review_manager.path), force_mode=True
        )
        self.review_manager.load_settings()
        self.review_manager.get_load_operation()
        records = self.review_manager.dataset.load_records_dict()
        quality_model = self.review_manager.get_qm()

        # delete the masterdata provenance notes and apply the new quality model
        # replace not_missing > not-missing
        for record_dict in tqdm(records.values()):
            if Fields.MD_PROV not in record_dict:
                continue
            not_missing_fields = []
            for key, prov in record_dict[Fields.MD_PROV].items():
                if "not-missing" in prov["note"]:
                    not_missing_fields.append(key)
                prov["note"] = ""
            for key in not_missing_fields:
                record_dict[Fields.MD_PROV][key]["note"] = "not-missing"
            if "cited_by_file" in record_dict:
                del record_dict["cited_by_file"]
            if "cited_by_id" in record_dict:
                del record_dict["cited_by_id"]
            if "tei_id" in record_dict:
                del record_dict["tei_id"]
            if Fields.D_PROV in record_dict:
                if "cited_by_file" in record_dict[Fields.D_PROV]:
                    del record_dict[Fields.D_PROV]["cited_by_file"]
                if "cited_by_id" in record_dict[Fields.D_PROV]:
                    del record_dict[Fields.D_PROV]["cited_by_id"]
                if "tei_id" in record_dict[Fields.D_PROV]:
                    del record_dict[Fields.D_PROV]["tei_id"]

            record = colrev.record.record.Record(record_dict)
            prior_state = record.data[Fields.STATUS]
            record.run_quality_model(quality_model)
            if prior_state == RecordState.rev_prescreen_excluded:
                record.data[  # pylint: disable=colrev-direct-status-assign
                    Fields.STATUS
                ] = RecordState.rev_prescreen_excluded
        self.review_manager.dataset.save_records_dict(records)
        return self.repo.is_dirty()

    def _migrate_0_8_4(self) -> bool:
        records = self.review_manager.dataset.load_records_dict()
        for record in records.values():
            if Fields.EDITOR not in record.get(Fields.D_PROV, {}):
                continue
            ed_val = record[Fields.D_PROV][Fields.EDITOR]
            del record[Fields.D_PROV][Fields.EDITOR]
            if FieldValues.CURATED not in record[Fields.MD_PROV]:
                record[Fields.MD_PROV][Fields.EDITOR] = ed_val

        self.review_manager.dataset.save_records_dict(records)

        return self.repo.is_dirty()

    def _migrate_0_9_1(self) -> bool:
        settings = self._load_settings_dict()
        for source in settings["sources"]:
            if "load_conversion_package_endpoint" in source:
                del source["load_conversion_package_endpoint"]
        self._save_settings(settings)
        return self.repo.is_dirty()

    # pylint: disable=too-many-branches
    def _migrate_0_9_3(self) -> bool:
        settings = self._load_settings_dict()
        for source in settings["sources"]:
            if source["endpoint"] == "colrev.crossref":
                if Fields.ISSN not in source["search_parameters"].get("scope", {}):
                    continue
                if isinstance(source["search_parameters"]["scope"][Fields.ISSN], str):
                    source["search_parameters"]["scope"][Fields.ISSN] = [
                        source["search_parameters"]["scope"][Fields.ISSN]
                    ]

        self._save_settings(settings)

        records = self.load_records_dict()
        for record_dict in records.values():
            if "pubmedid" in record_dict:
                record = colrev.record.record.Record(record_dict)
                record.rename_field(key="pubmedid", new_key="colrev.pubmed.pubmedid")

            if "pii" in record_dict:
                record = colrev.record.record.Record(record_dict)
                record.rename_field(key="pii", new_key="colrev.pubmed.pii")

            if "pmc" in record_dict:
                record = colrev.record.record.Record(record_dict)
                record.rename_field(key="pmc", new_key="colrev.pubmed.pmc")

            if "label_included" in record_dict:
                record = colrev.record.record.Record(record_dict)
                record.rename_field(
                    key="label_included",
                    new_key="colrev.synergy_datasets.label_included",
                )
            if "method" in record_dict:
                record = colrev.record.record.Record(record_dict)
                record.rename_field(
                    key="method", new_key="colrev.synergy_datasets.method"
                )

            if "dblp_key" in record_dict:
                record = colrev.record.record.Record(record_dict)
                record.rename_field(key="dblp_key", new_key=Fields.DBLP_KEY)
            if "wos_accession_number" in record_dict:
                record = colrev.record.record.Record(record_dict)
                record.rename_field(
                    key="wos_accession_number",
                    new_key=Fields.WEB_OF_SCIENCE_ID,
                )
            if "sem_scholar_id" in record_dict:
                record = colrev.record.record.Record(record_dict)
                record.rename_field(
                    key="sem_scholar_id", new_key=Fields.SEMANTIC_SCHOLAR_ID
                )

            if "openalex_id" in record_dict:
                record = colrev.record.record.Record(record_dict)
                record.rename_field(key="openalex_id", new_key="colrev.open_alex.id")

        self.save_records_dict(records)

        return self.repo.is_dirty()

    # pylint: disable=too-many-branches
    def _migrate_0_10_1(self) -> bool:
        prep_replacements = {
            "colrev.open_alex_prep": "colrev.open_alex",
            "colrev.get_masterdata_from_dblp": "colrev.dblp",
            "colrev.crossref_metadata_prep": "colrev.crossref_metadata_prep",
            "colrev.get_masterdata_from_crossref": "colrev.crossref",
            "colrev.get_masterdata_from_europe_pmc": "colrev.europe_pmc",
            "colrev.get_masterdata_from_pubmed": "colrev.pubmed",
            "colrev.get_masterdata_from_open_library": "colrev.open_library",
            "colrev.curation_prep": "colrev.colrev_curation",
            "colrev.get_masterdata_from_local_index": "colrev.local_index",
        }

        settings = self._load_settings_dict()
        for prep_round in settings["prep"]["prep_rounds"]:
            for prep_package in prep_round["prep_package_endpoints"]:
                for old, new in prep_replacements.items():
                    if prep_package["endpoint"] == old:
                        prep_package["endpoint"] = new
        for source in settings["sources"]:
            if source["endpoint"] == "colrev.pdfs_dir":
                source["endpoint"] = "colrev.files_dir"
            if (
                source["endpoint"] == "colrev.dblp"
                and "scope" in source["search_parameters"]
            ):
                if "query" in source["search_parameters"]:
                    source["search_type"] = "API"
                else:
                    source["search_type"] = "TOC"

            if (
                source["endpoint"] == "colrev.crossref"
                and "scope" in source["search_parameters"]
            ):
                if "query" in source["search_parameters"]:
                    source["search_type"] = "API"
                else:
                    source["search_type"] = "TOC"

            if "data/search/md_" in source["filename"]:
                source["search_type"] = "MD"
            if source["search_type"] == "PDFS":
                source["search_type"] = "FILES"

        self._save_settings(settings)
        return self.repo.is_dirty()

    def _migrate_0_10_2(self) -> bool:
        paper_md_path = Path("data/data/paper.md")
        if paper_md_path.is_file():
            paper_md_content = paper_md_path.read_text(encoding="utf-8")
            paper_md_content = paper_md_content.replace(
                "data/records.bib", "data/data/sample_references.bib"
            )
            paper_md_path.write_text(paper_md_content, encoding="utf-8")
            self.repo.index.add([str(paper_md_path)])

        return self.repo.is_dirty()

    def _migrate_0_11_0(self) -> bool:
        settings = self._load_settings_dict()
        if settings["project"]["review_type"] == "curated_masterdata":
            settings["project"]["review_type"] = "colrev.curated_masterdata"

        if "dedupe" in settings:
            settings["dedupe"].pop("same_source_merges", None)

        settings["pdf_get"]["defects_to_ignore"] = []

        settings["pdf_prep"]["pdf_prep_package_endpoints"] = [
            {"endpoint": "colrev.ocrmypdf"},
            {"endpoint": "colrev.grobid_tei"},
        ] + [
            x
            for x in settings["pdf_prep"]["pdf_prep_package_endpoints"]
            if x["endpoint"]
            not in [
                "colrev.check_ocr",
                "colrev.pdf_check_ocr",
                "colrev.validate_pdf_metadata",
                "colrev.validate_completeness",
                "colrev.create_tei",
                "colrev.tei_prep",
            ]
        ]

        if settings["project"]["review_type"] == "curated_masterdata":
            Path(".github/workflows/colrev_update.yml").unlink(missing_ok=True)
            colrev.env.utils.retrieve_package_file(
                template_file=Path(
                    "packages/review_type/curated_masterdata/curations_github_colrev_update.yml"
                ),
                target=Path(".github/workflows/colrev_update.yml"),
            )
            self.repo.index.add([".github/workflows/colrev_update.yml"])
        else:
            Path(".github/workflows/colrev_update.yml").unlink(missing_ok=True)
            colrev.env.utils.retrieve_package_file(
                template_file=Path("ops/init/colrev_update.yml"),
                target=Path(".github/workflows/colrev_update.yml"),
            )
            self.repo.index.add([".github/workflows/colrev_update.yml"])

        for p_round in settings["prep"]["prep_rounds"]:
            p_round["prep_package_endpoints"] = [
                x
                for x in p_round["prep_package_endpoints"]
                if x["endpoint"] != "colrev.resolve_crossrefs"
            ]
            if settings["project"]["review_type"] == "colrev.curated_masterdata":
                p_round["prep_package_endpoints"] = [
                    {"endpoint": "colrev.colrev_curation"}
                ] + p_round["prep_package_endpoints"]

        self._save_settings(settings)

        records = self.load_records_dict()
        for record_dict in records.values():
            if Fields.MD_PROV in record_dict:
                for key, value in record_dict[Fields.MD_PROV].items():
                    record_dict[Fields.MD_PROV][key]["note"] = value["note"].replace(
                        "not-missing", "IGNORE:missing"
                    )
        self.save_records_dict(records)

        return self.repo.is_dirty()

    def _migrate_0_12_0(self) -> bool:
        registry_yaml = Filepaths.LOCAL_ENVIRONMENT_DIR.joinpath(Path("registry.yaml"))

        def _cast_values_to_str(data) -> dict:  # type: ignore
            result = {}
            for key, value in data.items():
                if isinstance(value, dict):
                    result[key] = _cast_values_to_str(value)
                elif isinstance(value, list):
                    result[key] = [_cast_values_to_str(v) for v in value]  # type: ignore
                else:
                    result[key] = str(value)  # type: ignore
            return result

        if registry_yaml.is_file():
            backup_file = Path(str(registry_yaml) + ".bk")
            print(
                f"Found a yaml file, converting to json, it will be backed up as {backup_file}"
            )
            with open(registry_yaml, encoding="utf8") as file:
                environment_registry_df = pd.json_normalize(safe_load(file))
                repos = environment_registry_df.to_dict("records")
                environment_registry = {
                    "local_index": {
                        "repos": repos,
                    },
                    "packages": {},
                }
                Filepaths.REGISTRY_FILE.parents[0].mkdir(parents=True, exist_ok=True)
                with open(Filepaths.REGISTRY_FILE, "w", encoding="utf8") as file:
                    json.dump(
                        dict(_cast_values_to_str(environment_registry)),
                        indent=4,
                        fp=file,
                    )
                shutil.move(str(registry_yaml), str(backup_file))

        return self.repo.is_dirty()


# Note: we can ask users to make decisions (when defaults are not clear)
# via input() or simply cancel the process (raise a CoLrevException)


class CoLRevVersion:
    """Class for handling the CoLRev version"""

    def __init__(self, version_string: str) -> None:
        if "+" in version_string:
            version_string = version_string[: version_string.find("+")]
        assert re.match(r"\d+\.\d+\.\d+$", version_string)
        self.major = int(version_string[: version_string.find(".")])
        self.minor = int(
            version_string[version_string.find(".") + 1 : version_string.rfind(".")]
        )
        self.patch = int(version_string[version_string.rfind(".") + 1 :])

    def __eq__(self, other) -> bool:  # type: ignore
        return (
            self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
        )

    def __lt__(self, other) -> bool:  # type: ignore
        if self.major < other.major:
            return True
        if self.major == other.major and self.minor < other.minor:
            return True
        if (
            self.major == other.major
            and self.minor == other.minor
            and self.patch < other.patch
        ):
            return True
        return False

    def __ge__(self, other) -> bool:  # type: ignore
        if self.major > other.major:
            return True
        if self.major == other.major and self.minor > other.minor:
            return True
        if (
            self.major == other.major
            and self.minor == other.minor
            and self.patch > other.patch
        ):
            return True
        return False

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"
