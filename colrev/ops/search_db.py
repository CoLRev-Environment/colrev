#! /usr/bin/env python
"""Database search operations"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

import colrev.exceptions as colrev_exceptions
import colrev.search_file
import colrev.utils
from colrev.constants import Colors
from colrev.constants import EndpointType
from colrev.constants import SearchType
from colrev.git_repo import GitRepo
from colrev.package_manager.package_manager import PackageManager


# pylint: disable=too-few-public-methods


class _Paths:
    def __init__(self, root: Path) -> None:
        self.git_ignore = root / ".gitignore"


class _ReviewManagerStub:
    def __init__(self, root: Path) -> None:
        self.path = root
        self.paths = _Paths(root)


# pylint: disable=unused-argument
def run_db_search(
    *,
    db_url: str,
    source: colrev.search_file.ExtendedSearchFile,
    add_to_git: bool = False,
    project_root: typing.Optional[Path] = None,
    **kwargs: typing.Any,
) -> None:
    """Run the database search.

    add_to_git: when True, stage changes via a locally instantiated GitRepo.
    project_root: optional explicit root path; if not provided, derive from the source.
    """
    root = project_root or source.search_results_path.resolve().parents[2]
    review_manager = _ReviewManagerStub(root)
    git = GitRepo(path=review_manager.path)

    if colrev.utils.in_ci_environment():
        raise colrev_exceptions.SearchNotAutomated("DB search not automated.")

    print("DB search (update)")
    print(f"- Go to {Colors.ORANGE}{db_url}{Colors.END} and run the following query:")
    print()
    try:
        print(f"{Colors.ORANGE}{source.search_string}{Colors.END}")
        print()
    except KeyError:
        pass
    print(
        f"- Replace search results in {Colors.ORANGE}"
        + str(source.search_results_path)
        + Colors.END
    )
    input("Press enter to continue")
    if source.search_results_path.is_file():
        if add_to_git:
            git.add_changes(source.search_results_path)
    else:
        print("Search results not found.")


def get_query_filename(
    *,
    filename: Path,
    instantiate: bool = False,
    interactive: bool = False,
    add_to_git: bool = False,
    project_root: typing.Optional[Path] = None,
) -> Path:
    """Get the corresponding filename for the search query"""

    query_filename = Path("data/search/") / Path(f"{filename.stem}_query.txt")
    root = project_root or filename.resolve().parents[2]
    review_manager = _ReviewManagerStub(root)
    git = GitRepo(path=review_manager.path)

    if instantiate:
        with open(query_filename, "w", encoding="utf-8") as file:
            file.write("")
        if interactive:
            input(
                f"Created {Colors.ORANGE}{query_filename}{Colors.END}. "
                "Please store your query in the file and press Enter to continue.",
            )
        if add_to_git:
            git.add_changes(query_filename)
    return query_filename


def create_db_source(
    *,
    platform: str,
    path: Path,
    params: dict,
    add_to_git: bool = True,
    logger: typing.Optional[logging.Logger] = logging.getLogger(__name__),
) -> colrev.search_file.ExtendedSearchFile:
    """Interactively add a DB SearchSource"""

    if not all(x in ["search_file"] for x in list(params)):
        raise NotImplementedError  # or parameter error

    if "search_file" in params:
        filename = Path(params["search_file"])
    else:
        filename = colrev.utils.get_unique_filename(
            base_path=path,
            file_path_string=platform.replace("colrev.", ""),
        )
    logger.debug("Add new DB source: %s", filename)  # type: ignore

    logger.info(  # type: ignore
        "- Save search results in %s", Colors.ORANGE + str(filename) + Colors.END
    )
    input("Press Enter to complete")

    git_repo = GitRepo(path=path)
    if add_to_git:
        git_repo.add_changes(filename, ignore_missing=True)

    search_string = input("Enter search string: ")
    package_manager = PackageManager()
    search_source_class = package_manager.get_package_endpoint_class(
        package_type=EndpointType.search_source,
        package_identifier=platform,
    )
    # pylint: disable=broad-exception-caught
    try:
        version = getattr(search_source_class, "CURRENT_SYNTAX_VERSION", "0.1.0")
    except Exception:  # pragma: no cover - fall back to default
        version = "0.1.0"

    add_source = colrev.search_file.ExtendedSearchFile(
        platform=platform,
        search_results_path=filename,
        search_type=SearchType.DB,
        search_string=search_string,
        comment="",
        version=version,
    )
    if hasattr(search_source_class, "validate_source"):
        # prevents saving of search-file
        search_source_class.validate_source(add_source)

    add_source.save(git_repo=git_repo)

    return add_source
