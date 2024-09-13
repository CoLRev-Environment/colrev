#! /usr/bin/env python
"""Prescreen based on GenAI"""
from __future__ import annotations

import textwrap
from typing import ClassVar

import instructor
import zope.interface
from litellm import completion
from pydantic import BaseModel
from pydantic import Field

import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record
from colrev.constants import RecordState


# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


class PreScreenDecision:
    """
    Class for a prescreen
    """

    SYSTEM_PROMPT: ClassVar[str] = (
        "You are an expert screener of scientific literature. "
        "You are tasked with identifying relevant articles for a literature review. "
        "You are provided with the metadata of an article and are asked to determine "
        "whether the article should be included in the review based on an inclusion criterion."
    )
    included: bool = Field(
        description="Whether the article should be included in the review "
        + "based on the inclusion criterion."
    )
    explanation: str = Field(description="Explanation of the inclusion decision.")


@zope.interface.implementer(colrev.package_manager.interfaces.PrescreenInterface)
class GenAIPrescreen:
    """GenAI-based prescreen"""

    ci_supported: bool = Field(default=True)
    export_todos_only: bool = True

    class GenAIPrescreenSettings(
        colrev.package_manager.package_settings.DefaultSettings, BaseModel
    ):
        """Settings for GenAIPrescreen"""

        # pylint: disable=invalid-name
        # pylint: disable=too-many-instance-attributes

        endpoint: str
        model: str = "claude-3-haiku-20240307"

    settings_class = GenAIPrescreenSettings

    def __init__(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        settings: dict,
    ) -> None:
        self.review_manager = prescreen_operation.review_manager
        self.settings = self.settings_class(**settings)

    def _print_table(self, data: list, max_width: int = 200) -> None:
        """Print a table with the given data"""
        if not data:
            print("No data to display")
            return

        # Extract column names from the keys of the first dictionary
        col_names = list(data[0].keys())

        # Calculate the maximum width for each column
        col_widths = {col: len(col) for col in col_names}
        for row in data:
            for col, value in row.items():
                # Limit the maximum width of any column
                col_widths[col] = min(
                    max(col_widths[col], len(str(value).split("\n")[0])), max_width
                )

        # Print header
        header = " | ".join(
            f"{col[:col_widths[col]]:<{col_widths[col]}}" for col in col_names
        )
        print(header)
        print("-" * len(header))

        # Print rows
        for row in data:
            # Wrap text for each cell
            wrapped_row = {
                col: textwrap.wrap(str(row.get(col, "")), width=col_widths[col])
                for col in col_names
            }

            # Find the maximum number of lines in any cell of this row
            max_lines = max(len(cell) for cell in wrapped_row.values())

            # Print each line of the row
            for i in range(max_lines):
                line = []
                for col in col_names:
                    cell = wrapped_row[col]
                    if i < len(cell):
                        line.append(f"{cell[i]:<{col_widths[col]}}")
                    else:
                        line.append(" " * col_widths[col])
                print(" | ".join(line))

    # pylint: disable=unused-argument
    def run_prescreen(
        self,
        records: dict,
        split: list,
    ) -> dict:
        """Prescreen records based on GenAI"""

        # API key needs to be set as an environment variable
        client = instructor.from_litellm(completion)
        inclusion_criterion = self.review_manager.settings.prescreen.explanation

        screening_decisions = []

        for record_dict in records.values():
            record = colrev.record.record.Record(record_dict)
            response = client.chat.completions.create(
                model=self.settings.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": f"{PreScreenDecision.SYSTEM_PROMPT}\n\n"
                        + f"INCLUSION CRITERION:\n\n{inclusion_criterion}\n\n"
                        + f"METADATA:\n\n{record}",
                    }
                ],
                response_model=PreScreenDecision,
            )
            if response.included:
                record.set_status(RecordState.rev_prescreen_included)
            else:
                record.set_status(RecordState.rev_prescreen_excluded)

            screening_decisions.append(
                {
                    "Record": record.get_data()["ID"],
                    "Inclusion/Exclusion Decision": (
                        "Included" if response.included else "Excluded"
                    ),
                    "Explanation": response.explanation,
                }
            )

        print(f"\nGenAI (model: {self.settings.model}) screening decisions:")
        self._print_table(screening_decisions)
        print("\n")

        self.review_manager.dataset.save_records_dict(records)
        self.review_manager.dataset.create_commit(
            msg="Pre-screen (GenAI)",
            manual_author=False,
        )

        return records
