#! /usr/bin/env python
import configparser
import logging
import os
import pkgutil

import git
import requests


def retrieve_template_file(template_file: str, target: str) -> None:
    filedata = pkgutil.get_data(__name__, template_file)
    filedata = filedata.decode("utf-8")
    with open(target, "w") as file:
        file.write(filedata)
    return


def inplace_change(filename: str, old_string: str, new_string: str) -> None:

    # Safely read the input filename using 'with'
    with open(filename) as f:
        s = f.read()
        if old_string not in s:
            logging.info(f'"{old_string}" not found in {filename}.')
            return

    # Safely write the changed content, if found in the file
    with open(filename, "w") as f:
        s = s.replace(old_string, new_string)
        f.write(s)
    return


def get_value(msg: str, options: dict) -> str:
    valid_response = False
    user_input = ""
    while not valid_response:
        print(f" {msg} (" + "|".join(options) + ")")
        user_input = input()
        if user_input in options:
            valid_response = True
    return user_input


def get_name_mail_from_global_git_config() -> [str, str]:
    ggit_conf_path = os.path.normpath(os.path.expanduser("~/.gitconfig"))
    if os.path.exists(ggit_conf_path):
        glob_git_conf = git.GitConfigParser([ggit_conf_path], read_only=True)
        committer_name = glob_git_conf.get("user", "name")
        committer_email = glob_git_conf.get("user", "email")
        # TODO: test whether user and email are set in the global config
    else:
        committer_name = input("Please provide your name")
        committer_email = input("Please provide your e-mail")
    return committer_name, committer_email


def init_new_repo() -> git.Repo:

    from review_template import repo_setup  # noqa: F401

    saved_args = locals()

    logging.info("Initialize review repository")
    project_title = input("Project title: ")
    logging.info("Set project title:".ljust(30, " ") + f"{project_title}")

    committer_name, committer_email = get_name_mail_from_global_git_config()
    print("\n\nParameters for the review project\n" "Details avilable at: TODO/docs")

    # # TODO: allow multiple?
    # DATA_FORMAT = get_value('Select data structure',
    #                         ['NONE', 'STRUCTURED', 'MANUSCRIPT',
    #                          'SHEETs', 'MACODING'])
    SHARE_STAT_REQ = get_value(
        "Select share status requirement",
        ["NONE", "PROCESSED", "SCREENED", "COMPLETED"],
    )
    logging.info("Set SHARE_STAT_REQ:".ljust(30, " ") + f"{SHARE_STAT_REQ}")

    PDF_HANDLING = get_value("Select pdf handling", ["EXT", "GIT"])
    logging.info("Set PDF_HANDLING:".ljust(30, " ") + f"{PDF_HANDLING}")

    repo = git.Repo.init()
    os.mkdir("search")

    retrieve_template_file("../template/readme.md", "readme.md")
    retrieve_template_file(
        "../template/.pre-commit-config.yaml",
        ".pre-commit-config.yaml",
    )
    retrieve_template_file("../template/.gitattributes", ".gitattributes")

    inplace_change("readme.md", "{{project_title}}", project_title)

    private_config = configparser.ConfigParser()
    private_config.add_section("general")
    private_config["general"]["EMAIL"] = committer_email
    private_config["general"]["GIT_ACTOR"] = committer_name
    private_config["general"]["CPUS"] = "4"
    private_config["general"]["DEBUG_MODE"] = "no"
    with open("private_config.ini", "w") as configfile:
        private_config.write(configfile)

    # REPO_SETUP_VERSION = repo_setup.paths.keys()[-1]
    REPO_SETUP_VERSION = "v_0.1"
    shared_config = configparser.ConfigParser()
    shared_config.add_section("general")
    shared_config["general"]["REPO_SETUP_VERSION"] = REPO_SETUP_VERSION
    shared_config["general"]["SHARE_STAT_REQ"] = SHARE_STAT_REQ
    shared_config["general"]["PDF_HANDLING"] = PDF_HANDLING
    with open("shared_config.ini", "w") as configfile:
        shared_config.write(configfile)

    logging.info("Set REPO_SETUP_VERSION:".ljust(30, " ") + f"{REPO_SETUP_VERSION}")

    # Note: need to write the .gitignore because file would otherwise be
    # ignored in the template directory.
    f = open(".gitignore", "w")
    f.write(
        "*.bib.sav\nprivate_config.ini\n.local_pdf_indices"
        + "\n.index-*\nmissing_pdf_files.csv\n"
        + "manual_cleansing_statistics.csv"
    )
    f.close()

    os.system("pre-commit install")
    os.system("pre-commit autoupdate")

    from review_template import utils

    repo.index.add(
        [
            "readme.md",
            ".pre-commit-config.yaml",
            ".gitattributes",
            ".gitignore",
            "shared_config.ini",
        ]
    )

    utils.create_commit(repo, "Initial commit", saved_args, True)

    if "y" == input("Connect to shared (remote) repository (y)?"):
        remote_url = input("URL:")
        try:
            requests.get(remote_url)
            origin = repo.create_remote("origin", remote_url)
            repo.heads.main.set_tracking_branch(origin.refs.main)
            origin.push()
            logging.info(
                "Connected to shared repository:".ljust(30, " ") + f"{remote_url}"
            )
        except requests.ConnectionError:
            logging.error(
                "URL of shared repository cannot be reached. Use "
                "git remote add origin https://github.com/user/repo"
                "\ngit push origin main"
            )
            pass

    return repo


def clone_shared_repo() -> git.Repo:
    logging.info("Connecting to a shared repository ...")
    logging.info(
        "To initiate a new project, cancel (ctrl+c) and use "
        "review_template init in an empty directory"
    )

    remote_url = input("URL of shared repository:")
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


def initialize_repo() -> git.Repo:
    if 0 != len(os.listdir(os.getcwd())):
        if "y" == input("Connect to a shared repo (y/n)?"):
            repo = clone_shared_repo()
        else:
            return
    else:
        if "y" == input("Retrieve shared repository (y/n)?"):
            repo = clone_shared_repo()
        else:
            repo = init_new_repo()
    return repo


def get_repo() -> git.Repo:
    try:
        repo = git.Repo()
        return repo
    except git.exc.InvalidGitRepositoryError:
        logging.error("No git repository found.")
        pass

    repo = initialize_repo()
    return repo
