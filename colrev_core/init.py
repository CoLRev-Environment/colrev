#! /usr/bin/env python
import configparser
import logging
import os
from subprocess import check_call
from subprocess import DEVNULL
from subprocess import STDOUT

import git
import requests


def get_name_mail_from_global_git_config() -> list:
    ggit_conf_path = os.path.normpath(os.path.expanduser("~/.gitconfig"))
    global_conf_details = []
    if os.path.exists(ggit_conf_path):
        glob_git_conf = git.GitConfigParser([ggit_conf_path], read_only=True)
        global_conf_details = [
            glob_git_conf.get("user", "name"),
            glob_git_conf.get("user", "email"),
        ]
    return global_conf_details


def connect_to_remote(repo: git.Repo, remote_url: str) -> None:
    try:
        requests.get(remote_url)
        origin = repo.create_remote("origin", remote_url)
        repo.heads.main.set_tracking_branch(origin.refs.main)
        origin.push()
        logging.info("Connected to shared repository:".ljust(30, " ") + f"{remote_url}")
    except requests.ConnectionError:
        logging.error(
            "URL of shared repository cannot be reached. Use "
            "git remote add origin https://github.com/user/repo"
            "\ngit push origin main"
        )
        pass
    return


class NonEmptyDirectoryError(Exception):
    def __init__(self):
        self.message = "please change to an empty directory to initialize a project"
        super().__init__(self.message)


def require_empty_directory():

    cur_content = os.listdir(os.getcwd())
    if "venv" in cur_content:
        cur_content.remove("venv")
        # Note: we can use paths directly when initiating the project
    if "report.log" in cur_content:
        cur_content.remove("report.log")

    if 0 != len(cur_content):
        raise NonEmptyDirectoryError()


def initialize_repo(
    project_title: str,
    SHARE_STAT_REQ: str,
    PDF_HANDLING: str,
    DATA_FORMAT: str,
    remote_url: str = "NA",
) -> bool:

    saved_args = locals()

    require_empty_directory()

    assert SHARE_STAT_REQ in ["NONE", "PROCESSED", "SCREENED", "COMPLETED"]
    assert PDF_HANDLING in ["EXT", "GIT"]

    # TODO: allow multiple?
    assert DATA_FORMAT in ["NONE", "STRUCTURED", "MANUSCRIPT", "SHEETs", "MACODING"]

    global_git_vars = get_name_mail_from_global_git_config()
    if 2 != len(global_git_vars):
        logging.error("Global git variables (user name and email) not available.")
        return False
    committer_name, committer_email = global_git_vars

    repo = git.Repo.init()
    os.mkdir("search")

    from colrev_core import review_manager

    review_manager.retrieve_package_file("template/readme.md", "readme.md")
    review_manager.retrieve_package_file(
        "template/.pre-commit-config.yaml", ".pre-commit-config.yaml"
    )
    review_manager.retrieve_package_file("template/.gitattributes", ".gitattributes")

    review_manager.inplace_change(
        "readme.md", "{{project_title}}", project_title.rstrip(" ")
    )

    private_config = configparser.ConfigParser()
    private_config.add_section("general")
    private_config["general"]["EMAIL"] = committer_email
    private_config["general"]["GIT_ACTOR"] = committer_name
    private_config["general"]["CPUS"] = "4"
    private_config["general"]["DEBUG_MODE"] = "no"
    with open("private_config.ini", "w") as configfile:
        private_config.write(configfile)

    shared_config = configparser.ConfigParser()
    shared_config.add_section("general")
    shared_config["general"]["SHARE_STAT_REQ"] = SHARE_STAT_REQ
    shared_config["general"]["PDF_HANDLING"] = PDF_HANDLING
    with open("shared_config.ini", "w") as configfile:
        shared_config.write(configfile)

    # Note: need to write the .gitignore because file would otherwise be
    # ignored in the template directory.
    f = open(".gitignore", "w")
    f.write(
        "*.bib.sav\n"
        + "private_config.ini\n"
        + "missing_pdf_files.csv\n"
        + "manual_cleansing_statistics.csv\n"
        + "data.csv\n"
        + "venv"
    )
    f.close()

    logging.info("Install latest pre-commmit hooks")
    scripts_to_call = [
        ["pre-commit", "install"],
        ["pre-commit", "install", "--hook-type", "prepare-commit-msg"],
        ["pre-commit", "install", "--hook-type", "pre-push"],
        ["pre-commit", "autoupdate", "--bleeding-edge"],
    ]
    for script_to_call in scripts_to_call:
        check_call(script_to_call, stdout=DEVNULL, stderr=STDOUT)

    repo.index.add(
        [
            "readme.md",
            ".pre-commit-config.yaml",
            ".gitattributes",
            ".gitignore",
            "shared_config.ini",
        ]
    )

    from colrev_core.review_manager import ReviewManager

    REVIEW_MANAGER = ReviewManager()

    report_logger = logging.getLogger("colrev_core_report")
    report_logger.info("Initialize review repository")
    report_logger.info("Set project title:".ljust(30, " ") + f"{project_title}")
    report_logger.info("Set SHARE_STAT_REQ:".ljust(30, " ") + f"{SHARE_STAT_REQ}")
    report_logger.info("Set PDF_HANDLING:".ljust(30, " ") + f"{PDF_HANDLING}")

    REVIEW_MANAGER.create_commit(
        "Initial commit", manual_author=True, saved_args=saved_args
    )

    if "NA" != remote_url:
        connect_to_remote(repo, remote_url)

    return True


def clone_shared_repo(remote_url: str) -> git.Repo:
    try:
        requests.get(remote_url)
        repo_name = os.path.splitext(os.path.basename(remote_url))[0]
        logging.info("Clone shared repository...")
        repo = git.Repo.clone_from(remote_url, repo_name)
        logging.info(f"Use cd {repo_name}")
    except requests.ConnectionError:
        logging.error(
            "URL of shared repository cannot be reached. Use "
            "git remote add origin https://github.com/user/repo\n"
            "git push origin main"
        )
        pass
    return repo
