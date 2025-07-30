#! /usr/bin/env python
"""Data based on GenAI"""
from __future__ import annotations

import re
import typing
from pathlib import Path

from litellm import completion
from pydantic import BaseModel
from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.record.record_pdf
from colrev.constants import Fields
from colrev.constants import RecordState


# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


class GenAIData(base_classes.DataPackageBaseClass):
    """GenAI-based data"""

    ci_supported: bool = Field(default=False)

    class GenAIDataSettings(
        colrev.package_manager.package_settings.DefaultSettings, BaseModel
    ):
        """GenAI data settings"""

        endpoint: str
        version: str
        prompt: str
        model: str = "gpt-4o-mini"
        mode: str

    settings_class = GenAIDataSettings

    def __init__(
        self,
        *,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.review_manager = data_operation.review_manager
        self.data_operation = data_operation

        # Set default values (if necessary)
        if "version" not in settings:
            settings["version"] = "0.1"

        if "prompt" not in settings:
            settings["prompt"] = input("Enter the GenAI prompt: ")

        self.settings = self.settings_class(**settings)

        output_dir = self.review_manager.paths.output
        self.summary_path = output_dir / Path("prompt_summary.md")
        self.ouptut_dir_individual = output_dir / Path("individual_summaries")

    # pylint: disable=unused-argument
    @classmethod
    def add_endpoint(cls, operation: colrev.ops.data.Data, params: str) -> None:
        """Add as an endpoint"""

        add_package = {
            "endpoint": "colrev.prisma",
            "version": "0.1",
            "prompt": input("Enter the GenAI prompt: "),
        }
        operation.review_manager.settings.data.data_package_endpoints.append(
            add_package
        )

    def _run_prompt(self) -> None:

        print(f"Updating prompt_summary file at {self.summary_path}")

        existing_content = (
            self.summary_path.read_text() if self.summary_path.exists() else ""
        )
        records = self.review_manager.dataset.load_records_dict()
        existing_concepts: typing.List[str] = []
        counter = 0
        for record_dict in records.values():
            if record_dict[Fields.STATUS] not in [
                RecordState.rev_included,
                RecordState.rev_synthesized,
            ]:
                continue
            if f"{record_dict[Fields.ID]}\n" in existing_content:
                print(
                    f"Skipping record {record_dict[Fields.ID]} as it already exists in the summary."
                )
                continue

            individual_summary_path = (
                self.ouptut_dir_individual / f"{record_dict[Fields.ID]}.md"
            )
            if self.settings.mode == "individual":
                if individual_summary_path.exists():
                    continue

            print(f"\nProcessing record {record_dict[Fields.ID]}...")
            counter += 1

            record = colrev.record.record_pdf.PDFRecord(
                record_dict, path=self.review_manager.path
            )
            record.set_text_from_pdf()

            user_message = self.settings.prompt.format(
                record_id=record_dict[Fields.ID],
                text=record_dict[Fields.TEXT_FROM_PDF],
                existing_concepts=(
                    ", ".join(existing_concepts) if existing_concepts else ""
                ),
            )

            response = completion(
                model=self.settings.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": user_message,
                    }
                ],
            )

            for match in re.finditer(
                r"\[\[(.*?)\]\]", response.choices[0].message.content
            ):
                concept = match.group(1).strip()
                if concept not in existing_concepts:
                    existing_concepts.append(concept)

            if self.settings.mode == "individual":
                with open(individual_summary_path, "w", encoding="utf-8") as file:
                    file.write(response.choices[0].message.content)
            else:

                existing_content += f"{response.choices[0].message.content}\n\n"

                with open(self.summary_path, "w", encoding="utf-8") as file:
                    file.write(existing_content)

            # if counter >= 3:
            #     break

    # pylint: disable=unused-argument
    def update_data(
        self,
        records: dict,
        synthesized_record_status_matrix: dict,
        silent_mode: bool,
    ) -> None:
        """Update the data/prisma diagram"""

        self._run_prompt()

    def update_record_status_matrix(
        self,
        synthesized_record_status_matrix: dict,
        endpoint_identifier: str,
    ) -> None:
        """Update the record_status_matrix"""

        # Note : automatically set all to True / synthesized
        for syn_id in list(synthesized_record_status_matrix.keys()):
            synthesized_record_status_matrix[syn_id][endpoint_identifier] = True

    def get_advice(
        self,
    ) -> dict:
        """Get advice on the next steps (for display in the colrev status)"""

        # data_endpoint = "Data operation [prisma data endpoint]: "

        # path_str = ",".join(
        #     [
        #         str(x.relative_to(self.review_manager.path))
        #         for x in self.settings.diagram_path
        #     ]
        # )
        # advice = {
        #     "msg": f"{data_endpoint}"
        #     + "\n    - The PRISMA diagram is created automatically "
        #     + f"({path_str})",
        #     "detailed_msg": "TODO",
        # }
        msg = (
            f"GenAI data operation: {self.settings.endpoint} "
            f"(version: {self.settings.version})"
        )
        advice = {
            "msg": msg,
            "detailed_msg": f"Prompt used: {self.settings.prompt}",
        }
        return advice
