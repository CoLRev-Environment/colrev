#!/usr/bin/env python3
"""Scripts printing information for the colrev show command"""
import platform
from pathlib import Path

import colrev.record
import colrev.ui_cli.cli_colors as colors


def print_sample(review_manager: colrev.review_manager.ReviewManager) -> None:
    """Print the sample on cli"""

    colrev.operation.CheckOperation(review_manager=review_manager)
    records = review_manager.dataset.load_records_dict()
    sample = [
        r
        for r in records.values()
        if r["colrev_status"]
        in [
            colrev.record.RecordState.rev_synthesized,
            colrev.record.RecordState.rev_included,
        ]
    ]
    if 0 == len(sample):
        print("No records included in sample (yet)")

    for sample_r in sample:
        colrev.record.Record(data=sample_r).print_citation_format()


def print_venv_notes() -> None:
    """Print the virtual environment details on cli"""

    current_platform = platform.system()
    if current_platform == "Linux":
        print("Detected platform: Linux")
        if not Path("venv").is_dir():
            print("To create virtualenv, run")
            print(f"  {colors.ORANGE}python3 -m venv venv{colors.END}")
        print("To activate virtualenv, run")
        print(f"  {colors.ORANGE}source venv/bin/activate{colors.END}")
        print("To install colrev/colrev, run")
        print(f"  {colors.ORANGE}python -m pip install colrev{colors.END}")
        print("To deactivate virtualenv, run")
        print(f"  {colors.ORANGE}deactivate{colors.END}")
    elif current_platform == "Darwin":
        print("Detected platform: MacOS")
        if not Path("venv").is_dir():
            print("To create virtualenv, run")
            print(f"  {colors.ORANGE}python3 -m venv venv{colors.END}")
        print("To activate virtualenv, run")
        print(f"  {colors.ORANGE}source venv/bin/activate{colors.END}")
        print("To install colrev/colrev, run")
        print(f"  {colors.ORANGE}python -m pip install colrev{colors.END}")
        print("To deactivate virtualenv, run")
        print(f"  {colors.ORANGE}deactivate{colors.END}")
    elif current_platform == "Windows":
        print("Detected platform: Windows")
        if not Path("venv").is_dir():
            print("To create virtualenv, run")
            print(f"  {colors.ORANGE}python -m venv venv{colors.END}")
        print("To activate virtualenv, run")
        print(f"  {colors.ORANGE}venv\\Scripts\\Activate.ps1{colors.END}")
        print("To install colrev/colrev, run")
        print(f"  {colors.ORANGE}python -m pip install colrev{colors.END}")
        print("To deactivate virtualenv, run")
        print(f"  {colors.ORANGE}deactivate{colors.END}")
    else:
        print(
            "Platform not detected... "
            "cannot provide infos in how to activate virtualenv"
        )


if __name__ == "__main__":
    pass
