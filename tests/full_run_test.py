#!/usr/bin/env python
from pathlib import Path


def test_init(tmp_path: Path) -> None:
    import colrev.review_manager
    import os
    import colrev.env.utils
    from pathlib import Path

    os.chdir(tmp_path)

    import os, shutil

    for filename in os.listdir(tmp_path):
        file_path = os.path.join(tmp_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")

    colrev.review_manager.ReviewManager.get_init_operation(
        review_type="literature_review",
        example=True,
    )

    review_manager = colrev.review_manager.ReviewManager()
    review_manager.get_local_index(startup_without_waiting=True)
    load_operation = review_manager.get_load_operation()

    load_operation = review_manager.get_load_operation()
    new_sources = load_operation.get_new_sources(skip_query=True)
    load_operation.main(new_sources=new_sources, keep_ids=False, combine_commits=False)

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
    pdf_prep_operation.main(batch_size=0)

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
    review_manager.dataset.add_changes(path=Path("data/paper.md"))

    review_manager = colrev.review_manager.ReviewManager()
    data_operation = review_manager.get_data_operation()
    data_operation.main()
    review_manager.create_commit(msg="Data and synthesis", manual_author=True)
