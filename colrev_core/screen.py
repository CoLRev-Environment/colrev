#! /usr/bin/env python
import typing

from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.process import RecordState


class Screen(Process):
    def __init__(self):
        super().__init__(ProcessType.screen)

    def include_all_in_screen(
        self,
    ) -> None:

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()

        excl_criteria = self.get_exclusion_criteria(records)

        saved_args = locals()
        saved_args["include_all"] = ""
        PAD = 50  # TODO
        for record in records:
            if record["status"] != RecordState.pdf_prepared:
                continue
            self.report_logger.info(
                f' {record["ID"]}'.ljust(PAD, " ")
                + "Included in screen (automatically)"
            )
            record.update(excl_criteria=";".join([e + "=no" for e in excl_criteria]))
            record.update(status=RecordState.rev_included)

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        self.REVIEW_MANAGER.create_commit(
            "Screen (include_all)", manual_author=False, saved_args=saved_args
        )

        return

    def __get_excl_criteria(self, ec_string: str) -> list:
        return [ec.split("=")[0] for ec in ec_string.split(";") if ec != "NA"]

    def get_exclusion_criteria_from_str(self, ec_string: str) -> list:
        if ec_string != "":
            excl_criteria = self.__get_excl_criteria(ec_string)
        else:
            excl_criteria_str = input("Exclusion criteria (comma separated or NA)")
            excl_criteria = excl_criteria_str.split(",")
            if "" in excl_criteria:
                excl_criteria.remove("")
        if "NA" in excl_criteria:
            excl_criteria.remove("NA")

        return excl_criteria

    def get_exclusion_criteria(self, records: typing.List[dict]) -> list:
        ec_list = [str(x.get("excl_criteria")) for x in records if "excl_criteria" in x]
        if 0 == len(ec_list):
            ec_string = ""
        else:
            ec_string = ec_list.pop()
        return self.get_exclusion_criteria_from_str(ec_string)

    def get_data(self) -> dict:

        record_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
        nr_tasks = len(
            [x for x in record_state_list if str(RecordState.pdf_prepared) == x[1]]
        )
        PAD = min((max(len(x[0]) for x in record_state_list) + 2), 35)
        items = self.REVIEW_MANAGER.REVIEW_DATASET.read_next_record(
            conditions={"status": RecordState.pdf_prepared}
        )
        screen_data = {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}
        self.logger.debug(self.pp.pformat(screen_data))
        return screen_data

    def set_data(self, record: dict, PAD: int = 40) -> None:

        if RecordState.rev_included == record["status"]:
            self.report_logger.info(
                f" {record['ID']}".ljust(PAD, " ") + "Included in screen"
            )
            self.REVIEW_MANAGER.REVIEW_DATASET.update_record_by_ID(record)
        else:
            self.report_logger.info(
                f" {record['ID']}".ljust(PAD, " ") + "Excluded in screen"
            )
            self.REVIEW_MANAGER.REVIEW_DATASET.update_record_by_ID(record)

        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return


if __name__ == "__main__":
    pass
