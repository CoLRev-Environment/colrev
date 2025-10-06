#!/usr/bin/env python3
"""CoLRev REPL — starts immediately with a persistent colrev.review_manager.ReviewManager."""
from __future__ import annotations

import os
import typing as t
from pathlib import Path

import click
import click_repl
import inquirer

import colrev.env.tei_parser
import colrev.exceptions as colrev_exceptions
import colrev.ops.search_api_feed
import colrev.record.record
import colrev.review_manager
from colrev.constants import Fields
from colrev.constants import RecordState
from colrev.constants import SearchType

SHELL_MODE = True  # mimic CoLRev shell flag

# ---------- helpers ----------


def _ensure_rm(ctx: click.Context) -> colrev.review_manager.ReviewManager:
    """Get/create a persistent ReviewManager stored in ctx.obj."""
    ctx.ensure_object(dict)
    rm = ctx.obj.get("review_manager")
    if rm is not None:
        return rm
    try:
        rm = colrev.review_manager.ReviewManager()
        if SHELL_MODE:
            rm.shell_mode = True
        ctx.obj["review_manager"] = rm
        return rm
    except colrev_exceptions.RepoSetupError as exc:
        # Keep REPL usable; user can cd into a repo or run `colrev init` externally.
        click.echo(f"[note] No CoLRev project detected here: {exc}")
        click.echo(
            "       Create one with `colrev init` (then restart) or `cd` to an existing repo."
        )
        # Store a sentinel so commands can error nicely but REPL stays up
        ctx.obj["review_manager"] = None
        return None  # type: ignore[return-value]


def _require_rm(ctx: click.Context) -> colrev.review_manager.ReviewManager:
    """Require an initialized ReviewManager or fail with a friendly message."""
    rm = _ensure_rm(ctx)
    if rm is None:
        raise click.UsageError(
            "No CoLRev project here. Run `colrev init` in this directory, "
            "or `cd` to a CoLRev repo, then restart this REPL."
        )
    return rm


# ---------- CLI / REPL ----------


class OrderedGroup(click.Group):
    def list_commands(self, ctx: click.Context) -> t.List[str]:  # keep help tidy
        return list(self.commands.keys())


@click.group(cls=OrderedGroup, invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Run without arguments to enter the interactive CoLRev shell."""
    ctx.ensure_object(dict)
    _ensure_rm(ctx)  # try to create RM now (tolerates missing repo)

    # Enter REPL if no subcommand was given
    if ctx.invoked_subcommand is None:
        rm = ctx.obj.get("review_manager")
        click.echo(f"CoLRev {colrev.__version__} — exploration shell")
        if rm is None:
            click.echo("Call in CoLRev project. Exiting.")
            return
        # else:
        #     click.echo(f"review_manager ready: {rm!r}")
        click.echo("")
        click_repl.repl(ctx, prompt_kwargs={"message": "CoLRev > "})

        # TODO : command to set directory (replacing Downloads) in the session


@cli.command()
def exit() -> None:
    """Exit the shell."""
    raise click_repl.exceptions.ExitReplException


# ---------- stub commands you asked for ----------


def import_from_downloads(review_manager: colrev.review_manager.ReviewManager) -> list:

    downloads_folder = os.path.expanduser("~/Downloads")
    files = [
        f
        for f in os.listdir(downloads_folder)
        if os.path.isfile(os.path.join(downloads_folder, f))
        and f.lower().endswith(".pdf")
    ]
    if not files:
        click.echo("No files found in Downloads folder.")
        return []

    questions = [
        inquirer.Checkbox(
            "selected_files",
            message="Select files to import from Downloads",
            choices=files,
        )
    ]
    answers = inquirer.prompt(questions)
    selected_files = answers.get("selected_files", []) if answers else []

    if not selected_files:
        click.echo("No files selected for import.")
        return []

    records = []
    for file in selected_files:
        file_path = os.path.join(downloads_folder, file)
        click.echo(f"Importing {file_path} ...")

        pdf_dest_dir = review_manager.paths.pdf
        os.makedirs(pdf_dest_dir, exist_ok=True)
        os.path.join(pdf_dest_dir, file)
        # TODO: reactivate the following:
        # print("reactivate the following:")
        # shutil.move(file_path, dest_path)
        # click.echo(f"Moved PDF to {dest_path}")

        # record_dict = colrev.env.tei_parser.get_record_from_pdf(review_manager.path / file)
        record_dict = colrev.env.tei_parser.get_record_from_pdf(
            Path(downloads_folder) / file, add_doi_from_pdf=True
        )
        # print(record_dict)
        records.append(record_dict)

    return records


@cli.command(name="import")
@click.option("--source", help="Path/identifier of source to import.")
@click.pass_context
def import_cmd(ctx: click.Context, source: str | None) -> None:
    review_manager = _require_rm(ctx)
    # click.echo(f"[import] review_manager={review_manager!r} source={source or 'N/A'}")

    # TODO : user choice:
    method = "downloads"
    # also: doi , url, reference file (csv, bibtex, ris, ...), reference string (apa, bibtex, ...)
    if method == "downloads":
        imported_records = import_from_downloads(review_manager)
        # TODO : identify(prevent duplication)

        files_sources = [
            s
            for s in review_manager.settings.sources
            if s.search_type == SearchType.FILES
        ]
        assert files_sources
        files_source = files_sources.pop()

        # else: reate files_source:
        # search_source = colrev.search_file.ExtendedSearchFile(
        #     version="1.0.0",
        #     platform="colrev.files_dir",
        #     search_results_path=filename,
        #     search_type=SearchType.FILES,
        #     search_string="",
        #     comment="",
        # )

        files_dir_feed = colrev.ops.search_api_feed.SearchAPIFeed(
            source_identifier=Fields.FILE,
            search_source=files_source,
            update_only=False,
            logger=review_manager.logger,
            verbose_mode=False,
        )
        for imported_record in imported_records:
            files_dir_feed.add_update_record(
                colrev.record.record.Record(imported_record)
            )
            imported_record[Fields.ORIGIN] = [
                files_source.get_origin_prefix() + "/" + imported_record[Fields.ID]
            ]
            imported_record[Fields.STATUS] = RecordState.md_imported

        files_dir_feed.save()
        review_manager.dataset.git_repo.add_changes(files_source.search_results_path)

    load_operation = review_manager.get_load_operation()
    records = review_manager.dataset.load_records_dict()
    for imported_record in imported_records:
        load_operation.import_record(record_dict=imported_record, records=records)

    # TODO : match against crossref/md-prep

    # screen (tbd. pre/screen on fulltext)
    for imported_record in imported_records:
        print(imported_record)
        screening_decision = inquirer.confirm(
            "Add this record to the review?", default=True
        )
        if screening_decision:
            imported_record[Fields.STATUS] = RecordState.rev_included
            click.echo(f"Record added: {imported_record.get('ID', 'N/A')}")
        else:
            imported_record[Fields.STATUS] = RecordState.rev_excluded

    review_manager.dataset.save_records_dict(records)


@cli.command()
@click.option("-q", "--query", help="Search query.")
@click.pass_context
def search(ctx: click.Context, query: str | None) -> None:
    rm = _require_rm(ctx)
    click.echo(f"[search] review_manager={rm!r} query={query or 'N/A'}")


@cli.command()
@click.option("--criteria", default="(stub)", help="Screening criteria.")
@click.pass_context
def screen(ctx: click.Context, criteria: str) -> None:
    rm = _require_rm(ctx)
    click.echo(f"[screen] review_manager={rm!r} criteria={criteria}")


@cli.command()
@click.option("--method", default="(stub)", help="Analysis method.")
@click.pass_context
def analyze(ctx: click.Context, method: str) -> None:
    rm = _require_rm(ctx)
    click.echo(f"[analyze] review_manager={rm!r} method={method}")


@cli.command()
@click.option("--format", "fmt", default="text", help="Summary format.")
@click.pass_context
def summarize(ctx: click.Context, fmt: str) -> None:
    rm = _require_rm(ctx)
    click.echo(f"[summarize] review_manager={rm!r} format={fmt}")


@cli.command()
@click.option("-m", "--message", default="(stub)", help="Commit message.")
@click.pass_context
def commit(ctx: click.Context, message: str) -> None:
    rm = _require_rm(ctx)
    click.echo(f"[commit] review_manager={rm!r} message={message}")


# ---------- entrypoint ----------


def main() -> None:
    # usage:
    #   pip install click click-repl colrev
    #   python colrev_repl.py
    # Then at the prompt: help | search -q "test" | import --source data.ris | exit
    cli(obj={})
