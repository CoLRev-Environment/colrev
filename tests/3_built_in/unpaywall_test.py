#!/usr/bin/env python
"""Testing unpaywall"""
import json
from pathlib import Path

import pytest

import colrev.env.environment_manager
import colrev.env.tei_parser
import colrev.ops.built_in.pdf_get.unpaywall
import colrev.review_manager


@pytest.fixture(name="unpaywall")
def fixture_unpaywall(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> colrev.ops.built_in.pdf_get.unpaywall.Unpaywall:
    """Fixture for Unpaywall"""

    return colrev.ops.built_in.pdf_get.unpaywall.Unpaywall(
        pdf_get_operation=base_repo_review_manager.get_pdf_get_operation(),
        settings={"endpoint": "colrev.unpaywall"},
    )


def test_loading_user_specified_email_with_none_set(  # type: ignore
    base_repo_review_manager,
    unpaywall,
):
    """
    When user have specified username and email, we should use that, instead of
    Git.
    """
    # Test without settings
    env_man = colrev.env.environment_manager.EnvironmentManager()
    username, email = env_man.get_name_mail_from_git()
    cfg_username, cfg_email = unpaywall.get_user_specified_email()
    assert (username, email) == (cfg_username, cfg_email)
    # now create a new settings
    test_user = {"username": "Test User", "email": "test@email.com"}
    reg = json.dumps(
        {
            "local_index": {
                "repos": [],
            },
            "packages": {"pdf_get": {"colrev": {"unpaywall": test_user}}},
        }
    )
    with open(
        base_repo_review_manager.path / Path("reg.json"), "w", encoding="utf-8"
    ) as file:
        file.write(reg)
    # Check with new env_man
    cfg_username, cfg_email = unpaywall.get_user_specified_email()
    assert (test_user["username"], test_user["email"]) == (cfg_username, cfg_email)
    (base_repo_review_manager.path / Path("reg.json")).unlink()
