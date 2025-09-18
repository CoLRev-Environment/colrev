#!/usr/bin/env python
"""Testing unpaywall"""
import json
from pathlib import Path

import pytest

import colrev.env.environment_manager
import colrev.packages.unpaywall.src.unpaywall
import colrev.review_manager
from colrev.packages.unpaywall.src import utils


@pytest.fixture(name="unpaywall")
def fixture_unpaywall(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> colrev.packages.unpaywall.src.unpaywall.Unpaywall:
    """Fixture for Unpaywall"""

    return colrev.packages.unpaywall.src.unpaywall.Unpaywall(
        pdf_get_operation=base_repo_review_manager.get_pdf_get_operation(),
        settings={"endpoint": "colrev.unpaywall"},
    )


def test_loading_user_specified_email_with_none_set(  # type: ignore
    base_repo_review_manager,
    unpaywall,
):
    """
    When user have specified an email, we should use that, instead of
    the one registered for Git.
    """
    # Test without settings
    env_man = colrev.env.environment_manager.EnvironmentManager()
    _, email = env_man.get_name_mail_from_git()
    cfg_email = utils.get_email()
    assert email == cfg_email
    # now create a new settings
    test_user = {"email": "test@email.com"}
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
    cfg_email = utils.get_email()
    assert test_user["email"] == cfg_email
    (base_repo_review_manager.path / Path("reg.json")).unlink()
