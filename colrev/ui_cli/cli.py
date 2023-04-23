#! /usr/bin/env python3
"""Command-line interface for CoLRev."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
import typing
from pathlib import Path

import click
import click_completion.core
import pandas as pd

import colrev.exceptions as colrev_exceptions
import colrev.record
import colrev.review_manager
import colrev.ui_cli.cli_colors as colors
import colrev.ui_cli.cli_status_printer
import colrev.ui_cli.cli_validation

# pylint: disable=too-many-lines
# pylint: disable=redefined-builtin
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# Note: autocompletion needs bash/... activation:
# https://click.palletsprojects.com/en/7.x/bashcomplete/

EXACT_CALL = "colrev " + subprocess.list2cmdline(sys.argv[1:])


def __custom_startswith(string: str, incomplete: str) -> bool:
    """A custom completion matching that supports case insensitive matching"""
    if os.environ.get("_CLICK_COMPLETION_COMMAND_CASE_INSENSITIVE_COMPLETE"):
        string = string.lower()
        incomplete = incomplete.lower()
    return string.startswith(incomplete)


click_completion.core.startswith = __custom_startswith
click_completion.init()


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


@main.command(help_priority=1)
@click.option(
    "--type",
    type=str,
    default="literature_review",
    help="Review type (e.g., literature_review (default), scoping_review, theoretical_review)",
)
@click.option(
    "--light",
    is_flag=True,
    default=False,
    help="Setup a lightweight repository (not requiring Docker services)",
)
@click.option(
    "--example",
    is_flag=True,
    default=False,
    help="Add search results example",
)
@click.option(
    "-lpdf",
    "--local_pdf_collection",
    is_flag=True,
    default=False,
    help="Add a local PDF collection repository",
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
    help="Force mode: conduct full search again",
)
@click.pass_context
def init(
    ctx: click.core.Context,
    type: str,
    example: bool,
    light: bool,
    local_pdf_collection: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Initialize (define review objectives and type)"""
    # pylint: disable=import-outside-toplevel
    import colrev.ops.init

    try:
        colrev.review_manager.get_init_operation(
            review_type=type,
            example=example,
            light=light,
            local_pdf_collection=local_pdf_collection,
            exact_call=EXACT_CALL,
        )

    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


@main.command(help_priority=2)
@click.option(
    "-a",
    "--analytics",
    is_flag=True,
    default=False,
    help="Print analytics",
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
def status(
    ctx: click.core.Context,
    analytics: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Show status"""

    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
        )
        status_operation = review_manager.get_status_operation()

        if analytics:
            analytic_results = status_operation.get_analytics()
            for cid, data_item in reversed(analytic_results.items()):
                print(f"{cid} - {data_item}")
            return

        colrev.ui_cli.cli_status_printer.print_project_status(status_operation)

    except KeyboardInterrupt:
        print("Stopped...")
    except colrev_exceptions.RepoSetupError as exc:
        print(exc)
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

    try:
        review_manager = colrev.review_manager.ReviewManager(
            verbose_mode=verbose, force_mode=force, high_level_operation=True
        )

        if not any(review_manager.search_dir.iterdir()) and not any(
            review_manager.pdf_dir.iterdir()
        ):
            # Note : API-based searches automatically retrieve files
            # when they are added, i.e., the following message should
            # not be shown.
            print(
                "To retrieve search results,\n"
                " - copy files (*.bib, *.ris, *.xlsx, ...) "
                f"to the directory {review_manager.SEARCHDIR_RELATIVE} or\n"
                f" - copy PDF files to the directory {review_manager.PDF_DIR_RELATIVE} or \n"
                " - add an API-based search, as described in the documentation:\n"
                "https://colrev.readthedocs.io/en/latest/manual/metadata_retrieval/search.html"
            )
            return

        review_manager.logger.info("Retrieve")
        review_manager.logger.info(
            "Retrieve is a high-level operation consisting of search, load, prep, and dedupe:"
        )
        print()

        search_operation = review_manager.get_search_operation()
        search_operation.main(rerun=False)

        print()

        review_manager.exact_call = "colrev prep"
        load_operation = review_manager.get_load_operation()
        new_sources = load_operation.get_new_sources(skip_query=True)
        load_operation = review_manager.get_load_operation(hide_load_explanation=True)
        load_operation.main(
            new_sources=new_sources, keep_ids=False, combine_commits=False
        )

        print()
        review_manager.exact_call = "colrev prep"
        prep_operation = review_manager.get_prep_operation()
        prep_operation.main()

        print()

        review_manager.exact_call = "colrev dedupe"
        dedupe_operation = review_manager.get_dedupe_operation()
        dedupe_operation.main()

    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


@main.command(help_priority=4)
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
    "-r",
    "--rerun",
    is_flag=True,
    default=False,
    help="Rerun API-based searches, retrieving and updating all records "
    + "(not just the most recent ones)",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force mode",
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
def search(
    ctx: click.core.Context,
    add: str,
    view: bool,
    selected: str,
    rerun: bool,
    setup_custom_script: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Search for records"""

    # pylint: disable=import-outside-toplevel
    import colrev.ui_cli.add_packages

    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
        )
        search_operation = review_manager.get_search_operation()

        if add:
            colrev.ui_cli.add_packages.add_search_source(
                search_operation=search_operation,
                query=add,
            )

        elif view:
            search_operation.view_sources()

        elif setup_custom_script:
            search_operation.setup_custom_script()
            print("Activated custom_search_script.py.")
            print("Please update the source in settings.json and commit.")

        else:
            search_operation.main(selection_str=selected, rerun=rerun)

    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


@main.command(help_priority=5)
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
def load(
    ctx: click.core.Context,
    keep_ids: bool,
    combine_commits: bool,
    skip_query: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Load records"""

    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
        )
        # already start LocalIndex (for set_ids)
        load_operation = review_manager.get_load_operation()

        new_sources = load_operation.get_new_sources(skip_query=skip_query)

        if combine_commits:
            logging.info(
                "Combine mode: all search sources will be loaded in one commit"
            )

        # Note : reinitialize to load new scripts:
        load_operation = review_manager.get_load_operation(hide_load_explanation=True)

        load_operation.main(
            new_sources=new_sources, keep_ids=keep_ids, combine_commits=combine_commits
        )

    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


@main.command(help_priority=6)
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
    help="Reset IDs that have been changed (to fix the sort order in data/records.bib)",
)
@click.option(
    "-sid",
    "--set_ids",
    is_flag=True,
    default=False,
    help="Set IDs (regenerate)",
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
    "-df",
    "--debug_file",
    type=click.Path(exists=True),
    help="Debug the preparation step for a selected record (in a file).",
)
@click.option(
    "--skip",
    is_flag=True,
    default=False,
    help="Skip the preparation.",
    hidden=True,
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
def prep(
    ctx: click.core.Context,
    keep_ids: bool,
    polish: bool,
    reset_records: str,
    reset_ids: bool,
    set_ids: bool,
    debug: str,
    debug_file: Path,
    cpu: int,
    setup_custom_script: bool,
    skip: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Prepare records"""

    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals
    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
        )
        prep_operation = review_manager.get_prep_operation()

        if reset_records != "NA":
            try:
                reset_records = str(reset_records)
            except ValueError:
                pass
            prep_operation.reset_records(reset_ids=reset_records.split(","))
            return
        if reset_ids:
            prep_operation.reset_ids()
            return
        if set_ids:
            prep_operation.set_ids()
            return
        if debug or debug_file:
            prep_operation.main(
                keep_ids=keep_ids, debug_ids=debug, debug_file=debug_file
            )
            return
        if setup_custom_script:
            prep_operation.setup_custom_script()
            print("Activated custom_prep_script.py.")
            print(
                "Please check and adapt its position in the settings.json and commit."
            )
            return
        if skip:
            prep_operation.skip_prep()

        prep_operation.main(keep_ids=keep_ids, cpu=cpu, polish=polish)

    except colrev_exceptions.ServiceNotAvailableException as exc:
        print(exc)
        print("You can use the force mode to override")
        print("  colrev prep -f")
        return
    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


@main.command(help_priority=7)
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
def prep_man(
    ctx: click.core.Context, stats: bool, languages: bool, verbose: bool, force: bool
) -> None:
    """Prepare records manually"""

    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
        )
        prep_man_operation = review_manager.get_prep_man_operation()
        if languages:
            prep_man_operation.prep_man_langs()
            return

        if stats:
            prep_man_operation.prep_man_stats()
            return

        prep_man_operation.main()

    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


def __view_dedupe_details(dedupe_operation: colrev.ops.dedupe.Dedupe) -> None:
    info = dedupe_operation.get_info()

    if len(info["same_source_merges"]) > 0:
        print(f"\n\n{colors.RED}Same source merges to check:{colors.END}")
        print("\n- " + "\n- ".join(info["same_source_merges"]))


@main.command(help_priority=8)
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
@click.option("-v", "--view", is_flag=True, default=False, help="View dedupe info")
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
def dedupe(
    ctx: click.core.Context,
    merge: str,
    unmerge: str,
    fix_errors: bool,
    gid: bool,
    view: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Deduplicate records"""

    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
        )
        state_transition_operation = not view
        dedupe_operation = review_manager.get_dedupe_operation(
            notify_state_transition_operation=state_transition_operation
        )

        if merge:
            review_manager.settings.dedupe.same_source_merges = (
                colrev.settings.SameSourceMergePolicy.warn
            )
            dedupe_operation.merge_records(merge=merge)
            return

        if unmerge:
            dedupe_operation.unmerge_records(current_record_ids=unmerge.split(","))
            return
        if gid:
            dedupe_operation.merge_based_on_global_ids(apply=True)
            return
        if fix_errors:
            dedupe_operation.fix_errors()
            print(
                "You can manually remove the duplicates_to_validate.xlsx, "
                "non_duplicates_to_validate.xlsx, and dupes.txt files."
            )
            return

        if view:
            __view_dedupe_details(dedupe_operation)
            return

        dedupe_operation.main()

    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


@main.command(help_priority=9)
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
def prescreen(
    ctx: click.core.Context,
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
    """Pre-screen exclusion based on metadata (titles and abstracts)"""

    # pylint: disable=too-many-locals
    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
        )
        prescreen_operation = review_manager.get_prescreen_operation()

        if export_format:
            prescreen_operation.export_table(export_table_format=export_format)

        elif import_table:
            prescreen_operation.import_table(import_table_path=import_table)

        elif include_all or include_all_always:
            prescreen_operation.include_all_in_prescreen(persist=include_all_always)

        elif create_split:
            splits = prescreen_operation.create_prescreen_split(
                create_split=create_split
            )
            for created_split in splits:
                print(created_split + "\n")

        elif include:
            prescreen_operation.include_records(ids=include)

        elif exclude:
            prescreen_operation.exclude_records(ids=include)

        elif setup_custom_script:
            prescreen_operation.setup_custom_script()
            print("Activated custom_prescreen_script.py.")

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

    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


@main.command(help_priority=10)
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
def screen(
    ctx: click.core.Context,
    include_all: bool,
    include_all_always: bool,
    add_criterion: str,
    delete_criterion: str,
    create_split: int,
    split: str,
    setup_custom_script: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Screen based on PDFs and inclusion/exclusion criteria"""

    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
        )
        screen_operation = review_manager.get_screen_operation()

        if include_all or include_all_always:
            screen_operation.include_all_in_screen(persist=include_all_always)
            return
        if add_criterion:
            screen_operation.add_criterion(criterion_to_add=add_criterion)
            return
        if delete_criterion:
            screen_operation.delete_criterion(criterion_to_delete=delete_criterion)
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

    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


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
def pdfs(
    ctx: click.core.Context,
    discard: bool,
    dir: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Retrieve and prepare PDFs"""

    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force,
            verbose_mode=verbose,
            high_level_operation=True,
            exact_call=EXACT_CALL,
        )

        if dir:
            # pylint: disable=import-outside-toplevel
            # pylint: disable=consider-using-with
            # pylint: disable=no-member
            import platform

            path = review_manager.path / Path("data/pdfs")
            if platform.system() == "Windows":
                os.startfile(path)  # type: ignore
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
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

        print()

        pdf_prep_operation = review_manager.get_pdf_prep_operation()
        pdf_prep_operation.main(batch_size=0)

    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


@main.command(help_priority=12)
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
def pdf_get(
    ctx: click.core.Context,
    copy_to_repo: bool,
    rename: bool,
    relink_files: bool,
    setup_custom_script: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Get PDFs"""

    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
        )

        state_transition_operation = not relink_files and not setup_custom_script
        pdf_get_operation = review_manager.get_pdf_get_operation(
            notify_state_transition_operation=state_transition_operation
        )

        if relink_files:
            pdf_get_operation.relink_files()
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

    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


@main.command(help_priority=13)
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
def pdf_get_man(
    ctx: click.core.Context,
    export: bool,
    discard: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Get PDFs manually"""

    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
        )
        pdf_get_man_operation = review_manager.get_pdf_get_man_operation()

        if export:
            records = pdf_get_man_operation.review_manager.dataset.load_records_dict()
            pdf_get_man_records = [
                r
                for r in records.values()
                if r["colrev_status"]
                in [
                    colrev.record.RecordState.pdf_needs_manual_retrieval,
                    colrev.record.RecordState.rev_prescreen_included,
                ]
            ]
            pdf_get_man_records_df = pd.DataFrame.from_records(pdf_get_man_records)
            pdf_get_man_records_df = pdf_get_man_records_df[
                pdf_get_man_records_df.columns.intersection(
                    [
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

    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


def __extract_coverpage(*, cover: Path) -> None:
    cp_path = Path.home().joinpath("colrev") / Path(".coverpages")
    cp_path.mkdir(exist_ok=True)

    assert Path(cover).suffix == ".pdf"
    record = colrev.record.Record(data={"file": cover})
    record.extract_pages(
        pages=[0], project_path=Path(cover).parent, save_to_path=cp_path
    )


def __print_pdf_hashes(*, pdf_path: Path) -> None:
    # pylint: disable=import-outside-toplevel
    from PyPDF2 import PdfFileReader
    import colrev.qm.colrev_pdf_id

    try:
        pdf_reader = PdfFileReader(str(pdf_path), strict=False)
    except ValueError:
        print("Could not read PDF")
        return

    assert Path(pdf_path).suffix == ".pdf"

    first_page_average_hash_16 = colrev.qm.colrev_pdf_id.get_pdf_hash(
        pdf_path=Path(pdf_path),
        page_nr=1,
        hash_size=16,
    )
    print(f"first page: {first_page_average_hash_16}")
    first_page_average_hash_32 = colrev.qm.colrev_pdf_id.get_pdf_hash(
        pdf_path=Path(pdf_path),
        page_nr=1,
        hash_size=32,
    )
    print(f"first page: {first_page_average_hash_32}")

    last_page_nr = len(pdf_reader.pages)
    last_page_average_hash_16 = colrev.qm.colrev_pdf_id.get_pdf_hash(
        pdf_path=Path(pdf_path),
        page_nr=last_page_nr,
        hash_size=16,
    )
    print(f"last page: {last_page_average_hash_16}")
    last_page_average_hash_32 = colrev.qm.colrev_pdf_id.get_pdf_hash(
        pdf_path=Path(pdf_path),
        page_nr=last_page_nr,
        hash_size=32,
    )
    print(f"last page: {last_page_average_hash_32}")


@main.command(help_priority=14)
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
    "-c",
    "--cover",
    type=click.Path(exists=True),
    help="Remove cover page",
)
@click.option(
    "--pdf_hash",
    type=click.Path(exists=True),
    help="Get the PDF hash of a page",
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
def pdf_prep(
    ctx: click.core.Context,
    batch_size: int,
    update_colrev_pdf_ids: bool,
    reprocess: bool,
    pdf_hash: Path,
    setup_custom_script: bool,
    tei: bool,
    cover: Path,
    verbose: bool,
    force: bool,
) -> None:
    """Prepare PDFs"""

    if cover:
        __extract_coverpage(cover=cover)
        return

    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
        )
        pdf_prep_operation = review_manager.get_pdf_prep_operation(reprocess=reprocess)

        if pdf_hash:
            __print_pdf_hashes(pdf_path=pdf_hash)

        elif update_colrev_pdf_ids:
            pdf_prep_operation.update_colrev_pdf_ids()

        elif setup_custom_script:
            pdf_prep_operation.setup_custom_script()
            print("Activated custom_pdf_prep_script.py.")
        elif tei:
            pdf_prep_operation.generate_tei()
        else:
            pdf_prep_operation.main(batch_size=batch_size)

    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)
    except KeyboardInterrupt:
        print("Stopped the process")


def __delete_first_pages_cli(
    pdf_prep_man_operation: colrev.ops.pdf_prep_man.PDFPrepMan, record_id: str
) -> None:
    records = pdf_prep_man_operation.review_manager.dataset.load_records_dict()
    while True:
        if record_id in records:
            record_dict = records[record_id]
            if "file" in record_dict:
                print(record_dict["file"])
                pdf_path = pdf_prep_man_operation.review_manager.path / Path(
                    record_dict["file"]
                )
                pdf_prep_man_operation.extract_coverpage(filepath=pdf_path)
                pdf_prep_man_operation.set_pdf_man_prepared(
                    record=colrev.record.Record(data=record_dict)
                )
            else:
                print("no file in record")
        if input("Extract coverpage from another PDF? (y/n)") == "n":
            break
        record_id = input("ID of next PDF for coverpage extraction:")


@main.command(help_priority=15)
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
def pdf_prep_man(
    ctx: click.core.Context,
    delete_first_page: str,
    stats: bool,
    discard: bool,
    extract: bool,
    apply: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Prepare PDFs manually"""

    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
        )
        pdf_prep_man_operation = review_manager.get_pdf_prep_man_operation()

        if delete_first_page:
            __delete_first_pages_cli(pdf_prep_man_operation, delete_first_page)
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

    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


@main.command(help_priority=16)
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
    "--add",
    type=str,
    help="Add a data_format endpoint (e.g., colrev.structured)",
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
def data(
    ctx: click.core.Context,
    profile: bool,
    reading_heuristics: bool,
    add: str,
    setup_custom_script: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Complete selected forms of data analysis and synthesis"""

    # pylint: disable=import-outside-toplevel
    import colrev.ui_cli.add_packages

    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=(force or profile), verbose_mode=verbose, exact_call=EXACT_CALL
        )
        data_operation = review_manager.get_data_operation()

        if profile:
            data_operation.profile()
            return
        if reading_heuristics:
            heuristic_results = data_operation.reading_heuristics()
            review_manager.p_printer.pprint(heuristic_results)
            return
        if setup_custom_script:
            data_operation.setup_custom_script()
            print("Activated custom_data_script.py.")
            print("Please update the data_format in settings.json and commit.")
            return

        if add:
            colrev.ui_cli.add_packages.add_data(
                data_operation=data_operation,
                add=add,
            )
            return

        ret = data_operation.main()
        if data_operation.review_manager.in_ci_environment():
            if ret["ask_to_commit"]:
                review_manager.create_commit(
                    msg="Data and synthesis", manual_author=True
                )
        else:
            if ret["ask_to_commit"]:
                if input("Create commit (y/n)?") == "y":
                    review_manager.create_commit(
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

    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


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
    - a commit-sha,
    - a commit tree,
    - '.' for the latest commit,
    - HEAD~4 for commit 4 before HEAD
    - a contributor name
    """

    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
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

        review_manager.logger.info("%sCompleted validation%s", colors.GREEN, colors.END)

    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


@main.command(help_priority=18)
@click.option(
    "--id",  # pylint: disable=invalid-name
    help="Record ID to trace (citation_key).",
    required=True,
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
def trace(
    ctx: click.core.Context,
    id: str,  # pylint: disable=invalid-name
    verbose: bool,
    force: bool,
) -> None:
    """Trace a record"""

    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
        )
        trace_operation = review_manager.get_trace_operation()
        trace_operation.main(record_id=id)

    except colrev_exceptions.InvalidSettingsError as exc:
        print(exc)
        return


def __select_target_repository(environment_registry: list) -> Path:
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
def distribute(ctx: click.core.Context, path: Path, verbose: bool, force: bool) -> None:
    """Distribute records to other local repositories"""

    try:
        if not path:
            path = Path.cwd()
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=True, verbose_mode=verbose
        )
        distribute_operation = review_manager.get_distribute_operation()
        environment_registry = distribute_operation.get_environment_registry()

        target = __select_target_repository(environment_registry=environment_registry)
        # Note : add a "distribution mode" option?
        # (whole file -> add as source/load vs. records individually like a prescreen)
        distribute_operation.main(path=path, target=target)

    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


def __print_environment_status(
    review_manager: colrev.review_manager.ReviewManager,
) -> None:
    environment_manager = review_manager.get_environment_manager()
    environment_details = environment_manager.get_environment_details()

    print("\nCoLRev environment status\n")
    print("Index\n")
    if environment_details["index"]["status"] == "up":
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
@click.option("--start", is_flag=True, default=False, help="Start environment services")
@click.option("--stop", is_flag=True, default=False, help="Stop environment services")
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
    help="Update the package list (extensions).",
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
def env(
    ctx: click.core.Context,
    index: bool,
    install: str,
    pull: bool,
    status: bool,
    start: bool,
    stop: bool,
    register: bool,
    unregister: bool,
    update_package_list: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Manage the environment"""

    # pylint: disable=too-many-return-statements
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals

    review_manager = colrev.review_manager.ReviewManager(
        force_mode=True, verbose_mode=verbose
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
        for curated_resource in environment_manager.load_environment_registry():
            curated_resource_path = curated_resource["source_url"]
            if "/curated_metadata/" not in curated_resource_path:
                continue
            review_manager = colrev.review_manager.ReviewManager(
                force_mode=force,
                verbose_mode=verbose,
                path_str=curated_resource_path,
            )
            review_manager.dataset.pull_if_repo_clean()
            print(f"Pulled {curated_resource_path}")
        return

    if status:
        __print_environment_status(review_manager)
        return

    if stop:
        environment_manager = review_manager.get_environment_manager()
        environment_manager.stop_docker_services()
        return

    if register:
        environment_manager = review_manager.get_environment_manager()
        environment_manager.register_repo(path_to_register=Path.cwd())
        return

    if unregister is not None:
        environment_manager = review_manager.get_environment_manager()

        environment_registry = environment_manager.load_environment_registry()
        if str(unregister) not in [x["source_url"] for x in environment_registry]:
            print("Not in local registry (cannot remove): %s", unregister)
        else:
            environment_registry = [
                x for x in environment_registry if x["source_url"] != str(unregister)
            ]
            environment_manager.save_environment_registry(
                updated_registry=environment_registry
            )
            logging.info("Removed from local registry: %s", unregister)
        return

    if update_package_list:
        if "y" != input(
            "The following process instantiates objects listed in the "
            + "colrev/template/package_endpoints.json "
            + "(including ones that may not be secure).\n"
            + "Please confirm (y) to proceed."
        ):
            return

        # pylint: disable=import-outside-toplevel
        import colrev.env.package_manager as p_manager

        package_manager = p_manager.PackageManager()
        package_manager.update_package_list()

    local_index = review_manager.get_local_index()

    if index:
        local_index.index()

    elif start:
        print("Started.")


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
    verbose: bool,
    force: bool,
) -> None:
    """Settings of the CoLRev project"""

    # pylint: disable=import-outside-toplevel
    # pylint: disable=reimported
    # pylint: disable=too-many-locals

    from subprocess import check_call
    from subprocess import DEVNULL
    from subprocess import STDOUT
    import json
    import ast
    import glom
    import colrev.review_manager

    review_manager = colrev.review_manager.ReviewManager(
        force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
    )
    if update_hooks:
        print("Update pre-commit hooks")

        if review_manager.dataset.has_changes():
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
            check_call(script_to_call, stdout=DEVNULL, stderr=STDOUT)

        review_manager.dataset.add_changes(path=Path(".pre-commit-config.yaml"))
        review_manager.create_commit(msg="Update pre-commit hooks")
        print("Successfully updated pre-commit hooks")
        return

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

        with open("settings.json", encoding="utf-8") as file:
            project_settings = json.load(file)

        glom.assign(project_settings, path, value)

        with open("settings.json", "w", encoding="utf-8") as outfile:
            json.dump(project_settings, outfile, indent=4)

        review_manager.dataset.add_changes(path=Path("settings.json"))
        review_manager.create_commit(msg="Change settings", manual_author=True)
        return

    # import colrev_ui.ui_web.settings_editor

    # review_manager = colrev.review_manager.ReviewManager(
    #     force_mode=True, verbose_mode=verbose
    # )
    # settings_operation = colrev.ui_web.settings_editor.SettingsEditor(
    #     review_manager=review_manager
    # )
    # settings_operation.open_settings_editor()


@main.command(help_priority=22)
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
def sync(
    ctx: click.core.Context,
    verbose: bool,
    force: bool,
) -> None:
    """Sync records from CoLRev environment to non-CoLRev repo"""

    sync_operation = colrev.review_manager.ReviewManager.get_sync_operation()
    sync_operation.get_cited_papers()

    if len(sync_operation.non_unique_for_import) > 0:
        print("Non-unique keys to resolve:")
        # Resolve non-unique cases
        for case in sync_operation.non_unique_for_import:
            for val in case.values():
                # later: there may be more collisions (v3, v4)
                v_1 = val[0].format_bib_style()
                v_2 = val[1].format_bib_style()

                if v_1.lower() == v_2.lower():
                    sync_operation.add_to_records_to_import(record=val[0])
                    continue
                print("\n")
                print(f"1: {v_1}")
                print("      " + val[0].data.get("source_url", ""))
                print("")
                print(f"2: {v_2}")
                print("      " + val[1].data.get("source_url", ""))
                user_selection = input("Import version 1 or 2 (or skip)?")
                if user_selection == "1":
                    sync_operation.add_to_records_to_import(record=val[0])
                    continue
                if user_selection == "2":
                    sync_operation.add_to_records_to_import(record=val[1])
                    continue

    sync_operation.add_to_bib()


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
def pull(
    ctx: click.core.Context,
    verbose: bool,
    force: bool,
) -> None:
    """Pull CoLRev project remote and record updates"""

    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
        )
        pull_operation = review_manager.get_pull_operation()

        pull_operation.main()

    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


@main.command(help_priority=24)
@click.argument("git_url")
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
def clone(
    ctx: click.core.Context,
    git_url: str,
    verbose: bool,
    force: bool,
) -> None:
    """Create local clone from shared CoLRev repository with git_url"""

    clone_operation = colrev.review_manager.ReviewManager.get_clone_operation(
        git_url=git_url
    )
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
def push(
    ctx: click.core.Context,
    records_only: bool,
    project_only: bool,
    all: bool,
    verbose: bool,
    force: bool,
) -> None:
    """Push CoLRev project remote and record updates"""

    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
        )
        push_operation = review_manager.get_push_operation()

        push_operation.main(
            records_only=records_only, project_only=project_only, all_records=all
        )

    except colrev_exceptions.CoLRevException as exc:
        if verbose:
            raise exc
        print(exc)


@main.command(hidden=True, help_priority=26)
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
def service(
    ctx: click.core.Context,
    verbose: bool,
    force: bool,
) -> None:
    """Service for real-time reviews"""

    try:
        review_manager = colrev.review_manager.ReviewManager(
            force_mode=force, verbose_mode=verbose, exact_call=EXACT_CALL
        )
        review_manager.get_service_operation()

    except KeyboardInterrupt:
        print("\nPressed ctrl-c. Shutting down service")

    if review_manager.dataset.has_changes():
        if input("Commit current changes (y/n)?") == "y":
            review_manager.create_commit(msg="Update (using CoLRev service)")
    else:
        print("No changes to commit")


def __validate_show(ctx: click.core.Context, param: str, value: str) -> None:
    if value not in ["sample", "settings", "prisma", "venv"]:
        raise click.BadParameter("Invalid argument")


@main.command(help_priority=27)
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
    callback=__validate_show,
) -> None:
    """Show aspects (sample, ...)"""
    # pylint: disable=too-many-locals

    # pylint: disable=import-outside-toplevel
    import colrev.operation
    import colrev.ui_cli.show_printer

    if keyword == "venv":
        colrev.ui_cli.show_printer.print_venv_notes()
        return

    review_manager = colrev.review_manager.ReviewManager(
        force_mode=force, verbose_mode=verbose
    )

    if keyword == "sample":
        colrev.ui_cli.show_printer.print_sample(review_manager=review_manager)

    elif keyword == "settings":
        print(f"Settings:\n{review_manager.settings}")

    elif keyword == "prisma":
        status_operation = review_manager.get_status_operation()
        stats_report = status_operation.get_review_status_report()
        print(stats_report)

    elif keyword == "cmd_history":
        cmds = []
        colrev.operation.CheckOperation(review_manager=review_manager)
        revlist = review_manager.dataset.get_repo().iter_commits()

        for commit in reversed(list(revlist)):
            try:
                cmsg = str(commit.message)
                formatted_date = time.strftime(
                    "%Y-%m-%d %H:%M",
                    time.gmtime(commit.committed_date),
                )
                if not all(x in cmsg for x in ["Command", "Status"]):
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
                f"{colors.ORANGE}{cmd['cmd']}{colors.END}"
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

#     # pylint: disable=import-outside-toplevel
#     import colrev.ui_web.settings_editor

#     review_manager = colrev.review_manager.ReviewManager(
#         force_mode=force, verbose_mode=verbose
#     )
#     se_instance = colrev.ui_web.settings_editor.SettingsEditor(
#         review_manager=review_manager
#     )
#     se_instance.open_settings_editor()


@main.command(hidden=True, help_priority=29)
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
        review_manager.create_commit(msg="Disable auto-upgrade")
        return
    review_manager = colrev.review_manager.ReviewManager(
        force_mode=True, verbose_mode=verbose
    )
    upgrade_operation = review_manager.get_upgrade()
    upgrade_operation.main()


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
def repare(
    ctx: click.core.Context,
    verbose: bool,
    force: bool,
) -> None:
    """Repare file formatting errors in the CoLRev project."""

    review_manager = colrev.review_manager.ReviewManager(
        force_mode=True, verbose_mode=verbose
    )
    repare_operation = review_manager.get_repare()
    repare_operation.main()


@main.command(help_priority=31)
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

    review_manager = colrev.review_manager.ReviewManager(
        force_mode=force, verbose_mode=verbose
    )

    remove_operation = review_manager.get_remove_operation()

    if ids:
        remove_operation.remove_records(ids=ids)


@main.command(hidden=True, help_priority=32)
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
def man(
    ctx: click.core.Context,
    verbose: bool,
    force: bool,
) -> None:
    """Show the CoLRev manual."""

    # pylint: disable=import-outside-toplevel
    import webbrowser

    webbrowser.open(
        str(Path(colrev.__file__).resolve()).replace(
            "colrev/__init__.py", "docs/build/html/index.html"
        )
    )


@main.command(help_priority=33)
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

    review_manager = colrev.review_manager.ReviewManager(
        force_mode=force, verbose_mode=verbose
    )

    if not branch:
        colrev.operation.CheckOperation(review_manager=review_manager)
        git_repo = review_manager.dataset.get_repo()
        print(f"possible branches: {','.join([b.name for b in git_repo.heads])}")
        return

    merge_operation = review_manager.get_merge_operation()
    merge_operation.main(branch=branch)


@main.command(help_priority=34)
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

    review_manager = colrev.review_manager.ReviewManager(
        force_mode=force, verbose_mode=verbose
    )

    if selection == "commit":
        colrev.operation.CheckOperation(review_manager=review_manager)
        git_repo = review_manager.dataset.get_repo()
        git_repo.git.reset("--hard", "HEAD~1")


@main.command(help_priority=35)
@click.pass_context
def version(
    ctx: click.core.Context,
) -> None:
    """Show colrev version."""

    # pylint: disable=import-outside-toplevel
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
    shell, path = click_completion.core.install(
        shell=shell, path=path, append=append, extra_env=extra_env
    )
    click.echo(f"{shell} completion installed in {path}")
