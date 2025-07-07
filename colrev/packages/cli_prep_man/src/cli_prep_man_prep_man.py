#! /usr/bin/env python
"""CliPrepMan"""
import typing

import inquirer

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
        self, *, prep_man_operation: colrev.ops.prep_man.PrepMan, settings: dict
    ) -> "None":
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

            label = f"[{i+1}]\n{title}\n{citation_info.strip()}\n{link_info}"
            choices.append(label)
        choices.append("Skip merging")
        return choices

    def _get_selected_record(
        self, similar_records: typing.List[colrev.record.record_prep.PrepRecord]
    ) -> typing.Optional[colrev.record.record_prep.PrepRecord]:

        choices = self._get_choices(similar_records)
        # Prompt user to select a record
        answer = inquirer.list_input("Select a record to merge:", choices=choices)
        if answer == "Skip merging":
            return None

        selected_index = choices.index(answer)
        selected_record = similar_records[selected_index]
        return selected_record

    def _prep_record(self, record: dict) -> None:
        print(f"\n--- Record {record[Fields.ID]} ---")
        print(f"Title: {record[Fields.TITLE]}")

        # Use CrossrefAPI to find similar records
        try:
            # `url` gets overwritten internally
            api = crossref_api.CrossrefAPI(params={"url": ""})
            similar_records = api.crossref_query(
                record_input=colrev.record.record_prep.PrepRecord(record)
            )  # top_n=5
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
            if record[Fields.STATUS] != RecordState.md_needs_manual_preparation:
                continue
            if record[Fields.TITLE] in ["", "UNKNOWN"]:
                continue

            self._prep_record(record)

        return records


def main() -> None:
    """Main function to run the CLI"""

    print("CLI initialized")

    review_manager = colrev.review_manager.ReviewManager()
    prep_man_operation = review_manager.get_prep_man_operation()
    records = review_manager.dataset.load_records_dict()

    cli_prep_man = CliPrepMan(prep_man_operation=prep_man_operation, settings={})
    records = cli_prep_man.prepare_manual(records=records)

    review_manager.dataset.save_records_dict(records)
