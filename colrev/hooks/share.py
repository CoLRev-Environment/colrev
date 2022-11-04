#!/usr/bin/env python3
"""Hook for sharing in CoLRev repositories"""
import colrev.review_manager


def main() -> int:
    """Main entrypoint for the hook"""

    review_manager = colrev.review_manager.ReviewManager()
    ret = review_manager.sharing()

    print(ret["msg"])

    return ret["status"]


if __name__ == "__main__":
    raise SystemExit(main())
