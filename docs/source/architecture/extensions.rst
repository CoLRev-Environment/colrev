
Extensions
==================================

Developing extensions of CoLRev in Python/R is easy. We provide examples and instructions below.


.. code-block::

    import logging
    from colrev_core.review_manager import ReviewManager
    from colrev_core.review_manager import Process
    from colrev_core.review_manager import ProcessType

    # Set up the loggers
    report_logger = logging.getLogger("review_template_report")
    logger = logging.getLogger("extension")

    # Initialize the ReviewManager and notify about upcoming process
    REVIEW_MANAGER = ReviewManager()
    REVIEW_MANAGER.notify(Process(ProcessType.prescreen))

    # Load the records and apply changes
    records = REVIEW_MANAGER.load_records()
    for record in records:
        ....

    # Save the changes, add them to git, and create commit
    REVIEW_MANAGER.save_records(records)
    REVIEW_MANAGER.add_record_changes()
    REVIEW_MANAGER.create_commit("Pre-screening (extension X")


- Add the ```colrev-extension``` topic tag on GitHub to allow others to find and use your work

TODO:

- include a link to further resources and example repositories
- include an R example
- Get all paths from REVIEW_MANAGER.paths (ABSOLUTE or RELATIVE)
- Logger (report vs tool/extension)
    - logg infos that are helpful to examine and validate the process to review_template_report logger.
    - logg infos on the progress to the review_template logger. keep the output relatively short, allowing users to see the progress and judge whether any errors occurred
- PDF paths should be relative to the git repository (if PDFs are not versioned in git, this can be accomplished through ignored paths or symlinked directories)
- Commit message: link to docs with debugging-instructions
- Instead of throwing the raw build output at the user and telling them to figure it out, we detect the underlying cause, if we can, and provide them with a short, but descriptive failure message, with links to the relevant documentation.
