#!/usr/bin/env python
"""Tests of the custom script setup"""
from __future__ import annotations

import colrev.ui_cli.setup_custom_scripts


def test_prep_setup_custom_script(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test search setup_custom_script"""

    helpers.reset_commit(base_repo_review_manager, commit="load_commit")

    colrev.ui_cli.setup_custom_scripts.setup_custom_search_script(
        review_manager=base_repo_review_manager
    )
    base_repo_review_manager.settings.sources.pop()
