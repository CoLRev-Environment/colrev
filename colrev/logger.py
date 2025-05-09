#! /usr/bin/env python
"""Logger"""
from __future__ import annotations

import logging
from pathlib import Path

import colrev.exceptions as colrev_exceptions


def setup_logger(*, logger_path: Path, level: int = logging.INFO) -> logging.Logger:
    """Setup the CoLRev logger"""

    # for logger debugging:
    # from logging_tree import printout
    # printout()
    logger = logging.getLogger(f"colrev{str(logger_path).replace('/', '_')}")
    logger.setLevel(level)

    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(level)

    logger.addHandler(handler)
    logger.propagate = False

    return logger


def setup_report_logger(
    *, report_path: Path, level: int = logging.INFO
) -> logging.Logger:
    """Setup the report logger (used for git commit report)"""

    try:
        report_logger = logging.getLogger(
            f"colrev_report{str(report_path.parent).replace('/', '_')}"
        )

        if report_logger.handlers:
            for handler in report_logger.handlers:
                report_logger.removeHandler(handler)

        report_logger.setLevel(level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        report_file_handler = logging.FileHandler(report_path, mode="a")
        report_file_handler.setFormatter(formatter)

        report_logger.addHandler(report_file_handler)

        if logging.DEBUG == level:  # pragma: no cover
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            report_logger.addHandler(handler)
        report_logger.propagate = False
    except FileNotFoundError as exc:  # pragma: no cover
        raise colrev_exceptions.RepoSetupError("Missing file") from exc

    return report_logger


def reset_report_logger(*, report_path: Path) -> logging.FileHandler:
    """Reset the report log file (used for the git commit report)"""

    file_handler = logging.FileHandler(report_path, mode="a")
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    return file_handler
