#! /usr/bin/env python3
"""Command-line interface for CoLRev."""
from __future__ import annotations

import logging
import os
import subprocess  # nosec
import sys
import time
import typing
import webbrowser
from functools import partial
from functools import wraps
from pathlib import Path

import click
import click_completion.core
import click_repl
import pandas as pd
from git.exc import GitCommandError

import colrev.env.local_index
import colrev.env.local_index_builder
import colrev.exceptions as colrev_exceptions
import colrev.ops.check
import colrev.package_manager.package_manager
import colrev.record.record
import colrev.review_manager
import colrev.ui_cli.add_package_to_settings
import colrev.ui_cli.cli_status_printer
import colrev.ui_cli.cli_validation
import colrev.ui_cli.dedupe_errors
from colrev.constants import Colors
from colrev.constants import EndpointType
from colrev.constants import Fields
from colrev.constants import RecordState
from colrev.constants import ScreenCriterionType

# pylint: disable=too-many-lines
# pylint: disable=redefined-builtin
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=superfluous-parens
# pylint: disable=too-many-locals
# pylint: disable=import-outside-toplevel
# pylint: disable=too-many-locals
# pylint: disable=import-outside-toplevel
# pylint: disable=too-many-return-statements

# Note: autocompletion needs bash/... activation:
# https://click.palletsprojects.com/en/7.x/bashcomplete/

EXACT_CALL = "colrev " + subprocess.list2cmdline(sys.argv[1:])  # nosec

PACKAGE_MANAGER = colrev.package_manager.package_manager.PackageManager()
TYPE_IDENTIFIER_ENDPOINT_DICT = PACKAGE_MANAGER.load_type_identifier_endpoint_dict()

SHELL_MODE = False


def _custom_startswith(string: str, incomplete: str) -> bool:
    """A custom completion matching that supports case insensitive matching"""
    if os.environ.get("_CLICK_COMPLETION_COMMAND_CASE_INSENSITIVE_COMPLETE"):
        string = string.lower()
        incomplete = incomplete.lower()
    return string.startswith(incomplete)


click_completion.core.startswith = _custom_startswith
click_completion.init()


def get_search_files() -> list:
    """Get the search files (for click choices)"""
    # Take the filenames from sources because there may be API searches
    # without files (yet)
    try:
        review_manager = colrev.review_manager.ReviewManager()
        return [str(x.filename) for x in review_manager.settings.sources]
    except Exception:  # pylint: disable=broad-exception-caught
        return []


class SpecialHelpOrder(click.Group):
    """Order for cli commands in help page overview"""

    def __init__(self, *args, **kwargs) -> None:  # type: ignore
        self.help_priorities: dict = {}
        super().__init__(*args, **kwargs)

    def get_help(self, ctx: click.core.Context):  # type: ignore
        self.list_commands = self.list_commands_for_help  # type: ignore  # noqa
        return super().get_help(ctx)

    def list_commands_for_help(self, ctx: click.core.Context) -> typing.Generator:
        """reorder the list of commands when listing the help"""
        commands = super().list_commands(ctx)
        return (
            c[1]
            for c in sorted(
                (self.help_priorities.get(command, 1), command) for command in commands
            )
        )

    def command(self, *args, **kwargs):  # type: ignore
        """Behaves the same as `click.Group.command()` except capture
        a priority for listing command names in help.
        """
        help_priority = kwargs.pop("help_priority", 1)
        help_priorities = self.help_priorities

        def decorator(fun):  # type: ignore
            # pylint: disable=super-with-arguments
            cmd = super(SpecialHelpOrder, self).command(*args, **kwargs)(fun)
            help_priorities[cmd.name] = help_priority
            return cmd

        return decorator


def catch_exception(func=None, *, handle) -> typing.Any:  # type: ignore
    """Catch typical cli exceptions (e.g., CoLRevException)"""
    if not func:
        return partial(catch_exception, handle=handle)

    # pylint: disable=inconsistent-return-statements
    @wraps(func)
    def wrapper(*args, **kwargs) -> None:  # type: ignore
        try:
            return func(*args, **kwargs)
        except colrev_exceptions.CoLRevException as exc:
            if kwargs.get("verbose", False):
                raise exc
            print(exc)

    return wrapper


@click.group(cls=SpecialHelpOrder)
@click.pass_context
def main(ctx: click.core.Context) -> None:
    """CoLRev commands:

    \b
    status        Shows status, how to proceed, and checks for errors

    \b
    init          Initialize (define review objectives and type)
    retrieve      Search, load, prepare, and deduplicate metadata records
    prescreen     Exclude records based on metadata
    pdfs          Get and prepare PDFs
    screen        Include records based on PDFs
    data          Complete selected forms of data analysis and synthesis

    \b
    validate      Validate changes in the previous commit

    Recommended workflow: colrev status > colrev OPERATION > colrev validate

    Documentation:  https://colrev.readthedocs.io/
    """

    try:
        if ctx.invoked_subcommand == "shell":
            ctx.obj = {"review_manager": colrev.review_manager.ReviewManager()}
    except colrev.exceptions.RepoSetupError:
        pass


def get_review_manager(
    ctx: click.core.Context, review_manager_params: dict
) -> colrev.review_manager.ReviewManager:
    """Get review_manager instance. If it's available in ctx object, reuse that
    if not creates a new one, Once created will update the review_manager with
    the given parameters. If params requires review_manager to be reloaded, will
    reload it
    """

    review_manager_params["exact_call"] = ctx.command_path
    try:
        review_manager = ctx.obj["review_manager"]
        if (
            "navigate_to_home_dir" in review_manager_params
            or "path_str" in review_manager_params
            or "skip_upgrade" in review_manager_params
        ):
            print("init review manager object ...")
            review_manager = colrev.review_manager.ReviewManager(
                **review_manager_params
            )
            ctx.obj["review_manager"] = review_manager
        else:
            review_manager.update_config(**review_manager_params)
        if SHELL_MODE:
            review_manager.shell_mode = True
        return review_manager
    except (TypeError, KeyError):
        review_manager = colrev.review_manager.ReviewManager(**review_manager_params)
        ctx.obj = {"review_manager": review_manager}
        if SHELL_MODE:
            review_manager.shell_mode = True
        return review_manager


@main.command(help_priority=100)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def shell(
    ctx: click.core.Context,
) -> None:
    """Starts a interactive terminal"""
    from prompt_toolkit.history import FileHistory

    print(f"CoLRev version {colrev.__version__}")
    print("Workflow: status > OPERATION > validate")
    print("https://colrev.readthedocs.io/en/latest/")
    print("Type exit to close the shell")
    print()
    prompt_kwargs = {"history": FileHistory(".history"), "message": "CoLRev > "}
    # pylint: disable=global-statement
    global SHELL_MODE
    SHELL_MODE = True
    click_repl.repl(ctx, prompt_kwargs=prompt_kwargs)


@main.command(help_priority=100)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def exit(
    ctx: click.core.Context,
) -> None:
    """Starts a interactive terminal"""
    import inspect

    curframe = inspect.currentframe()
    calframe = inspect.getouterframes(curframe, 2)
    if calframe[7].function == "shell":
        raise click_repl.exceptions.ExitReplException


@main.command(help_priority=1)
@click.option(
    "--type",
    type=click.Choice(TYPE_IDENTIFIER_ENDPOINT_DICT[EndpointType.review_type]),
    default="colrev.literature_review",
    help="Review type for the setup.",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.option(
    "--light",
    is_flag=True,
    default=False,
    help="Setup a lightweight repository (without Docker services)",
)
@click.option(
    "--example",
    is_flag=True,
    default=False,
    help="Add search results example",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def init(
    ctx: click.core.Context,
    type: str,
    example: bool,
    force: bool,
    light: bool,
) -> None:
    """Initialize (define review objectives and type)

    Docs: https://colrev.readthedocs.io/en/latest/manual/problem_formulation/init.html
    """
    import colrev.ops.init

    colrev.ops.init.Initializer(
        review_type=type,
        target_path=Path.cwd(),
        example=example,
        force_mode=force,
        light=light,
        exact_call=EXACT_CALL,
    )


@main.command(help_priority=2)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def status(
    ctx: click.core.Context,
    verbose: bool,
) -> None:
    """Show status"""
    try:
        review_manager = get_review_manager(
            ctx,
            {"force_mode": False, "verbose_mode": verbose, "exact_call": EXACT_CALL},
        )
        status_operation = review_manager.get_status_operation()
        colrev.ui_cli.cli_status_printer.print_project_status(status_operation)

    except KeyboardInterrupt:
        print("Stopped...")
    except colrev_exceptions.RepoSetupError as exc:
        print(exc)


@main.command(help_priority=100)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.pass_context
def dashboard(
    ctx: click.core.Context,
    verbose: bool,
) -> None:
    """Allows to track project progress through dashboard"""
    import colrev.packages.ui_web.src.dashboard

    try:
        colrev.packages.ui_web.src.dashboard.main()
    except colrev_exceptions.NoRecordsError:
        print("No records imported yet.")
    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


@main.command(help_priority=3)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def retrieve(
    ctx: click.core.Context,
    verbose: bool,
    force: bool,
) -> None:
    """Retrieve, a high-level operation, consists of search, load, prep, and dedupe.

    \b
    To retrieve search results:
    - Copy files (*.bib, *.ris, *.xlsx, ...) to the directory data/search or
    - Copy PDF files to the directory data/pdfs or
    - Add an API-based search, as described in the documentation:

    https://colrev.readthedocs.io/en/latest/manual/metadata_retrieval/search.html
    """

    review_manager = get_review_manager(
        ctx,
        {"verbose_mode": verbose, "force_mode": force, "high_level_operation": True},
    )

    pdf_dir = review_manager.paths.pdf
    search_dir = review_manager.paths.search
    if not any(search_dir.iterdir()) and not any(pdf_dir.iterdir()):
        # Note : API-based searches automatically retrieve files
        # when they are added, i.e., the following message should
        # not be shown.
        print(
            "To retrieve search results,\n"
            " - copy files (*.bib, *.ris, *.xlsx, ...) "
            f"to the directory {review_manager.paths.SEARCH_DIR} or\n"
            f" - copy PDF files to the directory {review_manager.paths.PDF_DIR} or \n"
            " - add an API-based search, as described in the documentation:\n"
            "https://colrev.readthedocs.io/en/latest/manual/metadata_retrieval/search.html"
        )
        return

    review_manager.logger.info("Retrieve")
    review_manager.logger.info(
        "Retrieve is a high-level operation consisting of search, load, prep, and dedupe:"
    )
    print()

    review_manager.exact_call = "colrev search"
    search_operation = review_manager.get_search_operation()
    search_operation.add_most_likely_sources()
    search_operation.main(rerun=False)

    print()

    review_manager.exact_call = "colrev load"
    load_operation = review_manager.get_load_operation(hide_load_explanation=True)
    load_operation.main(keep_ids=False)

    print()
    review_manager.exact_call = "colrev prep"
    prep_operation = review_manager.get_prep_operation()
    prep_operation.main()

    print()

    review_manager.exact_call = "colrev dedupe"
    dedupe_operation = review_manager.get_dedupe_operation()
    dedupe_operation.main()


@main.command(help_priority=4)
@click.option(
    "-a",
    "--add",
    type=click.Choice(TYPE_IDENTIFIER_ENDPOINT_DICT[EndpointType.search_source]),
    help="""Search source to be added.""",
)
@click.option(
    "-p",
    "--params",
    type=str,
    help="Parameters",
)
@click.option("--view", is_flag=True, default=False, help="View search sources")
@click.option(
    "-s",
    "--selected",
    type=click.Choice(get_search_files()),
    help="Only retrieve search results for selected sources",
)
@click.option(
    "-r",
    "--rerun",
    is_flag=True,
    default=False,
    help="Rerun API-based searches, retrieving and updating all records "
    + "(not just the most recent ones)",
)
@click.option(
    "-bws",
    help="Backward search on a selected paper",
)
@click.option(
    "--skip",
    is_flag=True,
    default=False,
    help="Skip adding new SearchSources",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom search script.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def search(
    ctx: click.core.Context,
    add: str,
    params: str,
    view: bool,
    selected: str,
    rerun: bool,
    bws: str,
    skip: str,
    setup_custom_script: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Search for records

    Docs: https://colrev.readthedocs.io/en/latest/manual/metadata_retrieval/search.html
    """

    review_manager = get_review_manager(
        ctx, {"verbose_mode": verbose, "force_mode": force, "exact_call": EXACT_CALL}
    )

    search_operation = review_manager.get_search_operation()

    if view:
        for source in search_operation.sources:
            search_operation.review_manager.p_printer.pprint(source)
        return

    if add:
        # pylint: disable=import-outside-toplevel
        # pylint: disable=reimported
        import colrev.ui_cli.add_package_to_settings

        colrev.ui_cli.add_package_to_settings.add_package_to_settings(
            PACKAGE_MANAGER,
            operation=search_operation,
            package_identifier=add,
            params=params,
        )
        return

    if skip:
        existing_sources = ",".join(
            str(
                source.filename
                for source in search_operation.review_manager.settings.sources
            )
        )
        search_operation.main(selection_str=existing_sources, rerun=rerun)
        return

    if setup_custom_script:
        import colrev.ui_cli.setup_custom_scripts

        colrev.ui_cli.setup_custom_scripts.setup_custom_search_script(
            review_manager=review_manager
        )
        print("Activated custom_search_script.py.")
        print(
            f"Please update the source in {review_manager.paths.SETTINGS_FILE} and commit."
        )
    elif bws:
        import colrev.ui_cli.search_backward_selective

        colrev.ui_cli.search_backward_selective.main(
            search_operation=search_operation, bws=bws
        )
        return

    import colrev.ui_cli.cli_add_source

    cli_source_adder = colrev.ui_cli.cli_add_source.CLISourceAdder(
        search_operation=search_operation
    )
    sources_added = cli_source_adder.add_new_sources()
    if sources_added:
        if selected is None:
            selected = ",".join(
                [
                    str(source.filename)
                    for source in search_operation.review_manager.settings.sources
                    if source.filename not in [x.filename for x in sources_added]
                ]
            )
        else:
            input(selected)  # notify /handle pre-selected when adding new

    search_operation.main(selection_str=selected, rerun=rerun)


@main.command(help_priority=5)
@click.option(
    "-k",
    "--keep_ids",
    is_flag=True,
    default=False,
    help="Do not change the record IDs. Useful when importing an existing sample.",
)
@click.option(
    "-sq",
    "--skip_query",
    is_flag=True,
    default=False,
    help="Skip entering the search query (if applicable)",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def load(
    ctx: click.core.Context,
    keep_ids: bool,
    skip_query: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Load records

    Docs: https://colrev.readthedocs.io/en/latest/manual/metadata_retrieval/load.html
    """

    review_manager = get_review_manager(
        ctx, {"verbose_mode": verbose, "force_mode": force, "exact_call": EXACT_CALL}
    )
    load_operation = review_manager.get_load_operation()

    # Note : reinitialize to load new scripts:
    load_operation = review_manager.get_load_operation(hide_load_explanation=True)

    load_operation.main(keep_ids=keep_ids)


@main.command(help_priority=6)
@click.option(
    "-a",
    "--add",
    type=click.Choice(TYPE_IDENTIFIER_ENDPOINT_DICT[EndpointType.prep]),
    help="""Prep package to be added.""",
)
@click.option(
    "-p",
    "--params",
    type=str,
    help="Parameters",
)
@click.option(
    "-k",
    "--keep_ids",
    is_flag=True,
    default=False,
    help="Do not change the record IDs. Useful when importing an existing sample.",
)
@click.option(
    "--polish",
    is_flag=True,
    default=False,
    help="Polish record metadata (includes records in md_processed or beyond).",
)
@click.option(
    "-d",
    "--debug",
    type=str,
    help="Debug the preparation step for a selected record (can be 'all').",
)
@click.option(
    "--cpu",
    type=int,
    help="Number of cpus (parallel processes)",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom prep script.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def prep(
    ctx: click.core.Context,
    add: str,
    params: str,
    keep_ids: bool,
    polish: bool,
    debug: str,
    cpu: int,
    setup_custom_script: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Prepare records

    Docs: https://colrev.readthedocs.io/en/latest/manual/metadata_retrieval/prep.html
    """

    try:
        review_manager = get_review_manager(
            ctx,
            {"verbose_mode": verbose, "force_mode": force, "exact_call": EXACT_CALL},
        )

        if debug:
            review_manager.force_mode = True
            debug_prep_operation = review_manager.get_prep_operation(
                polish=polish,
                cpu=cpu,
                debug=True,
            )
            debug_prep_operation.run_debug(debug_ids=debug)  # type: ignore
            return

        prep_operation = review_manager.get_prep_operation(polish=polish, cpu=cpu)
        if setup_custom_script:
            prep_operation.setup_custom_script()
            print("Activated custom_prep_script.py.")
            print(
                "Please check and adapt its position in the "
                f"{review_manager.paths.SETTINGS_FILE} and commit."
            )
            return
        if add:

            colrev.ui_cli.add_package_to_settings.add_package_to_settings(
                PACKAGE_MANAGER,
                operation=prep_operation,
                package_identifier=add,
                params=params,
            )
            return

        prep_operation.main(keep_ids=keep_ids)

    except colrev_exceptions.ServiceNotAvailableException as exc:
        print(exc)
        print("You can use the force mode to override")
        print(f"  {Colors.ORANGE}colrev prep -f{Colors.END}")
        return


@main.command(help_priority=7)
@click.option(
    "-a",
    "--add",
    type=click.Choice(TYPE_IDENTIFIER_ENDPOINT_DICT[EndpointType.prep_man]),
    help="""Prep-man script  to be added.""",
)
@click.option(
    "-p",
    "--params",
    type=str,
    help="Parameters",
)
@click.option(
    "--stats",
    is_flag=True,
    default=False,
    help="Print statistics of records with colrev_status md_needs_manual_preparation",
)
@click.option(
    "-l",
    "--languages",
    is_flag=True,
    default=False,
    help="Export spreadsheet to add missing language fields.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def prep_man(
    ctx: click.core.Context,
    add: str,
    params: str,
    stats: bool,
    languages: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Prepare records manually

    Docs: https://colrev.readthedocs.io/en/latest/manual/metadata_retrieval/prep.html
    """

    review_manager = get_review_manager(
        ctx, {"verbose_mode": verbose, "force_mode": force, "exact_call": EXACT_CALL}
    )
    prep_man_operation = review_manager.get_prep_man_operation()
    if languages:
        prep_man_operation.prep_man_langs()
        return

    if stats:
        prep_man_operation.prep_man_stats()
        return

    if add:

        colrev.ui_cli.add_package_to_settings.add_package_to_settings(
            PACKAGE_MANAGER,
            operation=prep_man_operation,
            package_identifier=add,
            params=params,
        )
        return

    prep_man_operation.main()


def _view_dedupe_details(dedupe_operation: colrev.ops.dedupe.Dedupe) -> None:
    info = dedupe_operation.get_info()

    if len(info["same_source_merges"]) > 0:
        print(f"\n\n{Colors.RED}Same source merges to check:{Colors.END}")
        print("\n- " + "\n- ".join(info["same_source_merges"]))

    print(info["source_overlaps"])


@main.command(help_priority=8)
@click.option(
    "-a",
    "--add",
    type=click.Choice(TYPE_IDENTIFIER_ENDPOINT_DICT[EndpointType.dedupe]),
    help="""Dedupe package to be added.""",
)
@click.option(
    "-p",
    "--params",
    type=str,
    help="Parameters",
)
@click.option(
    "-m",
    "--merge",
    help="Merge records by providing a comma-separated list of IDs (ID1,ID2).",
    required=False,
)
@click.option(
    "-u",
    "--unmerge",
    help="Unmerge records by providing a comma-separated list of IDs (ID1,ID2).",
    required=False,
)
@click.option(
    "-f",
    "--fix_errors",
    is_flag=True,
    default=False,
    help="Fix errors marked in duplicates_to_validate.xlsx "
    "or non_duplicates_to_validate.xlsx or "
    "a dupes.txt file containing comma-separated ID tuples",
)
@click.option(
    "-gid",
    help="Merge records with identical global IDs (e.g., DOI)",
    is_flag=True,
    default=False,
)
@click.option("--view", is_flag=True, default=False, help="View dedupe info")
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    default=False,
    help="Debug mode",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def dedupe(
    ctx: click.core.Context,
    add: str,
    params: str,
    merge: str,
    unmerge: str,
    fix_errors: bool,
    gid: bool,
    view: bool,
    debug: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Deduplicate records

    Docs: https://colrev.readthedocs.io/en/latest/manual/metadata_retrieval/dedupe.html
    """

    review_manager = get_review_manager(
        ctx, {"verbose_mode": verbose, "force_mode": force, "exact_call": EXACT_CALL}
    )
    state_transition_operation = not view
    dedupe_operation = review_manager.get_dedupe_operation(
        notify_state_transition_operation=state_transition_operation
    )

    if add:

        colrev.ui_cli.add_package_to_settings.add_package_to_settings(
            PACKAGE_MANAGER,
            operation=dedupe_operation,
            package_identifier=add,
            params=params,
        )
        return

    if merge:
        assert "," in merge
        merge_ids = [i.split(",") for i in merge.split(";")]

        dedupe_operation.merge_records(merge=merge_ids)
        return

    if unmerge:
        dedupe_operation.unmerge_records(current_record_ids=unmerge.split(","))
        return
    if gid:
        dedupe_operation.merge_based_on_global_ids(apply=True)
        return
    if fix_errors:
        review_manager.report_logger.info("Dedupe: fix errors")
        review_manager.logger.info("Dedupe: fix errors")
        if not (
            dedupe_operation.dupe_file.is_file()
            or dedupe_operation.non_dupe_file_xlsx.is_file()
            or dedupe_operation.non_dupe_file_txt.is_file()
        ):
            review_manager.logger.error("No file with potential errors found.")
            return

        false_positives = colrev.ui_cli.dedupe_errors.load_dedupe_false_positives(
            dedupe_operation=dedupe_operation
        )
        false_negatives = colrev.ui_cli.dedupe_errors.load_dedupe_false_negatives(
            dedupe_operation=dedupe_operation
        )

        dedupe_operation.fix_errors(
            false_positives=false_positives,
            false_negatives=false_negatives,
        )
        print(
            "You can manually remove the duplicates_to_validate.xlsx, "
            "non_duplicates_to_validate.xlsx, and dupes.txt files."
        )
        return

    if view:
        _view_dedupe_details(dedupe_operation)
        return

    dedupe_operation.main(debug=debug)


@main.command(help_priority=9)
@click.option(
    "-a",
    "--add",
    type=click.Choice(TYPE_IDENTIFIER_ENDPOINT_DICT[EndpointType.prescreen]),
    help="""Prescreen package to be added.""",
)
@click.option(
    "-p",
    "--params",
    type=str,
    help="Parameters",
)
@click.option(
    "--include_all",
    is_flag=True,
    default=False,
    help="Include all records in prescreen",
)
@click.option(
    "--include_all_always",
    is_flag=True,
    default=False,
    help="Include all records in this and future prescreens",
)
@click.option(
    "--export_format",
    type=click.Choice(["CSV", "XLSX"], case_sensitive=False),
    help="Export table with the screening decisions",
)
@click.option(
    "--import_table",
    type=click.Path(exists=True),
    help="Import file with the screening decisions (csv/xlsx supported)",
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
    "-i",
    "--include",
    help="Prescreen include records based on IDs (ID1,ID2,...).",
    required=False,
)
@click.option(
    "-e",
    "--exclude",
    help="Prescreen exclude records based on IDs (ID1,ID2,...).",
    required=False,
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom prescreen script.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def prescreen(
    ctx: click.core.Context,
    add: str,
    params: str,
    include_all: bool,
    include_all_always: bool,
    export_format: str,
    import_table: str,
    create_split: int,
    split: str,
    include: str,
    exclude: str,
    setup_custom_script: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Pre-screen exclusion based on metadata (titles and abstracts)

    Docs: https://colrev.readthedocs.io/en/latest/manual/metadata_prescreen/prescreen.html
    """

    # pylint: disable=too-many-locals

    review_manager = get_review_manager(
        ctx, {"verbose_mode": verbose, "force_mode": force, "exact_call": EXACT_CALL}
    )
    prescreen_operation = review_manager.get_prescreen_operation()

    if export_format:
        prescreen_operation.export_table(export_table_format=export_format)

    elif import_table:
        prescreen_operation.import_table(import_table_path=import_table)

    elif include_all or include_all_always:
        prescreen_operation.include_all_in_prescreen(persist=include_all_always)

    elif create_split:
        splits = prescreen_operation.create_prescreen_split(create_split=create_split)
        for created_split in splits:
            print(created_split + "\n")

    elif include:
        prescreen_operation.include_records(ids=include)

    elif exclude:
        prescreen_operation.exclude_records(ids=exclude)

    elif setup_custom_script:
        prescreen_operation.setup_custom_script()
        print("Activated custom_prescreen_script.py.")
    elif add:

        colrev.ui_cli.add_package_to_settings.add_package_to_settings(
            PACKAGE_MANAGER,
            operation=prescreen_operation,
            package_identifier=add,
            params=params,
        )
    else:
        review_manager.logger.info("Prescreen")
        review_manager.logger.info(
            "Exclude irrelevant records based on metadata (i.e., titles and abstracts)."
        )
        review_manager.logger.info("Remaining records are retained provisionally")
        review_manager.logger.info(
            "In the screen, they can be included or excluded based on full-text documents."
        )
        review_manager.logger.info(
            "See https://colrev.readthedocs.io/en/"
            "latest/manual/metadata_prescreen/prescreen.html"
        )

        prescreen_operation.main(split_str=split)


@main.command(help_priority=10)
@click.option(
    "-a",
    "--add",
    type=click.Choice(TYPE_IDENTIFIER_ENDPOINT_DICT[EndpointType.screen]),
    help="""Screen package to be added.""",
)
@click.option(
    "-p",
    "--params",
    type=str,
    help="Parameters",
)
@click.option(
    "--include_all",
    is_flag=True,
    default=False,
    help="Include all records in the screen",
)
@click.option(
    "--include_all_always",
    is_flag=True,
    default=False,
    help="Include all records in this and future screens",
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
    help="Split the screen between n researchers "
    + "(each researcher screens the same number of papers without overlaps)",
)
@click.option(
    "--split",
    type=str,
    default="",
    help="Screen a split sample",
)
@click.option(
    "-abstracts",
    "--add_abstracts_from_tei",
    is_flag=True,
    default=False,
    help="Add abstracts from TEI files",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom screen script.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def screen(
    ctx: click.core.Context,
    add: str,
    params: str,
    include_all: bool,
    include_all_always: bool,
    add_criterion: str,
    delete_criterion: str,
    create_split: int,
    split: str,
    add_abstracts_from_tei: bool,
    setup_custom_script: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Screen based on PDFs and inclusion/exclusion criteria

    Docs: https://colrev.readthedocs.io/en/latest/manual/pdf_screen/screen.html
    """

    review_manager = get_review_manager(
        ctx, {"verbose_mode": verbose, "force_mode": force, "exact_call": EXACT_CALL}
    )
    screen_operation = review_manager.get_screen_operation()

    if add_abstracts_from_tei:
        screen_operation.add_abstracts_from_tei()

    if add:

        colrev.ui_cli.add_package_to_settings.add_package_to_settings(
            PACKAGE_MANAGER,
            operation=screen_operation,
            package_identifier=add,
            params=params,
        )
        return

    if include_all or include_all_always:
        screen_operation.include_all_in_screen(persist=include_all_always)
        return
    if add_criterion:
        assert add_criterion.count(",") == 2
        (
            criterion_name,
            criterion_type_str,
            criterion_explanation,
        ) = add_criterion.split(",")
        criterion_type = ScreenCriterionType[criterion_type_str]
        criterion = colrev.settings.ScreenCriterion(
            explanation=criterion_explanation,
            criterion_type=criterion_type,
            comment="",
        )
        screen_operation.add_criterion(
            criterion_name=criterion_name, criterion=criterion
        )
        return
    if delete_criterion:
        screen_operation.delete_criterion(delete_criterion)
        return
    if create_split:
        splits = screen_operation.create_screen_split(create_split=create_split)
        for created_split in splits:
            print(created_split + "\n")
        return
    if setup_custom_script:
        screen_operation.setup_custom_script()
        print("Activated custom_screen_script.py.")
        return

    screen_operation.main(split_str=split)


def _extract_coverpage(*, cover: Path) -> None:
    # pylint: disable=import-outside-toplevel
    import colrev.record.record_pdf

    cp_path = Path.home().joinpath("colrev") / Path(".coverpages")
    cp_path.mkdir(exist_ok=True)

    assert Path(cover).suffix == ".pdf"
    record = colrev.record.record_pdf.PDFRecord({Fields.FILE: cover})
    record.extract_pages(
        pages=[0], project_path=Path(cover).parent, save_to_path=cp_path
    )


@main.command(help_priority=17)
@click.argument("path", nargs=1, type=click.Path(exists=True))
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def pdf(
    ctx: click.core.Context,
    path: str,
) -> None:
    """Process a PDF"""

    ret = ""
    while ret in ["c", "h", ""]:
        ret = input("Option (c: remove cover page, h: show hashes, q: quit)")
        if ret == "c":
            _extract_coverpage(cover=Path(path))
        elif ret == "h":
            _print_pdf_hashes(pdf_path=Path(path))
        # elif ret == "o":
        #     print("TODO : ocr")
        # elif ret == "r":
        #     print("TODO: remove comments")
        # elif ret == "m":
        #     print("TODO : extract metadata")
        # elif ret == "t":
        #     print("TODO : create tei")
        # elif ret == "i":
        #     print("TODO: print infos (website / retracted /...)")


@main.command(help_priority=11)
@click.option(
    "--discard",
    is_flag=True,
    default=False,
    help="Discard all missing PDFs as not_available",
)
@click.option(
    "-d",
    "--dir",
    is_flag=True,
    default=False,
    help="Open the PDFs directory",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def pdfs(
    ctx: click.core.Context,
    discard: bool,
    dir: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Retrieve and prepare PDFs"""

    review_manager = get_review_manager(
        ctx,
        {
            "verbose_mode": verbose,
            "force_mode": force,
            "exact_call": EXACT_CALL,
            "high_level_operation": True,
        },
    )

    if dir:
        # pylint: disable=consider-using-with
        # pylint: disable=no-member

        path = review_manager.path / Path("data/pdfs")
        webbrowser.open(str(path))
        return

    if discard:
        pdf_prep_man_operation = review_manager.get_pdf_prep_man_operation()
        pdf_prep_man_operation.discard()

        pdf_get_man_operation = review_manager.get_pdf_get_man_operation()
        pdf_get_man_operation.discard()

        return

    review_manager.logger.info("PDFs")
    review_manager.logger.info(
        "PDFs is a high-level operation consisting of pdf-get and pdf-prep:"
    )
    print()

    pdf_get_operation = review_manager.get_pdf_get_operation(
        notify_state_transition_operation=True
    )
    pdf_get_operation.main()


@main.command(help_priority=12)
@click.option(
    "-a",
    "--add",
    type=click.Choice(TYPE_IDENTIFIER_ENDPOINT_DICT[EndpointType.pdf_get]),
    help="""PDF-get package to be added.""",
)
@click.option(
    "-p",
    "--params",
    type=str,
    help="Parameters",
)
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
    "--relink_pdfs",
    is_flag=True,
    default=False,
    help="Recreate links to PDFs based on colrev pdf-IDs (when PDFs were renamed)",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom pdf-get script.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def pdf_get(
    ctx: click.core.Context,
    add: str,
    params: str,
    copy_to_repo: bool,
    rename: bool,
    relink_pdfs: bool,
    setup_custom_script: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Get PDFs

    Docs: https://colrev.readthedocs.io/en/latest/manual/pdf_retrieval/pdf_get.html
    """

    review_manager = get_review_manager(
        ctx,
        {
            "verbose_mode": verbose,
            "force_mode": force,
            "exact_call": EXACT_CALL,
        },
    )

    state_transition_operation = not relink_pdfs and not setup_custom_script
    pdf_get_operation = review_manager.get_pdf_get_operation(
        notify_state_transition_operation=state_transition_operation
    )

    if add:

        colrev.ui_cli.add_package_to_settings.add_package_to_settings(
            PACKAGE_MANAGER,
            operation=pdf_get_operation,
            package_identifier=add,
            params=params,
        )
        return
    if relink_pdfs:
        pdf_get_operation.relink_pdfs()
        return
    if copy_to_repo:
        pdf_get_operation.copy_pdfs_to_repo()
        return
    if rename:
        pdf_get_operation.rename_pdfs()
        return
    if setup_custom_script:
        pdf_get_operation.setup_custom_script()
        print("Activated custom_pdf_get_script.py.")
        return

    pdf_get_operation.main()


@main.command(help_priority=13)
@click.option(
    "-a",
    "--add",
    type=click.Choice(TYPE_IDENTIFIER_ENDPOINT_DICT[EndpointType.pdf_get_man]),
    help="""PDF-get-man package to be added.""",
)
@click.option(
    "-p",
    "--params",
    type=str,
    help="Parameters",
)
@click.option(
    "-e",
    "--export",
    is_flag=True,
    default=False,
    help="Export a table.",
)
@click.option(
    "--discard",
    is_flag=True,
    default=False,
    help="Discard all missing PDFs as not_available",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def pdf_get_man(
    ctx: click.core.Context,
    add: str,
    params: str,
    export: bool,
    discard: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Get PDFs manually

    Docs: https://colrev.readthedocs.io/en/latest/manual/pdf_retrieval/pdf_get.html
    """

    review_manager = get_review_manager(
        ctx,
        {
            "verbose_mode": verbose,
            "force_mode": force,
            "exact_call": EXACT_CALL,
        },
    )
    pdf_get_man_operation = review_manager.get_pdf_get_man_operation()

    if add:

        colrev.ui_cli.add_package_to_settings.add_package_to_settings(
            PACKAGE_MANAGER,
            operation=pdf_get_man_operation,
            package_identifier=add,
            params=params,
        )
        return

    if export:
        records = pdf_get_man_operation.review_manager.dataset.load_records_dict()
        pdf_get_man_records = [
            r
            for r in records.values()
            if r[Fields.STATUS]
            in [
                RecordState.pdf_needs_manual_retrieval,
                RecordState.rev_prescreen_included,
            ]
        ]
        pdf_get_man_records_df = pd.DataFrame.from_records(pdf_get_man_records)
        pdf_get_man_records_df = pdf_get_man_records_df[
            pdf_get_man_records_df.columns.intersection(
                [
                    Fields.ID,
                    Fields.AUTHOR,
                    Fields.YEAR,
                    Fields.TITLE,
                    Fields.JOURNAL,
                    Fields.BOOKTITLE,
                    Fields.VOLUME,
                    Fields.NUMBER,
                    Fields.URL,
                    Fields.DOI,
                ]
            )
        ]
        pdf_get_man_records_df.to_csv("pdf_get_man_records.csv", index=False)
        pdf_get_man_operation.review_manager.logger.info(
            "Created pdf_get_man_records.csv"
        )
        return
    if discard:
        pdf_get_man_operation.discard()
        return

    pdf_get_man_operation.main()


def _print_pdf_hashes(*, pdf_path: Path) -> None:

    import colrev.record.record_pdf
    import pymupdf

    doc = pymupdf.Document(pdf_path)
    last_page_nr = doc.page_count

    assert Path(pdf_path).suffix == ".pdf"
    record = colrev.record.record_pdf.PDFRecord({"file": pdf_path})
    first_page_average_hash_16 = record.get_pdf_hash(page_nr=1, hash_size=16)
    print(f"first page: {first_page_average_hash_16}")
    first_page_average_hash_32 = record.get_pdf_hash(page_nr=1, hash_size=32)
    print(f"first page: {first_page_average_hash_32}")

    last_page_average_hash_16 = record.get_pdf_hash(page_nr=last_page_nr, hash_size=16)
    print(f"last page: {last_page_average_hash_16}")
    last_page_average_hash_32 = record.get_pdf_hash(page_nr=last_page_nr, hash_size=32)
    print(f"last page: {last_page_average_hash_32}")


@main.command(help_priority=14)
@click.option(
    "-a",
    "--add",
    type=click.Choice(TYPE_IDENTIFIER_ENDPOINT_DICT[EndpointType.pdf_prep]),
    help="""PDF-prep package to be added.""",
)
@click.option(
    "-p",
    "--params",
    type=str,
    help="Parameters",
)
@click.option(
    "--update_colrev_pdf_ids", is_flag=True, default=False, help="Update colrev_pdf_ids"
)
@click.option(
    "-b",
    "--batch_size",
    required=False,
    type=int,
    default=0,
    help="Batch size (when not all records should be processed in one batch).",
)
@click.option(
    "--reprocess",
    is_flag=True,
    default=False,
    help="Prepare all PDFs again (pdf_needs_manual_preparation).",
)
@click.option(
    "--tei",
    is_flag=True,
    default=False,
    help="Generate TEI documents.",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom pdf-prep script.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def pdf_prep(
    ctx: click.core.Context,
    add: str,
    params: str,
    batch_size: int,
    update_colrev_pdf_ids: bool,
    reprocess: bool,
    setup_custom_script: bool,
    tei: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Prepare PDFs

    Docs: https://colrev.readthedocs.io/en/latest/manual/pdf_retrieval/pdf_prep.html
    """

    # pylint: disable=import-outside-toplevel

    review_manager = get_review_manager(
        ctx,
        {
            "verbose_mode": verbose,
            "force_mode": force,
            "exact_call": EXACT_CALL,
        },
    )
    pdf_prep_operation = review_manager.get_pdf_prep_operation(reprocess=reprocess)

    if add:

        colrev.ui_cli.add_package_to_settings.add_package_to_settings(
            PACKAGE_MANAGER,
            operation=pdf_prep_operation,
            package_identifier=add,
            params=params,
        )
        return

    try:
        if update_colrev_pdf_ids:
            pdf_prep_operation.update_colrev_pdf_ids()

        elif setup_custom_script:
            pdf_prep_operation.setup_custom_script()
            print("Activated custom_pdf_prep_script.py.")
        elif tei:
            pdf_prep_operation.generate_tei()
        else:
            pdf_prep_operation.main(batch_size=batch_size)

    except KeyboardInterrupt:
        print("Stopped the process")


def _delete_first_pages_cli(
    pdf_prep_man_operation: colrev.ops.pdf_prep_man.PDFPrepMan, record_id: str
) -> None:
    records = pdf_prep_man_operation.review_manager.dataset.load_records_dict()
    while True:
        if record_id in records:
            record_dict = records[record_id]
            if Fields.FILE in record_dict:
                print(record_dict[Fields.FILE])
                pdf_path = pdf_prep_man_operation.review_manager.path / Path(
                    record_dict[Fields.FILE]
                )
                pdf_prep_man_operation.extract_coverpage(filepath=pdf_path)
                pdf_prep_man_operation.set_pdf_man_prepared(
                    colrev.record.record.Record(record_dict)
                )
            else:
                print("no file in record")
        if input("Extract coverpage from another PDF? (y/n)") == "n":
            break
        record_id = input("ID of next PDF for coverpage extraction:")


@main.command(help_priority=15)
@click.option(
    "-a",
    "--add",
    type=click.Choice(TYPE_IDENTIFIER_ENDPOINT_DICT[EndpointType.pdf_prep_man]),
    help="""PDF-prep-man package to be added.""",
)
@click.option(
    "-p",
    "--params",
    type=str,
    help="Parameters",
)
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
    "--discard",
    is_flag=True,
    default=False,
    help="Discard records whose PDF needs to be prepared manually",
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
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def pdf_prep_man(
    ctx: click.core.Context,
    add: str,
    params: str,
    delete_first_page: str,
    stats: bool,
    discard: bool,
    extract: bool,
    apply: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Prepare PDFs manually

    Docs: https://colrev.readthedocs.io/en/latest/manual/pdf_retrieval/pdf_prep.html
    """

    review_manager = get_review_manager(
        ctx,
        {
            "verbose_mode": verbose,
            "force_mode": force,
            "exact_call": EXACT_CALL,
        },
    )
    pdf_prep_man_operation = review_manager.get_pdf_prep_man_operation()

    if add:

        colrev.ui_cli.add_package_to_settings.add_package_to_settings(
            PACKAGE_MANAGER,
            operation=pdf_prep_man_operation,
            package_identifier=add,
            params=params,
        )
    if delete_first_page:
        _delete_first_pages_cli(pdf_prep_man_operation, delete_first_page)
        return
    if discard:
        pdf_prep_man_operation.discard()
        return
    if stats:
        pdf_prep_man_operation.pdf_prep_man_stats()
        return
    if extract:
        pdf_prep_man_operation.extract_needs_pdf_prep_man()
        return
    if apply:
        pdf_prep_man_operation.apply_pdf_prep_man()
        return

    pdf_prep_man_operation.main()


@main.command(help_priority=16)
@click.option(
    "-a",
    "--add",
    type=click.Choice(TYPE_IDENTIFIER_ENDPOINT_DICT[EndpointType.data]),
    help="Data package to be added.",
)
@click.option(
    "-p",
    "--params",
    type=str,
    help="Parameters",
)
@click.option(
    "--reading_heuristics",
    is_flag=True,
    default=False,
    help="Heuristics to prioritize reading efforts",
)
@click.option(
    "-scs",
    "--setup_custom_script",
    is_flag=True,
    default=False,
    help="Setup template for custom data script.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def data(
    ctx: click.core.Context,
    add: str,
    params: str,
    reading_heuristics: bool,
    setup_custom_script: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Complete selected forms of data analysis and synthesis

    Docs: https://colrev.readthedocs.io/en/latest/manual/data/data.html
    """

    review_manager = get_review_manager(
        ctx,
        {
            "verbose_mode": verbose,
            "force_mode": force,
            "exact_call": EXACT_CALL,
        },
    )
    data_operation = review_manager.get_data_operation()

    if reading_heuristics:
        heuristic_results = data_operation.reading_heuristics()
        review_manager.p_printer.pprint(heuristic_results)
        return
    if setup_custom_script:
        data_operation.setup_custom_script()
        print("Activated custom_data_script.py.")
        print(
            f"Please update the data_format in {review_manager.paths.SETTINGS_FILE} and commit."
        )
        return

    if add:

        colrev.ui_cli.add_package_to_settings.add_package_to_settings(
            PACKAGE_MANAGER,
            operation=data_operation,
            package_identifier=add,
            params=params,
        )
        return

    ret = data_operation.main()
    if data_operation.review_manager.in_ci_environment():
        if ret["ask_to_commit"]:
            review_manager.dataset.create_commit(
                msg="Data and synthesis", manual_author=True
            )
    else:
        if ret["ask_to_commit"]:
            if input("Create commit (y/n)?") == "y":
                review_manager.dataset.create_commit(
                    msg="Data and synthesis", manual_author=True
                )
        if ret["no_endpoints_registered"]:
            print(
                "No data format not specified. "
                "To register a data endpoint, "
                "use one (or several) of the following \n"
                "    colrev data --add colrev.paper_md\n"
                "    colrev data --add colrev.structured\n"
                "    colrev data --add colrev.bibliography_export\n"
                "    colrev data --add colrev.prisma\n"
                "    colrev data --add colrev.github_pages\n"
                "    colrev data --add colrev.zettlr\n"
                "    colrev data --add colrev.colrev_curation"
            )


@main.command(help_priority=17)
@click.argument("scope", nargs=1)
@click.option(
    "--filter",
    type=click.Choice(["prepare", "dedupe", "merge", "all"], case_sensitive=False),
    default="all",
    help="prepare, merge, or all.",
)
@click.option(
    "--threshold",
    type=float,
    default=0.05,
    help="Change score threshold for changes to display.",
)
@click.option(
    "--properties",
    is_flag=True,
    default=False,
    help="Flag indicating whether to validate the review properties.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def validate(
    ctx: click.core.Context,
    scope: str,
    filter: str,
    threshold: float,
    properties: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Validate changes in the given commit (scope)

    \b
    The validation scope argument can be
    - A commit-sha,
    - '.' for the latest commit,
    - HEAD~4 for commit 4 before HEAD
    - A contributor name
    """

    review_manager = get_review_manager(
        ctx,
        {
            "verbose_mode": verbose,
            "force_mode": force,
            "exact_call": EXACT_CALL,
        },
    )
    validate_operation = review_manager.get_validate_operation()

    validation_details = validate_operation.main(
        scope=scope,
        filter_setting=filter,
        properties=properties,
    )

    if validation_details:
        colrev.ui_cli.cli_validation.validate(
            validate_operation=validate_operation,
            validation_details=validation_details,
            threshold=threshold,
        )

    review_manager.logger.info("%sCompleted validation%s", Colors.GREEN, Colors.END)


@main.command(help_priority=18)
@click.option(
    "--id",  # pylint: disable=invalid-name
    help="Record ID to trace (citation_key).",
    required=True,
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def trace(
    ctx: click.core.Context,
    id: str,  # pylint: disable=invalid-name
) -> None:
    """Trace a record"""

    review_manager = get_review_manager(
        ctx,
        {
            "verbose_mode": False,
            "force_mode": False,
            "exact_call": EXACT_CALL,
        },
    )
    trace_operation = review_manager.get_trace_operation()
    trace_operation.main(record_id=id)


def _select_target_repository(environment_registry: list) -> Path:
    while True:
        for i, local_source in enumerate(environment_registry):
            print(
                f"{i+1} - {local_source['repo_name']} ({local_source['repo_source_path']})"
            )
        sel_str = input("Select target repository: ")
        sel = int(sel_str) - 1
        if sel in range(0, len(environment_registry)):
            target = Path(environment_registry[sel]["repo_source_path"])
            return target


@main.command(help_priority=19)
@click.option(
    "-p",
    "--path",
    type=click.Path(exists=True),
    help="Path to file(s)",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def distribute(ctx: click.core.Context, path: Path, verbose: bool, force: bool) -> None:
    """Distribute records to other local repositories"""

    if not path:
        path = Path.cwd()
    review_manager = get_review_manager(
        ctx,
        {
            "verbose_mode": verbose,
            "force_mode": force,
        },
    )
    distribute_operation = review_manager.get_distribute_operation()
    environment_registry = distribute_operation.get_environment_registry()

    target = _select_target_repository(environment_registry=environment_registry)
    # Note : add a "distribution mode" option?
    # (whole file -> add as source/load vs. records individually like a prescreen)
    distribute_operation.main(path=path, target=target)


def _print_environment_status(
    review_manager: colrev.review_manager.ReviewManager,
) -> None:
    environment_manager = review_manager.get_environment_manager()
    environment_details = environment_manager.get_environment_details()

    print("\nCoLRev environment status\n")
    print("Index\n")
    if environment_details["index"]["status"] == "up":
        print(f" - Status: {Colors.GREEN}up{Colors.END}")
        print(f' - Path          : {environment_details["index"]["path"]}')
        print(f' - Size          : {environment_details["index"]["size"]} records')
        print(f' - Last modified : {environment_details["index"]["last_modified"]}')
    else:
        print(f" - Status: {Colors.RED}down{Colors.END}")

    print("\nCoLRev projects\n")
    project_repos = [
        x
        for x in environment_details["local_repos"]["repos"]
        if "curated_metadata" not in x["repo_source_path"]
    ]
    for colrev_repo in sorted(project_repos, key=lambda d: d["repo_name"]):
        repo_stats = f' {colrev_repo["repo_name"]}'
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
        print(f'    - Path     : {colrev_repo["repo_source_path"]}')

    print("\nCurated CoLRev resources\n")
    curated_repos = [
        x
        for x in environment_details["local_repos"]["repos"]
        if "curated_metadata" in x["repo_source_path"]
    ]
    for colrev_repo in sorted(curated_repos, key=lambda d: d["repo_name"]):
        repo_stats = (
            f' - {colrev_repo["repo_name"].ljust(60, " ")}: '
            f'{str(colrev_repo["size"]).rjust(10, " ")} records'
        )
        if colrev_repo["behind_remote"]:
            repo_stats += " (behind remote)"
        print(repo_stats)

    print("\n")
    if len(environment_details["local_repos"]["broken_links"]) > 0:
        print("Broken links: \n")
        for broken_link in environment_details["local_repos"]["broken_links"]:
            print(f'- {broken_link["repo_source_path"]}')


@main.command(help_priority=20)
@click.option(
    "-i", "--index", is_flag=True, default=False, help="Create the LocalIndex"
)
@click.option(
    "--install",
    help="Install a new resource providing its url "
    + "(e.g., a curated metadata repository)",
)
@click.option("--pull", is_flag=True, default=False, help="Pull curated metadata")
@click.option(
    "-s", "--status", is_flag=True, default=False, help="Print environment status"
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
@click.option(
    "--update_package_list",
    is_flag=True,
    default=False,
    help="Update the package list (packages).",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.pass_context
def env(
    ctx: click.core.Context,
    index: bool,
    install: str,
    pull: bool,
    status: bool,
    register: bool,
    unregister: bool,
    update_package_list: bool,
    verbose: bool,
) -> None:
    """Manage the environment"""

    # pylint: disable=too-many-branches

    if update_package_list:
        if "y" != input(
            "The following process instantiates objects listed in the "
            + "packages/packages.json "
            + "(including ones that may not be secure).\n"
            + "Please confirm (y) to proceed."
        ):
            return

        PACKAGE_MANAGER.update_package_list()
        return

    if index:
        print("Index rankings")
        local_index_builder = colrev.env.local_index_builder.LocalIndexBuilder(
            verbose_mode=verbose
        )
        local_index_builder.index()
        local_index_builder.index_journal_rankings()
        return

    # The following options may need a review_manager

    review_manager = get_review_manager(
        ctx,
        {
            "verbose_mode": verbose,
            "force_mode": True,
        },
    )

    if install:
        env_resources = review_manager.get_resources()
        if env_resources.install_curated_resource(curated_resource=install):
            print("Successfully installed curated resource.")
            print("To make it available to other projects, run")
            print("colrev env --index")
        return

    if pull:
        environment_manager = review_manager.get_environment_manager()
        for curated_resource in environment_manager.local_repos():
            try:
                curated_resource_path = curated_resource["repo_source_path"]
                if "/curated_metadata/" not in curated_resource_path:
                    continue

                review_manager = get_review_manager(
                    ctx,
                    {
                        "verbose_mode": verbose,
                        "force_mode": False,
                        "path_str": curated_resource_path,
                    },
                )

                review_manager.dataset.pull_if_repo_clean()
                print(f"Pulled {curated_resource_path}")
            except GitCommandError as exc:
                print(exc)
        return

    if status:
        _print_environment_status(review_manager)
        return

    if register:
        environment_manager = review_manager.get_environment_manager()
        environment_manager.register_repo(Path.cwd())
        return

    if unregister is not None:
        environment_manager = review_manager.get_environment_manager()

        local_repos = environment_manager.local_repos()
        if str(unregister) not in [x["source_url"] for x in local_repos]:
            print("Not in local registry (cannot remove): %s", unregister)
        else:
            updated_local_repos = [
                x for x in local_repos if x["source_url"] != str(unregister)
            ]
            environment_manager.environment_registry["local_index"][
                "repos"
            ] = updated_local_repos
            environment_manager.save_environment_registry(
                environment_manager.environment_registry
            )
            logging.info("Removed from local registry: %s", unregister)
        return


@main.command(help_priority=21)
# @click.option("-v", "--view", is_flag=True, default=False)
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
@click.option(
    "-g",
    "--update-global",
    help="Global settings to update",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
def settings(
    ctx: click.core.Context,
    update_hooks: bool,
    modify: str,
    update_global: str,
    verbose: bool,
    force: bool,
) -> None:
    """Settings of the CoLRev project"""

    # pylint: disable=reimported

    from subprocess import check_call  # nosec
    from subprocess import DEVNULL  # nosec
    from subprocess import STDOUT  # nosec
    import json
    import ast
    import glom

    review_manager = get_review_manager(
        ctx,
        {"verbose_mode": verbose, "force_mode": force},
    )
    if update_hooks:
        print("Update pre-commit hooks")

        if review_manager.dataset.has_record_changes():
            print("Clean repo required. Commit or stash changes.")
            return

        scripts_to_call = [
            [
                "pre-commit",
                "autoupdate",
                "--repo",
                "https://github.com/CoLRev-Environment/colrev-hooks",
            ],
        ]
        for script_to_call in scripts_to_call:
            check_call(script_to_call, stdout=DEVNULL, stderr=STDOUT)  # nosec

        review_manager.dataset.add_changes(review_manager.paths.PRE_COMMIT_CONFIG)
        review_manager.dataset.create_commit(msg="Update pre-commit hooks")
        print("Successfully updated pre-commit hooks")
        return

    if update_global:
        from colrev.env.environment_manager import EnvironmentManager

        env_man = EnvironmentManager()
        path, value_string = update_global.split("=")
        print(f"Updating registry settings:\n{path} = {value_string}")
        env_man.update_registry(path, value_string)
    if modify:
        # TBD: maybe use glom.delete?
        # There is no simply append...
        # (we could replace the (last) position element with
        # keywords like prescreen.sripts.LAST_POSITION)
        # maybe prescreen.scripts.1.REPLACE/ADD/DELETE = ....
        # modify = 'dedupe.dedupe_package_endpoints='
        # '[{"endpoint":"colrev.simple_dedupe"}]'

        path, value_string = modify.split("=")
        value = ast.literal_eval(value_string)
        review_manager.logger.info("Change settings.%s to %s", path, value)

        with open(review_manager.paths.settings, encoding="utf-8") as file:
            project_settings = json.load(file)

        glom.assign(project_settings, path, value)

        with open(review_manager.paths.settings, "w", encoding="utf-8") as outfile:
            json.dump(project_settings, outfile, indent=4)

        review_manager.dataset.add_changes(review_manager.paths.SETTINGS_FILE)
        review_manager.dataset.create_commit(msg="Change settings", manual_author=True)

    # import colrev_ui.ui_web.settings_editor

    # review_manager = colrev.review_manager.ReviewManager(
    #     force_mode=True, verbose_mode=verbose
    # )
    # settings_operation = colrev.packages.ui_web.src.settings_editor.SettingsEditor(
    #     review_manager=review_manager
    # )
    # settings_operation.open_settings_editor()


@main.command(help_priority=23)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def pull(
    ctx: click.core.Context,
    verbose: bool,
    force: bool,
) -> None:
    """Pull CoLRev project remote and record updates"""

    review_manager = get_review_manager(
        ctx,
        {"verbose_mode": verbose, "force_mode": force},
    )
    pull_operation = review_manager.get_pull_operation()

    pull_operation.main()


@main.command(help_priority=24)
@click.argument("git_url")
@click.pass_context
def clone(
    ctx: click.core.Context,
    git_url: str,
) -> None:
    """Create local clone from shared CoLRev repository with git_url"""

    import colrev.ops.clone

    clone_operation = colrev.ops.clone.Clone(git_url=git_url)
    clone_operation.clone_git_repo()


@main.command(help_priority=25)
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
@click.option(
    "-a",
    "--all",
    is_flag=True,
    default=False,
    help="Push record changes/corrections to all sources (not just curations).",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
@catch_exception(handle=(colrev_exceptions.CoLRevException))
def push(
    ctx: click.core.Context,
    records_only: bool,
    project_only: bool,
    all: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Push CoLRev project remote and record updates"""

    review_manager = get_review_manager(
        ctx,
        {"verbose_mode": verbose, "force_mode": force},
    )
    push_operation = review_manager.get_push_operation()

    push_operation.main(
        records_only=records_only, project_only=project_only, all_records=all
    )


def _validate_show(ctx: click.core.Context, param: str, value: str) -> None:
    if value not in ["sample", "settings", "venv"]:
        raise click.BadParameter("Invalid argument")


@main.command(help_priority=26)
@click.argument("keyword")
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
def show(  # type: ignore
    ctx: click.core.Context,
    keyword: str,
    verbose: bool,
    force: bool,
    callback=_validate_show,
) -> None:
    """Show aspects (sample, ...)"""

    import colrev.process.operation
    import colrev.ui_cli.show_printer

    if keyword == "venv":
        colrev.ui_cli.show_printer.print_venv_notes()
        return

    review_manager = get_review_manager(
        ctx,
        {"verbose_mode": verbose, "force_mode": force},
    )

    if keyword == "sample":
        colrev.ui_cli.show_printer.print_sample(review_manager=review_manager)

    elif keyword == "settings":
        print(f"Settings:\n{review_manager.settings}")

    elif keyword == "cmd_history":
        cmds = []
        colrev.ops.check.CheckOperation(review_manager)
        revlist = review_manager.dataset.get_repo().iter_commits()

        for commit in reversed(list(revlist)):
            try:
                cmsg = str(commit.message)
                formatted_date = time.strftime(
                    "%Y-%m-%d %H:%M",
                    time.gmtime(commit.committed_date),
                )
                if not all(x in cmsg for x in ["Command", "Status"]):
                    # pylint: disable=colrev-missed-constant-usage
                    cmsg = "UNKNOWN"
                # min(cmsg.find("Status"), cmsg.find("On commit"))
                if "On commit" in cmsg:
                    cmsg = cmsg[: cmsg.find("On commit")]
                if "Status" in cmsg:
                    cmsg = cmsg[: cmsg.find("Status")]
                commit_message_first_line = (
                    cmsg[cmsg.find("Command") + 8 :]
                    .lstrip()
                    .rstrip()
                    .replace("\n", " ")
                )
                if len(commit_message_first_line) > 800:
                    # pylint: disable=colrev-missed-constant-usage
                    cmsg = "UNKNOWN"
                cmds.append(
                    {
                        "date": formatted_date,
                        "committer": commit.committer.name,
                        "commit_id": commit.hexsha,
                        "cmd": commit_message_first_line,
                    }
                )
            except KeyError:
                continue
        for cmd in cmds:
            print(
                f"{cmd['date']} ({cmd['committer']}, {cmd['commit_id']}):    "
                f"{Colors.ORANGE}{cmd['cmd']}{Colors.END}"
            )


# @main.command(help_priority=28)
# @click.option(
#     "-v",
#     "--verbose",
#     is_flag=True,
#     default=False,
#     help="Verbose: printing more infos",
# )
# @click.option(
#     "-f",
#     "--force",
#     is_flag=True,
#     default=False,
#     help="Force mode",
# )
# @click.pass_context
# def web(
#     ctx: click.core.Context,
#     verbose: bool,
#     force: bool,
# ) -> None:
#     """CoLRev web interface."""

#
#     import colrev.packages.ui_web.src.settings_editor

#     review_manager = colrev.review_manager.ReviewManager(
#         force_mode=force, verbose_mode=verbose
#     )
#     se_instance = colrev.packages.ui_web.src.settings_editor.SettingsEditor(
#         review_manager=review_manager
#     )
#     se_instance.open_settings_editor()


@main.command(hidden=True, help_priority=27)
@click.option(
    "--disable_auto",
    is_flag=True,
    default=False,
    help="Disable automated upgrades",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
def upgrade(
    ctx: click.core.Context,
    disable_auto: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Upgrade to the latest CoLRev project version."""

    if disable_auto:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=True, verbose_mode=verbose, skip_upgrade=True
        )

        review_manager.settings.project.auto_upgrade = False
        review_manager.save_settings()
        review_manager.dataset.create_commit(msg="Disable auto-upgrade")
        return
    review_manager = colrev.review_manager.ReviewManager(
        force_mode=True, verbose_mode=verbose
    )
    upgrade_operation = review_manager.get_upgrade()
    upgrade_operation.main()


@main.command(hidden=True, help_priority=28)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
def repare(
    ctx: click.core.Context,
    verbose: bool,
    force: bool,
) -> None:
    """Repare file formatting errors in the CoLRev project."""

    review_manager = get_review_manager(
        ctx,
        {"verbose_mode": verbose, "force_mode": force},
    )
    repare_operation = review_manager.get_repare()
    repare_operation.main()


@main.command(help_priority=29)
@click.option(
    "--ids",
    help="Remove records and their origins from the repository (ID1,ID2,...).",
    required=False,
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
def remove(
    ctx: click.core.Context,
    ids: str,
    verbose: bool,
    force: bool,
) -> None:
    """Remove records, ... from CoLRev repositories"""

    review_manager = get_review_manager(
        ctx,
        {"verbose_mode": verbose, "force_mode": force},
    )

    remove_operation = review_manager.get_remove_operation()

    if ids:
        remove_operation.remove_records(ids=ids)


@main.command(hidden=True, help_priority=30)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
def docs(
    ctx: click.core.Context,
    verbose: bool,
    force: bool,
) -> None:
    """Show the CoLRev documentation."""

    webbrowser.open("https://colrev.readthedocs.io/en/latest/")


@main.command(help_priority=31)
@click.option(
    "--branch",
    help="Branch to merge.",
    required=False,
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
def merge(
    ctx: click.core.Context,
    branch: str,
    verbose: bool,
    force: bool,
) -> None:
    """Merge git branches."""

    review_manager = get_review_manager(
        ctx,
        {"verbose_mode": verbose, "force_mode": force},
    )

    if not branch:
        colrev.ops.check.CheckOperation(review_manager)
        git_repo = review_manager.dataset.get_repo()
        print(f"possible branches: {','.join([b.name for b in git_repo.heads])}")
        return

    merge_operation = review_manager.get_merge_operation()
    merge_operation.main(branch=branch)


@main.command(help_priority=32)
@click.argument("selection")
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose: printing more infos",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
)
@click.pass_context
def undo(
    ctx: click.core.Context,
    selection: str,
    verbose: bool,
    force: bool,
) -> None:
    """Undo operations."""

    review_manager = get_review_manager(
        ctx,
        {"verbose_mode": verbose, "force_mode": force},
    )

    if selection == "commit":
        colrev.ops.check.CheckOperation(review_manager)
        git_repo = review_manager.dataset.get_repo()
        git_repo.git.reset("--hard", "HEAD~1")


@main.command(help_priority=33)
@click.pass_context
def version(
    ctx: click.core.Context,
) -> None:
    """Show colrev version."""

    from importlib.metadata import version

    print(f'colrev version {version("colrev")}')


@main.command(hidden=True)
@click.option(
    "-i", "--case-insensitive/--no-case-insensitive", help="Case insensitive completion"
)
@click.argument(
    "shell",
    required=False,
    type=click_completion.DocumentedChoice(click_completion.core.shells),
)
def show_click(shell, case_insensitive) -> None:  # type: ignore
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
def install_click(append, case_insensitive, shell, path) -> None:  # type: ignore
    """Install the click-completion-command completion"""
    extra_env = (
        {"_CLICK_COMPLETION_COMMAND_CASE_INSENSITIVE_COMPLETE": "ON"}
        if case_insensitive
        else {}
    )
    shell, path = click_completion.core.install(  # nosec
        shell=shell, path=path, append=append, extra_env=extra_env
    )
    click.echo(f"{shell} completion installed in {path}")
