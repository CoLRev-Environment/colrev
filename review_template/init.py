#! /usr/bin/env python
import configparser
import logging
import os
from subprocess import check_call
from subprocess import DEVNULL
from subprocess import STDOUT

import git
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("report.log", mode="a"),
        logging.StreamHandler(),
    ],
)


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


def initialize_repo(
    project_title: str,
    SHARE_STAT_REQ: str,
    PDF_HANDLING: str,
    DATA_FORMAT: str,
    remote_url: str = None,
) -> bool:

    saved_args = locals()

    if 0 != len(os.listdir(os.getcwd())) and ["report.log"] != os.listdir(os.getcwd()):
        logging.error("Directory not empty.")
        return 0

    assert SHARE_STAT_REQ in ["NONE", "PROCESSED", "SCREENED", "COMPLETED"]
    assert PDF_HANDLING in ["EXT", "GIT"]

    # TODO: allow multiple?
    assert DATA_FORMAT in ["NONE", "STRUCTURED", "MANUSCRIPT", "SHEETs", "MACODING"]

    global_git_vars = get_name_mail_from_global_git_config()
    if 2 != len(global_git_vars):
        logging.error("Global git variables (user name and email) not available.")
        return 0
    committer_name, committer_email = global_git_vars

    # REPO_SETUP_VERSION = repo_setup.paths.keys()[-1]
    REPO_SETUP_VERSION = "v_0.1"

    logging.info("Initialize review repository")
    logging.info("Set project title:".ljust(30, " ") + f"{project_title}")
    logging.info("Set SHARE_STAT_REQ:".ljust(30, " ") + f"{SHARE_STAT_REQ}")
    logging.info("Set PDF_HANDLING:".ljust(30, " ") + f"{PDF_HANDLING}")
    logging.info("Set REPO_SETUP_VERSION:".ljust(30, " ") + f"{REPO_SETUP_VERSION}")

    repo = git.Repo.init()
    os.mkdir("search")

    from review_template import review_manager

    review_manager.retrieve_package_file("../template/readme.md", "readme.md")
    review_manager.retrieve_package_file(
        "../template/.pre-commit-config.yaml", ".pre-commit-config.yaml"
    )
    review_manager.retrieve_package_file("../template/.gitattributes", ".gitattributes")

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
    shared_config["general"]["REPO_SETUP_VERSION"] = REPO_SETUP_VERSION
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
        + "data.csv"
    )
    f.close()

    logging.info("Install latest pre-commmit hooks")
    check_call(["pre-commit", "install"], stdout=DEVNULL, stderr=STDOUT)
    check_call(
        ["pre-commit", "autoupdate", "--bleeding-edge"], stdout=DEVNULL, stderr=STDOUT
    )

    repo.index.add(
        [
            "readme.md",
            ".pre-commit-config.yaml",
            ".gitattributes",
            ".gitignore",
            "shared_config.ini",
        ]
    )

    from review_template.review_manager import ReviewManager

    REVIEW_MANAGER = ReviewManager()
    REVIEW_MANAGER.create_commit("Initial commit", saved_args, True)

    if remote_url is not None:
        connect_to_remote(repo, remote_url)

    return 1


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
