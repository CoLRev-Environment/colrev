#! /usr/bin/env python
from pathlib import Path

import zope.interface
from dacite import from_dict

from colrev_core.process import DefaultSettings
from colrev_core.process import PreparationManualEndpoint


@zope.interface.implementer(PreparationManualEndpoint)
class CoLRevCLIManPrep:
    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(data_class=DefaultSettings, data=SETTINGS)

    def prepare_manual(self, PREP_MAN, records):

        from colrev.cli import prep_man_records_cli

        records = prep_man_records_cli(PREP_MAN, records)

        return records


@zope.interface.implementer(PreparationManualEndpoint)
class ExportManPrep:
    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(data_class=DefaultSettings, data=SETTINGS)

    def prepare_manual(self, PREP_MAN, records):
        from colrev_core.record import RecordState

        export_path = PREP_MAN.REVIEW_MANAGER.path / Path("references_prep_man.bib")

        if export_path.is_file():
            if "y" == input(f"Import changes from {export_path} [y,n]?"):

                with open(export_path, encoding="utf8") as target_bib:
                    man_prep_recs = (
                        PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                            load_str=target_bib.read()
                        )
                    )
                records = PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
                for ID, record in man_prep_recs.items():
                    # TODO : if there are changes, update the provenance accordingly
                    records[ID] = record
                PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(
                    records=records
                )
                PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
                PREP_MAN.REVIEW_MANAGER.create_commit(msg="Prep-man (ExportManPrep)")

        else:
            man_prep_recs = {
                k: v
                for k, v in records.items()
                if RecordState.md_needs_manual_preparation == v["colrev_status"]
            }
            PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict_to_file(
                records=man_prep_recs, save_path=export_path
            )

        return records
