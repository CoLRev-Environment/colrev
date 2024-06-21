#! /usr/bin/env python
"""Quality model for records."""
from __future__ import annotations

import importlib
from multiprocessing import Lock
from pathlib import Path

import colrev.record.qm.checkers
import colrev.record.record
from colrev.constants import Fields


class QualityModel:
    """The quality model for records"""

    checkers = []  # type: ignore

    def __init__(
        self,
        *,
        defects_to_ignore: list[str],
        pdf_mode: bool = False,
    ) -> None:
        self.pdf_mode = pdf_mode
        self.defects_to_ignore = defects_to_ignore
        self._register_checkers()
        self.local_index_lock = Lock()

    def _register_checkers(self) -> None:
        """Register checkers from the checker directory, looking for a
        'register' function in each one.
        """

        self.checkers = []
        if self.pdf_mode:
            module_path = "colrev.record.qm.pdf_checkers."
        else:
            module_path = "colrev.record.qm.checkers."

        if self.pdf_mode:
            checker_path = Path(__file__).parent / Path("pdf_checkers/")
        else:
            checker_path = Path(__file__).parent / Path("checkers")

        for filename in checker_path.glob("*.py"):
            if "__init__" in str(filename):
                continue

            try:
                module = importlib.import_module(module_path + filename.stem)
            except ValueError as exc:  # pragma: no cover
                print(f"Problem with filepath for module import {filename}: {exc}")
            except ImportError as exc:  # pragma: no cover
                print(f"Problem importing module {filename}: {exc}")
            else:
                if hasattr(module, "register"):
                    module.register(self)
                else:  # pragma: no cover
                    print(f"Module {filename} does not have a register function")

    def register_checker(self, checker) -> None:  # type: ignore
        """Register a checker"""
        self.checkers.append(checker)

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the checkers"""

        if self.pdf_mode:
            if (
                Fields.FILE not in record.data
                or not Path(record.data[Fields.FILE]).is_file()
            ):
                return
            # text_from_pdf is already set in tests
            if (
                Fields.TEXT_FROM_PDF not in record.data
                or Fields.NR_PAGES_IN_FILE not in record.data
            ):
                # The following should be improved.
                record = colrev.record.record_pdf.PDFRecord(record.data)
                record.set_text_from_pdf()

        for checker in self.checkers:
            if checker.msg in self.defects_to_ignore:
                continue
            checker.run(record=record)

        if self.pdf_mode:
            record.data.pop(Fields.TEXT_FROM_PDF, None)
            record.data.pop(Fields.NR_PAGES_IN_FILE, None)
