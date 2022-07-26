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
        from colrev_core.record import RecordState, PrepRecord

        export_path = PREP_MAN.REVIEW_MANAGER.path / Path("records_prep_man.bib")

        if not export_path.is_file():
            PREP_MAN.REVIEW_MANAGER.logger.info(
                f"Export records for man-prep to {export_path}"
            )

            man_prep_recs = {
                k: v
                for k, v in records.items()
                if RecordState.md_needs_manual_preparation == v["colrev_status"]
            }
            PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict_to_file(
                records=man_prep_recs, save_path=export_path
            )
        else:
            if "y" == input(f"Import changes from {export_path} [y,n]?"):

                PREP_MAN.REVIEW_MANAGER.logger.info(
                    f"Load import changes from {export_path}"
                )

                with open(export_path, encoding="utf8") as target_bib:
                    man_prep_recs = (
                        PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                            load_str=target_bib.read()
                        )
                    )

                records = PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
                for ID, record in man_prep_recs.items():
                    RECORD = PrepRecord(data=record)
                    RECORD.update_masterdata_provenance(
                        UNPREPARED_RECORD=RECORD.copy(),
                        REVIEW_MANAGER=PREP_MAN.REVIEW_MANAGER,
                    )
                    RECORD.set_status(target_state=RecordState.md_prepared)
                    for k in list(RECORD.data.keys()):
                        if k in ["colrev_status"]:
                            continue
                        if k in records[ID]:
                            if RECORD.data[k] != records[ID][k]:
                                if k in RECORD.data.get(
                                    "colrev_masterdata_provenance", {}
                                ):
                                    RECORD.add_masterdata_provenance(
                                        key=k, source="man_prep"
                                    )
                                else:
                                    RECORD.add_data_provenance(key=k, source="man_prep")

                    records[ID] = RECORD.get_data()

                PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(
                    records=records
                )
                PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
                PREP_MAN.REVIEW_MANAGER.create_commit(msg="Prep-man (ExportManPrep)")

                PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.set_IDs()
                PREP_MAN.REVIEW_MANAGER.create_commit(
                    msg="Set IDs", script_call="colrev prep", saved_args={}
                )

        return records
