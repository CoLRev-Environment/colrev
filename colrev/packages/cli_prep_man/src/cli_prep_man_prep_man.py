#! /usr/bin/env python
"""CliPrepMan"""

import logging
import typing

import questionary

import colrev.ops.prep_man
import colrev.review_manager
from colrev.constants import Fields
from colrev.constants import RecordState
from colrev.package_manager.package_base_classes import PrepManPackageBaseClass
from colrev.packages.crossref.src import crossref_api

# pylint: disable=too-few-public-methods


class CliPrepMan(PrepManPackageBaseClass):
    """CLI for manual preparation of records"""

    def __init__(
        self,
        *,
        prep_man_operation: colrev.ops.prep_man.PrepMan,
        settings: dict,
        logger: typing.Optional[logging.Logger] = None,
    ) -> "None":
        self.logger = logger or logging.getLogger(__name__)
        """Initialize self.  See help(type(self)) for accurate signature."""

    def _get_choices(
        self, similar_records: typing.List[colrev.record.record_prep.PrepRecord]
    ) -> list:
        """Generate choices for the user to select a record to merge."""

        choices = []
        for i, r in enumerate(similar_records):
            title = r.data.get(Fields.TITLE, "No Title")
            year = r.data.get(Fields.YEAR, "n.d.")
            container = r.data.get(Fields.JOURNAL, r.data.get(Fields.BOOKTITLE, ""))
            volume = r.data.get(Fields.VOLUME, "")
            number = r.data.get(Fields.NUMBER, "")

            vol_no = f"{volume}({number})" if volume and number else volume or number
            citation_info = (
                f"{year}, {container}, {vol_no}" if container or vol_no else year
            )
            link_info = f"DOI: {r.data.get(Fields.DOI, 'No DOI')}"

            label = f"[{i+1}] {title} - {citation_info.strip()} - {link_info}"
            choices.append(label)
        choices.append("Skip merging")
        return choices

    def _get_selected_record(
        self,
        similar_records: typing.List[colrev.record.record_prep.PrepRecord],
    ) -> typing.Optional[colrev.record.record_prep.PrepRecord]:

        choices = self._get_choices(similar_records)
        answer = questionary.select(
            "Select a record to merge:",
            choices=choices,
        ).ask()

        # If user cancels or chooses to skip
        if answer is None or answer == "Skip merging":
            return None

        selected_index = choices.index(answer)
        return similar_records[selected_index]

    def _prep_record(self, record: dict) -> None:
        print(f"\n--- Record {record[Fields.ID]} ---")
        # print(f"Title: {record[Fields.TITLE]}")
        print(colrev.record.record.Record(record))

        # Use CrossrefAPI to find similar records
        try:
            # `url` gets overwritten internally
            api = crossref_api.CrossrefAPI(url="https://api.crossref.org/")
            similar_records = api.crossref_query(
                record_input=colrev.record.record_prep.PrepRecord(record), top_n=5
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Crossref query failed: {e}")
            return

        if not similar_records:
            print("No similar records found.")
            return

        selected_record = self._get_selected_record(similar_records)
        if not selected_record:
            return

        # Merge logic (simplified: replace existing record with selected_record)
        print(f"Merging with record: {selected_record.data.get(Fields.TITLE)}")
        record.update(selected_record.get_data())
        # record[Fields.STATUS] = RecordState.md_prepared

    def prepare_manual(self, records: dict) -> dict:
        """Run the prep-man operation."""

        for record in records.values():
            # if record[Fields.STATUS] != RecordState.md_needs_manual_preparation:
            #     continue
            if record[Fields.TITLE] in ["", "UNKNOWN"]:
                continue

            self._prep_record(record)

        return records


def main() -> None:
    """Main function to run the CLI"""

    print("CLI initialized")

    def _select_target_ids(records: dict[str, dict]) -> list[str]:
        """Ask user which records to process and return the selected record_ids.

        Options:
        - All records where Fields.STATUS == RecordState.md_needs_man_prep
        - Manually entered, comma-separated record_ids
        """
        mode = questionary.select(
            "Which records do you want to prepare manually?",
            choices=[
                "All records with status: md_needs_man_prep",
                "Selected records by ID (comma-separated)",
            ],
        ).ask()

        if mode is None:
            # user cancelled
            return []

        if mode.startswith("All"):
            target_ids = [
                rec_id
                for rec_id, rec in records.items()
                if rec.get(Fields.STATUS, None)
                == RecordState.md_needs_manual_preparation
            ]
        else:
            raw_ids = (
                questionary.text("Enter record IDs (comma-separated):").ask() or ""
            )
            target_ids = [rid.strip() for rid in raw_ids.split(",") if rid.strip()]

            # sanity-check: warn about unknown IDs
            unknown = [rid for rid in target_ids if rid not in records]
            if unknown:
                questionary.print(
                    f"Warning: {len(unknown)} ID(s) not found and will be ignored: {', '.join(unknown)}",
                    style="bold fg:yellow",
                )
                target_ids = [rid for rid in target_ids if rid in records]

        return target_ids

    review_manager = colrev.review_manager.ReviewManager(force_mode=True)
    prep_man_operation = review_manager.get_prep_man_operation()
    records = review_manager.dataset.load_records_dict()

    target_ids = _select_target_ids(
        records
    )  # or _select_target_ids(...) if not in a class

    if not target_ids:
        questionary.print("No matching records selected.", style="bold fg:yellow")
        return

    subset = {rid: records[rid] for rid in target_ids}
    cli_prep_man = CliPrepMan(prep_man_operation=prep_man_operation, settings={})
    updated_subset = cli_prep_man.prepare_manual(records=subset)

    # merge back into the full set and save
    records.update(updated_subset)
    review_manager.dataset.save_records_dict(records)
    questionary.print(
        f"Prepared {len(updated_subset)} record(s).", style="bold fg:green"
    )
