#!/usr/bin/env python3
"""Hook for sharing in CoLRev repositories"""
import colrev.review_manager
from colrev.constants import OperationsType


def main() -> int:
    """Main entrypoint for the hook"""

    review_manager = colrev.review_manager.ReviewManager()
    review_manager.notified_next_operation = OperationsType.check
    advisor = review_manager.get_advisor()
    sharing_advice = advisor.get_sharing_instructions()
    print(sharing_advice["msg"])

    return sharing_advice["status"]


if __name__ == "__main__":
    raise SystemExit(main())
