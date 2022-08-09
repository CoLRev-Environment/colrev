import datetime
import logging
import os
import pprint
from pathlib import Path

import click
import click_completion.core
from dacite.exceptions import MissingValueError

import colrev_core.cli_colors as colors
import colrev_core.exceptions as colrev_exceptions

pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)


# Note: autocompletion needs bash/... activation:
# https://click.palletsprojects.com/en/7.x/bashcomplete/


def __custom_startswith(string, incomplete):
    """A custom completion matching that supports case insensitive matching"""
    if os.environ.get("_CLICK_COMPLETION_COMMAND_CASE_INSENSITIVE_COMPLETE"):
        string = string.lower()
        incomplete = incomplete.lower()
    return string.startswith(incomplete)


click_completion.core.startswith = __custom_startswith
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


def get_value(msg: str, options: list) -> str:
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
    """CoLRev

    Main commands: init | status | search, load, screen, ...

    Documentation:  https://github.com/geritwagner/colrev_core/docs
    """


@main.command(help_priority=1)
@click.option("-n", "--name", help="Name of the repository (project)")
@click.option(
    "--type",
    type=str,
    default="literature_review",
    help="Review type (e.g., literature_review(default), curated_masterdata, realtime)",
)
@click.option("--url", help="Git remote URL (optional)")
@click.option(
    "--example",
    is_flag=True,
    default=False,
    help="Create example repository",
)
@click.pass_context
def init(ctx, name, type, url, example) -> bool:
    """Initialize repository"""
    import colrev_core.init

    try:
        # We check this again when calling init.initialize_repo()
        # but at this point, we want to avoid that users enter a lot of data and
        # see an error at the end

        cur_content = [str(x) for x in Path.cwd().glob("**/*")]

        if "venv" in cur_content:
            cur_content.remove("venv")
            # Note: we can use paths directly when initiating the project
        if "report.log" in cur_content:
            cur_content.remove("report.log")

        if 0 != len(cur_content):
            print("Empty directory required.")
            return False

        # Set reasonable defaults
        SHARE_STAT_REQ = "PROCESSED"

        colrev_core.init.Initializer(
            project_name=name,
            SHARE_STAT_REQ=SHARE_STAT_REQ,
            review_type=type,
            url=url,
            example=example,
        )

    except colrev_exceptions.ParameterError as e:
        print(e)

    return True


def print_review_instructions(review_instructions: dict) -> None:

    print("Review project\n")

    verbose = False

    keylist = [list(x.keys()) for x in review_instructions]
    keys = [item for sublist in keylist for item in sublist]
    priority_item_set = "priority" in keys

    for review_instruction in review_instructions:
        if priority_item_set and "priority" not in review_instruction.keys():
            continue
        if "info" in review_instruction:
            print("  " + review_instruction["info"])
        if "msg" in review_instruction:
            if "cmd" in review_instruction:
                if verbose:
                    print("  " + review_instruction["msg"] + ", i.e., use ")
                print(f'  {colors.ORANGE}{review_instruction["cmd"]}{colors.END}')
            else:
                print(f"  {colors.ORANGE}{review_instruction['msg']}{colors.END}")
        if "cmd_after" in review_instruction:
            print("  Then use " + review_instruction["cmd_after"])
        print()


def print_collaboration_instructions(collaboration_instructions: dict) -> None:

    print("Versioning and collaboration\n")

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
            print(f'  {item["cmd_after"]}')
        print()


def print_environment_instructions(environment_instructions: dict) -> None:
    if len(environment_instructions) == 0:
        return

    print("CoLRev environment\n")

    keylist = [list(x.keys()) for x in environment_instructions]
    keys = [item for sublist in keylist for item in sublist]
    priority_item_set = "priority" in keys

    for environment_instruction in environment_instructions:
        if priority_item_set and "priority" not in environment_instruction.keys():
            continue
        if "info" in environment_instruction:
            print("  " + environment_instruction["info"])
        if "msg" in environment_instruction:
            if "cmd" in environment_instruction:
                print("  " + environment_instruction["msg"] + "  i.e., use ")
                print(f'  {colors.ORANGE}{environment_instruction["cmd"]}{colors.END}')
            else:
                print("  " + environment_instruction["msg"])
        if "cmd_after" in environment_instruction:
            print("  Then use " + environment_instruction["cmd_after"])
        print()


def print_progress(stat: dict) -> None:
    # Prints the percentage of atomic processing tasks that have been completed
    # possible extension: estimate the number of manual tasks (making assumptions on
    # frequencies of man-prep, ...)?

    total_atomic_steps = stat["atomic_steps"]
    completed_steps = stat["completed_atomic_steps"]

    if total_atomic_steps != 0:
        current = int((completed_steps / total_atomic_steps) * 100)
    else:
        current = -1

    sleep_interval = 1.1 / max(current, 100)
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
        if current in [i, -1]:
            break


def print_project_status(STATUS) -> None:

    stat = STATUS.REVIEW_MANAGER.get_status_freq()
    try:
        # if ret_check["status"] + ret_f["status"] == 0:
        STATUS.print_review_status(status_info=stat)
        print_progress(stat)
    except Exception as e:
        print(f"Status failed ({e})")

    print("")

    instructions = STATUS.get_instructions(stat=stat)
    print_review_instructions(instructions["review_instructions"])
    print_collaboration_instructions(instructions["collaboration_instructions"])
    print_environment_instructions(instructions["environment_instructions"])

    print("Checks\n")

    try:
        ret_check = STATUS.REVIEW_MANAGER.check_repo()
    except colrev_exceptions.RepoSetupError as e:
        ret_check = {"status": 1, "msg": e}

    if 0 == ret_check["status"]:
        print(
            "  ReviewManager.check_repo()  ...  "
            f'{colors.GREEN}{ret_check["msg"]}{colors.END}'
        )
    if 1 == ret_check["status"]:
        print(f"  ReviewManager.check_repo()  ...  {colors.RED}FAIL{colors.END}")
        print(f'{ret_check["msg"]}\n')
        return

    try:
        ret_f = STATUS.REVIEW_MANAGER.format_records_file()
    except KeyError as e:
        print(e)
        ret_f = {"status": 1, "msg": "KeyError"}
    if 0 == ret_f["status"]:
        print(
            "  ReviewManager.format()      ...  "
            f'{colors.GREEN}{ret_f["msg"]}{colors.END}'
        )
    if 1 == ret_f["status"]:
        print(f"  ReviewManager.format()      ...  {colors.RED}FAIL{colors.END}")
        print(f'\n    {ret_f["msg"]}\n')
    if not STATUS.REVIEW_MANAGER.in_virtualenv():
        print(
            f"  {colors.RED}WARNING{colors.END} running scripts outside of virtualenv"
        )
        print(
            "  For instructions to set up a virtual environment, run\n"
            f"  {colors.ORANGE}colrev show venv{colors.END}"
        )
    print()


@main.command(help_priority=2)
@click.option(
    "-a",
    "--analytics",
    is_flag=True,
    default=False,
    help="Print analytics",
)
@click.pass_context
def status(ctx, analytics) -> None:
    """Show status"""
    from git.exc import InvalidGitRepositoryError

    if analytics:
        import colrev_core.status
        import colrev_core.review_manager

        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
        STATUS = colrev_core.status.Status(REVIEW_MANAGER=REVIEW_MANAGER)
        analytic_results = STATUS.get_analytics()

        for cid, data_item in reversed(analytic_results.items()):
            print(f"{cid} - {data_item}")
        return

    try:
        import colrev_core.review_manager

        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
        STATUS = colrev_core.status.Status(REVIEW_MANAGER=REVIEW_MANAGER)

        print_project_status(STATUS)

    except InvalidGitRepositoryError:
        print("Not a CoLRev/git repository. Run")
        print("    colrev init")
        return
    except colrev_exceptions.CoLRevUpgradeError as e:
        print(e)
        return
    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
    except KeyboardInterrupt:
        print("Stopped...")


@main.command(help_priority=3)
@click.option(
    "-a",
    "--add",
    type=str,
    help="""
Format: RETRIEVE * FROM crossref WHERE title LIKE '%keyword%'
""",
)
@click.option("-v", "--view", is_flag=True, default=False, help="View search sources")
@click.option(
    "-s",
    "--selected",
    type=str,
    help="Only retrieve search results for selected sources",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom search script.",
)
@click.option(
    "-f",
    "--force_mode",
    is_flag=True,
    default=False,
    help="Force mode: conduct full search again",
)
@click.pass_context
def search(ctx, add, view, selected, setup_custom_script, force_mode) -> None:
    """Retrieve search records"""
    import colrev_core.search
    import colrev_core.review_manager

    try:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager(force_mode=force_mode)

        SEARCH = colrev_core.search.Search(REVIEW_MANAGER=REVIEW_MANAGER)
        if add:
            SEARCH.add_source(query=add)
        elif view:
            SEARCH.view_sources()
        elif setup_custom_script:
            SEARCH.setup_custom_script()
            print("Activated custom_search_script.py.")
            print("Please update the source in settings.json and commit.")
        else:
            SEARCH.main(selection_str=selected)

    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
    except colrev_exceptions.NoSearchFeedRegistered as e:
        print(e)
    except colrev_exceptions.ServiceNotAvailableException as e:
        print(e)


@main.command(help_priority=4)
@click.option(
    "-k",
    "--keep_ids",
    is_flag=True,
    default=False,
    help="Do not change the record IDs. Useful when importing an existing sample.",
)
@click.option(
    "-c",
    "--combine_commits",
    is_flag=True,
    default=False,
    help="Combine load of multiple sources in one commit.",
)
@click.pass_context
def load(ctx, keep_ids, combine_commits) -> None:
    """Import records"""
    import colrev_core.review_manager
    import colrev_core.load
    import colrev_core.environment

    try:
        # already start LocalIndex (for set_IDs)
        colrev_core.environment.LocalIndex(startup_without_waiting=True)
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
        return

    try:
        LOADER = colrev_core.load.Loader(REVIEW_MANAGER=REVIEW_MANAGER)
        LOADER.check_update_sources()
        if combine_commits:
            logging.info(
                "Combine mode: all search sources will be loaded in one commit"
            )
        # Note : reinitialize to load new scripts:
        LOADER = colrev_core.load.Loader(REVIEW_MANAGER=LOADER.REVIEW_MANAGER)
        LOADER.main(keep_ids=keep_ids, combine_commits=combine_commits)
    except colrev_exceptions.SearchSettingsError as e:
        logging.error(f"SearchSettingsError: {e}")


@main.command(help_priority=5)
@click.option(
    "--similarity",
    default=0.9,
    type=float,
    help="Retrieval similarity threshold",
)
@click.option(
    "-k",
    "--keep_ids",
    is_flag=True,
    default=False,
    help="Do not change the record IDs. Useful when importing an existing sample.",
)
@click.option(
    "--reset_records",
    default="NA",
    type=str,
    help="Reset record metadata to the imported version. "
    "Format: --reset_records ID1,ID2,ID3",
)
@click.option(
    "-rid",
    "--reset_ids",
    is_flag=True,
    default=False,
    help="Reset IDs that have been changed (to fix the sort order in records.bib)",
)
@click.option(
    "-d",
    "--debug",
    type=str,
    help="Debug the preparation step for a selected record (can be 'all').",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom prep script.",
)
@click.option(
    "-df",
    "--debug_file",
    type=click.Path(exists=True),
    help="Debug the preparation step for a selected record (in a file).",
)
@click.option("-f", "--force", is_flag=True, default=False)
@click.pass_context
def prep(
    ctx,
    similarity,
    keep_ids,
    reset_records,
    reset_ids,
    debug,
    debug_file,
    setup_custom_script,
    force,
) -> None:
    """Prepare records"""

    import colrev_core.prep
    import colrev_core.review_manager
    from sqlite3 import OperationalError

    try:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager(
            force_mode=force, debug_mode=debug
        )
    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
        return

    PREPARATION = colrev_core.prep.Preparation(
        REVIEW_MANAGER=REVIEW_MANAGER, similarity=similarity
    )
    if reset_records != "NA":
        try:
            reset_records = str(reset_records)
        except ValueError:
            pass
        reset_records = reset_records.split(",")
        PREPARATION.reset_records(reset_ids=reset_records)
    elif reset_ids:
        PREPARATION.reset_ids()
    elif debug or debug_file:
        PREPARATION.main(keep_ids=keep_ids, debug_ids=debug, debug_file=debug_file)
    elif setup_custom_script:
        PREPARATION.setup_custom_script()
        print("Activated custom_prep_script.py.")
        print("Please check and adapt its position in the settings.json and commit.")
    else:
        try:
            PREPARATION.main(keep_ids=keep_ids)
            print()
            print("Please check the changes (especially those with low_confidence)")
            print("To reset record(s) based on their ID, run")
            print("   colrev prep --reset_records ID1,ID2,...")
            print()
        except colrev_exceptions.ServiceNotAvailableException as e:
            print(e)
            print("You can use the force mode to override")
            print("  colrev prep -f")
        except colrev_exceptions.MissingDependencyError as e:
            print(e)
        except OperationalError as e:
            logging.error(
                f"SQLite Error: {e}. "
                "Another colrev process is accessing a shared resource. "
                "Please try again later."
            )


def view_dedupe_details(REVIEW_MANAGER) -> None:
    import colrev_core.dedupe

    DEDUPE = colrev_core.dedupe.Dedupe(
        REVIEW_MANAGER=REVIEW_MANAGER, notify_state_transition_process=False
    )
    info = DEDUPE.get_info()

    if len(info["same_source_merges"]) > 0:
        print(f"\n\n{colors.RED}Same source merges to check:{colors.END}")
        print("\n- " + "\n- ".join(info["same_source_merges"]))


@main.command(help_priority=6)
@click.option(
    "-f",
    "--fix_errors",
    is_flag=True,
    default=False,
    help="Fix errors marked in duplicates_to_validate.xlsx "
    "or non_duplicates_to_validate.xlsx or "
    "a dupes.txt file containing comma-separated ID tuples",
)
@click.option("-v", "--view", is_flag=True, default=False, help="View dedupe info")
@click.option(
    "-m",
    "--merge_threshold",
    type=float,
    help="Confidence threshold for automated merging (dedupe.io confidence)",
)
@click.option(
    "-p",
    "--partition_threshold",
    type=float,
    help="Partition threshold for duplicate clustering (dedupe.io partition)",
)
@click.option(
    "--source_comparison",
    is_flag=True,
    default=False,
    help="Export a spreadsheet for (non-matched) source comparison",
)
@click.pass_context
def dedupe(
    ctx,
    fix_errors,
    view,
    merge_threshold,
    partition_threshold,
    source_comparison,
) -> None:
    """Deduplicate records

    Duplicate identification and merging proceeds as follows:

        1. Training of an active learning (AL) deduplication model
          (based on dedupe.io and safeguards)

        2. Automated deduplication based on AL model

        3. Summaries (duplicates_to_validate.xlsx and non_duplicates_to_validate.xlsx)
          are exported for efficient validation and correction
          (colrev dedupe --fix_errors)

    When the sample size does not allow you to train an AL model (too small),
    deduplication will switch to a simple approach based on a fixed similarity measure

    When the sample size is too big, the blocking and indexing
    is stored in a PostgreSQL database (to avoid excessive RAM use)

    Duplicates can only occur within the set of new records
    (colrev status *md_prepared*) and between the set of new records and
    the set of records that have already been deduplicated
    (colrev_status *md_processed* or beyond).
    Records that are not prepared (colrev_status *md_imported*,
    *md_needs_manual_preparation*) are not considered for deduplication.
    The state model (colrev_status) ensures that users do not have to check
    potential duplicates within the deduplicated set repeatedly.

    Once records are marked as *processed* (or beyond),

    All steps rely on the LocalIndex to implement false positive safeguards against

        - Accidentally merging records that are non-duplicates

        - Accidentally merging records from the same source
    """
    import colrev_core.dedupe
    import colrev_core.review_manager

    try:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
        return

    try:
        if fix_errors:
            DEDUPE = colrev_core.dedupe.Dedupe(REVIEW_MANAGER=REVIEW_MANAGER)
            DEDUPE.fix_errors()
            print(
                "You can manually remove the duplicates_to_validate.xlsx, "
                "non_duplicates_to_validate.xlsx, and dupes.txt files."
            )

        elif view:
            view_dedupe_details(REVIEW_MANAGER)

        elif source_comparison:
            DEDUPE = colrev_core.dedupe.Dedupe(REVIEW_MANAGER=REVIEW_MANAGER)
            DEDUPE.source_comparison()

        else:
            logging.basicConfig()
            logging.getLogger("dedupe.canopy_index").setLevel(logging.WARNING)
            saved_args = locals()
            if "fix_errors" in saved_args:
                del saved_args["fix_errors"]

            DEDUPE = colrev_core.dedupe.Dedupe(REVIEW_MANAGER=REVIEW_MANAGER)
            DEDUPE.main()

    except colrev_exceptions.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")

    except colrev_exceptions.DedupeError as e:
        logging.error(f"DedupeError: {e}")


@main.command(help_priority=7)
@click.option(
    "--stats",
    is_flag=True,
    default=False,
    help="Print statistics of records with colrev_status md_needs_manual_preparation",
)
@click.pass_context
def prep_man(ctx, stats) -> None:
    """Manual preparation of records (not yet fully implemented)"""
    import colrev_core.prep_man
    import colrev_core.review_manager

    try:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
        return

    PREP_MAN = colrev_core.prep_man.PrepMan(REVIEW_MANAGER=REVIEW_MANAGER)

    if stats:
        PREP_MAN.prep_man_stats()
    else:
        PREP_MAN.main()


@main.command(help_priority=9)
@click.option(
    "--include_all",
    is_flag=True,
    default=False,
    help="Include all records in prescreen",
)
@click.option(
    "--export_format",
    type=click.Choice(["CSV", "XLSX"], case_sensitive=False),
    help="Export table with the screening decisions",
)
@click.option(
    "--import_table",
    type=click.Path(exists=True),
    help="Import file with the screening decisions (csv supported)",
)
@click.option(
    "--create_split",
    type=int,
    help="Split the prescreen between n researchers "
    + "(same size, non-overlapping samples)",
)
@click.option(
    "--split",
    type=str,
    default="",
    help="Prescreen a split sample",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom search script.",
)
@click.pass_context
def prescreen(
    ctx,
    include_all,
    export_format,
    import_table,
    create_split,
    split,
    setup_custom_script,
) -> None:
    """Pre-screen based on titles and abstracts"""
    import colrev_core.prescreen
    import colrev_core.review_manager

    try:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
        return

    try:
        PRESCREEN = colrev_core.prescreen.Prescreen(REVIEW_MANAGER=REVIEW_MANAGER)

        if export_format:
            PRESCREEN.export_table(export_table_format=export_format)
        elif import_table:
            PRESCREEN.import_table(import_table_path=import_table)
        elif include_all:
            PRESCREEN.include_all_in_prescreen()
        elif create_split:
            splits = PRESCREEN.create_prescreen_split(create_split=create_split)
            for split in splits:
                print(split + "\n")
        elif setup_custom_script:
            PRESCREEN.setup_custom_script()
            print("Activated custom_prescreen_script.py.")
        else:
            PRESCREEN.main(split_str=split)

    except colrev_exceptions.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")
    except colrev_exceptions.CleanRepoRequiredError as e:
        logging.error(f"CleanRepoRequiredError: {e}")


@main.command(help_priority=10)
@click.option(
    "--include_all",
    is_flag=True,
    default=False,
    help="Include all records in the screen",
)
@click.option(
    "-ac",
    "--add_criterion",
    type=str,
    help="Add a screening criterion. "
    "Format: -ac 'criterion_name,criterion explanation'",
)
@click.option(
    "-dc",
    "--delete_criterion",
    type=str,
    help="Delete a screening criterion. Format: -dc 'criterion_name'",
)
@click.option(
    "--create_split",
    type=int,
    help="Split the prescreen between n researchers "
    + "(same size, non-overlapping samples)",
)
@click.option(
    "--split",
    type=str,
    default="",
    help="Prescreen a split sample",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom search script.",
)
@click.pass_context
def screen(
    ctx,
    include_all,
    add_criterion,
    delete_criterion,
    create_split,
    split,
    setup_custom_script,
) -> None:
    """Screen based on exclusion criteria and fulltext documents"""
    import colrev_core.screen
    import colrev_core.review_manager

    try:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
        return

    try:
        SCREEN = colrev_core.screen.Screen(REVIEW_MANAGER=REVIEW_MANAGER)
        if include_all:
            SCREEN.include_all_in_screen()
        elif add_criterion:
            SCREEN.add_criterion(criterion_to_add=add_criterion)
        elif delete_criterion:
            SCREEN.delete_criterion(criterion_to_delete=delete_criterion)
        elif create_split:
            splits = SCREEN.create_screen_split(create_split=create_split)
            for split in splits:
                print(split + "\n")
        elif setup_custom_script:
            SCREEN.setup_custom_script()
            print("Activated custom_screen_script.py.")
        else:
            SCREEN.main(split_str=split)
    except colrev_exceptions.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")


@main.command(help_priority=11)
@click.option(
    "-c",
    "--copy-to-repo",
    is_flag=True,
    default=False,
    help="Copy PDF files to the repository (the /pdfs directory)",
)
@click.option(
    "-r",
    "--rename",
    is_flag=True,
    default=False,
    help="Rename the PDF files according to record IDs",
)
@click.option(
    "--relink_files",
    is_flag=True,
    default=False,
    help="Recreate links to PDFs based on colrev pdf-IDs (when PDFs were renamed)",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom search script.",
)
@click.pass_context
def pdf_get(ctx, copy_to_repo, rename, relink_files, setup_custom_script) -> None:
    """Retrieve PDFs to the default pdf directory (/pdfs)"""
    import colrev_core.pdf_get
    import colrev_core.review_manager

    try:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
        return

    try:
        if relink_files:
            PDF_RETRIEVAL = colrev_core.pdf_get.PDF_Retrieval(
                REVIEW_MANAGER=REVIEW_MANAGER, notify_state_transition_process=False
            )
            PDF_RETRIEVAL.relink_files()
        elif copy_to_repo:
            PDF_RETRIEVAL = colrev_core.pdf_get.PDF_Retrieval(
                REVIEW_MANAGER=REVIEW_MANAGER
            )
            PDF_RETRIEVAL.copy_pdfs_to_repo()
        elif rename:
            PDF_RETRIEVAL = colrev_core.pdf_get.PDF_Retrieval(
                REVIEW_MANAGER=REVIEW_MANAGER
            )
            PDF_RETRIEVAL.rename_pdfs()
        elif setup_custom_script:
            PDF_RETRIEVAL = colrev_core.pdf_get.PDF_Retrieval(
                REVIEW_MANAGER=REVIEW_MANAGER, notify_state_transition_process=False
            )
            PDF_RETRIEVAL.setup_custom_script()
            print("Activated custom_pdf_get_script.py.")
        else:
            PDF_RETRIEVAL = colrev_core.pdf_get.PDF_Retrieval(
                REVIEW_MANAGER=REVIEW_MANAGER
            )
            PDF_RETRIEVAL.main()

    except colrev_exceptions.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")


@main.command(help_priority=12)
@click.option(
    "--update_colrev_pdf_ids", is_flag=True, default=False, help="Update colrev_pdf_ids"
)
@click.option(
    "--reprocess",
    is_flag=True,
    default=False,
    help="Prepare all PDFs again (pdf_needs_manual_preparation).",
)
@click.option(
    "--debug",
    "-d",
    is_flag=True,
    default=False,
    help="Debug",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom search script.",
)
@click.pass_context
def pdf_prep(ctx, update_colrev_pdf_ids, reprocess, debug, setup_custom_script) -> None:
    """Prepare PDFs

    This involves:

        - Checking for machine readability and applying OCR if necessary

        - Removing coverpages and appended pages

        - Validating the PDF against the record metadata

        - Checking for completeness (number of pages according to record metadata)
    """
    import colrev_core.pdf_prep
    import colrev_core.review_manager

    try:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
        return

    try:
        PDF_PREPARATION = colrev_core.pdf_prep.PDF_Preparation(
            REVIEW_MANAGER=REVIEW_MANAGER, reprocess=reprocess, debug=debug
        )

        if update_colrev_pdf_ids:
            PDF_PREPARATION.update_colrev_pdf_ids()
        elif setup_custom_script:
            PDF_PREPARATION.setup_custom_script()
            print("Activated custom_pdf_prep_script.py.")
        else:
            PDF_PREPARATION.main()

    except colrev_exceptions.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")


@main.command(help_priority=13)
@click.pass_context
@click.option(
    "-e",
    "--export",
    is_flag=True,
    default=False,
    help="Export spreadsheet.",
)
def pdf_get_man(ctx, export) -> None:
    """Get PDFs manually"""
    import colrev_core.pdf_get_man
    import colrev_core.review_manager
    import colrev_core.record
    import pandas as pd

    try:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
        return

    try:
        PDF_RETRIEVAL_MAN = colrev_core.pdf_get_man.PDFRetrievalMan(
            REVIEW_MANAGER=REVIEW_MANAGER
        )
        if export:

            records = (
                PDF_RETRIEVAL_MAN.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
            )
            pdf_get_man_records = [
                r
                for r in records.values()
                if r["colrev_status"]
                in [
                    colrev_core.record.RecordState.pdf_needs_manual_retrieval,
                    colrev_core.record.RecordState.rev_prescreen_included,
                ]
            ]
            pdf_get_man_records_df = pd.DataFrame.from_records(pdf_get_man_records)
            pdf_get_man_records_df = pdf_get_man_records_df[
                pdf_get_man_records_df.columns.intersection(
                    {
                        "ID",
                        "author",
                        "year",
                        "title",
                        "journal",
                        "booktitle",
                        "volume",
                        "number",
                        "url",
                        "doi",
                    }
                )
            ]
            pdf_get_man_records_df.to_csv("pdf_get_man_records.csv", index=False)
            PDF_RETRIEVAL_MAN.REVIEW_MANAGER.logger.info(
                "Created pdf_get_man_records.csv"
            )

        else:
            PDF_RETRIEVAL_MAN.main()
    except colrev_exceptions.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")


def delete_first_pages_cli(PDF_PREP_MAN, ID) -> None:

    records = PDF_PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
    while True:
        if ID in records:
            record = records[ID]
            if "file" in record:
                print(record["file"])
                pdf_path = PDF_PREP_MAN.REVIEW_MANAGER.path / Path(record["file"])
                PDF_PREP_MAN.extract_coverpage(pdf_path)
            else:
                print("no file in record")
        if "n" == input("Extract coverpage from another PDF? (y/n)"):
            break
        ID = input("ID of next PDF for coverpage extraction:")


@main.command(help_priority=14)
@click.option(
    "-dfp",
    "--delete_first_page",
    type=str,
    help="Delete first page of PDF. Format: --delete_first_page ID",
)
@click.option(
    "--stats",
    is_flag=True,
    default=False,
    help="Print statistics of records with colrev_status pdf_needs_manual_preparation",
)
@click.option(
    "--extract",
    is_flag=True,
    default=False,
    help="Extract records for manual_preparation (to csv and bib)",
)
@click.option(
    "--apply",
    is_flag=True,
    default=False,
    help="Apply manual preparation (from csv or bib)",
)
@click.pass_context
def pdf_prep_man(ctx, delete_first_page, stats, extract, apply) -> None:
    """Prepare PDFs manually"""
    import colrev_core.pdf_prep_man
    import colrev_core.review_manager

    try:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
        return

    try:
        if delete_first_page:
            PDF_PREP_MAN = colrev_core.pdf_prep_man.PDFPrepMan(
                REVIEW_MANAGER=REVIEW_MANAGER
            )
            delete_first_pages_cli(PDF_PREP_MAN, delete_first_page)
            return

        PDF_PREP_MAN = colrev_core.pdf_prep_man.PDFPrepMan(
            REVIEW_MANAGER=REVIEW_MANAGER
        )
        if stats:
            PDF_PREP_MAN.pdf_prep_man_stats()
        elif extract:
            PDF_PREP_MAN.extract_needs_pdf_prep_man()
        elif apply:
            PDF_PREP_MAN.apply_pdf_prep_man()
        else:
            PDF_PREP_MAN.main()
    except colrev_exceptions.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")


@main.command(help_priority=15)
@click.option(
    "--profile",
    is_flag=True,
    default=False,
    help="Create a sample profile (papers per journal and year)",
)
@click.option(
    "--reading_heuristics",
    is_flag=True,
    default=False,
    help="Heuristics to prioritize reading efforts",
)
@click.option(
    "-a",
    "--add_endpoint",
    type=str,
    help="Add a data_format endpoint (e.g., MANUSCRIPT,STRUCTURED)",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom search script.",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Option to override process preconditions",
)
@click.pass_context
def data(
    ctx, profile, reading_heuristics, add_endpoint, setup_custom_script, force
) -> None:
    """Extract data"""
    import colrev_core.data
    import colrev_core.review_manager
    import requests

    try:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager(force_mode=force)
    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
        return

    try:
        DATA = colrev_core.data.Data(REVIEW_MANAGER=REVIEW_MANAGER)
        if profile:
            DATA.profile()
        elif reading_heuristics:
            heuristic_results = DATA.reading_heuristics()
            pp.pprint(heuristic_results)
            return
        elif setup_custom_script:
            DATA.setup_custom_script()
            print("Activated custom_data_script.py.")
            print("Please update the data_format in settings.json and commit.")
        elif add_endpoint:

            if add_endpoint in DATA.data_scripts:
                endpoint = DATA.data_scripts[add_endpoint]["endpoint"]
                ENDPOINT = endpoint()

                default_endpoint_conf = ENDPOINT.get_default_setup()

                if "MANUSCRIPT" == add_endpoint:
                    if "y" == input("Select a custom word template (y/n)?"):

                        template_name = input(
                            'Please copy the word template to " \
                        "the project directory and enter the filename.'
                        )
                        default_endpoint_conf["word_template"] = template_name
                    else:
                        print("Adding APA as a default")

                    if "y" == input("Select a custom citation stlye (y/n)?"):
                        print(
                            "Citation stlyes are available at: \n"
                            "https://github.com/citation-style-language/styles"
                        )
                        csl_link = input(
                            "Please select a citation style and provide the link."
                        )
                        r = requests.get(csl_link, allow_redirects=True)
                        open(Path(csl_link).name, "wb").write(r.content)
                        default_endpoint_conf["csl_style"] = Path(csl_link).name
                    else:
                        print("Adding APA as a default")

                    DATA.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
                        path=default_endpoint_conf["csl_style"]
                    )
                    DATA.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
                        path=default_endpoint_conf["word_template"]
                    )
                    # TODO : check whether template_name is_file
                    # and csl_link.name is_file()

                DATA.add_data_endpoint(default_endpoint_conf)
                DATA.REVIEW_MANAGER.create_commit(
                    msg="Add data endpoint",
                    script_call="colrev data",
                )

                # Note : reload updated settings
                REVIEW_MANAGER = colrev_core.review_manager.ReviewManager(
                    force_mode=force
                )
                DATA = colrev_core.data.Data(REVIEW_MANAGER=REVIEW_MANAGER)

            else:
                print("Data format not available")

            ret = DATA.main()
            if ret["ask_to_commit"]:
                if "y" == input("Create commit (y/n)?"):
                    REVIEW_MANAGER.create_commit(
                        msg="Data and synthesis", manual_author=True
                    )
        else:
            ret = DATA.main()
            if ret["ask_to_commit"]:
                if "y" == input("Create commit (y/n)?"):
                    REVIEW_MANAGER.create_commit(
                        msg="Data and synthesis", manual_author=True
                    )
            if ret["no_endpoints_registered"]:
                print(
                    "No data format not specified. "
                    "To register a data endpoint, "
                    "use one (or several) of the following \n"
                    "    colrev data --add_endpoint MANUSCRIPT\n"
                    "    colrev data --add_endpoint STRUCTURED\n"
                    "    colrev data --add_endpoint PRISMA\n"
                    "    colrev data --add_endpoint ZETTLR\n"
                    "    colrev data --add_endpoint ENDNOTE"
                )

    except colrev_exceptions.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")


def validate_commit(ctx, param, value):
    if value is None:
        return value

    import git

    repo = git.Repo()
    revlist = list(repo.iter_commits())

    if value in [x.hexsha for x in revlist]:
        return value

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


@main.command(help_priority=16)
@click.option(
    "--scope",
    type=click.Choice(["prepare", "merge", "all", "unspecified"], case_sensitive=False),
    default="unspecified",
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
    import colrev_core.validate
    import colrev_core.review_manager

    try:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
        return

    VALIDATE = colrev_core.validate.Validate(REVIEW_MANAGER=REVIEW_MANAGER)
    validation_details = VALIDATE.main(
        scope=scope, properties=properties, target_commit=commit
    )

    if 0 == len(validation_details):
        print("No substantial changes.")
        return

    keys = [
        "author",
        "title",
        "journal",
        "booktitle",
        "year",
        "volume",
        "number",
        "pages",
    ]

    for record_a, record_b, difference in validation_details:
        # Escape sequence to clear terminal output for each new comparison
        os.system("cls" if os.name == "nt" else "clear")
        if record_a["ID"] == record_b["ID"]:
            print(f"similarity: {str(round(difference, 4))} record {record_a['ID']}")
        else:
            print(
                f"similarity: {str(round(difference, 4))} "
                f"record {record_a['ID']} - {record_b['ID']}"
            )

        colrev_core.record.Record.print_diff_pair(
            record_pair=[record_a, record_b], keys=keys
        )

        user_selection = input("Validate [y,n,d,q]?")

        if "q" == user_selection:
            break
        if "y" == user_selection:
            continue

        # TODO: correct? if not, replace current record with old one


@main.command(help_priority=17)
@click.pass_context
@click.option("--id", help="Record ID to trace (citation_key).", required=True)
def trace(ctx, id) -> None:
    """Trace a record"""
    import colrev_core.trace
    import colrev_core.review_manager

    try:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
        return

    TRACE = colrev_core.trace.Trace(REVIEW_MANAGER=REVIEW_MANAGER)
    TRACE.main(ID=id)


@main.command(help_priority=18)
@click.pass_context
def paper(ctx) -> None:
    """Build the paper"""
    import colrev_core.paper
    import colrev_core.review_manager

    try:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
        return

    try:

        PAPER = colrev_core.paper.Paper(REVIEW_MANAGER=REVIEW_MANAGER)
        PAPER.main()
    except colrev_exceptions.NoPaperEndpointRegistered as e:
        print(f"NoPaperEndpointRegistered: {e}")
        print(
            "To register a paper endpoint, use \n"
            "    colrev data --add_endpoint MANUSCRIPT"
        )


@main.command(help_priority=19)
@click.option(
    "-p",
    "--path",
    type=click.Path(exists=True),
    help="Path to file(s)",
)
@click.pass_context
def distribute(ctx, path) -> None:
    """Distribute records to other local CoLRev repositories"""
    import pandas as pd
    from yaml import safe_load
    import colrev_core.review_manager
    import colrev_core.distribute

    # Note : distribute is designed with the assumption that it is called from
    # within a colrev project.
    # In other cases, colrev_core.review_manager.ReviewManager() will fail.
    # Other use cases may be related to sync/export (from LocalIndex)

    try:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
        return

    DISTRIBUTE = colrev_core.distribute.Distribute(REVIEW_MANAGER=REVIEW_MANAGER)

    local_registry_path = Path.home().joinpath(".colrev/registry.yaml")
    if not os.path.exists(local_registry_path):
        print("no local repositories registered")
        return

    with open(local_registry_path, encoding="utf-8") as f:
        local_registry_df = pd.json_normalize(safe_load(f))
        local_registry = local_registry_df.to_dict("records")
        local_registry = [
            x for x in local_registry if "curated_metadata/" not in x["source_url"]
        ]

    valid_selection = False
    while not valid_selection:
        for i, lreg in enumerate(local_registry):
            print(f"{i+1} - {lreg['source_name']} ({lreg['source_url']})")
        sel_str = input("Select target repository: ")
        sel = int(sel_str) - 1
        if sel in range(0, len(local_registry)):
            target = Path(local_registry[sel]["source_url"])
            valid_selection = True

    DISTRIBUTE.main(path_str=path, target=target)


def print_environment_status() -> None:
    import colrev_core.environment

    ENVIRONMENT_MANAGER = colrev_core.environment.EnvironmentManager()

    environment_details = ENVIRONMENT_MANAGER.get_environment_details()

    print("\nCoLRev environment status\n")
    print("Index\n")
    if "up" == environment_details["index"]["status"]:
        print(f" - Status: {colors.GREEN}up{colors.END}")
        print(f' - Path          : {environment_details["index"]["path"]}')
        print(f' - Size          : {environment_details["index"]["size"]} records')
        print(f' - Last modified : {environment_details["index"]["last_modified"]}')
    else:
        print(f" - Status: {colors.RED}down{colors.END}")

    print("\nCoLRev projects\n")
    project_repos = [
        x
        for x in environment_details["local_repos"]["repos"]
        if "curated_metadata" not in x["source_url"]
    ]
    for colrev_repo in sorted(project_repos, key=lambda d: d["source_name"]):

        repo_stats = f' {colrev_repo["source_name"]}'
        if colrev_repo["remote"]:
            if colrev_repo["behind_remote"]:
                repo_stats += " (shared, behind remote)"
            else:
                repo_stats += " (shared)"
        print(repo_stats)

        if -1 != colrev_repo["progress"]:
            print(f'    - Progress : {colrev_repo["progress"]*100} %')
        else:
            print("    - Progress : ??")
        print(f'    - Size     : {colrev_repo["size"]} records')
        print(f'    - Path     : {colrev_repo["source_url"]}')

    print("\nCurated CoLRev resources\n")
    curated_repos = [
        x
        for x in environment_details["local_repos"]["repos"]
        if "curated_metadata" in x["source_url"]
    ]
    for colrev_repo in sorted(curated_repos, key=lambda d: d["source_name"]):
        repo_stats = (
            f' - {colrev_repo["source_name"].ljust(60, " ")}: '
            f'{str(colrev_repo["size"]).rjust(10, " ")} records'
        )
        if colrev_repo["behind_remote"]:
            repo_stats += " (behind remote)"
        print(repo_stats)

    print("\n")
    if len(environment_details["local_repos"]["broken_links"]) > 0:
        print("Broken links: \n")
        for b in environment_details["local_repos"]["broken_links"]:
            print(f'- {b["source_url"]}')


@main.command(help_priority=20)
@click.option(
    "-i", "--index", is_flag=True, default=False, help="Create the LocalIndex"
)
@click.option(
    "--install",
    help="Install a new resource providing its url "
    + "(e.g., a curated metadata repository)",
)
@click.option(
    "-a",
    "--analyze",
    is_flag=True,
    default=False,
    help="Analyze the LocalIndex for potential problems",
)
@click.option("--pull", is_flag=True, default=False, help="Pull curated metadata")
@click.option(
    "-s", "--status", is_flag=True, default=False, help="Print environment status"
)
@click.option("--start", is_flag=True, default=False, help="Start environment services")
@click.option("--stop", is_flag=True, default=False, help="Stop environment services")
@click.option(
    "--search",
    is_flag=True,
    default=False,
    help="Start opensearch dashboard service to search the LocalIndex",
)
@click.option(
    "-r",
    "--register",
    is_flag=True,
    default=False,
    help="Register a repository in the CoLRev environment",
)
@click.option(
    "-ur",
    "--unregister",
    type=click.Path(exists=True),
    help="Path of repository to remove from local registry.",
)
@click.pass_context
def env(
    ctx,
    index,
    install,
    analyze,
    pull,
    status,
    start,
    stop,
    search,
    register,
    unregister,
):
    """CoLRev environment commands"""
    import colrev_core.environment
    import colrev_core.review_manager
    import webbrowser
    import docker

    if install:
        RESOURCES = colrev_core.environment.Resources()
        if RESOURCES.install_curated_resource(curated_resource=install):
            print("Successfully installed curated resource.")
            print("To make it available to other projects, run")
            print("colrev env --index")

    elif pull:
        for (
            curated_resource
        ) in colrev_core.environment.EnvironmentManager.load_local_registry():
            curated_resource_path = curated_resource["source_url"]
            if "/curated_metadata/" not in curated_resource_path:
                continue
            REVIEW_MANAGER = colrev_core.review_manager.ReviewManager(
                path_str=curated_resource_path
            )
            REVIEW_MANAGER.REVIEW_DATASET.pull_if_repo_clean()
            print(f"Pulled {curated_resource_path}")

    elif status:
        print_environment_status()

    elif start:
        LOCAL_INDEX = colrev_core.environment.LocalIndex()
        print("Started.")

    elif stop:
        client = docker.from_env()
        images_to_stop = [
            k
            for k, v in colrev_core.environment.EnvironmentManager.docker_images.items()
        ]
        for container in client.containers.list():
            if any(x in str(container.image) for x in images_to_stop):
                container.stop()
                print(f"Stopped container {container.name} ({container.image})")

    elif search:
        LOCAL_INDEX = colrev_core.environment.LocalIndex()
        LOCAL_INDEX.start_opensearch_docker_dashboards()
        print("Started.")
        webbrowser.open("http://localhost:5601/app/home#/", new=2)

    elif index:
        LOCAL_INDEX = colrev_core.environment.LocalIndex()
        LOCAL_INDEX.index()

    elif analyze:
        LOCAL_INDEX = colrev_core.environment.LocalIndex()
        LOCAL_INDEX.analyze()

    elif register:
        colrev_core.environment.EnvironmentManager.register_repo(
            path_to_register=Path.cwd()
        )

    elif unregister is not None:
        local_registry = (
            colrev_core.environment.EnvironmentManager.load_local_registry()
        )
        if str(unregister) not in [x["source_url"] for x in local_registry]:
            logging.error(f"Not in local registry (cannot remove): {unregister}")
        else:
            local_registry = [
                x for x in local_registry if x["source_url"] != str(unregister)
            ]
            colrev_core.environment.EnvironmentManager.save_local_registry(
                updated_registry=local_registry
            )
            logging.info(f"Removed from local registry: {unregister}")


@main.command(help_priority=21)
# @click.option("-v", "--view", is_flag=True, default=False)
@click.option(
    "-u",
    "--upgrade",
    is_flag=True,
    default=False,
    help="Update to the latest CoLRev project version",
)
@click.option(
    "-uh",
    "--update_hooks",
    is_flag=True,
    default=False,
    help="Update the pre-commit hooks",
)
@click.option(
    "-m",
    "--modify",
    type=str,
    default="",
    help="Modify the settings through the command line",
)
@click.pass_context
def settings(ctx, upgrade, update_hooks, modify):
    """Settings of the CoLRev project"""
    import colrev_core.review_manager

    # from colrev_core.settings_editor import Settings

    # REVIEW_MANAGER = colrev_core.review_manager.ReviewManager(force_mode=True)
    # SETTINGS = Settings(REVIEW_MANAGER=REVIEW_MANAGER)
    # SETTINGS.open_settings_editor()
    # input("stop")

    if upgrade:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager(force_mode=True)
        REVIEW_MANAGER.upgrade_colrev()

    elif update_hooks:
        from subprocess import check_call
        from subprocess import DEVNULL
        from subprocess import STDOUT

        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
        print("Update pre-commit hooks")

        if REVIEW_MANAGER.REVIEW_DATASET.has_changes():
            print("Clean repo required. Commit or stash changes.")
            return

        scripts_to_call = [
            [
                "pre-commit",
                "autoupdate",
                "--repo",
                "https://github.com/geritwagner/colrev-hooks",
            ],
        ]
        for script_to_call in scripts_to_call:
            check_call(script_to_call, stdout=DEVNULL, stderr=STDOUT)

        REVIEW_MANAGER.REVIEW_DATASET.add_changes(path=".pre-commit-config.yaml")
        REVIEW_MANAGER.create_commit(
            msg="Update pre-commit hooks", script_call="colrev settings --update"
        )
        print("Successfully updated pre-commit hooks")

    elif modify:

        import json
        import ast
        from glom import glom

        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
        # TBD: maybe use glom.delete?
        # There is no simply append...
        # (we could replace the (last) position element with
        # keywords like prescreen.sripts.LAST_POSITION)
        # maybe prescreen.scripts.1.REPLACE/ADD/DELETE = ....
        # modify = 'dedupe.scripts=[{"endpoint":"simple_dedupe"}]'

        path, value_string = modify.split("=")
        value = ast.literal_eval(value_string)
        REVIEW_MANAGER.logger.info(f"Change settings.{path} to {value}")

        with open("settings.json", encoding="utf-8") as f:
            project_settings = json.load(f)

        glom.assign(project_settings, path, value)

        with open("settings.json", "w", encoding="utf-8") as outfile:
            json.dump(project_settings, outfile, indent=4)

        REVIEW_MANAGER.REVIEW_DATASET.add_changes(path="settings.json")
        REVIEW_MANAGER.create_commit(
            msg="Change settings", manual_author=True, saved_args=None
        )

    else:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
        print(f"Settings:\n{REVIEW_MANAGER.settings}")
        print("\n")


@main.command(help_priority=22)
# @click.option("-r", "--register", is_flag=True, default=False)
@click.pass_context
def sync(
    ctx,
    # register,
):
    """Sync records from CoLRev environment to non-CoLRev repo"""
    import colrev_core.sync

    SYNC = colrev_core.sync.Sync()
    SYNC.get_cited_papers()

    if len(SYNC.non_unique_for_import) > 0:
        print("Non-unique keys to resolve:")
        # Resolve non-unique cases
        for case in SYNC.non_unique_for_import:
            for v in case.values():
                # TODO: there may be more collisions (v3, v4)
                v1 = SYNC.format_ref(reference=v[0])
                v2 = SYNC.format_ref(reference=v[1])
                if v1.lower() == v2.lower():
                    SYNC.add_to_records_to_import(record=v[0])
                    continue
                print("\n")
                print(f"1: {v1}")
                print("      " + v[0].get("source_url", ""))
                print("")
                print(f"2: {v2}")
                print("      " + v[1].get("source_url", ""))
                user_selection = input("Import version 1 or 2 (or skip)?")
                if "1" == user_selection:
                    SYNC.add_to_records_to_import(record=v[0])
                    continue
                if "2" == user_selection:
                    SYNC.add_to_records_to_import(record=v[1])
                    continue

    SYNC.add_to_bib()


@main.command(help_priority=23)
@click.option(
    "-r",
    "--records_only",
    is_flag=True,
    default=False,
    help="Update records only",
)
@click.option(
    "-p",
    "--project_only",
    is_flag=True,
    default=False,
    help="Push project only",
)
@click.pass_context
def pull(ctx, records_only, project_only):
    """Pull CoLRev project remote and record updates"""
    import colrev_core.pull
    import colrev_core.review_manager

    try:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
        return

    PULL = colrev_core.pull.Pull(REVIEW_MANAGER=REVIEW_MANAGER)
    PULL.main(records_only=records_only, project_only=project_only)


@main.command(help_priority=24)
@click.argument("git_url")
@click.pass_context
def clone(ctx, git_url):
    """Create local clone from shared CoLRev repository with git_url"""
    import colrev_core.clone

    CLONE = colrev_core.clone.Clone(git_url=git_url)
    CLONE.clone_git_repo()


@main.command(help_priority=26)
@click.option(
    "-r",
    "--records_only",
    is_flag=True,
    default=False,
    help="Update records only",
)
@click.option(
    "-p",
    "--project_only",
    is_flag=True,
    default=False,
    help="Push project only",
)
@click.pass_context
def push(ctx, records_only, project_only):
    """Push CoLRev project remote and record updates"""
    import colrev_core.review_manager
    import colrev_core.push

    try:
        REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
    except MissingValueError as e:
        print(f"Error in settings.json: {e}")
        print("To solve this, use\n  colrev settings --upgrade")
        return

    PUSH = colrev_core.push.Push(REVIEW_MANAGER=REVIEW_MANAGER)
    PUSH.main(records_only=records_only, project_only=project_only)


@main.command(help_priority=25)
@click.pass_context
def service(ctx):
    """Service for real-time reviews"""
    import colrev_core.review_manager
    import colrev_core.service

    REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
    try:

        colrev_core.service.Service(REVIEW_MANAGER=REVIEW_MANAGER)

    except KeyboardInterrupt:
        print("\nPressed ctrl-c. Shutting down service")

    if REVIEW_MANAGER.REVIEW_DATASET.has_changes():
        if "y" == input("Commit current changes (y/n)?"):
            REVIEW_MANAGER.create_commit(
                msg="Update (work on realtime review)", realtime_override=True
            )
    else:
        print("No changes to commit")


def validate_show(ctx, param, value):
    if value not in ["sample", "settings", "prisma", "venv"]:
        raise click.BadParameter("Invalid argument")


@main.command(help_priority=26)
@click.argument("keyword")
@click.pass_context
def show(ctx, keyword, callback=validate_show, required=True):
    """Show aspects (sample, ...)"""
    import colrev_core.review_manager
    import colrev_core.process
    import colrev_core.record

    REVIEW_MANAGER = colrev_core.review_manager.ReviewManager()
    if "sample" == keyword:

        colrev_core.process.CheckProcess(REVIEW_MANAGER=REVIEW_MANAGER)
        records = REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        sample = [
            r
            for r in records.values()
            if r["colrev_status"]
            in [
                colrev_core.record.RecordState.rev_synthesized,
                colrev_core.record.RecordState.rev_included,
            ]
        ]
        if 0 == len(sample):
            print("No records included in sample (yet)")

        for sample_r in sample:
            colrev_core.record.Record(data=sample_r).print_citation_format()
        # TODO : print sample size, distributions over years/journals

    elif "settings" == keyword:
        print(f"Settings:\n{REVIEW_MANAGER.settings}")

    elif "prisma" == keyword:

        stat = REVIEW_MANAGER.get_status_freq()
        print(stat)

        print(
            "Records identified through database searching: "
            f"{stat['colrev_status']['overall']['md_retrieved']}"
        )

    elif "venv" == keyword:
        # TODO : test installation of colrev in venv
        import platform

        current_platform = platform.system()
        if "Linux" == current_platform:
            print("Detected platform: Linux")
            if not Path("venv").is_dir():
                print("To create virtualenv, run")
                print(f"  {colors.ORANGE}python3 -m venv venv{colors.END}")
            print("To activate virtualenv, run")
            print(f"  {colors.ORANGE}source venv/bin/activate{colors.END}")
            print("To install colrev/colrev_core, run")
            print(
                f"  {colors.ORANGE}python -m pip install colrev colrev_core{colors.END}"
            )
            print("To deactivate virtualenv, run")
            print(f"  {colors.ORANGE}deactivate{colors.END}")
        elif "Darwin" == current_platform:
            print("Detected platform: MacOS")
            if not Path("venv").is_dir():
                print("To create virtualenv, run")
                print(f"  {colors.ORANGE}python3 -m venv venv{colors.END}")
            print("To activate virtualenv, run")
            print(f"  {colors.ORANGE}source venv/bin/activate{colors.END}")
            print("To install colrev/colrev_core, run")
            print(
                f"  {colors.ORANGE}python -m pip install colrev colrev_core{colors.END}"
            )
            print("To deactivate virtualenv, run")
            print(f"  {colors.ORANGE}deactivate{colors.END}")
        elif "Windows" == current_platform:
            print("Detected platform: Windows")
            if not Path("venv").is_dir():
                print("To create virtualenv, run")
                print(f"  {colors.ORANGE}python -m venv venv{colors.END}")
            print("To activate virtualenv, run")
            print(f"  {colors.ORANGE}venv\\Scripts\\Activate.ps1{colors.END}")
            print("To install colrev/colrev_core, run")
            print(
                f"  {colors.ORANGE}python -m pip install colrev colrev_core{colors.END}"
            )
            print("To deactivate virtualenv, run")
            print(f"  {colors.ORANGE}deactivate{colors.END}")
        else:
            print(
                "Platform not detected... "
                "cannot provide infos in how to activate virtualenv"
            )
    else:
        print("Keyword unknown")


@main.command(hidden=True)
@click.option(
    "-i", "--case-insensitive/--no-case-insensitive", help="Case insensitive completion"
)
@click.argument(
    "shell",
    required=False,
    type=click_completion.DocumentedChoice(click_completion.core.shells),
)
def show_click(shell, case_insensitive):
    """Show the click-completion-command completion code"""
    extra_env = (
        {"_CLICK_COMPLETION_COMMAND_CASE_INSENSITIVE_COMPLETE": "ON"}
        if case_insensitive
        else {}
    )
    click.echo(click_completion.core.get_code(shell, extra_env=extra_env))


@main.command(hidden=True)
@click.option(
    "--append/--overwrite", help="Append the completion code to the file", default=None
)
@click.option(
    "-i", "--case-insensitive/--no-case-insensitive", help="Case insensitive completion"
)
@click.argument(
    "shell",
    required=False,
    type=click_completion.DocumentedChoice(click_completion.core.shells),
)
@click.argument("path", required=False)
def install_click(append, case_insensitive, shell, path):
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
