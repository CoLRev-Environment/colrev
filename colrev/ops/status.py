#! /usr/bin/env python3
"""CoLRev status operation: Display the project status."""
from __future__ import annotations

import csv
import io
import typing
from dataclasses import dataclass

import yaml
from jinja2 import Environment
from jinja2 import FunctionLoader

import colrev.env.utils
import colrev.process
import colrev.record
import colrev.ui_cli.cli_colors as colors


class Status(colrev.process.Process):
    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        super().__init__(
            review_manager=review_manager,
            process_type=colrev.process.ProcessType.explore,
        )

    def get_analytics(self) -> dict:

        analytics_dict = {}
        git_repo = self.review_manager.dataset.get_repo()

        revlist = list(
            (
                commit.hexsha,
                commit.author.name,
                commit.committed_date,
                (commit.tree / "status.yaml").data_stream.read(),
            )
            for commit in git_repo.iter_commits(paths="status.yaml")
        )
        for ind, (commit_id, commit_author, committed_date, filecontents) in enumerate(
            revlist
        ):
            try:
                var_t = io.StringIO(filecontents.decode("utf-8"))

                # TBD: we could simply include the whole status.yaml
                # (to create a general-purpose status analyzer)
                # -> flatten nested structures (e.g., overall/currently)
                # -> integrate with get_status (current data) -
                # and get_prior? (levels: aggregated_statistics vs. record-level?)

                data_loaded = yaml.safe_load(var_t)
                analytics_dict[len(revlist) - ind] = {
                    "commit_id": commit_id,
                    "commit_author": commit_author,
                    "committed_date": committed_date,
                    "search": data_loaded["colrev_status"]["overall"]["md_retrieved"],
                    "included": data_loaded["colrev_status"]["overall"]["rev_included"],
                }
            except (IndexError, KeyError):
                pass

        keys = list(analytics_dict.values())[0].keys()

        with open("analytics.csv", "w", newline="", encoding="utf8") as output_file:
            dict_writer = csv.DictWriter(output_file, keys)
            dict_writer.writeheader()
            dict_writer.writerows(reversed(analytics_dict.values()))

        return analytics_dict

    def get_review_status_report(self, *, commit_report: bool = False) -> str:

        status_stats = self.review_manager.get_status_stats()

        environment = Environment(
            loader=FunctionLoader(colrev.env.utils.load_jinja_template)
        )
        template = environment.get_template("template/status.txt")
        content = template.render(status_stats=status_stats, colors=colors)

        if commit_report:
            content = (
                content.replace(colors.RED, "")
                .replace(colors.GREEN, "")
                .replace(colors.ORANGE, "")
                .replace(colors.BLUE, "")
                .replace(colors.END, "")
                .replace(" 🎉", "")
                .replace("🎉", "")
            )
            # content = content.replace("Status\n\n", "Status\n")

        return content


@dataclass
class StatusStats:
    # pylint: disable=too-many-instance-attributes
    atomic_steps: int
    nr_curated_records: int
    currently: StatusStatsCurrently
    overall: StatusStatsOverall
    completed_atomic_steps: int
    completeness_condition: bool

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
    ) -> None:

        self.review_manager = review_manager
        self._record_header_list = self.review_manager.dataset.get_record_header_list()

        self.status_list = [x["colrev_status"] for x in self._record_header_list]
        self.screening_criteria = [
            x["screening_criteria"]
            for x in self._record_header_list
            if x["screening_criteria"] not in ["", "NA"]
        ]
        self.md_duplicates_removed = sum(
            (x["colrev_origin"].count(";")) for x in self._record_header_list
        )

        origin_list = [x["colrev_origin"] for x in self._record_header_list]
        self.record_links = 0
        for origin in origin_list:
            nr_record_links = origin.count(";")
            self.record_links += nr_record_links + 1

        criteria = list(review_manager.settings.screen.criteria.keys())
        self.screening_statistics = {crit: 0 for crit in criteria}
        for screening_case in self.screening_criteria:
            for criterion in screening_case.split(";"):
                criterion_name, decision = criterion.split("=")
                if "out" == decision:
                    self.screening_statistics[criterion_name] += 1

        self.currently = self.StatusStatsCurrently(status_stats=self)
        self.overall = self.StatusStatsOverall(status_stats=self)

        self.completed_atomic_steps = 0
        self.nr_incomplete = 0

        self.overall_stats_backward_calculation()

        self.currently.non_processed = (
            self.currently.md_imported
            + self.currently.md_retrieved
            + self.currently.md_needs_manual_preparation
            + self.currently.md_prepared
        )

        self.currently.md_retrieved = self.overall.md_retrieved - self.record_links

        self.completeness_condition = (0 == self.nr_incomplete) and (
            0 == self.currently.md_retrieved
        )

        self.currently.exclusion = self.screening_statistics

        self.overall.rev_screen = self.overall.pdf_prepared

        self.overall.rev_prescreen = self.overall.md_processed
        self.currently.pdf_needs_retrieval = self.currently.rev_prescreen_included

        colrev_masterdata_items = [
            x["colrev_masterdata_provenance"] for x in self._record_header_list
        ]
        self.nr_curated_records = len(
            [x for x in colrev_masterdata_items if "CURATED:" in x]
        )
        if review_manager.settings.project.curated_masterdata:
            self.nr_curated_records = self.overall.md_processed

        self.atomic_steps = (
            # initially, all records have to pass 8 operations
            8 * self.overall.md_retrieved
            # for removed duplicates, 5 operations are no longer needed
            - 5 * self.currently.md_duplicates_removed
            # for rev_prescreen_excluded, 4 operations are no longer needed
            - 4 * self.currently.rev_prescreen_excluded
            - 3 * self.currently.pdf_not_available
            - self.currently.rev_excluded
        )

        self.perc_curated = 0
        denominator = (
            self.overall.md_processed
            + self.currently.md_prepared
            + self.currently.md_needs_manual_preparation
            + self.currently.md_imported
        )

        if denominator > 0:
            self.perc_curated = int((self.nr_curated_records / (denominator)) * 100)

    def overall_stats_backward_calculation(self) -> None:
        self.review_manager.logger.debug(
            "Set overall colrev_status statistics (going backwards)"
        )
        visited_states = []
        current_state = colrev.record.RecordState.rev_synthesized  # start with the last
        atomic_step_number = 0
        while True:
            self.review_manager.logger.debug(
                "current_state: %s with %s",
                current_state,
                getattr(self.overall, str(current_state)),
            )
            if colrev.record.RecordState.md_prepared == current_state:
                overall_md_prepared = (
                    getattr(self.overall, str(current_state))
                    + self.md_duplicates_removed
                )
                getattr(self.overall, str(current_state), overall_md_prepared)

            states_to_consider = [current_state]
            predecessors: list[dict[str, typing.Any]] = [
                {
                    "trigger": "init",
                    "source": colrev.record.RecordState.md_imported,
                    "dest": colrev.record.RecordState.md_imported,
                }
            ]
            # Go backward through the process model
            predecessor = None
            while predecessors:
                predecessors = [
                    t
                    for t in colrev.process.ProcessModel.transitions
                    if t["source"] in states_to_consider
                    and t["dest"] not in visited_states
                ]
                for predecessor in predecessors:
                    self.review_manager.logger.debug(
                        " add %s from %s (predecessor transition: %s)",
                        getattr(self.overall, str(predecessor["dest"])),
                        str(predecessor["dest"]),
                        predecessor["trigger"],
                    )
                    setattr(
                        self.overall,
                        str(current_state),
                        (
                            getattr(self.overall, str(current_state))
                            + getattr(self.overall, str(predecessor["dest"]))
                        ),
                    )
                    visited_states.append(predecessor["dest"])
                    if predecessor["dest"] not in states_to_consider:
                        states_to_consider.append(predecessor["dest"])
                if len(predecessors) > 0:
                    if predecessors[0]["trigger"] != "init":
                        self.completed_atomic_steps += getattr(
                            self.overall, str(predecessor["dest"])
                        )
            atomic_step_number += 1
            # Note : the following does not consider multiple parallel steps.
            for trans_for_completeness in [
                t
                for t in colrev.process.ProcessModel.transitions
                if current_state == t["dest"]
            ]:
                self.nr_incomplete += getattr(
                    self.currently, str(trans_for_completeness["source"])
                )

            t_list = [
                t
                for t in colrev.process.ProcessModel.transitions
                if current_state == t["dest"]
            ]
            transition: dict = t_list.pop()
            if current_state == colrev.record.RecordState.md_imported:
                break
            current_state = transition["source"]  # go a step back
            self.currently.non_completed += getattr(self.currently, str(current_state))

    def get_active_metadata_operation_info(self) -> str:
        infos = []
        if self.currently.md_retrieved > 0:
            infos.append(f"{self.currently.md_retrieved} to load")
        if self.currently.md_imported > 0:
            infos.append(f"{self.currently.md_imported} to prepare")
        if self.currently.md_needs_manual_preparation > 0:
            infos.append(
                f"{self.currently.md_needs_manual_preparation} to prepare manually"
            )
        if self.currently.md_prepared > 0:
            infos.append(f"{self.currently.md_prepared} to deduplicate")
        return ", ".join(infos)

    def get_active_pdf_operation_info(self) -> str:
        infos = []
        if self.currently.rev_prescreen_included > 0:
            infos.append(f"{self.currently.rev_prescreen_included} to retrieve")
        if self.currently.pdf_needs_manual_retrieval > 0:
            infos.append(
                f"{self.currently.pdf_needs_manual_retrieval} to retrieve manually"
            )
        if self.currently.pdf_imported > 0:
            infos.append(f"{self.currently.pdf_imported} to prepare")
        if self.currently.pdf_needs_manual_preparation > 0:
            infos.append(
                f"{self.currently.pdf_needs_manual_preparation} to prepare manually"
            )
        return ", ".join(infos)

    def get_transitioned_records(
        self, current_origin_states_dict: dict
    ) -> list[typing.Dict]:

        committed_origin_states_dict = (
            self.review_manager.dataset.get_committed_origin_states_dict()
        )
        transitioned_records = []
        for (
            committed_origin,
            committed_colrev_status,
        ) in committed_origin_states_dict.items():

            transitioned_record = {
                "origin": committed_origin,
                "source": committed_colrev_status,
                "dest": current_origin_states_dict.get(
                    committed_origin, "no_source_state"
                ),
            }

            process_type = [
                x["trigger"]
                for x in colrev.process.ProcessModel.transitions
                if str(x["source"]) == transitioned_record["source"]
                and str(x["dest"]) == transitioned_record["dest"]
            ]
            if (
                len(process_type) == 0
                and transitioned_record["source"] != transitioned_record["dest"]
            ):
                transitioned_record["process_type"] = "invalid_transition"

            if len(process_type) > 0:
                transitioned_record["process_type"] = process_type[0]
                transitioned_records.append(transitioned_record)

        return transitioned_records

    def get_priority_transition(self, *, current_origin_states_dict: dict) -> list:

        # get "earliest" states (going backward)
        earliest_state = []
        search_states = ["rev_synthesized"]
        while True:
            if any(
                search_state in current_origin_states_dict.values()
                for search_state in search_states
            ):
                earliest_state = [
                    search_state
                    for search_state in search_states
                    if search_state in current_origin_states_dict.values()
                ]
            search_states = [
                str(x["source"])
                for x in colrev.process.ProcessModel.transitions
                if str(x["dest"]) in search_states
            ]
            if [] == search_states:
                break
        # print(f'earliest_state: {earliest_state}')

        # next: get the priority transition for the earliest states
        priority_transitions = [
            x["trigger"]
            for x in colrev.process.ProcessModel.transitions
            if str(x["source"]) in earliest_state
        ]
        # print(f'priority_transitions: {priority_transitions}')

        priority_transitions = list(set(priority_transitions))

        self.review_manager.logger.debug(
            f"priority_processing_function: {priority_transitions}"
        )
        return priority_transitions

    def get_active_processing_functions(
        self, *, current_origin_states_dict: dict
    ) -> list:

        active_processing_functions = []
        for state in current_origin_states_dict.values():
            srec = colrev.process.ProcessModel(state=state)
            valid_transitions = srec.get_valid_transitions()
            active_processing_functions.extend(valid_transitions)

        self.review_manager.logger.debug(
            f"active_processing_functions: {active_processing_functions}"
        )
        return active_processing_functions

    def get_processes_in_progress(self, *, transitioned_records) -> list:
        in_progress_processes = list({x["process_type"] for x in transitioned_records})
        self.review_manager.logger.debug(
            f"in_progress_processes: {in_progress_processes}"
        )
        return in_progress_processes

    @dataclass
    class StatusStatsParent:
        # pylint: disable=too-many-instance-attributes
        # Note : StatusStatsCurrently and StatusStatsOverall start with the same frequencies
        def __init__(
            self,
            *,
            status_stats: StatusStats,
        ) -> None:
            self.status_stats = status_stats

            self.md_retrieved = self.get_freq("md_retrieved")

            self.md_imported = self.get_freq("md_imported")
            self.md_needs_manual_preparation = self.get_freq(
                "md_needs_manual_preparation"
            )
            self.md_prepared = self.get_freq("md_prepared")
            self.md_processed = self.get_freq("md_processed")
            self.rev_prescreen_excluded = self.get_freq("rev_prescreen_excluded")
            self.rev_prescreen_included = self.get_freq("rev_prescreen_included")
            self.pdf_needs_manual_retrieval = self.get_freq(
                "pdf_needs_manual_retrieval"
            )
            self.pdf_imported = self.get_freq("pdf_imported")
            self.pdf_not_available = self.get_freq("pdf_not_available")
            self.pdf_needs_manual_preparation = self.get_freq(
                "pdf_needs_manual_preparation"
            )
            self.pdf_prepared = self.get_freq("pdf_prepared")
            self.rev_excluded = self.get_freq("rev_excluded")
            self.rev_included = self.get_freq("rev_included")
            self.rev_synthesized = self.get_freq("rev_synthesized")
            self.md_duplicates_removed = self.status_stats.md_duplicates_removed

        def get_freq(self, colrev_status: str) -> int:
            return len([x for x in self.status_stats.status_list if colrev_status == x])

    @dataclass
    class StatusStatsCurrently(StatusStatsParent):
        # pylint: disable=too-many-instance-attributes
        md_retrieved: int
        md_imported: int
        md_prepared: int
        md_needs_manual_preparation: int
        md_duplicates_removed: int
        md_processed: int
        non_processed: int
        rev_prescreen_excluded: int
        rev_prescreen_included: int
        pdf_needs_retrieval: int
        pdf_needs_manual_retrieval: int
        pdf_not_available: int
        pdf_imported: int
        pdf_needs_manual_preparation: int
        pdf_prepared: int
        rev_excluded: int
        rev_included: int
        rev_synthesized: int
        non_completed: int
        exclusion: dict

        def __init__(
            self,
            *,
            status_stats: StatusStats,
        ) -> None:
            self.exclusion: typing.Dict[str, int] = {}
            self.non_completed = 0
            self.non_processed = 0
            super().__init__(status_stats=status_stats)
            self.pdf_needs_retrieval = self.rev_prescreen_included

    @dataclass
    class StatusStatsOverall(StatusStatsParent):
        # pylint: disable=too-many-instance-attributes
        md_retrieved: int
        md_imported: int
        md_needs_manual_preparation: int
        md_prepared: int
        md_processed: int
        rev_prescreen: int
        rev_prescreen_excluded: int
        rev_prescreen_included: int
        pdf_needs_manual_retrieval: int
        pdf_imported: int
        pdf_not_available: int
        pdf_needs_manual_preparation: int
        pdf_prepared: int
        rev_excluded: int
        rev_included: int
        rev_screen: int
        rev_synthesized: int

        def __init__(
            self,
            *,
            status_stats: StatusStats,
        ) -> None:
            self.rev_screen = 0
            self.rev_prescreen = 0
            super().__init__(status_stats=status_stats)
            self.md_retrieved = self.get_nr_search(
                search_dir=self.status_stats.review_manager.search_dir
            )

        def get_nr_search(self, *, search_dir) -> int:

            if not search_dir.is_dir():
                return 0
            bib_files = search_dir.glob("*.bib")
            number_search = 0
            for search_file in bib_files:
                number_search += self.status_stats.review_manager.dataset.get_nr_in_bib(
                    file_path=search_file
                )
            return number_search


if __name__ == "__main__":
    pass
