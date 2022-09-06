#! /usr/bin/env python
from __future__ import annotations

import colrev.exceptions as colrev_exceptions
import colrev.ops.data
import colrev.process


class Paper(colrev.process.Process):
    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        super().__init__(
            review_manager=review_manager,
            process_type=colrev.process.ProcessType.explore,
        )

    def main(self) -> None:

        data_operation = self.review_manager.get_data_operation()

        if "MANUSCRIPT" not in data_operation.data_scripts:
            raise colrev_exceptions.NoPaperEndpointRegistered()

        paper_endpoint = data_operation.data_scripts["MANUSCRIPT"]
        paper_endpoint.build_manuscript(data_operation=data_operation)


if __name__ == "__main__":
    pass
