#! /usr/bin/env python
"""Prescreen based on GenAI"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import ClassVar

import pandas as pd
from litellm import completion
from pydantic import BaseModel
from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.record.record
from colrev.constants import Colors
from colrev.constants import RecordState


# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


class PreScreenDecision(BaseModel):
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


class GenAIPrescreen(base_classes.PrescreenPackageBaseClass):
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
        model: str = "gpt-4o-mini"

    settings_class = GenAIPrescreenSettings

    def __init__(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        settings: dict,
    ) -> None:
        self.review_manager = prescreen_operation.review_manager
        self.settings = self.settings_class(**settings)
        self.prescreen_decision_explanation_path = (
            self.review_manager.paths.prescreen
            / Path("prescreen_decision_explanation.csv")
        )

    # pylint: disable=unused-argument
    def run_prescreen(
        self,
        records: dict,
        split: list,
    ) -> dict:
        """Prescreen records based on GenAI"""

        if self.review_manager.settings.prescreen.explanation == "":
            print(
                f"\n{Colors.ORANGE}Provide a short explanation of the prescreen{Colors.END} "
                "(why should particular papers be included?):"
            )
            print(
                'Example objective: "Include papers that focus on digital technology."'
            )
            self.review_manager.settings.prescreen.explanation = input("")
            self.review_manager.save_settings()
        else:
            print("\nIn the prescreen, the following process is followed:\n")
            print("   " + self.review_manager.settings.prescreen.explanation)
            print()

        # API key needs to be set as an environment variable
        inclusion_criterion = self.review_manager.settings.prescreen.explanation

        screening_decisions = []

        for record_dict in records.values():
            record = colrev.record.record.Record(record_dict)
            response = completion(
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
                response_format=PreScreenDecision,
            )
            prescreen_decision = PreScreenDecision.model_validate_json(
                response.choices[0].message.content
            )
            if prescreen_decision.included:
                record.set_status(RecordState.rev_prescreen_included)
            else:
                record.set_status(RecordState.rev_prescreen_excluded)

            screening_decisions.append(
                {
                    "Record": record.get_data()["ID"],
                    "Inclusion/Exclusion Decision": (
                        "Included" if prescreen_decision.included else "Excluded"
                    ),
                    "Explanation": prescreen_decision.explanation,
                }
            )

        self.review_manager.paths.prescreen.mkdir(parents=True, exist_ok=True)
        screening_decisions_df = pd.DataFrame(screening_decisions)
        screening_decisions_df.to_csv(
            self.prescreen_decision_explanation_path, index=False, quoting=csv.QUOTE_ALL
        )
        self.review_manager.logger.info(
            f"Exported prescreening decisions to {self.prescreen_decision_explanation_path}"
        )

        self.review_manager.dataset.save_records_dict(records)
        self.review_manager.dataset.create_commit(
            msg="Pre-screen (GenAI)",
            manual_author=False,
        )

        return records
