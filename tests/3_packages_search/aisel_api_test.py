from pathlib import Path
from unittest.mock import Mock

import colrev.search_file
from colrev.constants import Fields
from colrev.constants import SearchType
from colrev.packages.ais_library.src.aisel_api import AISeLAPI


def test_get_ais_query_return_loads_and_maps_enl_records() -> None:
    response = Mock()
    response.text = """%T A test record
%0 Journal Article
%A Doe, Jane
%B Test Journal
%D 2024
%U https://aisel.aisnet.org/test/123
"""
    session = Mock()
    session.get.return_value = response
    search_file = colrev.search_file.ExtendedSearchFile(
        platform="colrev.ais_library",
        search_results_path=Path("data/search/aisel.bib"),
        search_type=SearchType.API,
        search_string="",
        comment="",
        version="0.1.0",
    )
    search_file.search_parameters = {"query": "digital"}

    records = AISeLAPI(search_file=search_file, session=session).get_ais_query_return()

    assert records == [
        {
            Fields.ENTRYTYPE: "article",
            Fields.ID: "test/123",
            Fields.TITLE: "A test record",
            Fields.AUTHOR: "Doe, Jane",
            Fields.JOURNAL: "Test Journal",
            Fields.YEAR: "2024",
            Fields.URL: "https://aisel.aisnet.org/test/123",
        }
    ]
    session.get.assert_called_once()
