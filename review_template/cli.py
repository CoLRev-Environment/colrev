import datetime
import os
import sys

import click
import git
import yaml

from review_template import entry_hash_function

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']


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
        return (c[1] for c in sorted(
            (self.help_priorities.get(command, 1), command)
            for command in commands))

    def command(self, *args, **kwargs):
        """Behaves the same as `click.Group.command()` except capture
        a priority for listing command names in help.
        """
        help_priority = kwargs.pop('help_priority', 1)
        help_priorities = self.help_priorities

        def decorator(f):
            cmd = super(SpecialHelpOrder, self).command(*args, **kwargs)(f)
            help_priorities[cmd.name] = help_priority
            return cmd

        return decorator

# Note: autocompletion needs bash/... activation:
# https://click.palletsprojects.com/en/7.x/bashcomplete/


@click.group(cls=SpecialHelpOrder)
@click.pass_context
def main(ctx):
    """Review template pipeline

    Main commands: process | status"""


@main.command(help_priority=1)
@click.pass_context
def initialize(ctx):
    """Initialize repository"""
    from review_template import initialize
    initialize.initialize_repo()


@main.command(help_priority=2)
@click.pass_context
def process(ctx):
    """Process pipeline"""
    from review_template import review_template
    review_template.main()


@main.command(help_priority=3)
@click.pass_context
def status(ctx):
    """Show status"""
    os.system('pre-commit run -a')


@main.command(help_priority=4)
@click.pass_context
def complete_manual(ctx):
    """Complete records manually"""
    from review_template import complete_manual
    complete_manual.main()


@main.command(help_priority=5)
@click.pass_context
def cleanse_manual(ctx):
    """Cleanse records manually"""
    from review_template import cleanse_manual
    cleanse_manual.main()


@main.command(help_priority=6)
@click.pass_context
def proc_duplicates_manual(ctx):
    """Process duplicates manually"""
    from review_template import process_duplicates_manual
    process_duplicates_manual.main()


@main.command(help_priority=7)
@click.pass_context
def screen_1(ctx):
    """Execute screen 1"""
    from review_template import screen_1
    screen_1.main()


@main.command(help_priority=8)
@click.pass_context
def screen_2(ctx):
    """Execute screen 2"""
    from review_template import screen_2
    screen_2.main()


@main.command(help_priority=9)
@click.pass_context
def acquire_pdfs(ctx):
    """Acquire PDFs"""
    # from review_template import acquire_pdfs
    acquire_pdfs.main()


@main.command(help_priority=10)
@click.pass_context
def validate_pdfs(ctx):
    """Validate PDFs"""
    from review_template import validate_pdfs
    validate_pdfs.main()


@main.command(help_priority=11)
@click.pass_context
def backward_search(ctx):
    """Execute backward search based on PDFs"""
    from review_template import backward_search
    backward_search.main()


@main.command(help_priority=12)
@click.pass_context
def data(ctx):
    """Execute data extraction"""
    from review_template import data
    data.main()


@main.command(help_priority=13)
@click.pass_context
def sample_profile(ctx):
    """Generate a sample profile"""
    from review_template import sample_profile
    sample_profile.main()


def validate_commit(ctx, param, value):
    if 'none' == value:
        return value
    repo = git.Repo()

    revlist = [commit for commit in repo.iter_commits()]

    if value in [x.hexsha for x in revlist]:
        # TODO: allow short commit_ids as values!
        return value
    else:
        print('Error: Invalid value for \'--commit\': not a git commit id\n')
        print('Select any of the following commit ids:')
        commits_for_checking = []
        for c in reversed(list(revlist)):
            commits_for_checking.append(c)
        for commit in revlist:
            print(commit.hexsha,
                  datetime.datetime.fromtimestamp(commit.committed_date),
                  ' - ', commit.message.replace('\n', ' '))
        print('\n')
        raise click.BadParameter('not a git commit id')


@main.command(help_priority=14)
@click.option('--scope',
              type=click.Choice(['cleanse', 'merge', 'all'],
                                case_sensitive=False),
              default='all', help='cleanse, merge, or all.')
@click.option('--commit', help='Git commit id to validate.',
              default='none', callback=validate_commit)
@click.pass_context
def validate_changes(ctx, scope, commit):
    """Validate changes (in prior versions)"""
    from review_template import validate_changes
    validate_changes.main(scope, commit)


@main.command(help_priority=15)
@click.pass_context
def trace_hash_id(ctx):
    """Trace a hash_id"""
    from review_template import trace_hash_id
    trace_hash_id.main()


@main.command(help_priority=16)
@click.pass_context
def trace_search_result(ctx):
    """Trace a search result"""
    from review_template import trace_search_result
    trace_search_result.main()


@main.command(help_priority=16)
@click.pass_context
@click.option('--id', help='Entry ID to trace (citation_key).', required=True)
def trace_entry(ctx, id):
    """Trace an entry"""
    from review_template import trace_entry
    trace_entry.main(id)



if __name__ == '__main__':
    sys.exit(main())
