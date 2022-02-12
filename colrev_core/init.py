#! /usr/bin/env python
import logging
from pathlib import Path

import git


class Initializer:
    def __init__(
        self,
        project_title: str,
        SHARE_STAT_REQ: str,
        local_index_repo: bool = False,
    ) -> None:

        saved_args = locals()
        self.project_title = project_title
        self.SHARE_STAT_REQ = SHARE_STAT_REQ
        assert SHARE_STAT_REQ in ["NONE", "PROCESSED", "SCREENED", "COMPLETED"]

        self.__require_empty_directory()
        self.__setup_files()
        self.__setup_git()
        self.__create_commit(saved_args)
        self.REVIEW_MANAGER.register_repo()
        self.__create_local_index(local_index_repo)

    def __create_commit(self, saved_args: dict) -> None:
        from colrev_core.review_manager import ReviewManager
        from colrev_core.process import Process, ProcessType

        self.REVIEW_MANAGER = ReviewManager()
        self.REVIEW_MANAGER.notify(Process(ProcessType.format))

        report_logger = logging.getLogger("colrev_core_report")
        report_logger.info("Initialize review repository")
        report_logger.info(
            "Set project title:".ljust(30, " ") + f"{self.project_title}"
        )
        report_logger.info(
            "Set SHARE_STAT_REQ:".ljust(30, " ") + f"{self.SHARE_STAT_REQ}"
        )
        del saved_args["local_index_repo"]
        self.REVIEW_MANAGER.create_commit(
            "Initial commit", manual_author=True, saved_args=saved_args
        )
        return

    def __setup_files(self) -> None:
        import configparser

        Path("search").mkdir()

        files_to_retrieve = [
            [Path("template/readme.md"), Path("readme.md")],
            [Path("template/.pre-commit-config.yaml"), Path(".pre-commit-config.yaml")],
            [Path("template/.markdownlint.yaml"), Path(".markdownlint.yaml")],
            [Path("template/.gitattributes"), Path(".gitattributes")],
        ]
        for rp, p in files_to_retrieve:
            self.__retrieve_package_file(rp, p)

        self.__inplace_change(
            Path("readme.md"), "{{project_title}}", self.project_title.rstrip(" ")
        )

        global_git_vars = self.__get_name_mail_from_global_git_config()
        if 2 != len(global_git_vars):
            logging.error("Global git variables (user name and email) not available.")
            return
        committer_name, committer_email = global_git_vars
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
        shared_config["general"]["SHARE_STAT_REQ"] = self.SHARE_STAT_REQ
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
            + ".references_learned_settings"
        )
        f.close()
        return

    def __setup_git(self) -> None:
        from subprocess import check_call
        from subprocess import DEVNULL
        from subprocess import STDOUT

        git_repo = git.Repo.init()
        logging.info("Install latest pre-commmit hooks")
        scripts_to_call = [
            ["pre-commit", "install"],
            ["pre-commit", "install", "--hook-type", "prepare-commit-msg"],
            ["pre-commit", "install", "--hook-type", "pre-push"],
            ["pre-commit", "autoupdate"],
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
        return

    def __require_empty_directory(self):

        cur_content = [str(x) for x in Path.cwd().glob("**/*")]

        if "venv" in cur_content:
            cur_content.remove("venv")
            # Note: we can use paths directly when initiating the project
        if "report.log" in cur_content:
            cur_content.remove("report.log")

        if 0 != len(cur_content):
            raise NonEmptyDirectoryError()

    def __inplace_change(
        self, filename: Path, old_string: str, new_string: str
    ) -> None:
        with open(filename) as f:
            s = f.read()
            if old_string not in s:
                logging.info(f'"{old_string}" not found in {filename}.')
                return
        with open(filename, "w") as f:
            s = s.replace(old_string, new_string)
            f.write(s)
        return

    def __retrieve_package_file(self, template_file: Path, target: Path) -> None:
        import pkgutil

        filedata = pkgutil.get_data(__name__, str(template_file))
        if filedata:
            with open(target, "w") as file:
                file.write(filedata.decode("utf-8"))
        return

    def __get_name_mail_from_global_git_config(self) -> list:
        ggit_conf_path = Path.home() / Path(".gitconfig")
        global_conf_details = []
        if ggit_conf_path.is_file():
            glob_git_conf = git.GitConfigParser([str(ggit_conf_path)], read_only=True)
            global_conf_details = [
                glob_git_conf.get("user", "name"),
                glob_git_conf.get("user", "email"),
            ]
        return global_conf_details

    def __create_local_index(self, local_index_repo: bool) -> None:
        if local_index_repo:
            return
        self.REVIEW_MANAGER.report_logger.handlers = []

        import os

        local_index_path = Path.home().joinpath(".colrev/local_index")
        curdir = Path.cwd()
        if not local_index_path.is_dir():
            local_index_path.mkdir(parents=True, exist_ok=True)
            os.chdir(local_index_path)
            Initializer("local_index", "PROCESSED", True)
            print("Created local_index repository")

        os.chdir(curdir)
        return


class NonEmptyDirectoryError(Exception):
    def __init__(self):
        self.message = "please change to an empty directory to initialize a project"
        super().__init__(self.message)


if __name__ == "__main__":
    pass
