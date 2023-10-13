#! /usr/bin/env python
"""Checker for name particles."""
from __future__ import annotations

import colrev.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class NameParticlesChecker:
    """The NameParticlesChecker"""

    fields_to_check = [Fields.AUTHOR, Fields.EDITOR]

    msg = DefectCodes.NAME_PARTICLES

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the name-particles checks"""

        for key in self.fields_to_check:
            if key not in record.data:
                continue

            names = record.data[key].split(" and ")
            if any(self.__particle_defect(name=name) for name in names):
                record.add_masterdata_provenance_note(key=key, note=self.msg)
            else:
                record.remove_masterdata_provenance_note(key=key, note=self.msg)

    def __particle_defect(self, *, name: str) -> bool:
        if name.endswith(" vom") or name.startswith("vom "):
            return True

        if name.endswith(" von") or name.startswith("von "):
            return True

        return False


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(NameParticlesChecker(quality_model))
