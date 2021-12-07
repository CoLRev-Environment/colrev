import datetime
import difflib
import logging
import os
import pprint
from collections import OrderedDict

import ansiwrap
import click
import click_completion.core
import git
from bibtexparser.bibdatabase import BibDatabase
from dictdiffer import diff

from review_template.review_manager import RecordState

pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)

logger = logging.getLogger("review_template")

key_order = [
    "ENTRYTYPE",
    "ID",
    "year",
    "author",
    "title",
    "journal",
    "booktitle",
    "volume",
    "number",
    "doi",
    "link",
    "url",
    "fulltext",
    "status",
]


def customsort(dict1: dict) -> OrderedDict:
    items = [dict1[k] if k in dict1.keys() else "" for k in key_order]
    sorted_dict = OrderedDict()
    for i in range(len(key_order)):
        sorted_dict[key_order[i]] = items[i]
    return sorted_dict


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

    init.require_empty_directory()

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

    total_atomic_steps = stat["atomic_steps"]
    completed_steps = stat["completed_atomic_steps"]

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
    from review_template import status, review_manager
    from review_template.review_manager import ReviewManager

    REVIEW_MANAGER = ReviewManager()

    print("\nChecks\n")

    ret_check = REVIEW_MANAGER.check_repo()
    if 0 == ret_check["status"]:
        print(
            "  ReviewManager.check_repo() ...... "
            f'{colors.GREEN}{ret_check["msg"]}{colors.END}'
        )
    if 1 == ret_check["status"]:
        print(f"  ReviewManager.check_repo() ...... {colors.RED}FAIL{colors.END}")
        print(f'\n    {ret_check["msg"]}\n')

    ret_f = REVIEW_MANAGER.format_references()
    if 0 == ret_f["status"]:
        print(
            "  ReviewManager.format()     ...... "
            f'{colors.GREEN}{ret_f["msg"]}{colors.END}'
        )
    if 1 == ret_f["status"]:
        print(f"  ReviewManager.format()     ...... {colors.RED}FAIL{colors.END}")
        print(f'\n    {ret_f["msg"]}\n')
    if not review_manager.in_virtualenv():
        print(
            f"  {colors.RED}WARNING{colors.END} running scripts outside of virtualenv"
        )

    REVIEW_MANAGER.update_status_yaml()

    if ret_check["status"] + ret_f["status"] == 0:
        stat = status.get_status_freq(REVIEW_MANAGER)
        status.print_review_status(REVIEW_MANAGER, stat)
        print_progress(stat)

        instructions = status.get_instructions(REVIEW_MANAGER, stat)
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
    #     "template/.pre-commit-config.yaml",
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
    from review_template.review_manager import ReviewManager
    from review_template import dedupe
    from review_template import load
    from review_template import pdf_prepare
    from review_template import pdf_get
    from review_template import prepare

    try:
        REVIEW_MANAGER = ReviewManager()

        if reprocess_id is not None:
            REVIEW_MANAGER.reprocess_id(reprocess_id)

        load.main(REVIEW_MANAGER, keep_ids)

        prepare.main(REVIEW_MANAGER, keep_ids)

        dedupe.main(REVIEW_MANAGER)

        pdf_get.main(REVIEW_MANAGER)

        pdf_prepare.main(REVIEW_MANAGER)
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
    from review_template.review_manager import ReviewManager, ProcessType, Process

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
    help="Prepare all records set to status="
    + "md_needs_manual_preparation again. Useful if "
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
    from review_template.review_manager import ReviewManager, ProcessType, Process

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
    from review_template.review_manager import ReviewManager, ProcessType, Process

    try:
        REVIEW_MANAGER = ReviewManager()
        dedupe_process = Process(ProcessType.dedupe, dedupe.main)
        REVIEW_MANAGER.run_process(dedupe_process)

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


record_type_mapping = {
    "a": "article",
    "p": "inproceedings",
    "b": "book",
    "ib": "inbook",
    "pt": "phdthesis",
    "mt": "masterthesis",
    "o": "other",
    "unp": "unpublished",
}


def print_record(record: dict) -> None:
    # Escape sequence to clear terminal output for each new comparison
    os.system("cls" if os.name == "nt" else "clear")
    pp.pprint(record)
    if "title" in record:
        print(
            "https://scholar.google.de/scholar?hl=de&as_sdt=0%2C5&q="
            + record["title"].replace(" ", "+")
        )
    return


def man_correct_recordtype(record: dict) -> dict:

    if "n" == input("ENTRYTYPE=" + record["ENTRYTYPE"] + " correct?"):
        choice = input(
            "Correct type: "
            + "a (article), p (inproceedings), "
            + "b (book), ib (inbook), "
            + "pt (phdthesis), mt (masterthesis), "
            "unp (unpublished), o (other), "
        )
        assert choice in record_type_mapping.keys()
        correct_record_type = [
            value for (key, value) in record_type_mapping.items() if key == choice
        ]
        record["ENTRYTYPE"] = correct_record_type[0]
    return record


def man_provide_required_fields(record: dict) -> dict:
    from review_template import prepare

    if prepare.is_complete(record):
        return record

    reqs = prepare.record_field_requirements[record["ENTRYTYPE"]]
    for field in reqs:
        if field not in record:
            value = input("Please provide the " + field + " (or NA)")
            record[field] = value
    return record


def man_fix_field_inconsistencies(record: dict) -> dict:
    from review_template import prepare

    if not prepare.has_inconsistent_fields(record):
        return record

    print("TODO: ask whether the inconsistent fields can be dropped?")

    return record


def man_fix_incomplete_fields(record: dict) -> dict:
    from review_template import prepare

    if not prepare.has_incomplete_fields(record):
        return record

    print("TODO: ask for completion of fields")
    # organize has_incomplete_fields() values in a dict?

    return record


def prep_man_records_cli(REVIEW_MANAGER):
    from review_template import prep_man

    saved_args = locals()

    md_prep_man_data = prep_man.get_data(REVIEW_MANAGER)
    stat_len = md_prep_man_data["nr_tasks"]
    PAD = md_prep_man_data["PAD"]
    all_ids = md_prep_man_data["all_ids"]
    # TODO: log details for processing_report

    logger.debug(pp.pformat(md_prep_man_data))

    if 0 == stat_len:
        logger.info("No records to prepare manually")

    input("Man-prep not fully implemented (yet).")

    i = 0
    for record in md_prep_man_data["items"]:

        print("\n\n")
        revrecord = customsort(record)
        pp.pprint(revrecord)

        ret = "NA"
        i += 1
        while ret not in ["u", "s", "q"]:
            ret = input(f"({i}/{stat_len}) Update this record [u,q,s]? ")
            if "q" == ret:
                quit_pressed = True
            elif "s" == ret:
                continue
            elif "u":

                # os.system("cls" if os.name == "nt" else "clear")
                # print(f"{i}/{stat_len}")
                # i += 1
                # print_record(record)

                man_correct_recordtype(record)
                man_provide_required_fields(record)
                man_fix_field_inconsistencies(record)
                man_fix_incomplete_fields(record)

                # Note: for complete_based_on_doi field:
                # record = prepare.retrieve_doi_metadata(record)

                # TODO : maybe update the IDs when we have a replace_record procedure
                # set_IDs
                # that can handle changes in IDs
                # record.update(
                #     ID=REVIEW_MANAGER.generate_ID_blacklist(
                #         record, all_ids, record_in_bib_db=True, raise_error=False
                #     )
                # )
                # all_ids.append(record["ID"])

                prep_man.set_data(REVIEW_MANAGER, record, PAD)

    REVIEW_MANAGER.create_commit(
        "Manual preparation of records", manual_author=True, saved_args=saved_args
    )

    return


@main.command(help_priority=7)
@click.option(
    "--stats",
    is_flag=True,
    default=False,
    help="Print statistics of records with status md_needs_manual_preparation",
)
@click.option(
    "--extract",
    is_flag=True,
    default=False,
    help="Extract records with status md_needs_manual_preparation",
)
@click.pass_context
def prep_man(ctx, stats, extract) -> None:
    """Manual preparation of records"""
    from review_template import prep_man
    from review_template.review_manager import ReviewManager

    REVIEW_MANAGER = ReviewManager()

    if stats:
        prep_man.prep_man_stats(REVIEW_MANAGER)
    elif extract:
        prep_man.extract_needs_prep_man(REVIEW_MANAGER)
    else:
        prep_man_records_cli(REVIEW_MANAGER)

    return


def print_diff(change: dict, prefix_len: int) -> None:

    d = difflib.Differ()

    if change[0] == "change":
        if change[1] not in ["ID", "status"]:
            letters = list(d.compare(change[2][0], change[2][1]))
            for i in range(len(letters)):
                if letters[i].startswith("  "):
                    letters[i] = letters[i][-1]
                elif letters[i].startswith("+ "):
                    letters[i] = f"{colors.RED}" + letters[i][-1] + f"{colors.END}"
                elif letters[i].startswith("- "):
                    letters[i] = f"{colors.GREEN}" + letters[i][-1] + f"{colors.END}"
            prefix = change[1] + ": "
            print(
                ansiwrap.fill(
                    "".join(letters),
                    initial_indent=prefix.ljust(prefix_len),
                    subsequent_indent=" " * prefix_len,
                )
            )
    elif change[0] == "add":
        prefix = change[1] + ": "
        print(
            ansiwrap.fill(
                f"{colors.RED}{change[2]}{colors.END}",
                initial_indent=prefix.ljust(prefix_len),
                subsequent_indent=" " * prefix_len,
            )
        )
    elif change[0] == "remove":
        prefix = change[1] + ": "
        print(
            ansiwrap.fill(
                f"{colors.GREEN}{change[2]}{colors.END}",
                initial_indent=prefix.ljust(prefix_len),
                subsequent_indent=" " * prefix_len,
            )
        )
    return


def merge_manual_dialogue(bib_db: BibDatabase, item: dict, stat: str) -> dict:
    if "decision" in item:
        return item

    # Note: all changes must be made to the main_record (i.e., if we display
    # the main_record on the left side and if the user selects "1", this
    # means "no changes to the main record".)
    # We effectively have to consider only cases in which the user
    # wants to merge fields from the duplicate record into the main record

    main_record = [x for x in bib_db.entries if item["main_ID"] == x["ID"]][0]
    duplicate_record = [x for x in bib_db.entries if item["duplicate_ID"] == x["ID"]][0]

    # Escape sequence to clear terminal output for each new comparison
    # os.system("cls" if os.name == "nt" else "clear")
    print(
        f"Merge {colors.GREEN}{main_record['ID']}{colors.END} < "
        + f"{colors.RED}{duplicate_record['ID']}{colors.END}?\n"
    )

    keys = set(list(main_record) + list(duplicate_record))
    differences = list(diff(main_record, duplicate_record))

    if len([x[2] for x in differences if "add" == x[0]]) > 0:
        added_fields = [y[0] for y in [x[2] for x in differences if "add" == x[0]][0]]
    else:
        added_fields = []
    if len([x[2] for x in differences if "remove" == x[0]]) > 0:
        removed_fields = [
            y[0] for y in [x[2] for x in differences if "remove" == x[0]][0]
        ]
    else:
        removed_fields = []
    prefix_len = len(max(keys, key=len) + ": ")
    for key in [
        "author",
        "title",
        "journal",
        "booktitle",
        "year",
        "volume",
        "number",
        "pages",
        "doi",
        "ENTRYTYPE",
    ]:
        if key in added_fields:
            change = [
                y
                for y in [x[2] for x in differences if "add" == x[0]][0]
                if key == y[0]
            ]
            print_diff(("add", *change[0]), prefix_len)
        elif key in removed_fields:
            change = [
                y
                for y in [x[2] for x in differences if "remove" == x[0]][0]
                if key == y[0]
            ]
            print_diff(("remove", *change[0]), prefix_len)
        elif key in [x[1] for x in differences]:
            change = [x for x in differences if x[1] == key]
            print_diff(change[0], prefix_len)
        elif key in keys:
            prefix = key + ": "
            print(
                ansiwrap.fill(
                    main_record[key],
                    initial_indent=prefix.ljust(prefix_len),
                    subsequent_indent=" " * prefix_len,
                )
            )

    response_string = "(" + stat + ") Merge records [y,n,d,q,?]? "
    response = input("\n" + response_string)
    while response not in ["y", "n", "d", "q"]:
        print(
            f"y - merge the {colors.RED}red record{colors.END} into the "
            + f"{colors.GREEN}green record{colors.END}"
        )
        print("n - keep both records (not duplicates)")
        print("d - detailed merge: decide for each field (to be implemented)")
        print("q - stop processing duplicate records")
        print("? - print help")
        response = input(response_string)

    if "y" == response:
        item["decision"] = "duplicate"

    if "n" == response:
        item["decision"] = "no_duplicate"

    if "q" == response:
        item["decision"] = "quit"

    return item


def dedupe_man_cli(REVIEW_MANAGER):
    from review_template import dedupe_man

    saved_args = locals()

    bib_db = REVIEW_MANAGER.load_main_refs()
    dedupe_man_data = dedupe_man.get_data(REVIEW_MANAGER, bib_db)
    if 0 == dedupe_man_data["nr_tasks"]:
        return

    for i, dedupe_man_item in enumerate(dedupe_man_data["items"]):
        stat = str(i) + "/" + str(dedupe_man_data["nr_tasks"])

        dedupe_man_item = merge_manual_dialogue(bib_db, dedupe_man_item, stat)
        bib_db = dedupe_man.set_data(REVIEW_MANAGER, bib_db, dedupe_man_item)

        if "quit" == dedupe_man_item["decision"]:
            if "y" == input("Create commit (y/n)?"):
                break
            else:
                return

    REVIEW_MANAGER.create_commit(
        "Process duplicates manually", manual_author=True, saved_args=saved_args
    )
    return


@main.command(help_priority=8)
@click.pass_context
def dedupe_man(ctx) -> None:
    """Manual processing of duplicates"""
    from review_template import review_manager
    from review_template.review_manager import ReviewManager

    try:
        REVIEW_MANAGER = ReviewManager()
        dedupe_man_cli(REVIEW_MANAGER)

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

    from review_template import prescreen

    logger = logging.getLogger("review_template")

    prescreen_data = prescreen.get_data(REVIEW_MANAGER)
    stat_len = prescreen_data["nr_tasks"]
    PAD = prescreen_data["PAD"]

    pp = pprint.PrettyPrinter(indent=4, width=140)
    i, quit_pressed = 0, False

    logging.info("Start prescreen")

    if 0 == stat_len:
        logger.info("No records to prescreen")

    for record in prescreen_data["items"]:

        print("\n\n")
        revrecord = customsort(record)
        pp.pprint(revrecord)

        ret, inclusion_decision = "NA", "NA"
        i += 1
        while ret not in ["y", "n", "s", "q"]:
            ret = input(f"({i}/{stat_len}) Include this record [y,n,q,s]? ")
            if "q" == ret:
                quit_pressed = True
            elif "s" == ret:
                continue
            else:
                inclusion_decision = ret.replace("y", "yes").replace("n", "no")

        if quit_pressed:
            logger.info("Stop prescreen")
            break

        inclusion_decision = "yes" == inclusion_decision
        prescreen.set_data(REVIEW_MANAGER, record, inclusion_decision, PAD)

    if i < stat_len:  # if records remain for pre-screening
        if "y" != input("Create commit (y/n)?"):
            return

    REVIEW_MANAGER.create_commit(
        "Pre-screening (manual)", manual_author=True, saved_args=None
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
def prescreen(ctx, include_all, export_format, import_table) -> None:
    """Pre-screen based on titles and abstracts"""
    from review_template import prescreen
    from review_template import review_manager
    from review_template.review_manager import ReviewManager

    try:
        REVIEW_MANAGER = ReviewManager()

        if export_format:
            prescreen.export_table(REVIEW_MANAGER, export_format)
        elif import_table:
            prescreen.import_table(REVIEW_MANAGER, import_table)
        elif include_all:
            prescreen.include_all_in_prescreen(REVIEW_MANAGER)
        else:
            prescreen_cli(REVIEW_MANAGER)

    except review_manager.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")
        pass
    except review_manager.CleanRepoRequiredError as e:
        logging.error(f"CleanRepoRequiredError: {e}")
        pass

    return


def screen_cli(
    REVIEW_MANAGER,
) -> None:

    from review_template import screen

    logger = logging.getLogger("review_template")

    screen_data = screen.get_data(REVIEW_MANAGER)
    stat_len = screen_data["nr_tasks"]
    PAD = screen_data["PAD"]

    pp = pprint.PrettyPrinter(indent=4, width=140)
    i, quit_pressed = 0, False

    logging.info("Start screen")

    if 0 == stat_len:
        logger.info("No records to prescreen")

    bib_db = REVIEW_MANAGER.load_main_refs()
    excl_criteria = screen.get_exclusion_criteria(bib_db)
    if excl_criteria:
        excl_criteria_available = True
    else:
        excl_criteria_available = False
        excl_criteria = ["NA"]

    for record in screen_data["items"]:

        print("\n\n")
        i += 1
        skip_pressed = False

        revrecord = customsort(record.copy())
        pp.pprint(revrecord)

        if excl_criteria_available:
            decisions = []

            for exclusion_criterion in excl_criteria:

                decision, ret = "NA", "NA"
                while ret not in ["y", "n", "q", "s"]:
                    ret = input(
                        f"({i}/{stat_len}) Violates"
                        f" {exclusion_criterion} [y,n,q,s]? "
                    )
                    if "q" == ret:
                        quit_pressed = True
                    elif "s" == ret:
                        skip_pressed = True
                        continue
                    elif ret in ["y", "n"]:
                        decision = ret

                if quit_pressed or skip_pressed:
                    break

                decisions.append([exclusion_criterion, decision])

            if skip_pressed:
                continue
            if quit_pressed:
                logger.info("Stop screen")
                break

            ec_field = ""
            for exclusion_criterion, decision in decisions:
                if ec_field != "":
                    ec_field = f"{ec_field};"
                decision = decision.replace("y", "yes").replace("n", "no")
                ec_field = f"{ec_field}{exclusion_criterion}={decision}"
            record["excl_criteria"] = ec_field.replace(" ", "")

            if all([decision == "n" for ec, decision in decisions]):
                record.update(status=RecordState.rev_included)
                screen.set_data(REVIEW_MANAGER, record, PAD)
            else:
                record.update(status=RecordState.rev_excluded)
                screen.set_data(REVIEW_MANAGER, record, PAD)

        else:

            decision, ret = "NA", "NA"
            while ret not in ["y", "n", "q", "s"]:
                ret = input(f"({i}/{stat_len}) Include [y,n,q,s]? ")
                if "q" == ret:
                    quit_pressed = True
                elif "s" == ret:
                    skip_pressed = True
                    continue
                elif ret in ["y", "n"]:
                    decision = ret

            if quit_pressed:
                logger.info("Stop screen")
                break

            if decision == "y":
                record.update(status=RecordState.rev_included)
                screen.set_screen_status(REVIEW_MANAGER, record, PAD)
            if decision == "n":
                record.update(status=RecordState.rev_excluded)
                screen.set_screen_status(REVIEW_MANAGER, record, PAD)

            record["excl_criteria"] = "NA"

        if quit_pressed:
            logger.info("Stop screen")
            break

    if stat_len == 0:
        logger.info("No records to screen")
        return

    if i < stat_len:  # if records remain for screening
        if "y" != input("Create commit (y/n)?"):
            return

    REVIEW_MANAGER.create_commit(
        "Screening (manual)", manual_author=True, saved_args=None
    )
    return


@main.command(help_priority=10)
@click.pass_context
def screen(ctx) -> None:
    """Screen based on exclusion criteria and fulltext documents"""
    from review_template import review_manager
    from review_template.review_manager import ReviewManager

    try:
        REVIEW_MANAGER = ReviewManager()
        screen_cli(REVIEW_MANAGER)
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
        pdf_get_process = Process(ProcessType.pdf_get, pdf_get.main)
        REVIEW_MANAGER.run_process(pdf_get_process)

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
        pdf_prepare_process = Process(ProcessType.pdf_prepare, pdf_prepare.main)
        REVIEW_MANAGER.run_process(pdf_prepare_process)

    except review_manager.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")
        pass

    return


def get_pdf_from_google(record: dict) -> dict:
    import urllib.parse

    # import webbrowser

    title = record["title"]
    title = urllib.parse.quote_plus(title)
    url = f"https://www.google.com/search?q={title}+filetype%3Apdf"
    # webbrowser.open_new_tab(url)
    print(url)
    return record


def man_retrieve(REVIEW_MANAGER, bib_db, item: dict, stat: str) -> dict:
    from review_template import pdf_get_man

    logger.debug(f"called man_retrieve for {pp.pformat(item)}")
    print(stat)
    pp.pprint(item)

    record = [x for x in bib_db.entries if item["ID"] == x["ID"]][0]
    if RecordState.pdf_needs_manual_retrieval != record["status"]:
        return record

    retrieval_scripts = {
        "get_pdf_from_google": get_pdf_from_google,
        #  'get_pdf_from_researchgate': get_pdf_from_researchgate,
    }

    for retrieval_script in retrieval_scripts:
        logger.debug(f'{retrieval_script}({record["ID"]}) called')
        record = retrieval_scripts[retrieval_script](record)
        if "y" == input("Retrieved (y/n)?"):
            # TODO : some of the following should be moved
            # to the pdf_get_man script ("apply changes")
            filepath = os.path.join(
                REVIEW_MANAGER.paths["PDF_DIRECTORY"], record["ID"] + ".pdf"
            )
            if not os.path.exists(filepath):
                print(f'File does not exist: {record["ID"]}.pdf')
            else:
                pdf_get_man.set_data(REVIEW_MANAGER, record, filepath)
                break
    if "y" == input("Set to pdf_not_available (y/n)?"):
        pdf_get_man.set_data(REVIEW_MANAGER, record, None)

    return


def pdf_get_man_cli(REVIEW_MANAGER):
    from review_template import pdf_get
    from review_template import pdf_get_man

    saved_args = locals()
    logger.info("Retrieve PDFs manually")

    PDF_DIRECTORY = REVIEW_MANAGER.paths["PDF_DIRECTORY"]

    bib_db = REVIEW_MANAGER.load_main_refs()
    bib_db = pdf_get.check_existing_unlinked_pdfs(bib_db, PDF_DIRECTORY)

    for record in bib_db.entries:
        record = pdf_get.link_pdf(record, PDF_DIRECTORY, set_needs_man_retrieval=False)

    pdf_get_man.export_retrieval_table(bib_db)

    pdf_get_man_data = pdf_get_man.get_data(REVIEW_MANAGER)

    input("Get the pdfs, rename them (ID.pdf) and store them in the pdfs directory.")

    for i, item in enumerate(pdf_get_man_data["items"]):
        stat = str(i + 1) + "/" + str(pdf_get_man_data["nr_tasks"])
        man_retrieve(REVIEW_MANAGER, bib_db, item, stat)

    if pdf_get_man.pdfs_retrieved_maually(REVIEW_MANAGER):
        if "y" == input("Create commit (y/n)?"):
            REVIEW_MANAGER.create_commit(
                "Retrieve PDFs manually", manual_author=True, saved_args=saved_args
            )
    else:
        logger.info(
            "Retrieve PDFs manually and copy the files to "
            f"the {PDF_DIRECTORY}. Afterwards, use "
            "review_template pdf-get-man"
        )

    return


@main.command(help_priority=13)
@click.pass_context
def pdf_get_man(ctx) -> None:
    """Get PDFs manually"""
    from review_template import review_manager
    from review_template.review_manager import ReviewManager

    try:
        REVIEW_MANAGER = ReviewManager()
        pdf_get_man_cli(REVIEW_MANAGER)
    except review_manager.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")
        pass
    return


def man_pdf_prep(REVIEW_MANAGER, bib_db, item, stat):
    from review_template import pdf_prep_man

    logger.debug(f"called man_pdf_prep for {pp.pformat(item)}")
    print(stat)
    pp.pprint(item)

    record = [x for x in bib_db.entries if item["ID"] == x["ID"]][0]
    if RecordState.pdf_needs_manual_preparation != record["status"]:
        return record

    print("Manual preparation needed (TODO: include details)")

    filepath = os.path.join(
        REVIEW_MANAGER.paths["PDF_DIRECTORY"], record["ID"] + ".pdf"
    )
    if not os.path.exists(filepath):
        print(f'File does not exist: {record["ID"]}.pdf')
    else:
        if "y" == input("Prepared? (y/n)?"):

            pdf_prep_man.set_data(REVIEW_MANAGER, record)

    return


def pdf_prep_man_cli(REVIEW_MANAGER):
    from review_template import pdf_prep_man

    saved_args = locals()
    input(
        "TODO: check /print problems for each PDF with status = "
        "pdf_needs_manual_preparation and suggest how it could be fixed"
    )

    pdf_prep_man_data = pdf_prep_man.get_data(REVIEW_MANAGER)
    bib_db = REVIEW_MANAGER.load_main_refs()

    for i, item in enumerate(pdf_prep_man_data["items"]):
        stat = str(i + 1) + "/" + str(pdf_prep_man_data["nr_tasks"])
        man_pdf_prep(REVIEW_MANAGER, bib_db, item, stat)

    if pdf_prep_man.pdfs_prepared_manually(REVIEW_MANAGER):
        if "y" == input("Create commit (y/n)?"):
            REVIEW_MANAGER.create_commit(
                "Prepare PDFs manually", manual_author=True, saved_args=saved_args
            )
    else:
        logger.info(
            "Prepare PDFs manually. Afterwards, use review_template pdf-get-man"
        )

    return


@main.command(help_priority=14)
@click.pass_context
def pdf_prep_man(ctx) -> None:
    """Prepare PDFs manually"""
    from review_template import review_manager
    from review_template.review_manager import ReviewManager

    try:
        REVIEW_MANAGER = ReviewManager()
        pdf_prep_man_cli(REVIEW_MANAGER)
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

    try:
        REVIEW_MANAGER = ReviewManager()
        data.main(REVIEW_MANAGER, edit_csv, load_csv)
    except review_manager.ProcessOrderViolation as e:
        logging.error(f"ProcessOrderViolation: {e}")
        pass
    return


def validate_commit(ctx, param, value):

    if "none" == value:
        return value

    lgrepo = git.Repo()
    revlist = [commit for commit in lgrepo.iter_commits()]

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
@click.option("-a", "--activate", is_flag=True, default=False)
@click.option("-d", "--deactivate", is_flag=True, default=False)
@click.pass_context
def debug(ctx, activate, deactivate):
    """Debug"""
    from review_template import debug
    from review_template import review_manager

    review_manager.setup_logger()
    logger = logging.getLogger("review_template")

    if activate:
        logger.info("Debugging activated")
        debug.set_debug_mode(True)

    elif deactivate:
        logger.info("Debugging deactivated")
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
