#!/usr/bin/env python
"""Tests of the CoLRev check operation"""
import colrev.review_manager

# flake8: noqa


def test_check_operation_precondition(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    review_manager_helpers,
) -> None:
    """Test the check operation preconditions"""

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="changed_settings_commit"
    )
    advisor = base_repo_review_manager.get_advisor()
    actual = advisor.get_instructions()
    assert actual == {
        "review_instructions": [
            {
                "msg": "To import, copy search results to the search directory.",
                "cmd": "colrev load",
            },
            {
                "msg": "Next step: retrieve metadata",
                "cmd": "colrev retrieve",
                "priority": "yes",
            },
        ],
        "environment_instructions": [],
        "collaboration_instructions": {
            "items": [
                {
                    "title": "Project not yet shared",
                    "level": "WARNING",
                    "msg": "Please visit  https://github.com/new\n  create an empty repository called  <USERNAME>/base_repo0\n  and run git remote add origin  <REMOTE_URL>\n  git push origin main",
                }
            ],
            "title": "Versioning (not connected to shared repository)",
        },
    }

    review_manager_helpers.reset_commit(base_repo_review_manager, commit="load_commit")
    advisor = base_repo_review_manager.get_advisor()
    actual = advisor.get_instructions()
    assert actual == {
        "review_instructions": [
            {
                "msg": "Next step: Prepare records",
                "cmd": "colrev prep",
                "priority": "yes",
            }
        ],
        "environment_instructions": [],
        "collaboration_instructions": {
            "items": [
                {
                    "title": "Project not yet shared",
                    "level": "WARNING",
                    "msg": "Please visit  https://github.com/new\n  create an empty repository called  <USERNAME>/base_repo0\n  and run git remote add origin  <REMOTE_URL>\n  git push origin main",
                }
            ],
            "title": "Versioning (not connected to shared repository)",
        },
    }

    review_manager_helpers.reset_commit(base_repo_review_manager, commit="prep_commit")
    advisor = base_repo_review_manager.get_advisor()
    actual = advisor.get_instructions()
    assert actual == {
        "review_instructions": [
            {
                "msg": "Next step: Deduplicate records",
                "cmd": "colrev dedupe",
                "priority": "yes",
            }
        ],
        "environment_instructions": [],
        "collaboration_instructions": {
            "items": [
                {
                    "title": "Project not yet shared",
                    "level": "WARNING",
                    "msg": "Please visit  https://github.com/new\n  create an empty repository called  <USERNAME>/base_repo0\n  and run git remote add origin  <REMOTE_URL>\n  git push origin main",
                }
            ],
            "title": "Versioning (not connected to shared repository)",
        },
    }

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="dedupe_commit"
    )
    advisor = base_repo_review_manager.get_advisor()
    actual = advisor.get_instructions()
    assert actual == {
        "review_instructions": [
            {
                "msg": "Next step: Prescreen records",
                "cmd": "colrev prescreen",
                "priority": "yes",
            }
        ],
        "environment_instructions": [],
        "collaboration_instructions": {
            "items": [
                {
                    "title": "Project not yet shared",
                    "level": "WARNING",
                    "msg": "Please visit  https://github.com/new\n  create an empty repository called  <USERNAME>/base_repo0\n  and run git remote add origin  <REMOTE_URL>\n  git push origin main",
                }
            ],
            "title": "Versioning (not connected to shared repository)",
        },
    }

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="prescreen_commit"
    )
    advisor = base_repo_review_manager.get_advisor()
    actual = advisor.get_instructions()
    assert actual == {
        "review_instructions": [
            {
                "msg": "Next step: Retrieve PDFs",
                "cmd": "colrev pdf-get",
                "priority": "yes",
            }
        ],
        "environment_instructions": [],
        "collaboration_instructions": {
            "items": [
                {
                    "title": "Project not yet shared",
                    "level": "WARNING",
                    "msg": "Please visit  https://github.com/new\n  create an empty repository called  <USERNAME>/base_repo0\n  and run git remote add origin  <REMOTE_URL>\n  git push origin main",
                }
            ],
            "title": "Versioning (not connected to shared repository)",
        },
    }

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="pdf_get_commit"
    )
    advisor = base_repo_review_manager.get_advisor()
    actual = advisor.get_instructions()
    assert actual == {
        "review_instructions": [
            {
                "msg": "Next step: Retrieve PDFs (manually)",
                "cmd": "colrev pdf-get-man",
                "priority": "yes",
            }
        ],
        "environment_instructions": [],
        "collaboration_instructions": {
            "items": [
                {
                    "title": "Project not yet shared",
                    "level": "WARNING",
                    "msg": "Please visit  https://github.com/new\n  create an empty repository called  <USERNAME>/base_repo0\n  and run git remote add origin  <REMOTE_URL>\n  git push origin main",
                }
            ],
            "title": "Versioning (not connected to shared repository)",
        },
    }
