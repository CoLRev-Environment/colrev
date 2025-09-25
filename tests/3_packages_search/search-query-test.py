#!/usr/bin/env python
"""Test the eric SearchSource"""
from search_query import AndQuery
from search_query import OrQuery

from colrev.packages.crossref.src.crossref_search_source import CrossrefSearchSource

# pylint: disable=line-too-long


def test_crossref_query() -> None:
    """Test crossref query"""

    # TODO : commit in separate branch

    # digital+virtual
    query = CrossrefSearchSource.parse_query(
        query="/works?query.title=room+at+the+bottom&query.author=richard+feynman",
        syntax_version="crossref_1.0",
    )
    # print(query)
    print(query.to_string())

    digital_synonyms = OrQuery(
        ["digital", "virtual", "online"], search_field="Abstract"
    )
    work_synonyms = OrQuery(["work", "labor", "service"], search_field="Abstract")
    query_to_serialize = AndQuery(
        [digital_synonyms, work_synonyms], search_field="Author Keywords"
    )
    query_str = CrossrefSearchSource.get_query_string(
        query=query_to_serialize, syntax_version="crossref_1.0"
    )
    print(query_str)

    raise Exception
