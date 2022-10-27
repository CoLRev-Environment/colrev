#!/usr/bin/env python
from pathlib import Path


def test_init(tmp_path: Path) -> None:
    import colrev.review_manager
    import os
    import colrev.env.utils
    from pathlib import Path

    os.chdir(tmp_path)

    colrev.review_manager.ReviewManager.get_init_operation(
        review_type="literature_review",
        example=True,
    )

    review_manager = colrev.review_manager.ReviewManager()
    review_manager.get_local_index(startup_without_waiting=True)
    load_operation = review_manager.get_load_operation()

    load_operation.check_update_sources(skip_query=True)

    load_operation = review_manager.get_load_operation()
    load_operation.main(keep_ids=False, combine_commits=False)

    review_manager = colrev.review_manager.ReviewManager()
    prep_operation = review_manager.get_prep_operation()
    prep_operation.main(keep_ids=False)

    review_manager = colrev.review_manager.ReviewManager()
    dedupe_operation = review_manager.get_dedupe_operation(
        notify_state_transition_operation=True
    )
    dedupe_operation.main()

    review_manager = colrev.review_manager.ReviewManager()
    prescreen_operation = review_manager.get_prescreen_operation()
    prescreen_operation.include_all_in_prescreen()

    review_manager = colrev.review_manager.ReviewManager()
    pdf_get_operation = review_manager.get_pdf_get_operation(
        notify_state_transition_operation=True
    )
    pdf_get_operation.main()

    review_manager = colrev.review_manager.ReviewManager()
    pdf_prep_operation = review_manager.get_pdf_prep_operation(reprocess=False)
    pdf_prep_operation.main()

    review_manager = colrev.review_manager.ReviewManager()
    pdf_get_man_operation = review_manager.get_pdf_get_man_operation()
    pdf_get_man_operation.discard()

    review_manager = colrev.review_manager.ReviewManager()
    pdf_prep_man_operation = review_manager.get_pdf_prep_man_operation()
    pdf_prep_man_operation.discard()

    review_manager = colrev.review_manager.ReviewManager()
    screen_operation = review_manager.get_screen_operation()
    screen_operation.include_all_in_screen()

    review_manager = colrev.review_manager.ReviewManager()
    data_operation = review_manager.get_data_operation()
    data_operation.main()
    review_manager.create_commit(msg="Data and synthesis", manual_author=True)

    colrev.env.utils.inplace_change(
        filename=Path("data/paper.md"),
        old_string="<!-- NEW_RECORD_SOURCE -->",
        new_string="",
    )
    colrev.env.utils.inplace_change(
        filename=Path("data/paper.md"),
        old_string="# References",
        new_string="<!-- NEW_RECORD_SOURCE -->\n# References",
    )

    review_manager = colrev.review_manager.ReviewManager()
    data_operation = review_manager.get_data_operation()
    data_operation.main()
    review_manager.create_commit(msg="Data and synthesis", manual_author=True)
