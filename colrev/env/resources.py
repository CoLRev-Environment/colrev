#! /usr/bin/env python
"""Install curated CoLRev resources."""
from __future__ import annotations

from pathlib import Path

import git

import colrev.env.environment_manager
import colrev.process.operation
import colrev.record.record


class Resources:
    """Class for curated CoLRev resourcs (metadata repositories, annotators)"""

    # pylint: disable=too-few-public-methods
    curations_path = Path.home().joinpath("colrev/curated_metadata")

    def install_curated_resource(self, *, curated_resource: str) -> bool:
        """Install a curated resource"""

        if "http" not in curated_resource:
            curated_resource = "https://github.com/" + curated_resource
        self.curations_path.mkdir(exist_ok=True, parents=True)
        repo_dir = self.curations_path / Path(curated_resource.split("/")[-1])
        if repo_dir.is_dir():
            print(f"Repo already exists ({repo_dir})")
            return False
        print(f"Download curated resource from {curated_resource}")
        git.Repo.clone_from(curated_resource, repo_dir, depth=1)

        environment_manager = colrev.env.environment_manager.EnvironmentManager()
        if (repo_dir / Path("data/records.bib")).is_file():
            environment_manager.register_repo(repo_dir)
        elif (repo_dir / Path("readme.md")).is_file():
            text = Path(repo_dir / "readme.md").read_text(encoding="utf-8")
            for line in [x for x in text.splitlines() if "colrev env --install" in x]:
                if line.endswith(curated_resource.replace("https://github.com/", "")):
                    continue
                self.install_curated_resource(
                    curated_resource=line.replace("colrev env --install ", "")
                )
        else:
            print(
                f"Error: repo does not contain a data/records.bib or linked repos {repo_dir}"
            )
        return True
