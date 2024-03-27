import colrev.process.operation


def test_check_precondition_load(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:

    helpers.reset_commit(review_manager=base_repo_review_manager, commit="dedupe_commit")
