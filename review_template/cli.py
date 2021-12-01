import datetime
import logging
import os
import pprint
import subprocess

import click
import click_completion.core
import git

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


def get_value(msg: str, options: dict) -> str:
    valid_response = False
    user_input = ""
    while not valid_response:
        print(f" {msg} (" + "|".join(options) + ")")
        user_input = input()
        if user_input in options:
            valid_response = True
    return user_input


class colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    ORANGE = "\033[93m"
    BLUE = "\033[94m"
    END = "\033[0m"


@click.group(cls=SpecialHelpOrder)
@click.pass_context
def main(ctx):
    """Review template pipeline

    Main commands: init | status | process, screen, ..."""


@main.command(help_priority=1)
@click.pass_context
def init(ctx) -> bool:
    """Initialize repository"""
    from review_template import init

    # We check this again when calling init.initialize_repo()
    # but at this point, we want to avoid that users enter a lot of data and
    # see an error at the end
    if 0 != len(os.listdir(os.getcwd())) and ["report.log"] != os.listdir(os.getcwd()):
        logging.error("Directory not empty.")
        return False

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
    return True


def print_review_instructions(review_instructions: dict) -> None:

    logging.debug(pp.pformat(review_instructions))
    print("\n\nNext steps\n")

    keylist = [list(x.keys()) for x in review_instructions]
    keys = [item for sublist in keylist for item in sublist]
    priority_item_set = "priority" in keys

    for review_instruction in review_instructions:
        if priority_item_set and "priority" not in review_instruction.keys():
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
            print("  Then use \n   \n  ".join(item["cmd_after"].split("\n")))
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
def status(ctx) -> None:
    """Show status"""
    from review_template import status
    from review_template.review_manager import ReviewManager

    status.repository_validation()
    REVIEW_MANAGER = ReviewManager()
    REVIEW_MANAGER.update_status_yaml()

    # TODO: check whether it is a valid git repo

    print("\nChecks\n")
    ret = subprocess.call(["pre-commit", "run", "-a"])

    if ret == 0:
        stat = status.get_status_freq(REVIEW_MANAGER)
        status.print_review_status(REVIEW_MANAGER, stat)
        print_progress(stat)

        instructions = status.get_instructions(REVIEW_MANAGER, stat)
        logging.debug(pp.pformat(instructions))
        print_review_instructions(instructions["review_instructions"])
        print_collaboration_instructions(instructions["collaboration_instructions"])

        print(
            "Documentation\n\n   "
            "See https://github.com/geritwagner/review_template/docs\n"
        )

    # TODO: automatically update pre-commit hooks if necessary?
    # # Default: automatically update hooks
    # logging.info("Update pre-commmit hooks")
    # check_call(
    #     ["pre-commit", "autoupdate", "--bleeding-edge"],
    #     stdout=DEVNULL,
    #     stderr=STDOUT,
    # )

    # REVIEW_MANAGER.update_status_yaml()

    # repo.index.add([".pre-commit-config.yaml", "status.yaml"])
    # repo.index.commit(
    #     "Update pre-commit-config"
    #     + REVIEW_MANAGER.get_version_flag()
    #     + REVIEW_MANAGER.get_commit_report(),
    #     author=git.Actor("script:" + os.path.basename(__file__), ""),
    #     committer=git.Actor(
    #         REVIEW_MANAGER.config["GIT_ACTOR"], REVIEW_MANAGER.config["EMAIL"]
    #     ),
    # )
    # logging.info("Commited updated pre-commit hooks")

    # we could offer a parameter to disable autoupdates (warn accordingly)
    #     ('  pipeline-validation-hooks version outdated.
    #           use pre-commit autoupdate')
    #     sys.exit()
    #     # once we use tags, we may consider recommending
    #     # pre-commit autoupdate --bleeding-edge

    # os.rename(".pre-commit-config.yaml", "bak_pre-commit-config.yaml")
    # REVIEW_MANAGER.retrieve_package_file(
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
    return


@main.command(help_priority=3)
@click.pass_context
@click.option("--reprocess", help='Record ID to reprocess ("all" to reprocess all).')
@click.option(
    "-k",
    "--keep_ids",
    is_flag=True,
    default=False,
    help="Do not change the record IDs. Useful when importing an existing sample.",
)
def process(ctx, reprocess_id, keep_ids) -> None:
    """Process records (automated steps)"""
    from review_template import process
    from review_template.review_manager import ReviewManager

    try:
        REVIEW_MANAGER = ReviewManager()
        process.main(REVIEW_MANAGER, reprocess_id, keep_ids)
    except git.exc.InvalidGitRepositoryError:
        logging.error("No git repository found. Use review_template init")
        pass
        return

    return


def check_update_search_details(REVIEW_MANAGER) -> None:
    from review_template import load

    search_details = REVIEW_MANAGER.search_details

    search_files = load.get_search_files()
    for sfp in search_files:
        # Note : for non-bib files, we check search_details for corresponding bib file
        # (which will be created later in the process)
        if not sfp.endswith("bib"):
            sfp = sfp[: sfp.rfind(".")] + ".bib"
        search_file = os.path.basename(sfp)
        if search_file not in [x["filename"] for x in search_details]:
            source_name = load.source_heuristics(sfp)
            print(f"Please provide details for {search_file}")
            search_type = "TODO"
            while search_type not in REVIEW_MANAGER.search_type_opts:
                print(f"Search type options: {REVIEW_MANAGER.search_type_opts}")
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
            load.append_search_details(REVIEW_MANAGER, new_record)

    return


@main.command(help_priority=4)
@click.option(
    "-k",
    "--keep_ids",
    is_flag=True,
    default=False,
    help="Do not change the record IDs. Useful when importing an existing sample.",
)
@click.pass_context
def load(ctx, keep_ids) -> None:
    """Import records (part of automated processing)"""
    from review_template import load
    from review_template.review_manager import SearchDetailsMissingError
    from review_template.review_manager import ReviewManager
    from review_template.review_manager import ProcessType
    from review_template.review_manager import Process

    try:

        REVIEW_MANAGER = ReviewManager()
        load.validate_file_formats()
        check_update_search_details(REVIEW_MANAGER)
        load_process = Process(ProcessType.load, load.main)
        REVIEW_MANAGER.run_process(load_process, keep_ids)

    except load.UnsupportedImportFormatError as e:
        logging.error(e)
        logging.info(
            "UnsupportedImportFormatError: Remove file from repository and "
            + "use review_template load"
        )
        pass
    except SearchDetailsMissingError as e:
        logging.error(f"SearchDetailsMissingError: {e}")
        pass
    except load.NoSearchResultsAvailableError as e:
        logging.error(f"NoSearchResultsAvailableError: {e}")
        pass
    return


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
    help="Do not change the record IDs. Useful when importing an existing sample.",
)
@click.pass_context
def prepare(ctx, reset_id, reprocess, keep_ids) -> None:
    """Prepare records (part of automated processing)"""
    from review_template import prepare
    from review_template.review_manager import ReviewManager
    from review_template.review_manager import ProcessType
    from review_template.review_manager import Process

    REVIEW_MANAGER = ReviewManager()

    if reset_id:
        try:
            reset_id = str(reset_id)
        except ValueError:
            pass
        reset_id = reset_id.split(",")
        prepare.reset_ids(REVIEW_MANAGER, reset_id)
    else:
        prepare_process = Process(ProcessType.prepare, prepare.main)
        REVIEW_MANAGER.run_process(prepare_process, reprocess, keep_ids)

    return


@main.command(help_priority=6)
@click.pass_context
def dedupe(ctx) -> None:
    """Deduplicate records (part of automated processing)"""
    from review_template import dedupe
    from review_template import review_manager
    from review_template.review_manager import ReviewManager
    from review_template.review_manager import ProcessType
    from review_template.review_manager import Process

    try:
        REVIEW_MANAGER = ReviewManager()
        dedupe_process = Process(ProcessType.dedupe, dedupe.main)
        REVIEW_MANAGER.run_process(dedupe_process)
        # dedupe.main(REVIEW_MANAGER)

    except review_manager.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")
        pass
    except KeyboardInterrupt:
        logging.error("KeyboardInterrupt")
        if os.path.exists("non_duplicates.csv"):
            os.remove("non_duplicates.csv")
        if os.path.exists("queue_order.csv"):
            os.remove("queue_order.csv")
        pass
    return


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
def man_prep(ctx, stats, extract) -> None:
    """Manual preparation of records"""
    from review_template import man_prep
    from review_template.review_manager import ReviewManager
    from review_template.review_manager import ProcessType
    from review_template.review_manager import Process

    REVIEW_MANAGER = ReviewManager()

    if stats:
        man_prep.man_prep_stats(REVIEW_MANAGER)
    elif extract:
        man_prep.extract_needs_man_prep(REVIEW_MANAGER)
    else:
        REVIEW_MANAGER.notify(
            Process(ProcessType.man_prep, man_prep.man_prep_records, interactive=True)
        )
        man_prep.man_prep_records(REVIEW_MANAGER)

    return


@main.command(help_priority=8)
@click.pass_context
def man_dedupe(ctx) -> None:
    """Manual processing of duplicates"""
    from review_template import man_dedupe
    from review_template import review_manager
    from review_template.review_manager import ReviewManager
    from review_template.review_manager import ProcessType
    from review_template.review_manager import Process

    try:
        REVIEW_MANAGER = ReviewManager()
        REVIEW_MANAGER.notify(
            Process(ProcessType.man_dedupe, man_dedupe.main, interactive=True)
        )
        man_dedupe.main(REVIEW_MANAGER)
    except review_manager.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")
        pass
    except review_manager.CleanRepoRequiredError as e:
        logging.error(f"CleanRepoRequiredError: {e}")
        pass
    return


def prescreen_cli(
    REVIEW_MANAGER,
) -> None:

    from review_template import prescreen, screen

    # Note : the get_next() (generator/yield ) pattern would be appropriate for GUIs...

    git_repo = REVIEW_MANAGER.get_repo()

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

    for record in prescreen.get_next_prescreening_item(REVIEW_MANAGER):

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
            prescreen.set_prescreen_status(REVIEW_MANAGER, record["ID"], False)
            logging.info(f' {record["ID"]}'.ljust(PAD, " ") + "Excluded in prescreen")
        if "yes" == inclusion_decision:
            prescreen.set_prescreen_status(REVIEW_MANAGER, record["ID"], True)
            logging.info(f' {record["ID"]}'.ljust(PAD, " ") + "Included in prescreen")

    if i < stat_len:  # if records remain for pre-screening
        if "y" != input("Create commit (y/n)?"):
            return
    elif i == stat_len:
        git_repo.index.add([REVIEW_MANAGER.paths["MAIN_REFERENCES"]])
        REVIEW_MANAGER.create_commit("Pre-screening (manual)", manual_author=True)
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
def prescreen(ctx, include_all, export_format, import_table) -> None:
    """Pre-screen based on titles and abstracts"""
    from review_template import prescreen
    from review_template import review_manager
    from review_template.review_manager import ReviewManager
    from review_template.review_manager import ProcessType
    from review_template.review_manager import Process

    try:
        REVIEW_MANAGER = ReviewManager()

        if export_format:
            prescreen.export_table(REVIEW_MANAGER, export_format)
        elif import_table:
            prescreen.import_table(REVIEW_MANAGER, import_table)
        elif include_all:
            prescreen.include_all_in_prescreen(REVIEW_MANAGER)
        else:
            REVIEW_MANAGER.notify(
                Process(ProcessType.prescreen, prescreen_cli, interactive=True)
            )
            prescreen_cli(REVIEW_MANAGER)

    except review_manager.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")
        pass
    except review_manager.CleanRepoRequiredError as e:
        logging.error(f"CleanRepoRequiredError: {e}")
        pass

    return


@main.command(help_priority=10)
@click.pass_context
def screen(ctx) -> None:
    """Screen based on exclusion criteria and fulltext documents"""
    from review_template import screen
    from review_template import review_manager
    from review_template.review_manager import ReviewManager
    from review_template.review_manager import ProcessType
    from review_template.review_manager import Process

    try:
        REVIEW_MANAGER = ReviewManager()
        REVIEW_MANAGER.notify(
            Process(ProcessType.screen, screen.screen, interactive=True)
        )
        screen.screen(REVIEW_MANAGER)
    except review_manager.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")
        pass

    return


@main.command(help_priority=11)
@click.pass_context
def pdf_get(ctx) -> None:
    """Retrieve PDFs  (part of automated processing)"""
    from review_template import pdf_get
    from review_template import review_manager
    from review_template.review_manager import ReviewManager
    from review_template.review_manager import ProcessType
    from review_template.review_manager import Process

    try:
        REVIEW_MANAGER = ReviewManager()
        REVIEW_MANAGER.notify(
            Process(ProcessType.pdf_get, pdf_get.main, interactive=True)
        )
        pdf_get.main(REVIEW_MANAGER)
    except review_manager.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")
        pass

    return


@main.command(help_priority=12)
@click.pass_context
def pdf_prepare(ctx) -> None:
    """Prepare PDFs  (part of automated processing)"""
    from review_template import pdf_prepare
    from review_template import review_manager
    from review_template.review_manager import ReviewManager
    from review_template.review_manager import ProcessType
    from review_template.review_manager import Process

    try:
        REVIEW_MANAGER = ReviewManager()
        REVIEW_MANAGER.notify(
            Process(ProcessType.pdf_prepare, pdf_prepare.main, interactive=True)
        )
        pdf_prepare.main(REVIEW_MANAGER)
    except review_manager.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")
        pass

    return


@main.command(help_priority=13)
@click.pass_context
def pdf_get_man(ctx) -> None:
    """Get PDFs manually"""
    from review_template import pdf_get_man
    from review_template import review_manager
    from review_template.review_manager import ReviewManager
    from review_template.review_manager import ProcessType
    from review_template.review_manager import Process

    try:
        REVIEW_MANAGER = ReviewManager()
        REVIEW_MANAGER.notify(
            Process(ProcessType.pdf_get_man, pdf_get_man.main, interactive=True)
        )
        pdf_get_man.main(REVIEW_MANAGER)
    except review_manager.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")
        pass
    return


@main.command(help_priority=14)
@click.pass_context
def pdf_prep_man(ctx) -> None:
    """Prepare PDFs manually"""
    from review_template import pdf_prep_man
    from review_template import review_manager
    from review_template.review_manager import ReviewManager
    from review_template.review_manager import ProcessType
    from review_template.review_manager import Process

    try:
        REVIEW_MANAGER = ReviewManager()
        REVIEW_MANAGER.notify(
            Process(ProcessType.pdf_prep_man, pdf_prep_man.main, interactive=True)
        )
        pdf_prep_man.main(REVIEW_MANAGER)
    except review_manager.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")
        pass
    return


@main.command(help_priority=15)
@click.option("--edit_csv", is_flag=True, default=False)
@click.option("--load_csv", is_flag=True, default=False)
@click.pass_context
def data(ctx, edit_csv, load_csv) -> None:
    """Extract data"""
    from review_template import data
    from review_template import review_manager
    from review_template.review_manager import ReviewManager
    from review_template.review_manager import ProcessType
    from review_template.review_manager import Process

    try:
        REVIEW_MANAGER = ReviewManager()
        REVIEW_MANAGER.notify(Process(ProcessType.data, data.main, interactive=True))
        data.main(REVIEW_MANAGER, edit_csv, load_csv)
    except review_manager.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")
        pass
    return


def validate_commit(ctx, param, value):
    from review_template.review_manager import ReviewManager

    if "none" == value:
        return value

    REVIEW_MANAGER = ReviewManager()
    git_repo = REVIEW_MANAGER.get_repo()
    revlist = [commit for commit in git_repo.iter_commits()]

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
    return


@main.command(help_priority=16)
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
def validate(ctx, scope, properties, commit) -> None:
    """Validate changes"""
    from review_template import validate
    from review_template.review_manager import ReviewManager

    REVIEW_MANAGER = ReviewManager()
    validate.main(REVIEW_MANAGER, scope, properties, commit)
    return


@main.command(help_priority=17)
@click.pass_context
@click.option("--id", help="Record ID to trace (citation_key).", required=True)
def trace(ctx, id) -> None:
    """Trace a record"""
    from review_template import trace
    from review_template.review_manager import ReviewManager

    REVIEW_MANAGER = ReviewManager()
    trace.main(REVIEW_MANAGER, id)
    return


@main.command(help_priority=18)
@click.pass_context
def paper(ctx) -> None:
    """Build the paper"""
    from review_template import paper
    from review_template.review_manager import ReviewManager

    REVIEW_MANAGER = ReviewManager()
    paper.main(REVIEW_MANAGER)

    return


ccs = click_completion.core.shells


@main.command(help_priority=19)
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
