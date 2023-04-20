#! /usr/bin/env python
"""Dedupe functionality dedicated to curated metadata repositories"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from thefuzz import fuzz
from tqdm import tqdm

import colrev.env.package_manager
import colrev.ops.built_in.pdf_prep.metadata_validation
import colrev.record
import colrev.ui_cli.cli_colors as colors

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.dedupe

# pylint: disable=too-many-arguments
# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.DedupePackageEndpointInterface)
@dataclass
class CurationDedupe(JsonSchemaMixin):
    """Deduplication endpoint for curations with full journals/proceedings
    retrieved from different sources (identifying duplicates in groups of
    volumes/issues or years)"""

    settings: CurationDedupeSettings
    ci_supported: bool = True

    @dataclass
    class CurationDedupeSettings(
        colrev.env.package_manager.DefaultSettings, JsonSchemaMixin
    ):
        """Settings for CurationDedupe"""

        endpoint: str
        selected_source: str

        _details = {
            "selected_source": {"tooltip": "Source (path) selected for the dedupe run"},
        }

    settings_class = CurationDedupeSettings

    def __init__(
        self,
        *,
        dedupe_operation: colrev.ops.dedupe.Dedupe,  # pylint: disable=unused-argument
        settings: dict,
    ):
        self.settings = self.settings_class.load_settings(data=settings)

        pdf_prep_operation = dedupe_operation.review_manager.get_pdf_prep_operation()
        self.pdf_metadata_validation = (
            colrev.ops.built_in.pdf_prep.metadata_validation.PDFMetadataValidation(
                pdf_prep_operation=pdf_prep_operation,
                settings={"endpoint": "dedupe_pdf_md_validation"},
            )
        )

    def __get_similarity(self, *, df_a: pd.Series, df_b: pd.Series) -> float:
        author_similarity = fuzz.ratio(df_a["author"], df_b["author"]) / 100

        title_similarity = (
            fuzz.ratio(df_a["title"].lower(), df_b["title"].lower()) / 100
        )

        # Note : the toc-based processing means that we are robust against
        # outlet, year, volume, number variations!
        weights = [0.4, 0.6]
        similarities = [
            author_similarity,
            title_similarity,
        ]

        weighted_average = sum(
            similarities[g] * weights[g] for g in range(len(similarities))
        )

        similarity_score = round(weighted_average, 4)

        return similarity_score

    def __calculate_similarities(
        self,
        *,
        similarity_array: np.ndarray,
        references: pd.DataFrame,
        min_similarity: float,
    ) -> tuple:
        # Fill out the similarity matrix first
        for base_entry_i in range(1, references.shape[0]):
            for comparison_entry_i in range(1, references.shape[0]):
                if base_entry_i > comparison_entry_i:
                    if -1 != similarity_array[base_entry_i, comparison_entry_i]:
                        similarity_array[
                            base_entry_i, comparison_entry_i
                        ] = self.__get_similarity(
                            df_a=references.iloc[base_entry_i],
                            df_b=references.iloc[comparison_entry_i],
                        )

        tuples_to_process = []
        maximum_similarity = 1
        while True:
            maximum_similarity = np.amax(similarity_array)
            if maximum_similarity < min_similarity:
                break
            result = np.where(similarity_array == np.amax(similarity_array))
            list_of_coordinates = list(zip(result[0], result[1]))
            for cord in list_of_coordinates:
                similarity_array[cord] = 0  # ie., has been processed
                tuples_to_process.append(
                    [
                        references.iloc[cord[0]]["ID"],
                        references.iloc[cord[1]]["ID"],
                        maximum_similarity,
                        "not_processed",
                    ]
                )

        return similarity_array, tuples_to_process

    def __get_toc_items(self, *, records_list: list) -> list:
        toc_items = []
        for record in records_list:
            toc_item = {}
            if record["ENTRYTYPE"] == "article":
                if "journal" in record:
                    toc_item["journal"] = record["journal"]
                if "volume" in record:
                    toc_item["volume"] = record["volume"]
                if "number" in record:
                    toc_item["number"] = record["number"]

            if record["ENTRYTYPE"] == "inproceedings":
                if "booktitle" in record:
                    toc_item["booktitle"] = record["booktitle"]
                    toc_item["year"] = record["year"]
            if len(toc_item) > 0:
                toc_items.append(toc_item)

        temp = {tuple(sorted(sub.items())) for sub in toc_items}
        toc_items = list(map(dict, temp))  # type: ignore
        return toc_items

    def __warn_on_missing_sources(
        self, *, dedupe_operation: colrev.ops.dedupe.Dedupe, first_source: bool
    ) -> None:
        # warn if not all SOURCE.filenames are included in a dedupe script
        if first_source:
            available_sources = [
                str(s.filename)
                for s in dedupe_operation.review_manager.settings.sources
                if "md_" not in str(s.filename)
            ]
            dedupe_sources = [
                s["selected_source"]
                for s in dedupe_operation.review_manager.settings.dedupe.dedupe_package_endpoints
                if "colrev.curation_full_outlet_dedupe" == s["endpoint"]
            ]
            sources_missing_in_dedupe = [
                x for x in available_sources if x not in dedupe_sources
            ]
            if len(sources_missing_in_dedupe) > 0:
                dedupe_operation.review_manager.logger.warning(
                    f"{colors.ORANGE}Sources missing in "
                    "dedupe.scripts.colrev.curation_full_outlet_dedupe: "
                    f"{','.join(sources_missing_in_dedupe)}{colors.END}"
                )
                if input("Add sources [y,n]?") == "y":
                    for source_missing_in_dedupe in sources_missing_in_dedupe:
                        dedupe_package_endpoints = (
                            dedupe_operation.review_manager.settings.dedupe.dedupe_package_endpoints
                        )
                        penultimate_position = len(dedupe_package_endpoints) - 1
                        dedupe_script_to_add = {
                            "endpoint": "colrev.curation_full_outlet_dedupe",
                            "selected_source": source_missing_in_dedupe,
                        }
                        dedupe_package_endpoints.insert(
                            penultimate_position, dedupe_script_to_add
                        )
                        dedupe_operation.review_manager.save_settings()
                        dedupe_operation.review_manager.logger.info(
                            f"{colors.GREEN}Added {source_missing_in_dedupe} "
                            f"to dedupe.scripts{colors.END}"
                        )

    def __add_first_source_if_deduplicated(
        self, *, dedupe_operation: colrev.ops.dedupe.Dedupe, records: dict
    ) -> None:
        dedupe_operation.review_manager.logger.info(
            f"Starting with records from {self.settings.selected_source}"
            " (setting to md_processed as the initial records)"
        )

        source_records = [
            r
            for r in records.values()
            if r["colrev_status"] == colrev.record.RecordState.md_prepared
            and any(
                self.settings.selected_source.replace("data/search/", "") in co
                for co in r["colrev_origin"]
            )
        ]

        toc_items = self.__get_toc_items(records_list=source_records)

        for toc_item in toc_items:
            # Note : these would be potential errors (duplicates)
            # because they have the same selected_source
            processed_same_toc_same_source_records = [
                r
                for r in records.values()
                if all(r.get(k, "NA") == v for k, v in toc_item.items())
                and r["colrev_status"]
                not in [
                    colrev.record.RecordState.md_prepared,
                    colrev.record.RecordState.md_needs_manual_preparation,
                    colrev.record.RecordState.md_imported,
                    colrev.record.RecordState.rev_prescreen_excluded,
                ]
                and any(
                    self.settings.selected_source.replace("data/search/", "") in co
                    for co in r["colrev_origin"]
                )
            ]
            if 0 == len(processed_same_toc_same_source_records):
                print("\n\n")
                print(toc_item)

                for source_record_dict in sorted(
                    source_records, key=lambda d: d["author"]
                ):
                    if all(
                        source_record_dict.get(k, "NA") == v
                        for k, v in toc_item.items()
                    ):
                        # Record(data=sr).print_citation_format()
                        print(
                            f"{source_record_dict.get('author', 'NO_AUTHOR')} : "
                            f"{source_record_dict.get('title', 'NO_TITLE')}"
                        )
                recs_unique = dedupe_operation.review_manager.force_mode
                if not recs_unique:
                    recs_unique = "y" == input(
                        "No existing records (md_processed*) found. "
                        "All records unique? Set to md_processed [y]? "
                    )
                if recs_unique:
                    for source_record_dict in source_records:
                        if all(
                            source_record_dict.get(k, "NA") == v
                            for k, v in toc_item.items()
                        ):
                            source_record = colrev.record.Record(
                                data=source_record_dict
                            )
                            source_record.set_status(
                                target_state=colrev.record.RecordState.md_processed
                            )
            else:
                print(toc_item)
                print("Pre-imported records found for this toc_item (skipping)")
                # print(processed_same_toc_same_source_records)

        for record in records.values():
            record.pop("container_title")
        dedupe_operation.review_manager.dataset.save_records_dict(records=records)
        dedupe_operation.review_manager.dataset.add_record_changes()

        if dedupe_operation.review_manager.dataset.has_changes():
            dedupe_operation.review_manager.logger.info(
                f"{colors.GREEN}Commit changes{colors.END}"
            )
            dedupe_operation.review_manager.create_commit(
                msg=(
                    "Merge duplicate records (set unique records from "
                    f"{self.settings.selected_source} "
                    "to md_processed)"
                ),
            )
        else:
            dedupe_operation.review_manager.logger.info(
                f"{colors.GREEN}No duplicates found{colors.END}"
            )

    def __prep_records(self, *, records: dict) -> dict:
        required_fields = [
            "title",
            "author",
            "year",
            "journal",
            "volume",
            "number",
            "pages",
            "booktitle",
        ]
        for record in records.values():
            if "container_title" not in record:
                record["container_title"] = (
                    record.get("journal", "")
                    + record.get("booktitle", "")
                    + record.get("series", "")
                )

            for required_field in required_fields:
                if required_field not in record:
                    record[required_field] = ""
        return records

    def __dedupe_source(
        self, *, dedupe_operation: colrev.ops.dedupe.Dedupe, records: dict
    ) -> list[dict]:
        dedupe_operation.review_manager.logger.info(
            "Processing as a non-pdf source (matching exact colrev_ids)"
        )

        source_records = [
            r
            for r in records.values()
            if r["colrev_status"] == colrev.record.RecordState.md_prepared
            and any(
                self.settings.selected_source.replace("data/search/", "") in co
                for co in r["colrev_origin"]
            )
        ]

        toc_items = self.__get_toc_items(records_list=source_records)

        decision_list: list[dict] = []
        # decision_list =[{'ID1': ID1, 'ID2': ID2, 'decision': 'duplicate'}]

        # match based on overlapping  colrev_ids
        for toc_item in tqdm(toc_items):
            processed_same_toc_records = [
                r
                for r in records.values()
                if all(r.get(k, "NA") == v for k, v in toc_item.items())
                and r["colrev_status"]
                not in [
                    colrev.record.RecordState.md_imported,
                    colrev.record.RecordState.md_needs_manual_preparation,
                    colrev.record.RecordState.md_prepared,
                    colrev.record.RecordState.rev_prescreen_excluded,
                ]
                and not any(
                    self.settings.selected_source.replace("data/search/", "") in co
                    for co in r["colrev_origin"]
                )
            ]
            new_same_toc_records = [
                r
                for r in source_records
                if all(r.get(k, "NA") == v for k, v in toc_item.items())
            ]
            if len(new_same_toc_records) > 0:
                # print(new_same_toc_records)
                for new_same_toc_record in new_same_toc_records:
                    for rec2 in processed_same_toc_records:
                        overlapping_colrev_ids = colrev.record.Record(
                            data=new_same_toc_record
                        ).has_overlapping_colrev_id(
                            record=colrev.record.Record(data=rec2)
                        )
                        if overlapping_colrev_ids:
                            decision_list.append(
                                {
                                    "ID1": new_same_toc_record["ID"],
                                    "ID2": rec2["ID"],
                                    "decision": "duplicate",
                                }
                            )
                            print("TODO : validate whether it merges correctly:")
                            input(decision_list)

        return decision_list

    def __validate_potential_merge(
        self, *, rec1: dict, rec2: dict, dedupe_operation: colrev.ops.dedupe.Dedupe
    ) -> dict:
        if "file" in rec2:
            updated_record = rec1.copy()
            updated_record["file"] = rec2["file"]
        elif "file" in rec1:
            updated_record = rec2.copy()
            updated_record["file"] = rec1["file"]
        else:  # None of the records is curated
            raise FileNotFoundError

        record = colrev.record.Record(data=updated_record)
        validation_info = self.pdf_metadata_validation.validates_based_on_metadata(
            review_manager=dedupe_operation.review_manager,
            record=record,
        )
        return validation_info

    def __process_pdf_tuple(
        self,
        *,
        tuple_to_process: tuple,
        records: dict,
        decision_list: list,
        curated_record_ids: list,
        pdf_record_ids: list,
        dedupe_operation: colrev.ops.dedupe.Dedupe,
    ) -> None:
        rec1 = records[tuple_to_process[0]]
        rec2 = records[tuple_to_process[1]]

        # Note : Focus on merges between
        # curated_records and pdf_same_toc_records
        # Note : this should also ensure that pdf groups are not merged
        # until a corresponding curated record group is available.
        if (rec1["ID"] in curated_record_ids and rec2["ID"] in curated_record_ids) or (
            rec1["ID"] in pdf_record_ids and rec2["ID"] in pdf_record_ids
        ):
            return

        try:
            validation_info = self.__validate_potential_merge(
                rec1=rec1, rec2=rec2, dedupe_operation=dedupe_operation
            )
        except FileNotFoundError:
            return

        overlapping_colrev_ids = colrev.record.Record(
            data=rec1
        ).has_overlapping_colrev_id(record=colrev.record.Record(data=rec2))
        if validation_info["validates"] or overlapping_colrev_ids:
            # Note : make sure that we merge into the CURATED record
            if "file" in rec1:
                if tuple_to_process[0] in [x["ID1"] for x in decision_list]:
                    return
                if rec1["colrev_status"] < rec2["colrev_status"]:
                    decision_list.append(
                        {
                            "ID1": tuple_to_process[1],
                            "ID2": tuple_to_process[0],
                            "decision": "duplicate",
                        }
                    )
                else:
                    decision_list.append(
                        {
                            "ID1": tuple_to_process[0],
                            "ID2": tuple_to_process[1],
                            "decision": "duplicate",
                        }
                    )
            else:
                if tuple_to_process[1] in [x["ID1"] for x in decision_list]:
                    return
                if rec1["colrev_status"] < rec2["colrev_status"]:
                    decision_list.append(
                        {
                            "ID1": tuple_to_process[1],
                            "ID2": tuple_to_process[0],
                            "decision": "duplicate",
                        }
                    )
                else:
                    decision_list.append(
                        {
                            "ID1": tuple_to_process[0],
                            "ID2": tuple_to_process[1],
                            "decision": "duplicate",
                        }
                    )

    def __dedupe_pdf_toc_item(
        self,
        *,
        decision_list: list[dict],
        toc_item: dict,
        records: dict,
        source_records: list,
        dedupe_operation: colrev.ops.dedupe.Dedupe,
    ) -> None:
        processed_same_toc_records = [
            r
            for r in records.values()
            if all(r.get(k, "NA") == v for k, v in toc_item.items())
            and r["colrev_status"]
            not in [
                colrev.record.RecordState.md_imported,
                colrev.record.RecordState.md_needs_manual_preparation,
                colrev.record.RecordState.md_prepared,
                colrev.record.RecordState.rev_prescreen_excluded,
            ]
            and not any(
                self.settings.selected_source.replace("data/search/", "") in co
                for co in r["colrev_origin"]
            )
        ]
        pdf_same_toc_records = [
            r
            for r in source_records
            if all(r.get(k, "NA") == v for k, v in toc_item.items())
        ]

        references = pd.DataFrame.from_records(
            processed_same_toc_records + pdf_same_toc_records
        )

        nr_entries = references.shape[0]
        if nr_entries == 0:
            return
        similarity_array = np.zeros([nr_entries, nr_entries])

        # Note : min_similarity only means that the PDF will be considered
        # for validates_based_on_metadata(...), which is the acutal test!
        similarity_array, tuples_to_process = self.__calculate_similarities(
            similarity_array=similarity_array,
            references=references,
            min_similarity=0.7,
        )

        curated_record_ids = [r["ID"] for r in processed_same_toc_records]
        pdf_record_ids = [r["ID"] for r in pdf_same_toc_records]
        for tuple_to_process in tuples_to_process:
            self.__process_pdf_tuple(
                tuple_to_process=tuple_to_process,
                records=records,
                decision_list=decision_list,
                curated_record_ids=curated_record_ids,
                pdf_record_ids=pdf_record_ids,
                dedupe_operation=dedupe_operation,
            )

    def __dedupe_pdf_source(
        self, *, dedupe_operation: colrev.ops.dedupe.Dedupe, records: dict
    ) -> list[dict]:
        dedupe_operation.review_manager.logger.info("Processing as a pdf source")

        source_records = [
            r
            for r in records.values()
            if r["colrev_status"] == colrev.record.RecordState.md_prepared
            and any(
                self.settings.selected_source.replace("data/search/", "") in co
                for co in r["colrev_origin"]
            )
        ]

        decision_list: list[dict] = []
        # decision_list =[{'ID1': ID1, 'ID2': ID2, 'decision': 'duplicate'}]

        for toc_item in tqdm(self.__get_toc_items(records_list=source_records)):
            self.__dedupe_pdf_toc_item(
                decision_list=decision_list,
                toc_item=toc_item,
                records=records,
                source_records=source_records,
                dedupe_operation=dedupe_operation,
            )

        return decision_list

    def __pdf_source_selected(
        self, *, dedupe_operation: colrev.ops.dedupe.Dedupe
    ) -> bool:
        pdf_source = False
        relevant_source = [
            s
            for s in dedupe_operation.review_manager.settings.sources
            if str(s.filename) == self.settings.selected_source
        ]
        if len(relevant_source) > 0:
            pdf_source = "colrev.pdfs_dir" == relevant_source[0].endpoint
        return pdf_source

    def __first_source_selected(
        self, *, dedupe_operation: colrev.ops.dedupe.Dedupe
    ) -> bool:
        return (
            self.settings.selected_source
            == dedupe_operation.review_manager.settings.dedupe.dedupe_package_endpoints[
                0
            ]["selected_source"]
        )

    def run_dedupe(self, dedupe_operation: colrev.ops.dedupe.Dedupe) -> None:
        """Run the curation dedupe procedure"""

        records = dedupe_operation.review_manager.dataset.load_records_dict()
        records = self.__prep_records(records=records)

        # first_source should be the highest quality source
        # (which moves to md_processed first)
        first_source = self.__first_source_selected(dedupe_operation=dedupe_operation)

        self.__warn_on_missing_sources(
            dedupe_operation=dedupe_operation, first_source=first_source
        )

        if first_source:
            self.__add_first_source_if_deduplicated(
                dedupe_operation=dedupe_operation, records=records
            )
            return

        dedupe_operation.review_manager.logger.info(
            "Identify duplicates between "
            f"curated_records and {self.settings.selected_source} (within toc_items)"
        )

        decision_list: list[dict] = []
        # decision_list =[{'ID1': ID1, 'ID2': ID2, 'decision': 'duplicate'}]
        if not self.__pdf_source_selected(dedupe_operation=dedupe_operation):
            decision_list = self.__dedupe_source(
                dedupe_operation=dedupe_operation, records=records
            )
        else:
            decision_list = self.__dedupe_pdf_source(
                dedupe_operation=dedupe_operation, records=records
            )

        # Note : dedupe.apply_merges reloads the records and
        # thereby discards previous changes
        if len(decision_list) == 0:
            dedupe_operation.review_manager.logger.info(
                f"{colors.GREEN}No merge-candidates identified between sets{colors.END}"
            )
            return

        dedupe_operation.review_manager.logger.info(
            f"{colors.GREEN}Duplicates identified{colors.END}"
        )

        # decision_list =
        # [{'ID1': '0000000053', 'ID2': 'BellMillsFadel2013', 'decision': 'duplicate'}, .. . ]

        preferred_masterdata_sources = [
            s
            for s in dedupe_operation.review_manager.settings.sources
            if s.endpoint != "colrev.pdfs_dir"
        ]
        dedupe_operation.apply_merges(
            results=decision_list,
            preferred_masterdata_sources=preferred_masterdata_sources,
        )

        dedupe_operation.review_manager.dataset.add_record_changes()

        dedupe_operation.review_manager.create_commit(
            msg="Merge duplicate records",
        )


if __name__ == "__main__":
    pass
