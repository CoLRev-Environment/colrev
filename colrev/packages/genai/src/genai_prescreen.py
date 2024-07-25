#! /usr/bin/env python
"""Prescreen based on GenAI"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import instructor
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
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


class PreScreenDecision(BaseModel):
    """
    Class for a prescreen
    """

    SYSTEM_PROMPT: ClassVar[str] = (
        "You are an expert screener of scientific literature. You are tasked with identifying relevant articles for a literature review. You are provided with the metadata of an article and are asked to determine whether the article should be included in the review based on an inclusion criterion."
    )
    included: bool = Field(
        description="Whether the article should be included in the review based on the inclusion criterion."
    )
    explanation: str = Field(description="Explanation of the inclusion decision.")


@zope.interface.implementer(colrev.package_manager.interfaces.PrescreenInterface)
@dataclass
class GenAIPrescreen(JsonSchemaMixin):
    """GenAI-based prescreen"""

    ci_supported: bool = True
    export_todos_only: bool = True

    @dataclass
    class GenAIPrescreenSettings(
        colrev.package_manager.package_settings.DefaultSettings, JsonSchemaMixin
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
        self.settings = self.settings_class.load_settings(data=settings)

    def run_prescreen(
        self,
        records: dict,
        split: list,
    ) -> dict:
        """Prescreen records based on GenAI"""

        # API key needs to be set as an environment variable
        client = instructor.from_litellm(completion)
        inclusion_criterion = self.review_manager.settings.prescreen.explanation

        for record_dict in records.values():
            record = colrev.record.record.Record(record_dict)
            response = client.chat.completions.create(
                model=self.settings.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": f"{PreScreenDecision.SYSTEM_PROMPT}\n\nINCLUSION CRITERION:\n\n{inclusion_criterion}\n\nMETADATA:\n\n{record}",
                    }
                ],
                response_model=PreScreenDecision,
            )
            if response.included:
                record.set_status(RecordState.rev_prescreen_included)
            else:
                record.set_status(RecordState.rev_prescreen_excluded)

        self.review_manager.dataset.save_records_dict(records)
        self.review_manager.dataset.create_commit(
            msg="Pre-screen (GenAI)",
            manual_author=False,
        )

        return records
