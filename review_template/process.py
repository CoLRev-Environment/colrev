#! /usr/bin/env python
import logging
import os

import git

from review_template import dedupe
from review_template import load
from review_template import pdf_prepare
from review_template import pdfs
from review_template import prepare


def reprocess_id(REVIEW_MANAGER, id: str, git_repo: git.Repo) -> None:
    saved_args = locals()

    MAIN_REFERENCES = REVIEW_MANAGER.paths["MAIN_REFERENCES"]
    if "all" == id:
        logging.info("Removing/reprocessing all records")
        os.remove(MAIN_REFERENCES)
        git_repo.index.remove([MAIN_REFERENCES], working_tree=True)

    else:
        bib_db = REVIEW_MANAGER.load_main_refs()
        bib_db.entries = [x for x in bib_db.entries if id != x["ID"]]
        REVIEW_MANAGER.save_bib_file(bib_db)
        git_repo.index.add([MAIN_REFERENCES])

    REVIEW_MANAGER.create_commit("Reprocess", saved_args)

    return


def main(REVIEW_MANAGER, reprocess_id: str = None, keep_ids: bool = False) -> None:

    REVIEW_MANAGER.build_docker_images()
    git_repo = REVIEW_MANAGER.get_repo()

    if id is not None:
        reprocess_id(reprocess_id, git_repo)

    load.main(REVIEW_MANAGER, keep_ids)

    prepare.main(REVIEW_MANAGER, keep_ids)

    dedupe.main(REVIEW_MANAGER)

    pdfs.main(REVIEW_MANAGER)

    pdf_prepare.main(REVIEW_MANAGER)

    return
