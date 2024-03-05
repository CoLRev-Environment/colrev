#!/usr/bin/env python3
"""Hook for reporting in CoLRev projects"""
import sys
from pathlib import Path

import colrev.review_manager
from colrev.constants import ExitCodes


def main() -> int:
    """Main entrypoint for the reporting"""

    print(sys.argv)
    msgfile = Path(sys.argv[1])

    review_manager = colrev.review_manager.ReviewManager()
    review_manager.report(msg_file=msgfile)

    return ExitCodes.SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
