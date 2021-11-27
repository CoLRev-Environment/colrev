import datetime
import logging
import os
import pprint
import subprocess

import click
import click_completion.core
import git

from review_template import repo_setup

pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)


def custom_startswith(string, incomplete):
    """A custom completion matching that supports case insensitive matching"""
    if os.environ.get("_CLICK_COMPLETION_COMMAND_CASE_INSENSITIVE_COMPLETE"):
        string = string.lower()
        incomplete = incomplete.lower()
    return string.startswith(incomplete)


# Note: autocompletion needs bash/... activation:
# https://click.palletsprojects.com/en/7.x/bashcomplete/


click_completion.core.startswith = custom_startswith
click_completion.init()


class SpecialHelpOrder(click.Group):
    def __init__(self, *args, **kwargs):
        self.help_priorities = {}
        super().__init__(*args, **kwargs)

    def get_help(self, ctx):
        self.list_commands = self.list_commands_for_help
        return super().get_help(ctx)

    def list_commands_for_help(self, ctx):
        """reorder the list of commands when listing the help"""
        commands = super().list_commands(ctx)
        return (
            c[1]
            for c in sorted(
                (self.help_priorities.get(command, 1), command) for command in commands
            )
        )

    def command(self, *args, **kwargs):
        """Behaves the same as `click.Group.command()` except capture
        a priority for listing command names in help.
        """
        help_priority = kwargs.pop("help_priority", 1)
        help_priorities = self.help_priorities

        def decorator(f):
            cmd = super(SpecialHelpOrder, self).command(*args, **kwargs)(f)
            help_priorities[cmd.name] = help_priority
            return cmd

        return decorator


def get_repo() -> git.Repo:
    try:
        repo = git.Repo()
    except git.exc.InvalidGitRepositoryError:
        logging.error("No git repository found. Use review_template init")
        pass
        return None

    return repo


def get_value(msg: str, options: dict) -> str:
    valid_response = False
    user_input = ""
    while not valid_response:
        print(f" {msg} (" + "|".join(options) + ")")
        user_input = input()
        if user_input in options:
            valid_response = True
    return user_input


@click.group(cls=SpecialHelpOrder)
@click.pass_context
def main(ctx):
    """Review template pipeline

    Main commands: init | status | process, screen, ..."""


@main.command(help_priority=1)
@click.pass_context
def init(ctx):
    """Initialize repository"""
    from review_template import init

    # We check this again when calling init.initialize_repo()
    # but at this point, we want to avoid that users enter a lot of data and
    # see an error at the end
    if 0 != len(os.listdir(os.getcwd())) and ["report.log"] != os.listdir(os.getcwd()):
        logging.error("Directory not empty.")
        return 0

    project_title = input("Project title: ")

    # maybe ask for committer_name, committer_mail (if not in git globals?)
    # committer_name = input("Please provide your name")
    # committer_email = input("Please provide your e-mail")

    SHARE_STAT_REQ = get_value(
        "Select share status requirement",
        ["NONE", "PROCESSED", "SCREENED", "COMPLETED"],
    )
    PDF_HANDLING = get_value("Select pdf handling", ["EXT", "GIT"])

    # TODO: allow multiple?
    DATA_FORMAT = get_value(
        "Select data structure",
        ["NONE", "STRUCTURED", "MANUSCRIPT", "SHEETs", "MACODING"],
    )

    if "y" == input("Connect to shared (remote) repository (y)?"):
        remote_url = input("URL:")
    else:
        remote_url = None

    init.initialize_repo(
        project_title, SHARE_STAT_REQ, PDF_HANDLING, DATA_FORMAT, remote_url
    )


def print_review_instructions(review_instructions: dict) -> None:

    logging.debug(pp.pformat(review_instructions))
    print("\n\nNext steps\n")
    for review_instruction in review_instructions:

        if repo_setup.config["DELAY_AUTOMATED_PROCESSING"]:
            if "priority" not in review_instruction:
                continue

        if "info" in review_instruction:
            print("  " + review_instruction["info"])
        if "msg" in review_instruction:
            print("  " + review_instruction["msg"])
        if "cmd" in review_instruction:
            print("  i.e., use " + review_instruction["cmd"])
        if "cmd_after" in review_instruction:
            print("  Then use " + review_instruction["cmd_after"])
        print()

    return


class colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    ORANGE = "\033[93m"
    BLUE = "\033[94m"
    END = "\033[0m"


def print_collaboration_instructions(collaboration_instructions: dict) -> None:

    logging.debug(pp.pformat(collaboration_instructions))
    print(collaboration_instructions["title"] + "\n")

    if "status" in collaboration_instructions:
        if "title" in collaboration_instructions["status"]:
            title = collaboration_instructions["status"]["title"]
            if "WARNING" == collaboration_instructions["status"].get("level", "NA"):
                print(f"  {colors.RED}{title}{colors.END}")
            elif "SUCCESS" == collaboration_instructions["status"].get("level", "NA"):
                print(f"  {colors.GREEN}{title}{colors.END}")
            else:
                print("  " + title)
        if "msg" in collaboration_instructions["status"]:
            print(f'  {collaboration_instructions["status"]["msg"]}')

    if "SHARE_STAT_REQ" in collaboration_instructions:
        print(f"  Sharing requirement: {collaboration_instructions['SHARE_STAT_REQ']}")
    for item in collaboration_instructions["items"]:
        if "title" in item:
            if "level" in item:
                if "WARNING" == item["level"]:
                    print(f'  {colors.RED}{item["title"]}{colors.END}')
                elif "SUCCESS" == item["level"]:
                    print(f'  {colors.GREEN}{item["title"]}{colors.END}')
            else:
                print("  " + item["title"])

        if "msg" in item:
            print("  " + item["msg"])
        if "cmd_after" in item:
            print("  Then use \n   " + "\n  ".join(item["cmd_after"].split("\n")))
        print()
    return


def print_progress(stat: dict) -> None:
    # Prints the percentage of atomic processing tasks that have been completed
    # possible extension: estimate the number of manual tasks (making assumptions on
    # frequencies of man-prep, ...)?

    total_atomic_steps = stat["review_status"]["overall"]["atomic_steps"]
    completed_steps = stat["review_status"]["currently"]["completed_atomic_steps"]

    if total_atomic_steps != 0:
        current = int((completed_steps / total_atomic_steps) * 100)
    else:
        current = -1

    sleep_interval = 1.3 / max(current, 100)
    print()
    from time import sleep
    from tqdm import tqdm

    for i in tqdm(
        range(100),
        desc="  Progress:",
        bar_format="{desc} |{bar}|{percentage:.0f}%",
        ncols=40,
    ):
        sleep(sleep_interval)
        if current == i or current == -1:
            break
    return


@main.command(help_priority=2)
@click.pass_context
def status(ctx):
    """Show status"""
    from review_template import status
    from review_template import utils

    status.repository_validation()
    # TODO: automatically update pre-commit hooks if necessary?
    # # Default: automatically update hooks
    # logging.info("Update pre-commmit hooks")
    # check_call(
    #     ["pre-commit", "autoupdate", "--bleeding-edge"],
    #     stdout=DEVNULL,
    #     stderr=STDOUT,
    # )

    # utils.update_status_yaml()

    # repo.index.add([".pre-commit-config.yaml", "status.yaml"])
    # repo.index.commit(
    #     "Update pre-commit-config"
    #     + utils.get_version_flag()
    #     + utils.get_commit_report(),
    #     author=git.Actor("script:" + os.path.basename(__file__), ""),
    #     committer=git.Actor(
    #         repo_setup.config["GIT_ACTOR"], repo_setup.config["EMAIL"]
    #     ),
    # )
    # logging.info("Commited updated pre-commit hooks")
    # utils.reset_log()

    # we could offer a parameter to disable autoupdates (warn accordingly)
    #     ('  pipeline-validation-hooks version outdated.
    #           use pre-commit autoupdate')
    #     sys.exit()
    #     # once we use tags, we may consider recommending
    #     # pre-commit autoupdate --bleeding-edge

    # os.rename(".pre-commit-config.yaml", "bak_pre-commit-config.yaml")
    # utils.retrieve_package_file(
    #     "../template/.pre-commit-config.yaml",
    #     ".pre-commit-config.yaml",
    # )
    # logging.info("Install pre-commmit hooks")
    # check_call(["pre-commit", "install"], stdout=DEVNULL, stderr=STDOUT)

    # logging.info("Update pre-commmit hooks")
    # check_call(
    #     ["pre-commit", "autoupdate", "--bleeding-edge"],
    #     stdout=DEVNULL,
    #     stderr=STDOUT,
    # )

    # logging.warning(
    #     "Updated pre-commit hook. Please check/remove bak_pre-commit-config.yaml"
    # )

    utils.update_status_yaml()

    # TODO: check whether it is a valid git repo

    print("\nChecks\n")
    ret = subprocess.call(["pre-commit", "run", "-a"])

    if ret == 0:
        stat = status.get_status_freq()
        status.print_review_status(stat)
        print_progress(stat)
        review_instructions = status.get_review_instructions(stat)
        print_review_instructions(review_instructions)
        collaboration_instructions = status.get_collaboration_instructions(stat)
        print_collaboration_instructions(collaboration_instructions)

        print(
            "Documentation\n\n   "
            "See https://github.com/geritwagner/review_template/docs\n"
        )


@main.command(help_priority=3)
@click.pass_context
@click.option("--reprocess", help='Record ID to reprocess ("all" to reprocess all).')
@click.option(
    "-k",
    "--keep_ids",
    is_flag=True,
    default=False,
    help="Do not change the record IDs. Useful when importing " + "an existing sample.",
)
def process(ctx, reprocess, keep_ids):
    """Process records (automated steps)"""
    from review_template import process

    process.main(reprocess, keep_ids)


def check_update_search_details() -> None:
    from review_template import utils
    from review_template import importer

    search_details = utils.load_search_details()

    search_files = importer.get_search_files()
    for sfp in search_files:
        # Note : for non-bib files, we check search_details for corresponding bib file
        # (which will be created later in the process)
        if not sfp.endswith("bib"):
            sfp = sfp[: sfp.rfind(".")] + ".bib"
        search_file = os.path.basename(sfp)
        if search_file not in [x["filename"] for x in search_details]:
            source_name = importer.source_heuristics(sfp)
            print(f"Please provide details for {search_file}")
            search_type = "TODO"
            while search_type not in importer.search_type_opts:
                print(f"Search type options: {importer.search_type_opts}")
                search_type = input("Enter search type".ljust(40, " ") + ": ")
            if source_name is None:
                source_name = input(
                    "Enter source name (e.g., GoogleScholar)".ljust(40, " ") + ": "
                )
            else:
                print("Source name".ljust(40, " ") + f": {source_name}")
            source_url = input("Enter source_url".ljust(40, " ") + ": ")
            search_parameters = input("Enter search_parameters".ljust(40, " ") + ": ")
            comment = input("Enter a comment (or NA)".ljust(40, " ") + ": ")

            new_record = {
                "filename": search_file,
                "search_type": search_type,
                "source_name": source_name,
                "source_url": source_url,
                "search_parameters": search_parameters,
                "comment": comment,
            }
            importer.append_search_details(new_record)

    return


@main.command(help_priority=4)
@click.option(
    "-k",
    "--keep_ids",
    is_flag=True,
    default=False,
    help="Do not change the record IDs. Useful when importing " + "an existing sample.",
)
@click.pass_context
def importer(ctx, keep_ids):
    """Import records (part of automated processing)"""
    from review_template import importer

    try:
        importer.validate_file_formats()
        check_update_search_details()
        repo = get_repo()
        importer.main(repo, keep_ids)
    except importer.UnsupportedImportFormatError as e:
        logging.error(e)
        logging.info("Remove file from repository and use review_template importer")
        pass
    except importer.SearchDetailsMissingError as e:
        logging.error(e)
        pass


@main.command(help_priority=5)
@click.option(
    "--reset_id",
    default=False,
    help="Reset record metadata to the imported version. "
    "Format: --reset_id ID1,ID2,ID3",
)
@click.option(
    "--reprocess",
    is_flag=True,
    default=False,
    help="Prepare all records set to md_status="
    + "needs_manual_preparation again. Useful if "
    + "network/databases were not available",
)
@click.option(
    "-k",
    "--keep_ids",
    is_flag=True,
    default=False,
    help="Do not change the record IDs. Useful when importing " + "an existing sample.",
)
@click.pass_context
def prepare(ctx, reset_id, reprocess, keep_ids):
    """Prepare records (part of automated processing)"""
    from review_template import prepare, utils

    repo = get_repo()
    bib_db = utils.load_main_refs()

    # parse to reset_ids list
    if reset_id:
        try:
            reset_id = str(reset_id)
        except ValueError:
            pass
        reset_id = reset_id.split(",")
        prepare.reset_ids(bib_db, repo, reset_id)
    else:
        prepare.main(bib_db, repo, reprocess, keep_ids)


@main.command(help_priority=6)
@click.pass_context
def dedupe(ctx):
    """Deduplicate records (part of automated processing)"""
    from review_template import dedupe, utils

    repo = get_repo()
    bib_db = utils.load_main_refs()
    dedupe.main(bib_db, repo)


@main.command(help_priority=7)
@click.option(
    "--stats",
    is_flag=True,
    default=False,
    help="Print statistics of records with md_status needs_manual_preparation",
)
@click.option(
    "--extract",
    is_flag=True,
    default=False,
    help="Extract records with md_status needs_manual_preparation",
)
@click.pass_context
def man_prep(ctx, stats, extract):
    """Manual preparation of records"""
    from review_template import man_prep

    if stats:
        man_prep.man_prep_stats()
    elif extract:
        man_prep.extract_needs_man_prep()
    else:
        man_prep.man_prep_records()


@main.command(help_priority=8)
@click.pass_context
def man_dedupe(ctx):
    """Manual processing of duplicates"""
    from review_template import man_dedupe

    man_dedupe.main()


def prescreen_cli(
    repo,
) -> None:

    from review_template import prescreen, utils, screen

    # Note : the get_next() (generator/yield ) pattern would be appropriate for GUIs...

    saved_args = locals()

    pp = pprint.PrettyPrinter(indent=4, width=140)
    i, quit_pressed = 1, False
    PAD = 50
    # PAD = min((max(len(x["ID"]) for x in bib_db.entries) + 2), 35)
    # logging.info("Start prescreen")
    # stat_len = len(
    #     [x for x in bib_db.entries if "retrieved" == x.get("rev_status", "NA")]
    # )
    stat_len = 100  # TODO
    if 0 == stat_len:
        logging.info("No records to prescreen")

    for record in prescreen.get_next_prescreening_item():

        print("\n\n")
        revrecord = screen.customsort(record)
        pp.pprint(revrecord)

        ret, inclusion_decision = "NA", "NA"
        while ret not in ["y", "n", "s", "q"]:
            # ret = input(f"({i+1}/{stat_len}) Include this record [y,n,q,s]? ")
            ret = input("Include this record [y,n,q,s]? ")
            if "q" == ret:
                quit_pressed = True
            elif "s" == ret:
                continue
            else:
                inclusion_decision = ret.replace("y", "yes").replace("n", "no")

        if quit_pressed:
            logging.info("Stop prescreen")
            break

        if "no" == inclusion_decision:
            prescreen.set_prescreen_status(record["ID"], False)
            logging.info(f' {record["ID"]}'.ljust(PAD, " ") + "Excluded in prescreen")
        if "yes" == inclusion_decision:
            prescreen.set_prescreen_status(record["ID"], True)
            logging.info(f' {record["ID"]}'.ljust(PAD, " ") + "Included in prescreen")

    if i < stat_len:  # if records remain for pre-screening
        if "y" != input("Create commit (y/n)?"):
            return
    elif i == stat_len:
        repo.index.add([repo_setup.paths["MAIN_REFERENCES"]])
        utils.create_commit(
            repo, "Pre-screening (manual)", saved_args, manual_author=True
        )
    return


@main.command(help_priority=9)
@click.option("--include_all", is_flag=True, default=False)
@click.option(
    "--export_format",
    type=click.Choice(["CSV", "XLSX"], case_sensitive=False),
    help="Export table with the screening decisions",
)
@click.option(
    "--import_table",
    type=click.Path(),
    help="Import file with the screening decisions (csv supported)",
)
@click.pass_context
def prescreen(ctx, include_all, export_format, import_table):
    """Pre-screen based on titles and abstracts"""
    from review_template import prescreen, utils

    repo = get_repo()
    if export_format:
        bib_db = utils.load_main_refs()
        prescreen.export_table(bib_db, export_format)
    elif import_table:
        bib_db = utils.load_main_refs()
        prescreen.import_table(bib_db, import_table)
    elif include_all:
        bib_db = utils.load_main_refs()
        prescreen.include_all_in_prescreen(bib_db, repo)
    else:
        prescreen_cli(repo)


@main.command(help_priority=10)
@click.pass_context
def screen(ctx):
    """Screen based on exclusion criteria and fulltext documents"""
    from review_template import screen

    screen.screen()


@main.command(help_priority=11)
@click.pass_context
def pdfs(ctx):
    """Retrieve PDFs  (part of automated processing)"""
    from review_template import pdfs, utils

    bib_db = utils.load_main_refs()
    repo = get_repo()
    pdfs.main(bib_db, repo)


@main.command(help_priority=12)
@click.pass_context
def pdf_prepare(ctx):
    """Prepare PDFs  (part of automated processing)"""
    from review_template import pdf_prepare, utils

    bib_db = utils.load_main_refs()
    repo = get_repo()
    pdf_prepare.main(bib_db, repo)


@main.command(help_priority=13)
@click.pass_context
def pdf_get_man(ctx):
    """Get PDFs manually"""
    from review_template import pdf_get_man, utils

    bib_db = utils.load_main_refs()
    repo = get_repo()
    pdf_get_man.main(bib_db, repo)


@main.command(help_priority=14)
@click.pass_context
def pdf_prep_man(ctx):
    """Prepare PDFs manually"""
    from review_template import pdf_prep_man, utils

    bib_db = utils.load_main_refs()
    repo = get_repo()
    pdf_prep_man.main(bib_db, repo)


@main.command(help_priority=15)
@click.pass_context
def back_search(ctx):
    """Backward search based on PDFs"""
    from review_template import back_search

    back_search.main()


@main.command(help_priority=16)
@click.option("--edit_csv", is_flag=True, default=False)
@click.option("--load_csv", is_flag=True, default=False)
@click.pass_context
def data(ctx, edit_csv, load_csv):
    """Extract data"""
    from review_template import data

    data.main(edit_csv, load_csv)


@main.command(help_priority=17)
@click.pass_context
def profile(ctx):
    """Generate a sample profile"""
    from review_template import profile

    profile.main()


def validate_commit(ctx, param, value):
    if "none" == value:
        return value
    repo = git.Repo()

    revlist = [commit for commit in repo.iter_commits()]

    if value in [x.hexsha for x in revlist]:
        # TODO: allow short commit_ids as values!
        return value
    else:
        print("Error: Invalid value for '--commit': not a git commit id\n")
        print("Select any of the following commit ids:\n")
        print("commit-id".ljust(41, " ") + "date".ljust(24, " ") + "commit message")
        commits_for_checking = []
        for c in reversed(list(revlist)):
            commits_for_checking.append(c)
        for commit in revlist:
            print(
                commit.hexsha,
                datetime.datetime.fromtimestamp(commit.committed_date),
                " - ",
                commit.message.split("\n")[0],
            )
        print("\n")
        raise click.BadParameter("not a git commit id")


@main.command(help_priority=18)
@click.option(
    "--scope",
    type=click.Choice(["prepare", "merge", "all"], case_sensitive=False),
    default="all",
    help="prepare, merge, or all.",
)
@click.option(
    "--properties", is_flag=True, default=False, help="Git commit id to validate."
)
@click.option(
    "--commit",
    help="Git commit id to validate.",
    default=None,
    callback=validate_commit,
)
@click.pass_context
def validate(ctx, scope, properties, commit):
    """Validate changes"""
    from review_template import validate

    validate.main(scope, properties, commit)


@main.command(help_priority=19)
@click.pass_context
@click.option("--id", help="Record ID to trace (citation_key).", required=True)
def trace(ctx, id):
    """Trace a record"""
    from review_template import trace

    trace.main(id)


@main.command(help_priority=20)
@click.pass_context
def paper(ctx):
    """Build the paper"""
    from review_template import paper

    paper.main()


ccs = click_completion.core.shells


@main.command(help_priority=21)
@click.option("--activate", is_flag=True, default=False)
@click.option("--deactivate", is_flag=True, default=False)
@click.pass_context
def debug(ctx, activate, deactivate):
    """Debug"""
    from review_template import debug

    if activate:
        debug.set_debug_mode(True)

    elif deactivate:
        debug.set_debug_mode(False)
    else:
        debug.main()


@main.command(hidden=True)
@click.option(
    "--append/--overwrite", help="Append the completion code to the file", default=None
)
@click.option(
    "-i", "--case-insensitive/--no-case-insensitive", help="Case insensitive completion"
)
@click.argument("shell", required=False, type=click_completion.DocumentedChoice(ccs))
@click.argument("path", required=False)
def cli_completion_activate(append, case_insensitive, shell, path):
    """Install the click-completion-command completion"""
    extra_env = (
        {"_CLICK_COMPLETION_COMMAND_CASE_INSENSITIVE_COMPLETE": "ON"}
        if case_insensitive
        else {}
    )
    shell, path = click_completion.core.install(
        shell=shell, path=path, append=append, extra_env=extra_env
    )
    click.echo(f"{shell} completion installed in {path}")
