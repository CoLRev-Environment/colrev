#!/usr/bin/env python3
"""Create and apply record corrections in source repositories."""
from __future__ import annotations

import json
import typing
from pathlib import Path

from dictdiffer import diff

from colrev.constants import Fields

if typing.TYPE_CHECKING:  # pragma: no cover
    import colrev.review_manager

# pylint: disable=too-few-public-methods


class Corrections:
    """Handling corrections of metadata"""

    # pylint: disable=duplicate-code
    essential_md_keys = [
        Fields.TITLE,
        Fields.AUTHOR,
        Fields.JOURNAL,
        Fields.YEAR,
        Fields.BOOKTITLE,
        Fields.NUMBER,
        Fields.VOLUME,
        Fields.AUTHOR,
        Fields.DOI,
        Fields.ORIGIN,  # Note : for merges
    ]

    keys_to_ignore = [
        Fields.ID,
        Fields.SCREENING_CRITERIA,
        Fields.STATUS,
        "source_url",
        "metadata_source_repository_paths",
        "grobid-version",
        "colrev_pdf_id",
        Fields.FILE,
        Fields.ORIGIN,
        Fields.D_PROV,
        Fields.MD_PROV,
        Fields.SEMANTIC_SCHOLAR_ID,
        Fields.CITED_BY,
        Fields.ABSTRACT,
        Fields.PAGES,
    ]

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
    ) -> None:
        self.review_manager = review_manager
        self.corrections_path = self.review_manager.paths.corrections
        self.corrections_path.mkdir(exist_ok=True)

    def _record_corrected(self, *, prior_r: dict, record_dict: dict) -> bool:
        return not all(
            prior_r.get(k, "NA") == record_dict.get(k, "NA")
            for k in self.essential_md_keys
        )

    def _prep_for_change_item_creation(
        self, *, original_record: dict, corrected_record: dict
    ) -> None:
        # Cast to string for persistence
        original_record = {k: str(v) for k, v in original_record.items()}
        corrected_record = {k: str(v) for k, v in corrected_record.items()}

        # Note : removing the fields is a temporary fix
        # because the subsetting of change_items does not seem to
        # work properly
        keys_to_drop = [Fields.PAGES, Fields.STATUS]
        for k in keys_to_drop:
            original_record.pop(k, None)
            corrected_record.pop(k, None)

    def _get_selected_change_items(
        self, original_record: dict, corrected_record: dict
    ) -> list:
        changes = diff(original_record, corrected_record)
        selected_change_items = []
        for change_item in list(changes):
            change_type, key, val = change_item

            if not isinstance(key, str):
                continue

            if change_type != "add" and key == "":
                continue

            if key.split(".")[0] in self.keys_to_ignore:
                continue

            if change_type == "add":
                for add_item in val:
                    add_item_key, add_item_val = add_item
                    if not isinstance(add_item_key, str):
                        break
                    if add_item_key.split(".")[0] in self.keys_to_ignore:
                        break
                    selected_change_items.append(
                        ("add", "", [(add_item_key, add_item_val)])
                    )

            elif change_type == "change":
                selected_change_items.append(change_item)
        return selected_change_items

    def _create_change_item(
        self,
        *,
        original_record: dict,
        corrected_record: dict,
    ) -> None:

        self._prep_for_change_item_creation(
            original_record=original_record,
            corrected_record=corrected_record,
        )

        selected_change_items = self._get_selected_change_items(
            original_record, corrected_record
        )

        if len(selected_change_items) == 0:
            return

        if len(corrected_record.get(Fields.ORIGIN, [])) > len(
            original_record.get(Fields.ORIGIN, [])
        ):
            if (
                Fields.DBLP_KEY in corrected_record
                and Fields.DBLP_KEY in original_record
            ):
                if (
                    corrected_record[Fields.DBLP_KEY]
                    != original_record[Fields.DBLP_KEY]
                ):
                    selected_change_items = {  # type: ignore
                        "merge": [
                            corrected_record[Fields.DBLP_KEY],
                            original_record[Fields.DBLP_KEY],
                        ]
                    }
            # else:
            #     selected_change_items = {
            #         "merge": [
            #             corrected_record[Fields.ID],
            #             original_record[Fields.ID],
            #         ]
            #     }

        # cover non-masterdata corrections
        if Fields.MD_PROV not in original_record:
            return

        dict_to_save = {
            "original_record": {
                k: v for k, v in original_record.items() if k not in [Fields.STATUS]
            },
            "changes": selected_change_items,
        }

        filepath = self.corrections_path / Path(f"{corrected_record['ID']}.json")

        with open(filepath, "w", encoding="utf8") as corrections_file:
            json.dump(dict_to_save, corrections_file, indent=4)

    def check_corrections_of_records(self) -> None:
        """Check for corrections of records"""

        # to test run
        # colrev-hooks-report .report.log

        records = self.review_manager.dataset.load_records_dict()
        prior_records_dict = next(
            self.review_manager.dataset.load_records_from_history(), {}
        )
        for record_dict in records.values():
            # identify curated records for which essential metadata is changed
            record_prior = [
                x
                for x in prior_records_dict.values()
                if any(y in record_dict[Fields.ORIGIN] for y in x[Fields.ORIGIN])
            ]

            if len(record_prior) == 0:
                self.review_manager.logger.debug("No prior records found")
                continue

            for prior_r in record_prior:
                if self._record_corrected(prior_r=prior_r, record_dict=record_dict):
                    corrected_record = record_dict.copy()

                    self._create_change_item(
                        original_record=prior_r,
                        corrected_record=corrected_record,
                    )
