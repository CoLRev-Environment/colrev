from __future__ import annotations

from pathlib import Path
from typing import Any
from typing import Optional

import colrev.exceptions as colrev_exceptions
import colrev.search_file
import colrev.utils
from colrev.constants import Colors
from colrev.git_repo import GitRepo


class _Paths:
    def __init__(self, root: Path) -> None:
        self.git_ignore = root / ".gitignore"


class _ReviewManagerStub:
    def __init__(self, root: Path) -> None:
        self.path = root
        self.paths = _Paths(root)


def run_db_search(
    *,
    search_source_cls,
    source: colrev.search_file.ExtendedSearchFile,
    add_to_git: bool = False,
    project_root: Optional[Path] = None,
    **kwargs: Any,
) -> None:
    """Run the database search.

    add_to_git: when True, stage changes via a locally instantiated GitRepo.
    project_root: optional explicit root path; if not provided, derive from the source.
    """
    root = project_root or source.search_results_path.resolve().parents[2]
    review_manager = _ReviewManagerStub(root)
    git = GitRepo(review_manager=review_manager)

    if colrev.utils.in_ci_environment():
        raise colrev_exceptions.SearchNotAutomated("DB search not automated.")

    print("DB search (update)")
    print(
        f"- Go to {Colors.ORANGE}{search_source_cls.db_url}{Colors.END} "
        "and run the following query:"
    )
    print()
    try:
        print(f"{Colors.ORANGE}{source.get_query()}{Colors.END}")
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
