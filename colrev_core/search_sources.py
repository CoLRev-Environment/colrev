from __future__ import annotations

import pprint
import typing

import colrev_core.built_in.search_sources as built_in_search_sources
import colrev_core.process

pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)


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

    def __init__(self, *, REVIEW_MANAGER):
        required_search_scripts = [
            r for s in REVIEW_MANAGER.settings.sources for r in s.source_prep_scripts
        ] + [{"endpoint": k} for k in list(self.built_in_scripts.keys())]

        self.type = colrev_core.process.ProcessType.check

        Adaptermanager = REVIEW_MANAGER.get_environment_service(
            service_identifier="AdapterManager"
        )
        self.search_source_scripts: dict[str, typing.Any] = Adaptermanager.load_scripts(
            PROCESS=self, scripts=required_search_scripts, script_type="SearchSource"
        )


if __name__ == "__main__":
    pass
