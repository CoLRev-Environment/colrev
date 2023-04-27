#!/usr/bin/env python3
"""Upgrades CoLRev projects."""
from __future__ import annotations

import json
import shutil
import typing
from importlib.metadata import version
from pathlib import Path

import git
from tqdm import tqdm

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.ui_cli.cli_colors as colors

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.review_manager


# pylint: disable=too-few-public-methods


class Upgrade(colrev.operation.Operation):
    """Upgrade a CoLRev project"""

    repo: git.Repo

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
    ) -> None:
        prev_force_mode = review_manager.force_mode
        review_manager.force_mode = True
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.check,
            notify_state_transition_operation=False,
        )
        review_manager.force_mode = prev_force_mode
        self.review_manager = review_manager

    def __move_file(self, source: Path, target: Path) -> None:
        target.parent.mkdir(exist_ok=True, parents=True)
        if source.is_file():
            shutil.move(str(source), self.review_manager.path / target)
            self.repo.index.remove([str(source)])
            self.repo.index.add([str(target)])

    def __load_settings_dict(self) -> dict:
        if not self.review_manager.settings_path.is_file():
            raise colrev_exceptions.CoLRevException()
        with open(self.review_manager.settings_path, encoding="utf-8") as file:
            settings = json.load(file)
        return settings

    def __save_settings(self, settings: dict) -> None:
        with open("settings.json", "w", encoding="utf-8") as outfile:
            json.dump(settings, outfile, indent=4)
        self.repo.index.add(["settings.json"])

    def main(self) -> None:
        """Upgrade a CoLRev project (main entrypoint)"""

        try:
            self.repo = git.Repo(str(self.review_manager.path))
            self.repo.iter_commits()
        except ValueError:
            # Git repository has no initial commit
            return

        settings = self.__load_settings_dict()
        settings_version_str = settings["project"]["colrev_version"]

        settings_version = CoLRevVersion(settings_version_str)
        # Start with the first step if the version is older:
        if settings_version < CoLRevVersion("0.7.0"):
            settings_version = CoLRevVersion("0.7.0")
        installed_colrev_version = CoLRevVersion(version("colrev"))

        if installed_colrev_version == settings_version:
            return

        # version: indicates from which version on the migration should be applied
        migration_scripts: typing.List[typing.Dict[str, typing.Any]] = [
            {
                "version": CoLRevVersion("0.7.0"),
                "script": self.__migrate_0_7_0,
                "released": True,
            },
            {
                "version": CoLRevVersion("0.7.1"),
                "script": self.__migrate_0_7_1,
                "released": True,
            },
            # Note : we may add a flag to update to pre-released versions
            {
                "version": CoLRevVersion("0.8.0"),
                "target_version": CoLRevVersion("0.8.1"),
                "script": self.__migrate_0_8_0,
                "released": True,
            },
            {
                "version": CoLRevVersion("0.8.1"),
                "target_version": CoLRevVersion("0.8.2"),
                "script": self.__migrate_0_8_1,
                "released": True,
            },
            {
                "version": CoLRevVersion("0.8.2"),
                "target_version": CoLRevVersion("0.8.3"),
                "script": self.__migrate_0_8_2,
                "released": True,
            },
        ]

        # Note: we should always update the colrev_version in settings.json because the
        # checker.__check_software requires the settings version and
        # the installed version to be identical

        # skipping_versions_before_settings_version = True
        run_migration = False
        while migration_scripts:
            migrator = migration_scripts.pop(0)
            # Activate run_migration for the current settings_version
            if (
                settings_version == migrator["version"]
            ):  # settings_version == migrator["version"] or
                run_migration = True
            if not run_migration:
                continue

            migration_script = migrator["script"]
            self.review_manager.logger.info(
                "Upgrade to: %s", migrator["target_version"]
            )
            if migrator["released"]:
                self.__print_release_notes(selected_version=migrator["target_version"])

            updated = migration_script()
            if not updated:
                continue

        settings = self.__load_settings_dict()
        settings["project"]["colrev_version"] = str(installed_colrev_version)
        self.__save_settings(settings)

        if self.repo.is_dirty():
            msg = f"Upgrade to CoLRev {installed_colrev_version}"
            if not migrator["released"]:
                msg += " (pre-release)"
            review_manager = colrev.review_manager.ReviewManager()
            review_manager.create_commit(
                msg=msg,
            )

    def __print_release_notes(self, *, selected_version: CoLRevVersion) -> None:
        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("../CHANGELOG.md")
        )
        active, printed = False, False
        if filedata:
            for line in filedata.decode("utf-8").split("\n"):
                if str(selected_version) in line:
                    active = True
                    print(f"{colors.ORANGE}Release notes v{selected_version}")
                    continue
                if line.startswith("## "):
                    active = False
                if active:
                    print(line)
                    printed = True
        if not printed:
            print(f"{colors.ORANGE}No release notes")
        print(f"{colors.END}")

    def __migrate_0_7_0(self) -> bool:
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

    def __migrate_0_7_1(self) -> bool:
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

        self.__move_file(
            source=Path("data/paper.md"), target=Path("data/data/paper.md")
        )
        self.__move_file(
            source=Path("data/APA-7.docx"), target=Path("data/data/APA-7.docx")
        )
        self.__move_file(
            source=Path("data/non_sample_references.bib"),
            target=Path("data/data/non_sample_references.bib"),
        )

        return self.repo.is_dirty()

    def __migrate_0_8_0(self) -> bool:
        Path(".github/workflows/").mkdir(exist_ok=True, parents=True)

        if "colrev/curated_metadata" in str(self.review_manager.path):
            Path(".github/workflows/colrev_update.yml").unlink(missing_ok=True)
            colrev.env.utils.retrieve_package_file(
                template_file=Path("template/init/colrev_update_curation.yml"),
                target=Path(".github/workflows/colrev_update.yml"),
            )
            self.repo.index.add([".github/workflows/colrev_update.yml"])
        else:
            Path(".github/workflows/colrev_update.yml").unlink(missing_ok=True)
            colrev.env.utils.retrieve_package_file(
                template_file=Path("template/init/colrev_update.yml"),
                target=Path(".github/workflows/colrev_update.yml"),
            )
            self.repo.index.add([".github/workflows/colrev_update.yml"])

        Path(".github/workflows/pre-commit.yml").unlink(missing_ok=True)
        colrev.env.utils.retrieve_package_file(
            template_file=Path("template/init/pre-commit.yml"),
            target=Path(".github/workflows/pre-commit.yml"),
        )
        self.repo.index.add([".github/workflows/pre-commit.yml"])
        return self.repo.is_dirty()

    def __migrate_0_8_1(self) -> bool:
        Path(".github/workflows/").mkdir(exist_ok=True, parents=True)
        if "colrev/curated_metadata" in str(self.review_manager.path):
            Path(".github/workflows/colrev_update.yml").unlink(missing_ok=True)
            colrev.env.utils.retrieve_package_file(
                template_file=Path("template/init/colrev_update_curation.yml"),
                target=Path(".github/workflows/colrev_update.yml"),
            )
            self.repo.index.add([".github/workflows/colrev_update.yml"])
        else:
            Path(".github/workflows/colrev_update.yml").unlink(missing_ok=True)
            colrev.env.utils.retrieve_package_file(
                template_file=Path("template/init/colrev_update.yml"),
                target=Path(".github/workflows/colrev_update.yml"),
            )
            self.repo.index.add([".github/workflows/colrev_update.yml"])

        settings = self.__load_settings_dict()
        settings["project"]["auto_upgrade"] = True
        self.__save_settings(settings)

        return self.repo.is_dirty()

    def __migrate_0_8_2(self) -> bool:
        records = self.review_manager.dataset.load_records_dict()

        for record_dict in tqdm(records.values()):
            if "colrev_pdf_id" not in record_dict:
                continue
            if not record_dict["colrev_pdf_id"].startswith("cpid1:"):
                continue
            if not Path(record_dict.get("file", "")).is_file():
                continue

            pdf_path = Path(record_dict["file"])
            colrev_pdf_id = colrev.record.Record.get_colrev_pdf_id(pdf_path=pdf_path)
            record_dict["colrev_pdf_id"] = colrev_pdf_id

        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()

        return self.repo.is_dirty()


class CoLRevVersion:
    """Class for handling the CoLRev version"""

    def __init__(self, version_string: str) -> None:
        if "+" in version_string:
            version_string = version_string[: version_string.find("+")]

        self.major = version_string[: version_string.find(".")]
        self.minor = version_string[
            version_string.find(".") + 1 : version_string.rfind(".")
        ]
        self.patch = version_string[version_string.rfind(".") + 1 :]

    def __eq__(self, other) -> bool:  # type: ignore
        return str(self) == str(other)

    def __lt__(self, other) -> bool:  # type: ignore
        if self.major < other.major:
            return True
        if self.minor < other.minor:
            return True
        if self.patch < other.patch:
            return True
        return False

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


if __name__ == "__main__":
    pass
