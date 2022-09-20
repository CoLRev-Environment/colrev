#! /usr/bin/env python
"""Screening utilities"""
from __future__ import annotations

from typing import TYPE_CHECKING

import colrev.env.package_manager
import colrev.record
import colrev.settings


if TYPE_CHECKING:
    import colrev.ops.screen


def get_screening_criteria_from_user_input(
    *, screen_operation: colrev.ops.screen.Screen, records: dict
) -> dict:

    screening_criteria = screen_operation.review_manager.settings.screen.criteria
    if len(screening_criteria) == 0 and 0 == len(
        [
            r
            for r in records.values()
            if r["colrev_status"]
            in [
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_excluded,
                colrev.record.RecordState.rev_synthesized,
            ]
        ]
    ):

        screening_criteria = {}
        while "y" == input("Add screening criterion [y,n]?"):
            short_name = input("Provide a short name: ")
            if "i" == input("Inclusion or exclusion criterion [i,e]?: "):
                criterion_type = colrev.settings.ScreenCriterionType.inclusion_criterion
            else:
                criterion_type = colrev.settings.ScreenCriterionType.exclusion_criterion
            explanation = input("Provide a short explanation: ")

            screening_criteria[short_name] = colrev.settings.ScreenCriterion(
                explanation=explanation, criterion_type=criterion_type, comment=""
            )

        screen_operation.set_screening_criteria(screening_criteria=screening_criteria)

    return screening_criteria
