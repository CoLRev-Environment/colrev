#! /usr/bin/env python
"""Creation of an Obsidian database as part of the data operations"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.env.utils
import colrev.record


if TYPE_CHECKING:
    import colrev.ops.data


@zope.interface.implementer(colrev.env.package_manager.DataPackageEndpointInterface)
@dataclass
class Obsidian(JsonSchemaMixin):
    """Export the sample into an Obsidian database"""

    @dataclass
    class ObsidianSettings(JsonSchemaMixin):
        """Settings for Obsidian"""

        endpoint: str
        version: str
        config: dict

        # _details = {
        #     "config": {
        #         "tooltip": "TODO"
        #     },
        # }

    settings_class = ObsidianSettings

    OBSIDIAN_PATH_RELATIVE = Path("data/obsidian")
    OBSIDIAN_PAPER_PATH_RELATIVE = Path("data/obsidian/paper")
    OBSIDIAN_INBOX_PATH_RELATIVE = Path("data/obsidian/inbox.md")

    def __init__(
        self,
        *,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

        self.endpoint_path = (
            data_operation.review_manager.path / self.OBSIDIAN_PATH_RELATIVE
        )
        self.endpoint_paper_path = (
            data_operation.review_manager.path / self.OBSIDIAN_PAPER_PATH_RELATIVE
        )
        self.endpoint_inbox_path = (
            data_operation.review_manager.path / self.OBSIDIAN_INBOX_PATH_RELATIVE
        )
        self.review_manager = data_operation.review_manager

    def get_default_setup(self) -> dict:
        """Get the default setup"""
        obsidian_endpoint_details = {
            "endpoint": "colrev_built_in.obsidian",
            "version": "0.1",
            "config": {},
        }
        return obsidian_endpoint_details

    def __get_obsidian_missing(self, *, included: list) -> list:
        in_obsidian = []
        for md_file in self.endpoint_paper_path.glob("*.md"):
            # missing: if #todo in file
            if "#todo" not in md_file.read_text():
                in_obsidian.append(str(md_file.name).replace(".md", ""))
        return [x for x in included if x not in in_obsidian]

    def __get_keywords(self, *, record_dict: dict) -> list:
        keywords = []

        tei_file = (
            self.review_manager.path
            / colrev.record.Record(data=record_dict).get_tei_filename()
        )

        if tei_file.is_file():
            tei = self.review_manager.get_tei(tei_path=tei_file)
            keywords = [x.lower().replace(" ", "-") for x in tei.get_paper_keywords()]

        if int(record_dict.get("cited_by", 0)) > 100:
            keywords.append("highly_cited")

        return keywords

    def __append_missing_records(
        self,
        *,
        data_operation: colrev.ops.data.Data,
    ) -> None:

        records_dict = data_operation.review_manager.dataset.load_records_dict()
        included = data_operation.get_record_ids_for_synthesis(records_dict)
        missing_records = self.__get_obsidian_missing(included=included)
        if len(missing_records) == 0:
            print("All records included. Nothing to export.")
            return

        # inbox_text = ""
        # if self.endpoint_inbox_path.is_file():
        #     inbox_text = self.endpoint_inbox_path.read_text()

        # if not self.endpoint_inbox_path.is_file():
        #     with open(self.endpoint_inbox_path, "w", encoding="utf-8") as inbox_file:
        #         inbox_file.write("Papers to synthesize:\n\n")

        missing_record_entities = {}
        # with open(self.endpoint_inbox_path, "a", encoding="utf-8") as inbox_file:
        for missing_record in missing_records:
            # if missing_record not in inbox_text:
            #     inbox_file.write(f"- [[{missing_record}]]\n")
            paper_summary_path = self.endpoint_paper_path / Path(f"{missing_record}.md")

            missing_record_entities[paper_summary_path] = {
                "keywords": self.__get_keywords(
                    record_dict=records_dict[missing_record]
                )
            }

        all_keywords = [x["keywords"] for x in missing_record_entities.values()]
        all_keywords = [item for sublist in all_keywords for item in sublist]

        from collections import Counter

        cnt = Counter(all_keywords)
        frequent_keywords = [k for k, v in cnt.items() if v > 2]

        # Drop research-methods related keywords:
        frequent_keywords = [
            x
            for x in frequent_keywords
            if x
            not in [
                "case-study",
                "design-science",
                "design-science-research",
                "research-agenda",
                "design-theory",
                "mixed-methods",
                "multilevel-analysis",
                "pls",
                "text-minig",
                "associate-editor",
                "chang",
                "ethnography",
                "empirical-research",
                "qualitative-study",
                "ramesh",
                "natural-experiment",
                "simulation",
                "structural-equation-modeling",
                "longitudinal-study",
            ]
        ]

        for (
            paper_summary_path,
            missing_record_entity,
        ) in missing_record_entities.items():
            if not paper_summary_path.is_file():
                paper_summary_path.parent.mkdir(exist_ok=True, parents=True)
                with open(paper_summary_path, "w", encoding="utf-8") as paper_summary:
                    selected_keywords = [
                        x
                        for x in missing_record_entity["keywords"]
                        if x in frequent_keywords and x not in ["highly_cited"]
                    ]
                    # paper_summary.write(f"#paper {' #'.join(selected_keywords)} #todo\n\n")
                    paper_summary.write(f"#{' #'.join(selected_keywords)}\n\n")
                    if "highly_cited" in missing_record_entity["keywords"]:
                        paper_summary.write("highly_cited")

        # TODO : export to csl-json (absolute PDF paths, read-only/hidden/gitignored, no provenance fields)

        # data_operation.review_manager.dataset.add_changes(path=self.OBSIDIAN_INBOX_PATH_RELATIVE)

    def update_data(
        self,
        data_operation: colrev.ops.data.Data,
        records: dict,  # pylint: disable=unused-argument
        synthesized_record_status_matrix: dict,  # pylint: disable=unused-argument
    ) -> None:
        """Update the obsidian vault"""

        data_operation.review_manager.logger.info("Export to obsidian endpoint")

        self.__append_missing_records(
            data_operation=data_operation,
        )

    def update_record_status_matrix(
        self,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        synthesized_record_status_matrix: dict,
        endpoint_identifier: str,
    ) -> None:
        """Update the record_status_matrix"""

        records_dict = data_operation.review_manager.dataset.load_records_dict()
        included = data_operation.get_record_ids_for_synthesis(records_dict)
        missing_records = self.__get_obsidian_missing(included=included)

        # Note : automatically set all to True / synthesized
        for syn_id in list(synthesized_record_status_matrix.keys()):
            if syn_id in missing_records:
                synthesized_record_status_matrix[syn_id][endpoint_identifier] = False
            else:
                synthesized_record_status_matrix[syn_id][endpoint_identifier] = True


if __name__ == "__main__":
    pass
