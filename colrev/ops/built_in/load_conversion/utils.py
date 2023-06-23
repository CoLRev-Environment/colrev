#! /usr/bin/env python
"""Load conversion based on zotero importers (ris, rdf, json, mods, ...)"""
from __future__ import annotations

import re
from pathlib import Path


def apply_ris_fixes(*, filename: Path) -> None:
    """Fix common defects in RIS files"""

    # Error to fix: for lists of keywords, each line should start with the KW tag

    with open(filename, encoding="UTF-8") as file:
        lines = [line.rstrip("\n") for line in file]  # .rstrip()
        processing_tag = ""
        for i, line in enumerate(lines):
            tag_match = re.match(r"^[A-Z][A-Z0-9]+(\s+)-", line)  # |^ER\s?|^EF\s?
            if tag_match:
                processing_tag = tag_match.group()
            elif line == "":
                processing_tag = ""
                continue
            elif processing_tag == "":
                continue
            else:
                lines[i] = f"{processing_tag} {line}"

    with open(filename, "w", encoding="utf-8") as file:
        for line in lines:
            file.write(f"{line}\n")
