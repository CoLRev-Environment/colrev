#! /usr/bin/env python
"""Custom script setup."""
import typing
from pathlib import Path

import colrev.env.utils
import colrev.settings
from colrev.constants import SearchType

if typing.TYPE_CHECKING:  # pragma: no cover
    import colrev.review_manager


def setup_custom_search_script(
    *, review_manager: colrev.review_manager.ReviewManager
) -> None:
    """Setup a custom search script"""

    filedata = colrev.env.utils.get_package_file_content(
        module="colrev.ops",
        filename=Path("custom_scripts/custom_search_source_script.py"),
    )

    if filedata:
        with open("custom_search_source_script.py", "w", encoding="utf-8") as file:
            file.write(filedata.decode("utf-8"))

    review_manager.dataset.add_changes(Path("custom_search_source_script.py"))

    new_source = colrev.settings.SearchSource(
        endpoint="custom_search_source_script",
        filename=Path("data/search/custom_search.bib"),
        search_type=SearchType.DB,
        search_parameters={},
        comment="",
    )

    review_manager.settings.sources.append(new_source)
    review_manager.save_settings()
