#!/usr/bin/env python3
"""Upgrades CoLRev projects."""
from __future__ import annotations

import typing
from importlib.metadata import version
from pathlib import Path

import colrev.env.utils
import colrev.operation

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
            {"from": "0.7.0", "to": "0.7.1", "script": self.__migrate_0_7_0},
            {"from": "0.7.1", "to": upcoming_version, "script": self.__migrate_0_7_1},
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

        self.review_manager.settings.project.colrev_version = version("colrev")
        self.review_manager.save_settings()

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

    def __migrate_0_7_0(self) -> None:
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

    def __migrate_0_7_1(self) -> None:
        settings_content = (self.review_manager.path / Path("settings.json")).read_text(
            encoding="utf-8"
        )
        settings_content = settings_content.replace("colrev_built_in.", "colrev.")
        with open(
            (self.review_manager.path / Path("settings.json")), "w", encoding="utf-8"
        ) as file:
            file.write(settings_content)

        self.review_manager.dataset.add_changes(
            path=(self.review_manager.path / Path("settings.json"))
        )


if __name__ == "__main__":
    pass
