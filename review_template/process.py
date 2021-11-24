#! /usr/bin/env python
import logging
import os

import git
from bibtexparser.bibdatabase import BibDatabase

from review_template import dedupe
from review_template import importer
from review_template import init
from review_template import pdf_prepare
from review_template import pdfs
from review_template import prepare
from review_template import repo_setup
from review_template import status
from review_template import utils


def reprocess_id(id: str, repo: git.Repo) -> None:
    saved_args = locals()
    if id is None:
        return

    MAIN_REFERENCES = repo_setup.paths["MAIN_REFERENCES"]

    if "all" == id:
        logging.info("Removing/reprocessing all records")
        os.remove(MAIN_REFERENCES)
        repo.index.remove([MAIN_REFERENCES], working_tree=True)

    else:
        bib_db = utils.load_main_refs(mod_check=False)
        bib_db.entries = [x for x in bib_db.entries if id != x["ID"]]
        utils.save_bib_file(bib_db, MAIN_REFERENCES)
        repo.index.add([MAIN_REFERENCES])

    utils.create_commit(repo, "⚙️ Reprocess", saved_args)

    logging.info("Create commit)")
    utils.reset_log()
    return


class DelayRequirement(Exception):
    pass


def check_delay(bib_db: BibDatabase, min_status_requirement: str) -> bool:

    # all records need to have at least the min_status_requirement (or latter)
    # ie. raise DelayRequirement if any record has a prior status
    # do not consider terminal states:
    # prescreen_excluded, not_available, excluded

    # TODO: distingusih rev_status, md_status, pdf_status

    # Records should not be propagated/screened when the batch
    # has not yet been committed
    DELAY_AUTOMATED_PROCESSING = repo_setup.config["DELAY_AUTOMATED_PROCESSING"]

    if "md_imported" == min_status_requirement:
        # Note: md_status=retrieved should not happen
        if len(bib_db.entries) == 0:
            logging.error("No search results available for import.")
            raise DelayRequirement

    if not DELAY_AUTOMATED_PROCESSING:
        return False

    cur_rev_status = [x.get("rev_status", "NA") for x in bib_db.entries]
    cur_md_status = [x.get("md_status", "NA") for x in bib_db.entries]
    cur_pdf_status = [x.get("pdf_status", "NA") for x in bib_db.entries]

    prior_md_status = ["retrieved", "imported", "needs_manual_preparation"]
    if "md_prepared" == min_status_requirement:
        if any(x in cur_md_status for x in prior_md_status):
            status.review_instructions()
            raise DelayRequirement

    prior_md_status.append("prepared")
    prior_md_status.append("needs_manual_merging")
    if "md_processed" == min_status_requirement:
        if any(x in cur_md_status for x in prior_md_status):
            status.review_instructions()
            raise DelayRequirement

    # prior_md_status.append('processed') - this is the "end-state"
    if "prescreen_inclusion" == min_status_requirement:
        if any(x in cur_md_status for x in prior_md_status):
            status.review_instructions()
            raise DelayRequirement

    prior_rev_status = ["retrieved"]
    if "pdf_needs_retrieval" == min_status_requirement:
        if any(x in cur_md_status for x in prior_md_status) or any(
            x in cur_rev_status for x in prior_rev_status
        ):
            status.review_instructions()
            raise DelayRequirement

    prior_pdf_status = ["needs_retrieval"]
    prior_pdf_status.append("needs_manual_retrieval")
    # Note: it's ok if PDFs a re "not_available"
    if "pdf_imported" == min_status_requirement:
        if any(x in cur_pdf_status for x in prior_pdf_status) or any(
            x in cur_rev_status for x in prior_rev_status
        ):
            status.review_instructions()
            raise DelayRequirement

    prior_pdf_status.append("imported")
    prior_pdf_status.append("pdf_needs_manual_preparation")
    if "prescreened_and_pdf_prepared" == min_status_requirement:
        if any(x in cur_pdf_status for x in prior_pdf_status) or any(
            x in cur_rev_status for x in prior_rev_status
        ):
            raise DelayRequirement

    # prior_rev_status.append('prescreen_included')

    return False


def main(reprocess: bool = None, keep_ids: bool = False) -> None:

    status.repository_validation()
    repo = init.get_repo()
    utils.require_clean_repo(repo, ignore_pattern="search/")
    utils.build_docker_images()
    reprocess_id(reprocess, repo)

    try:
        bib_db = importer.main(repo, keep_ids)

        bib_db = prepare.main(bib_db, repo, keep_ids)

        bib_db = dedupe.main(bib_db, repo)

        bib_db = pdfs.main(bib_db, repo)

        bib_db = pdf_prepare.main(bib_db, repo)

        # Note: the checks for delaying the screen
        # are implemented in the screen.py

    except DelayRequirement:
        pass

    print()
    os.system("pre-commit run -a")

    return
