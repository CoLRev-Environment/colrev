#!/usr/bin/env python3
"""Hook to check CoLRev repositories"""
import colrev.review_manager


def main() -> int:
    """Main entrypoint for the checks"""

    review_manager = colrev.review_manager.ReviewManager()
    ret = review_manager.check_repo()
    print(ret)

    return ret["status"]


if __name__ == "__main__":
    raise SystemExit(main())
