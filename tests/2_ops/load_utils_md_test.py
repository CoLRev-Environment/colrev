from pathlib import Path

import colrev.ops.load_utils_md
import colrev.review_manager
import colrev.settings


def test_load_md(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the load utils for md files"""

    helpers.reset_commit(review_manager=base_repo_review_manager, commit="load_commit")

    if base_repo_review_manager.in_ci_environment():
        return

    search_source = colrev.settings.SearchSource(
        endpoint="colrev.unknown_source",
        filename=Path("data/search/references.md"),
        search_type=colrev.settings.SearchType.OTHER,
        search_parameters={},
        comment="",
    )

    helpers.retrieve_test_file(
        source=Path("load_utils/") / Path("references.md"),
        target=Path("data/search/") / Path("references.md"),
    )
    load_operation = base_repo_review_manager.get_load_operation()

    md_loader = colrev.ops.load_utils_md.MarkdownLoader(
        load_operation=load_operation, source=search_source
    )
    records = md_loader.load()

    actual_records_text = base_repo_review_manager.dataset.parse_bibtex_str(
        recs_dict_in=records
    )
    expected_file_path = (
        helpers.test_data_path / Path("load_utils/") / Path("references_expected.bib")
    )
    expected_records_text = expected_file_path.read_text(encoding="utf-8")

    if expected_records_text != actual_records_text:
        expected_file_path.write_text(actual_records_text, encoding="utf-8")

    assert (
        expected_records_text == actual_records_text
    ), "The loaded records from the MD file do not match the expected records."
