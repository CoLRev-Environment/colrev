from unittest.mock import MagicMock

import pytest

from colrev.ops.commit import Commit


@pytest.fixture(scope="session", name="commit_fixture")
def get_commit_fixture(tmp_path_factory):  # type: ignore
    """Fixture returning the commit object"""

    review_manager = MagicMock()
    msg = "Test commit"
    manual_author = False
    script_name = "test_script"
    saved_args = {"arg1": "value1", "arg2": "value2"}
    skip_hooks = False

    commit = Commit(
        review_manager=review_manager,
        msg=msg,
        manual_author=manual_author,
        script_name=script_name,
        saved_args=saved_args,
        skip_hooks=skip_hooks,
    )
    return commit


def test_parse_script_name(tmp_path, commit_fixture):  # type: ignore
    script_name = "colrev cli"
    parsed_script_name = commit_fixture._parse_script_name(script_name=script_name)
    assert parsed_script_name == "colrev"
