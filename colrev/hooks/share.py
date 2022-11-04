#!/usr/bin/env python3
import colrev.review_manager


def main() -> int:

    review_manager = colrev.review_manager.ReviewManager()
    ret = review_manager.sharing()

    print(ret["msg"])

    return ret["status"]


if __name__ == "__main__":
    raise SystemExit(main())
