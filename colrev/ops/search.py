#! /usr/bin/env python
"""CoLRev search operation: Search for relevant records."""
from __future__ import annotations

import typing
from pathlib import Path

import colrev.exceptions as colrev_exceptions
import colrev.process.operation
import colrev.search_file
from colrev import utils
from colrev.constants import Colors
from colrev.constants import EndpointType
from colrev.constants import Fields
from colrev.constants import OperationsType
from colrev.constants import SearchType
from colrev.package_manager.package_manager import PackageManager
from colrev.writer.write_utils import write_file


class Search(colrev.process.operation.Operation):
    """Search for new records"""

    type = OperationsType.search

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=self.type,
            notify_state_transition_operation=notify_state_transition_operation,
        )
        self.review_manager = review_manager
        self.sources = review_manager.settings.sources
        self.package_manager = PackageManager()

    def _get_search_sources(
        self, *, selection_str: str
    ) -> list[colrev.search_file.ExtendedSearchFile]:

        search_histories = self.review_manager.settings.sources
        sources_selected = search_histories
        if selection_str != "all":
            selected_filenames = {Path(f).name for f in selection_str.split(",")}
            sources_selected = [
                s
                for s in self.sources
                if s.search_results_path.name in selected_filenames
            ]

        assert len(sources_selected) != 0
        return sources_selected

    def _remove_forthcoming(
        self, source: colrev.search_file.ExtendedSearchFile
    ) -> None:
        """Remove forthcoming papers from a SearchSource"""

        if self.review_manager.settings.search.retrieve_forthcoming:
            return

        if source.search_results_path.suffix != ".bib":
            print(f"{source.search_results_path.suffix} not yet supported")
            return

        records = colrev.loader.load_utils.load(
            filename=source.search_results_path,
            logger=self.review_manager.logger,
        )

        record_list = list(records.values())
        before = len(record_list)
        record_list = [
            r for r in record_list if "forthcoming" != r.get(Fields.YEAR, "")
        ]
        removed = before - len(record_list)
        self.review_manager.logger.info(
            f"{Colors.GREEN}Removed {removed} forthcoming{Colors.END}"
        )
        records = {r[Fields.ID]: r for r in record_list}

        write_file(records_dict=records, filename=source.search_results_path)

    # pylint: disable=no-self-argument
    def _check_source_selection_exists(var_name: str) -> typing.Callable:  # type: ignore
        """Check if the source selection exists"""

        # pylint: disable=no-self-argument
        def check_accepts(func_in: typing.Callable) -> typing.Callable:
            def new_f(self, *args, **kwds) -> typing.Callable:  # type: ignore
                if kwds.get(var_name, None) is None:
                    return func_in(self, *args, **kwds)
                for search_source in kwds[var_name].split(","):
                    if Path(search_source) not in [
                        s.search_results_path
                        for s in self.review_manager.settings.sources
                    ]:
                        raise colrev_exceptions.ParameterError(
                            parameter="select",
                            value=kwds[var_name],
                            options=[
                                str(s.search_results_path)
                                for s in self.review_manager.settings.sources
                            ],
                        )
                return func_in(self, *args, **kwds)

            new_f.__name__ = func_in.__name__
            return new_f

        return check_accepts

    def get_new_search_files(self) -> list[Path]:
        """Retrieve new search files (not yet registered in settings)"""

        search_dir = self.review_manager.paths.search
        files = [
            f.relative_to(self.review_manager.path) for f in search_dir.glob("**/*")
        ]

        # Only files that are not yet registered
        # (also exclude bib files corresponding to a registered file)
        files = [
            f
            for f in files
            if f
            not in [s.search_results_path for s in self.review_manager.settings.sources]
            and f.suffix
            in [
                ".bib",
                ".nbib",
                ".ris",
                ".enl",
                ".csv",
                ".xls",
                "xlsx",
                ".md",
                ".txt",
                ".json",
            ]
            # Note: do not cover .Identifier, ".~lock" etc.
            and not f.name.startswith(".")
            and not f.name.endswith("_search_history.json")
        ]

        return sorted(list(set(files)))

    def _get_heuristics_results_list(
        self,
        *,
        filepath: Path,
        search_sources: dict,
        data: str,
    ) -> list:
        results_list = []
        for endpoint in search_sources:
            try:
                search_source_class = self.package_manager.get_package_endpoint_class(
                    package_type=EndpointType.search_source,
                    package_identifier=endpoint,
                )
                res = search_source_class.heuristic(filepath, data)  # type: ignore
                self.review_manager.logger.debug(f"- {endpoint}: {res['confidence']}")
                if res["confidence"] == 0.0:
                    continue
                result_item = {}

                res["endpoint"] = endpoint

                search_type = SearchType.DB
                # Note : as the identifier, we use the filename
                # (if search results are added by file/not via the API)

                version = getattr(
                    search_source_class, "CURRENT_SYNTAX_VERSION", "0.1.0"
                )
                source_candidate = colrev.search_file.ExtendedSearchFile(
                    platform=endpoint,
                    search_results_path=filepath,
                    search_type=search_type,
                    search_string="",
                    comment="",
                    version=version,
                )

                result_item["source_candidate"] = source_candidate
                result_item["confidence"] = res["confidence"]

                results_list.append(result_item)
            except (
                colrev_exceptions.UnsupportedImportFormatError,
                ModuleNotFoundError,
            ):
                continue
        return results_list

    def _apply_source_heuristics(
        self, *, filepath: Path, search_sources: dict
    ) -> list[typing.Dict]:
        """Apply heuristics to identify source"""

        data = ""
        try:
            data = filepath.read_text()
        except UnicodeDecodeError:
            pass

        results_list = self._get_heuristics_results_list(
            filepath=filepath,
            search_sources=search_sources,
            data=data,
        )

        # Reduce the results_list when there are results with very high confidence
        if [r for r in results_list if r["confidence"] > 0.95]:
            results_list = [r for r in results_list if r["confidence"] > 0.8]

        return results_list

    def add_most_likely_sources(self) -> None:
        """Get the most likely SearchSources

        returns a dictionary:
        {"filepath": [SearchSource1,..]}
        """

        new_search_files = self.get_new_search_files()
        for filename in new_search_files:
            heuristic_list = self.get_new_source_heuristic(filename)

            for results_list in heuristic_list:
                # Use the last / unknown_source
                max_conf = 0.0
                best_candidate_pos = 0
                for i, heuristic_candidate in enumerate(results_list):
                    if heuristic_candidate["confidence"] > max_conf:
                        best_candidate_pos = i + 1
                        max_conf = heuristic_candidate["confidence"]
                if not any(c["confidence"] > 0.1 for c in results_list):
                    source = [
                        x
                        for x in results_list
                        if "unknown_source" in x["source_candidate"].platform
                    ][0]
                else:
                    selection = str(best_candidate_pos)
                    source = results_list[int(selection) - 1]

                self.review_manager.settings.sources.append(source["source_candidate"])
        self.review_manager.save_settings()
        self.review_manager.create_commit(msg="Add new search sources")

    def get_new_source_heuristic(self, filename: Path) -> list:
        """Get the heuristic result list of SearchSources candidates

        returns a dictionary:
        {"filepath": ({"search_source": SourceCandidate1", "confidence": 0.98},..]}
        """

        self.review_manager.logger.debug("Load available search_source endpoints...")

        search_sources = self.package_manager.discover_installed_packages(
            package_type=EndpointType.search_source
        )

        heuristic_results = []
        self.review_manager.logger.debug(f"Discover new DB source file: {filename}")

        heuristic_results.append(
            self._apply_source_heuristics(
                filepath=filename,
                search_sources=search_sources,
            )
        )

        return heuristic_results

    def add_source_and_search(
        self, search_file: colrev.search_file.ExtendedSearchFile
    ) -> None:
        """Add a SearchSource and run the search"""

        search_file.save()
        self.review_manager.dataset.git_repo.add_changes(
            search_file.get_search_history_path()
        )

        self.review_manager.create_commit(
            msg=f"Search: add {search_file.platform}:{search_file.search_type} → "
            f"data/search/{search_file.get_search_history_path().name}",
        )
        if not search_file.get_search_history_path().is_file():
            print()
            self.main(
                selection_str=str(search_file.get_search_history_path()), rerun=True
            )

    @_check_source_selection_exists(  # pylint: disable=too-many-function-args
        "selection_str"
    )
    @colrev.process.operation.Operation.decorate()
    def main(
        self,
        *,
        selection_str: str = "all",
        rerun: bool,
        skip_commit: bool = False,
    ) -> None:
        """Search for records (main entrypoint)"""

        rerun_flag = "" if not rerun else f" ({Colors.GREEN}rerun{Colors.END})"
        self.review_manager.logger.info(f"Search{rerun_flag}")
        self.review_manager.logger.info(
            "Retrieve new records from an API or files (search sources)."
        )
        self.review_manager.logger.info(
            "See https://colrev-environment.github.io/colrev/manual/metadata_retrieval/search.html"
        )

        # Reload the settings because the search sources may have been updated
        self.review_manager.settings = self.review_manager.load_settings()
        for source in self._get_search_sources(selection_str=selection_str):
            try:

                if not self.review_manager.high_level_operation:
                    print()
                self.review_manager.logger.info(
                    f"search: {source.platform}:{source.search_type} → "
                    f"data/search/{source.search_results_path}"
                )

                search_source_class = self.package_manager.get_package_endpoint_class(
                    package_type=EndpointType.search_source,
                    package_identifier=source.platform,
                )
                endpoint = search_source_class(
                    search_file=source,
                    logger=self.review_manager.logger,
                )

                endpoint.search(rerun=rerun)  # type: ignore

                self._remove_forthcoming(source)
                self.review_manager.dataset.git_repo.add_changes(
                    source.search_results_path, ignore_missing=True
                )
                if not skip_commit:
                    self.review_manager.create_commit(
                        msg=f"Search: run {source.platform}:{source.search_type} → "
                        f"data/search/{source.search_results_path.name}",
                    )
            except colrev_exceptions.ServiceNotAvailableException:
                self.review_manager.logger.warning("ServiceNotAvailableException")
            except colrev_exceptions.SearchNotAutomated as exc:
                self.review_manager.logger.warning(exc)
            except colrev_exceptions.MissingDependencyError as exc:
                self.review_manager.logger.warning(exc)
            except ModuleNotFoundError as exc:
                self.review_manager.logger.warning(exc)

        if utils.in_ci_environment():
            print("\n\n")
