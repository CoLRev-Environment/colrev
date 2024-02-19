#! /usr/bin/env python
"""Quality model for records."""
from __future__ import annotations

import importlib
from pathlib import Path

import colrev.qm.checkers
import colrev.record
from colrev.constants import Fields


class QualityModel:
    """The quality model for records"""

    checkers = []  # type: ignore

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        pdf_mode: bool = False,
    ) -> None:
        self.pdf_mode = pdf_mode
        self.review_manager = review_manager
        self.defects_to_ignore = self.review_manager.settings.prep.defects_to_ignore
        self.__register_checkers()

    def __register_checkers(self) -> None:
        """Register checkers from the checker directory, looking for a
        'register' function in each one.
        """

        self.checkers = []
        if self.pdf_mode:
            module_path = "colrev.qm.pdf_checkers."
        else:
            module_path = "colrev.qm.checkers."

        if self.pdf_mode:
            checker_path = Path(__file__).parent / Path("pdf_checkers/")
        else:
            checker_path = Path(__file__).parent / Path("checkers")

        for filename in checker_path.glob("*.py"):
            if "__init__" in str(filename):
                continue

            try:
                module = importlib.import_module(module_path + filename.stem)
            except ValueError as exc:
                print(exc)
            except ImportError as exc:
                print(f"Problem importing module {filename}: {exc}")
            else:
                if hasattr(module, "register"):
                    module.register(self)

    def register_checker(self, checker) -> None:  # type: ignore
        """Register a checker"""
        self.checkers.append(checker)

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the checkers"""

        if self.pdf_mode:
            if "file" not in record.data or not Path(record.data["file"]).is_file():
                return
            # text_from_pdf is already set in tests
            if Fields.TEXT_FROM_PDF not in record.data:
                record.set_text_from_pdf()

        for checker in self.checkers:
            if checker.msg in self.defects_to_ignore:
                continue
            checker.run(record=record)

        if self.pdf_mode:
            if Fields.TEXT_FROM_PDF in record.data:
                del record.data[Fields.TEXT_FROM_PDF]
            if Fields.PAGES_IN_FILE in record.data:
                del record.data[Fields.PAGES_IN_FILE]
