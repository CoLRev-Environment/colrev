#! /usr/bin/env python
import configparser
import json
import logging
import os
from pathlib import Path
from subprocess import check_call
from subprocess import DEVNULL
from subprocess import STDOUT

import git
import pandas as pd
import requests
import yaml


def get_name_mail_from_global_git_config() -> list:
    ggit_conf_path = Path.home() / Path(".gitconfig")
    global_conf_details = []
    if ggit_conf_path.is_file():
        glob_git_conf = git.GitConfigParser([str(ggit_conf_path)], read_only=True)
        global_conf_details = [
            glob_git_conf.get("user", "name"),
            glob_git_conf.get("user", "email"),
        ]
    return global_conf_details


def connect_to_remote(git_repo: git.Repo, remote_url: str) -> None:
    try:
        requests.get(remote_url)
        origin = git_repo.create_remote("origin", remote_url)
        git_repo.heads.main.set_tracking_branch(origin.refs.main)
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


def save_local_registry(REVIEW_MANAGER, local_registry: list) -> None:
    local_registry_path = REVIEW_MANAGER.paths["LOCAL_REGISTRY"]

    local_registry_df = pd.DataFrame(local_registry)
    orderedCols = [
        "filename",
        "source_name",
        "source_url",
    ]
    for x in [x for x in local_registry_df.columns if x not in orderedCols]:
        orderedCols.append(x)
    local_registry_df = local_registry_df.reindex(columns=orderedCols)

    with open(local_registry_path, "w") as f:
        yaml.dump(
            json.loads(
                local_registry_df.to_json(orient="records", default_handler=str)
            ),
            f,
            default_flow_style=False,
            sort_keys=False,
        )

    return


def register_repo(REVIEW_MANAGER):
    logger = logging.getLogger("colrev_core")

    local_registry = REVIEW_MANAGER.load_local_registry()

    registered_paths = [x["source_url"] for x in local_registry]
    # TODO: maybe resolve symlinked directories?
    path_to_register = str(Path.cwd())
    if registered_paths != []:
        if path_to_register in registered_paths:
            logger.error(f"Path already registered: {path_to_register}")
    else:
        logger.error(f"Creating {REVIEW_MANAGER.paths['LOCAL_REGISTRY']}")

    new_record = {
        "filename": Path.cwd().stem,
        "source_name": Path.cwd().stem,
        "source_url": Path.cwd(),
    }
    local_registry.append(new_record)
    save_local_registry(REVIEW_MANAGER, local_registry)

    logger.info(f"Registered path ({path_to_register})")

    return


def initialize_repo(
    project_title: str,
    SHARE_STAT_REQ: str,
    PDF_HANDLING: str,
    remote_url: str = "NA",
) -> bool:

    saved_args = locals()

    require_empty_directory()

    assert SHARE_STAT_REQ in ["NONE", "PROCESSED", "SCREENED", "COMPLETED"]
    assert PDF_HANDLING in ["EXT", "GIT"]

    global_git_vars = get_name_mail_from_global_git_config()
    if 2 != len(global_git_vars):
        logging.error("Global git variables (user name and email) not available.")
        return False
    committer_name, committer_email = global_git_vars

    git_repo = git.Repo.init()
    os.mkdir("search")

    from colrev_core import review_manager

    files_to_retrieve = [
        [Path("template/readme.md"), Path("readme.md")],
        [Path("template/.pre-commit-config.yaml"), Path(".pre-commit-config.yaml")],
        [Path("template/.markdownlint.yaml"), Path(".markdownlint.yaml")],
        [Path("template/.gitattributes"), Path(".gitattributes")],
    ]
    for rp, p in files_to_retrieve:
        review_manager.retrieve_package_file(rp, p)

    review_manager.inplace_change(
        Path("readme.md"), "{{project_title}}", project_title.rstrip(" ")
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
        + "venv\n"
        # + ".references_dedupe_training.json\n"
        + ".references_learned_settings"
    )
    f.close()

    logging.info("Install latest pre-commmit hooks")
    scripts_to_call = [
        ["pre-commit", "install"],
        ["pre-commit", "install", "--hook-type", "prepare-commit-msg"],
        ["pre-commit", "install", "--hook-type", "pre-push"],
        ["pre-commit", "autoupdate"],
        # ["pre-commit", "autoupdate", "--bleeding-edge"],
    ]
    for script_to_call in scripts_to_call:
        check_call(script_to_call, stdout=DEVNULL, stderr=STDOUT)

    git_repo.index.add(
        [
            "readme.md",
            ".pre-commit-config.yaml",
            ".gitattributes",
            ".gitignore",
            "shared_config.ini",
            ".markdownlint.yaml",
        ]
    )

    from colrev_core.review_manager import ReviewManager, Process, ProcessType

    REVIEW_MANAGER = ReviewManager()
    REVIEW_MANAGER.notify(Process(ProcessType.format))

    report_logger = logging.getLogger("colrev_core_report")
    report_logger.info("Initialize review repository")
    report_logger.info("Set project title:".ljust(30, " ") + f"{project_title}")
    report_logger.info("Set SHARE_STAT_REQ:".ljust(30, " ") + f"{SHARE_STAT_REQ}")
    report_logger.info("Set PDF_HANDLING:".ljust(30, " ") + f"{PDF_HANDLING}")

    REVIEW_MANAGER.create_commit(
        "Initial commit", manual_author=True, saved_args=saved_args
    )

    # LOCAL_REGISTRY
    register_repo(REVIEW_MANAGER)

    # TODO : include a link on how to connect to a remote repo

    return True
