#! /usr/bin/env python
"""Convenience functions to load files (BiBTeX, RIS, CSV, etc.)

Usage::

    import colrev.loader.load_utils

    # Files
    records = colrev.loader.load_utils.load(filename=filename, logger=logger)

    # Strings
    records = colrev.loader.load_utils.loads(load_str=load_str, logger=logger)

    returns: records (dict)

Most formats require a mapping from the FIELDS to the standard CoLRev Fields (see CEP 002), which

- can involve merging of FIELDS (e.g. AU / author fields)
- can be conditional upon the ENTRYTYPE (e.g., publication_name: journal or booktitle)

Example BibTeX record::

    @article{Guo2021,
        title    = {How Trust Leads to Commitment on Microsourcing Platforms},
        author   = {Guo, Wenbo and Straub, Detmar W. and Zhang, Pengzhu and Cai, Zhao},
        journal  = {MIS Quarterly},
        year     = {2021}
        volume   = {45},
        number   = {3},
        pages    = {1309--1348},
        url      = {https://aisel.aisnet.org/misq/vol45/iss3/13},
        doi      = {10.25300/MISQ/2021/16100},
    }

Example ENL record::

    %T How Trust Leads to Commitment on Microsourcing Platforms
    %0 Journal Article
    %A Guo, Wenbo
    %A Straub, Detmar W.
    %A Zhang, Pengzhu
    %A Cai, Zhao
    %B Management Information Systems Quarterly
    %D 2021
    %8 September  1, 2021
    %V 45
    %N 3
    %P 1309-1348
    %U https://aisel.aisnet.org/misq/vol45/iss3/13
    %X IS research has extensively examined the role of trust in client-vendor relationships...

Example markdown reference section::

    # References

    Guo, W. and Straub, D. W. and Zhang, P. and Cai, Z. (2021). How Trust Leads to Commitment
          on Microsourcing Platforms. MIS Quarterly, 45(3), 1309--1348.


Example nbib record::

    OWN - ERIC
    TI  - How Trust Leads to Commitment on Microsourcing Platforms
    AU  - Guo, Wenbo
    AU  - Straub, Detmar W.
    AU  - Zhang, Pengzhu
    AU  - Cai, Zhao
    JT  - MIS Quarterly
    DP  - 2021
    VI  - 45
    IP  - 3
    PG  - 1309-1348

Example RIS record::

    TY  - JOUR
    AU  - Guo, Wenbo
    AU  - Straub, Detmar W.
    AU  - Zhang, Pengzhu
    AU  - Cai, Zhao
    DA  - 2021/09/01
    DO  - 10.25300/MISQ/2021/16100
    ID  - Guo2021
    T2  - Management Information Systems Quarterly
    TI  - How Trust Leads to Commitment on Microsourcing Platforms
    VL  - 45
    IS  - 3
    SP  - 1309
    EP  - 1348
    UR  - https://aisel.aisnet.org/misq/vol45/iss3/13
    PB  - Association for Information Systems
    ER  -

Example csv records::

    title;author;year;
    How Trust Leads to Commitment;Guo, W. and Straub, D.;2021;

"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import colrev.exceptions as colrev_exceptions
import colrev.loader.bib
import colrev.loader.enl
import colrev.loader.md
import colrev.loader.nbib
import colrev.loader.ris
import colrev.loader.table

if TYPE_CHECKING:  # pragma: no cover
    from typing import Callable

# pylint: disable=too-many-arguments


def load(  # type: ignore
    filename: Path,
    *,
    entrytype_setter: Callable = lambda x: x,
    field_mapper: Callable = lambda x: x,
    id_labeler: Callable = lambda x: x,
    unique_id_field: str = "",
    logger: logging.Logger = logging.getLogger(__name__),
) -> dict:
    """Load a file and return records as a dictionary"""

    if not filename.exists():
        raise colrev_exceptions.ImportException(f"File not found: {filename.name}")

    if filename.suffix == ".bib":
        parser = colrev.loader.bib.BIBLoader  # type: ignore
    elif filename.suffix in [".csv", ".xls", ".xlsx"]:
        parser = colrev.loader.table.TableLoader  # type: ignore
    elif filename.suffix == ".ris":
        parser = colrev.loader.ris.RISLoader  # type: ignore
    elif filename.suffix in [".enl", ".txt"]:
        parser = colrev.loader.enl.ENLLoader  # type: ignore
    elif filename.suffix == ".md":
        parser = colrev.loader.md.MarkdownLoader  # type: ignore
    elif filename.suffix == ".nbib":
        parser = colrev.loader.nbib.NBIBLoader  # type: ignore
    else:
        raise NotImplementedError

    return parser(
        filename=filename,
        entrytype_setter=entrytype_setter,
        field_mapper=field_mapper,
        id_labeler=id_labeler,
        unique_id_field=unique_id_field,
        logger=logger,
    ).load()


def loads(  # type: ignore
    load_string: str,
    *,
    implementation: str,
    entrytype_setter: Callable = lambda x: x,
    field_mapper: Callable = lambda x: x,
    id_labeler: Callable = lambda x: x,
    unique_id_field: str = "",
    logger: logging.Logger = logging.getLogger(__name__),
) -> dict:
    """Load a string and return records as a dictionary"""

    if implementation not in [
        "bib",
        "csv",
        "xls",
        "xlsx",
        "ris",
        "enl",
        "md",
        "nbib",
    ]:
        raise NotImplementedError

    with tempfile.NamedTemporaryFile(
        mode="wb", delete=False, suffix=f".{implementation}"
    ) as temp_file:
        temp_file.write(load_string.encode("utf-8"))
        temp_file_path = Path(temp_file.name)

    return load(
        filename=temp_file_path,
        entrytype_setter=entrytype_setter,
        field_mapper=field_mapper,
        id_labeler=id_labeler,
        unique_id_field=unique_id_field,
        logger=logger,
    )


def get_nr_records(  # type: ignore
    filename: Path,
    # logger: logging.Logger = logging.getLogger(__name__),
) -> int:
    """Get the number of records in a file"""

    if not filename.exists():
        return 0

    if filename.suffix == ".bib":
        parser = colrev.loader.bib.BIBLoader  # type: ignore
    elif filename.suffix in [".csv", ".xls", ".xlsx"]:
        parser = colrev.loader.table.TableLoader  # type: ignore
    elif filename.suffix == ".ris":
        parser = colrev.loader.ris.RISLoader  # type: ignore
    elif filename.suffix in [".enl", ".txt"]:
        parser = colrev.loader.enl.ENLLoader  # type: ignore
    elif filename.suffix == ".md":
        parser = colrev.loader.md.MarkdownLoader  # type: ignore
    elif filename.suffix == ".nbib":
        parser = colrev.loader.nbib.NBIBLoader  # type: ignore
    else:
        raise NotImplementedError

    return parser.get_nr_records(filename)
