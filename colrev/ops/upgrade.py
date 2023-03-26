#!/usr/bin/env python3
"""Upgrades CoLRev projects."""
from __future__ import annotations

import shutil
import typing
from importlib.metadata import version
from pathlib import Path

import colrev.env.utils
import colrev.operation
import colrev.ui_cli.cli_colors as colors

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

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

    def __move_file(self, source: Path, target: Path) -> None:
        target.parent.mkdir(exist_ok=True, parents=True)
        if source.is_file():
            shutil.move(str(source), self.review_manager.path / target)
            self.review_manager.dataset.add_changes(path=source, remove=True)
            self.review_manager.dataset.add_changes(path=target)

    def main(self) -> None:
        """Upgrade a CoLRev project (main entrypoint)"""

        (
            settings_version_str,
            _,
        ) = self.review_manager.get_colrev_versions()

        settings_version = CoLRevVersion(settings_version_str)

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
                "script": self.__migrate_0_8_0,
                "released": True,
            },
            {
                "version": CoLRevVersion("0.9.0"),
                "script": self.__migrate_0_9_0,
                "released": False,
            },
        ]

        if settings_version == migration_scripts[-1]["version"]:
            return

        # self.review_manager.logger.info(
        #     "Current CoLRev repository version: %s", settings_version
        # )

        # Start with the first step if the version is older:
        if settings_version not in [x["version"] for x in migration_scripts]:
            settings_version = CoLRevVersion("0.7.0")

        skipping_versions_before_settings_version = True
        while migration_scripts:
            migrator = migration_scripts.pop(0)

            if (
                migrator["version"] != settings_version
                and skipping_versions_before_settings_version
            ):
                continue
            skipping_versions_before_settings_version = False

            migration_script = migrator["script"]

            updated = migration_script()
            if not updated:
                continue
            self.review_manager.logger.info("Update to: %s", migrator["version"])
            if migrator["released"]:
                self.__print_release_notes(selected_version=migrator["version"])

        self.review_manager.load_settings()
        self.review_manager.settings.project.colrev_version = version("colrev")
        self.review_manager.save_settings()

        if self.review_manager.dataset.has_changes():
            msg = str(migrator["version"])
            if not migrator["released"]:
                msg += " (pre-release)"
            self.review_manager.create_commit(
                msg=f"Upgrade to CoLRev {msg}",
            )

    def __print_release_notes(self, *, selected_version: CoLRevVersion) -> None:
        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("../CHANGELOG.md")
        )
        active = False
        if filedata:
            for line in filedata.decode("utf-8").split("\n"):
                if str(selected_version) in line:
                    active = True
                    print(f"{colors.ORANGE}Release notes v{selected_version}")
                    continue
                if "### [" in line and str(selected_version) not in line:
                    active = False
                if active:
                    print(line)
        if not active:
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
        self.review_manager.dataset.add_changes(path=Path(".pre-commit-config.yaml"))
        return self.review_manager.dataset.has_changes()

    def __migrate_0_7_1(self) -> bool:
        settings_content = (self.review_manager.path / Path("settings.json")).read_text(
            encoding="utf-8"
        )
        settings_content = settings_content.replace("colrev_built_in.", "colrev.")

        with open(Path("settings.json"), "w", encoding="utf-8") as file:
            file.write(settings_content)

        self.review_manager.dataset.add_changes(path=Path("settings.json"))
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

        return self.review_manager.dataset.has_changes()

    def __migrate_0_8_0(self) -> bool:
        Path(".github/workflows/").mkdir(exist_ok=True, parents=True)
        if self.review_manager.settings.is_curated_masterdata_repo():
            Path(".github/workflows/colrev_update.yml").unlink(missing_ok=True)
            colrev.env.utils.retrieve_package_file(
                template_file=Path("template/init/colrev_update_curation.yml"),
                target=Path(".github/workflows/colrev_update.yml"),
            )
            self.review_manager.dataset.add_changes(
                path=Path(".github/workflows/colrev_update.yml")
            )
        else:
            Path(".github/workflows/colrev_update.yml").unlink(missing_ok=True)
            colrev.env.utils.retrieve_package_file(
                template_file=Path("template/init/colrev_update.yml"),
                target=Path(".github/workflows/colrev_update.yml"),
            )
            self.review_manager.dataset.add_changes(
                path=Path(".github/workflows/colrev_update.yml")
            )

        Path(".github/workflows/pre-commit.yml").unlink(missing_ok=True)
        colrev.env.utils.retrieve_package_file(
            template_file=Path("template/init/pre-commit.yml"),
            target=Path(".github/workflows/pre-commit.yml"),
        )
        self.review_manager.dataset.add_changes(
            path=Path(".github/workflows/pre-commit.yml")
        )
        return self.review_manager.dataset.has_changes()

    def __migrate_0_9_0(self) -> bool:
        print("Nothing to do (yet).")
        return self.review_manager.dataset.has_changes()


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
