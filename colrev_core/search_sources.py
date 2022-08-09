from __future__ import annotations

import pprint
import re
import typing
from pathlib import Path

import colrev_core.built_in.search_sources as built_in_search_sources
import colrev_core.environment
import colrev_core.load
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
        self.search_source_scripts: dict[
            str, typing.Any
        ] = colrev_core.environment.AdapterManager.load_scripts(
            PROCESS=self, scripts=required_search_scripts, script_type="SearchSource"
        )

    def apply_source_heuristics(
        self, *, filepath: Path
    ) -> list[colrev_core.settings.SearchSource]:
        """Apply heuristics to identify source"""

        data = ""
        try:
            data = filepath.read_text()
        except UnicodeDecodeError:
            pass

        results_list = []

        for source_name, endpoint in self.search_source_scripts.items():
            res = endpoint.heuristic(filepath, data)
            if res["confidence"] > 0:
                search_type = colrev_core.settings.SearchType("DB")

                res["source_name"] = source_name
                res["source_prep_scripts"] = (
                    [source_name] if callable(endpoint.prepare) else []
                )
                if "search_script" not in res:
                    res["search_script"] = {}

                if "filename" not in res:
                    # Correct the file extension if necessary
                    if re.search("%0", data) and filepath.suffix not in [".enl"]:
                        new_filename = filepath.with_suffix(".enl")
                        print(
                            f"\033[92mRenaming to {new_filename} "
                            "(because the format is .enl)\033[0m"
                        )
                        filepath.rename(new_filename)
                        filepath = new_filename

                if "conversion_script" not in res:
                    res[
                        "conversion_script"
                    ] = colrev_core.load.Loader.get_conversion_script(filepath=filepath)

                SOURCE_CANDIDATE = colrev_core.settings.SearchSource(
                    filename=filepath,
                    search_type=search_type,
                    source_name=source_name,
                    source_identifier=res["source_identifier"],
                    search_parameters="",
                    search_script=res["search_script"],
                    conversion_script=res["conversion_script"],
                    source_prep_scripts=[
                        {"endpoint": s}
                        for s in res["source_prep_scripts"]  # type: ignore
                    ],
                    comment="",
                )

                results_list.append(SOURCE_CANDIDATE)

        if 0 == len(results_list):
            SOURCE_CANDIDATE = colrev_core.settings.SearchSource(
                filename=Path(filepath),
                search_type=colrev_core.settings.SearchType("DB"),
                source_name="NA",
                source_identifier="NA",
                search_parameters="NA",
                search_script={},  # Note : primarily adding files (not feeds)
                conversion_script={"endpoint": "bibtex"},
                source_prep_scripts=[],
                comment="",
            )
            results_list.append(SOURCE_CANDIDATE)

        return results_list


if __name__ == "__main__":
    pass
