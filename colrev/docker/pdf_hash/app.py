#! /usr/bin/env python
import sys

import imagehash
from pdf2image import convert_from_path


def main():
    pdf_path = sys.argv[1]
    page_nr = sys.argv[2]
    hash_size = sys.argv[3]

    pdf_path = "/home/docker/" + pdf_path

    res = imagehash.average_hash(
        convert_from_path(pdf_path, first_page=int(page_nr), last_page=int(page_nr))[0],
        hash_size=int(hash_size),
    )
    print(res)


if __name__ == "__main__":
    main()
