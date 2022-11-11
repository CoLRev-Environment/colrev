#!/usr/bin/env python3
"""Repair CoLRev projects."""
from __future__ import annotations

from typing import TYPE_CHECKING

import colrev.env.utils
import colrev.operation

if TYPE_CHECKING:
    import colrev.review_manager


# pylint: disable=too-few-public-methods


class Repair(colrev.operation.Operation):
    """Repair a CoLRev project"""

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.check,
            notify_state_transition_operation=False,
        )

    def main(self) -> None:
        """Repair a CoLRev project (main entrypoint)"""

        self.review_manager.logger.warning("Repair is not fully implemented.")

        # Try: open settings, except: notify & start repair

        # Try: open records, except: notify & start repair

        with open(self.review_manager.dataset.records_file, encoding="utf-8") as file:
            record_str = ""
            line = file.readline()

            while line:
                if line == "\n":
                    records = self.review_manager.dataset.load_records_dict(
                        load_str=record_str
                    )
                    if len(records) != 1:
                        print(record_str)
                    record_str = ""
                record_str += line
                line = file.readline()


if __name__ == "__main__":
    pass
