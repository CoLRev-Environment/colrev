#!/usr/bin/env python3
from __future__ import annotations

import typing

import colrev.built_in.search_sources as built_in_search_sources
import colrev.process


class SearchSources:

    built_in_scripts: dict[str, dict[str, typing.Any]] = {
        "dblp": {"endpoint": built_in_search_sources.DBLP},
        "acm_digital_library": {"endpoint": built_in_search_sources.ACMDigitalLibrary},
        "pubmed": {"endpoint": built_in_search_sources.PubMed},
        "wiley": {"endpoint": built_in_search_sources.WileyOnlineLibrary},
        "ais_library": {"endpoint": built_in_search_sources.AISeLibrarySearchSource},
        "google_scholar": {
            "endpoint": built_in_search_sources.GoogleScholarSearchSource
        },
        "web_of_science": {
            "endpoint": built_in_search_sources.WebOfScienceSearchSource
        },
        "scopus": {"endpoint": built_in_search_sources.ScopusSearchSource},
        "PDF": {"endpoint": built_in_search_sources.PDFSearchSource},
        "PDF backward search": {
            "endpoint": built_in_search_sources.BackwardSearchSearchSource
        },
    }

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        required_search_scripts = [
            r for s in review_manager.settings.sources for r in s.source_prep_scripts
        ] + [{"endpoint": k} for k in list(self.built_in_scripts.keys())]

        self.type = colrev.process.ProcessType.check

        adapter_manager = review_manager.get_adapter_manager()
        self.search_source_scripts: dict[
            str, typing.Any
        ] = adapter_manager.load_scripts(
            process=self, scripts=required_search_scripts, script_type="SearchSource"
        )


if __name__ == "__main__":
    pass
