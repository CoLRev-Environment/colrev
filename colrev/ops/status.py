#! /usr/bin/env python3
"""CoLRev status operation: Display the project status."""
from __future__ import annotations

import io
import typing

import yaml

import colrev.env.utils
import colrev.process.operation
from colrev.constants import Colors
from colrev.constants import OperationsType


class Status(colrev.process.operation.Operation):
    """Determine the status of the project"""

    type = OperationsType.check

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=self.type,
        )

    def get_analytics(self) -> dict:
        """Get status analytics"""

        analytics_dict = {}
        git_repo = self.review_manager.dataset.get_repo()

        revlist = list(
            (
                commit.hexsha,
                commit.message,
                commit.author.name,
                commit.committed_date,
                (
                    commit.tree / str(self.review_manager.paths.STATUS_FILE)
                ).data_stream.read(),
            )
            for commit in git_repo.iter_commits(
                paths=str(self.review_manager.paths.STATUS_FILE)
            )
        )
        for ind, (
            commit_id,
            commit_msg,
            commit_author,
            committed_date,
            filecontents,
        ) in enumerate(revlist):
            var_t = io.StringIO(filecontents.decode("utf-8"))

            # TBD: we could simply include the whole STATUS_FILE
            # (to create a general-purpose status analyzer)
            # -> flatten nested structures (e.g., overall/currently)
            # -> integrate with get_status (current data) -
            # and get_prior? (levels: aggregated_statistics vs. record-level?)

            data_loaded = yaml.safe_load(var_t)
            analytics_dict[len(revlist) - ind] = {
                "atomic_steps": data_loaded["atomic_steps"],
                "completed_atomic_steps": data_loaded["completed_atomic_steps"],
                "commit_id": commit_id,
                "commit_message": commit_msg.split("\n")[0],
                "commit_author": commit_author,
                "committed_date": committed_date,
                "search": data_loaded["overall"]["md_retrieved"],
                "included": data_loaded["overall"]["rev_included"],
            }

        # keys = list(analytics_dict.values())[0].keys()
        # with open("analytics.csv", "w", newline="", encoding="utf8") as output_file:
        #     dict_writer = csv.DictWriter(output_file, keys)
        #     dict_writer.writeheader()
        #     dict_writer.writerows(reversed(analytics_dict.values()))

        return analytics_dict

    def get_review_status_report(
        self, *, records: typing.Optional[dict] = None, colors: bool = True
    ) -> str:
        """Get the review status report"""

        status_stats = self.review_manager.get_status_stats(records=records)

        template = colrev.env.utils.get_template(template_path="ops/commit/status.txt")

        if colors:
            content = template.render(status_stats=status_stats, colors=Colors)
        else:
            content = template.render(status_stats=status_stats, colors=None)

        return content
