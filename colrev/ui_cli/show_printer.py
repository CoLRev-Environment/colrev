#!/usr/bin/env python3
"""Scripts printing information for the colrev show command"""
import platform
from pathlib import Path

import colrev.ops.check
import colrev.record.record
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import RecordState


def print_sample(review_manager: colrev.review_manager.ReviewManager) -> None:
    """Print the sample on cli"""

    colrev.ops.check.CheckOperation(review_manager)
    records = review_manager.dataset.load_records_dict()
    sample = [
        r
        for r in records.values()
        if r[Fields.STATUS]
        in [
            RecordState.rev_synthesized,
            RecordState.rev_included,
        ]
    ]
    if 0 == len(sample):
        print("No records included in sample (yet)")

    for sample_r in sample:
        colrev.record.record.Record(sample_r).print_citation_format()


def print_venv_notes() -> None:
    """Print the virtual environment details on cli"""

    current_platform = platform.system()
    if current_platform == "Linux":
        print("Detected platform: Linux")
        if not Path("venv").is_dir():
            print("To create virtualenv, run")
            print(f"  {Colors.ORANGE}python3 -m venv venv{Colors.END}")
        print("To activate virtualenv, run")
        print(f"  {Colors.ORANGE}source venv/bin/activate{Colors.END}")
        print("To install colrev/colrev, run")
        print(f"  {Colors.ORANGE}python -m pip install colrev{Colors.END}")
        print("To deactivate virtualenv, run")
        print(f"  {Colors.ORANGE}deactivate{Colors.END}")
    elif current_platform == "Darwin":
        print("Detected platform: MacOS")
        if not Path("venv").is_dir():
            print("To create virtualenv, run")
            print(f"  {Colors.ORANGE}python3 -m venv venv{Colors.END}")
        print("To activate virtualenv, run")
        print(f"  {Colors.ORANGE}source venv/bin/activate{Colors.END}")
        print("To install colrev/colrev, run")
        print(f"  {Colors.ORANGE}python -m pip install colrev{Colors.END}")
        print("To deactivate virtualenv, run")
        print(f"  {Colors.ORANGE}deactivate{Colors.END}")
    elif current_platform == "Windows":
        print("Detected platform: Windows")
        if not Path("venv").is_dir():
            print("To create virtualenv, run")
            print(f"  {Colors.ORANGE}python -m venv venv{Colors.END}")
        print("To activate virtualenv, run")
        print(f"  {Colors.ORANGE}venv\\Scripts\\Activate.ps1{Colors.END}")
        print("To install colrev/colrev, run")
        print(f"  {Colors.ORANGE}python -m pip install colrev{Colors.END}")
        print("To deactivate virtualenv, run")
        print(f"  {Colors.ORANGE}deactivate{Colors.END}")
    else:
        print(
            "Platform not detected... "
            "cannot provide infos in how to activate virtualenv"
        )
