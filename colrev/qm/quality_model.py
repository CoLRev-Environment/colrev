#! /usr/bin/env python
"""Quality model for records."""
from __future__ import annotations

import importlib
from pathlib import Path

import colrev.qm.checkers
import colrev.record


class QualityModel:
    """The quality model for records"""

    __checker_path = Path(__file__).parent / Path("checkers")
    checkers = []  # type: ignore

    # TODO : "centralize" defect codes!

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        self.review_manager = review_manager
        self.__register_checkers()

    def __register_checkers(self) -> None:
        """Register checkers from the checker directory, looking for a
        'register' function in each one.
        """

        for filename in self.__checker_path.glob("*.py"):
            if "__init__" in str(filename):
                continue

            try:
                module = importlib.import_module("colrev.qm.checkers." + filename.stem)
            except ValueError:
                continue
            except ImportError as exc:
                print(
                    f"Problem importing module {filename}: {exc}"
                )  # , file=sys.stderr
            else:
                if hasattr(module, "register"):
                    module.register(self)

    def register_checker(self, checker) -> None:  # type: ignore
        """Register a checker"""
        self.checkers.append(checker)

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the checkers"""
        for checker in self.checkers:
            checker.run(record=record)


if __name__ == "__main__":
    pass
