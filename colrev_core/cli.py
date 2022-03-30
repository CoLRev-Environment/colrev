import os
import pprint

import click
import click_completion.core

pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)


# Note: autocompletion needs bash/... activation:
# https://click.palletsprojects.com/en/7.x/bashcomplete/


def custom_startswith(string, incomplete):
    """A custom completion matching that supports case insensitive matching"""
    if os.environ.get("_CLICK_COMPLETION_COMMAND_CASE_INSENSITIVE_COMPLETE"):
        string = string.lower()
        incomplete = incomplete.lower()
    return string.startswith(incomplete)


click_completion.core.startswith = custom_startswith
click_completion.init()


ccs = click_completion.core.shells


@click.group()
@click.pass_context
def main(ctx):
    """Colrev core

    Main command: debug

    Use colrev for a complete CLI

    """


@main.command()
@click.option("-a", "--activate", is_flag=True, default=False)
@click.option("-d", "--deactivate", is_flag=True, default=False)
@click.pass_context
def debug(ctx, activate, deactivate):
    """Debug"""
    from colrev_core import debug

    if activate:
        print("Debugging activated")
        debug.set_debug_mode(True)

    elif deactivate:
        print("Debugging deactivated")
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
