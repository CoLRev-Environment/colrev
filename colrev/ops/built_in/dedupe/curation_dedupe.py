#! /usr/bin/env python
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import zope.interface
from dacite import from_dict
from thefuzz import fuzz
from tqdm import tqdm

import colrev.env.package_manager
import colrev.ops.built_in.pdf_prep.metadata_valiation
import colrev.record
import colrev.ui_cli.cli_colors as colors

if TYPE_CHECKING:
    import colrev.ops.dedupe

# pylint: disable=too-many-arguments
# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.DedupePackageInterface)
class CurationDedupe:
    """Deduplication endpoint for curations with full journals/proceedings
    retrieved from different sources (identifying duplicates in groups of
    volumes/issues or years)"""

    @dataclass
    class CurationDedupeSettings:
        name: str
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
        # TODO : the settings could be used
        # to select the specific files/grouping properties?!
        # -> see selected_source.
        # TODO : validate whether selected_source is in SOURCES.filenames
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def __get_similarity(self, *, df_a: pd.DataFrame, df_b: pd.DataFrame) -> float:

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
        self, *, similarity_array, references: pd.DataFrame, min_similarity: float
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
            if "article" == record["ENTRYTYPE"]:
                if "journal" in record:
                    toc_item["journal"] = record["journal"]
                if "volume" in record:
                    toc_item["volume"] = record["volume"]
                if "number" in record:
                    toc_item["number"] = record["number"]

            if "inproceedings" == record["ENTRYTYPE"]:
                if "booktitle" in record:
                    toc_item["booktitle"] = record["booktitle"]
                    toc_item["year"] = record["year"]
            if len(toc_item) > 0:
                toc_items.append(toc_item)

        temp = {tuple(sorted(sub.items())) for sub in toc_items}
        toc_items = list(map(dict, temp))  # type: ignore
        return toc_items

    def run_dedupe(self, dedupe_operation: colrev.ops.dedupe.Dedupe) -> None:

        records = dedupe_operation.review_manager.dataset.load_records_dict()

        for record in records.values():
            if "container_title" not in record:
                record["container_title"] = (
                    record.get("journal", "")
                    + record.get("booktitle", "")
                    + record.get("series", "")
                )
            if "title" not in record:
                record["title"] = ""
            if "author" not in record:
                record["author"] = ""
            if "year" not in record:
                record["year"] = ""
            if "journal" not in record:
                record["journal"] = ""
            if "volume" not in record:
                record["volume"] = ""
            if "number" not in record:
                record["number"] = ""
            if "pages" not in record:
                record["pages"] = ""
            if "booktitle" not in record:
                record["booktitle"] = ""

        # first_source should be the highest quality source
        # (which moves to md_processed first)
        first_source = (
            self.settings.selected_source
            == dedupe_operation.review_manager.settings.dedupe.scripts[0][
                "selected_source"
            ]
        )

        # warn if not all SOURCE.filenames are included in a dedupe script
        if first_source:
            available_sources = [
                str(s.filename)
                for s in dedupe_operation.review_manager.settings.sources
            ]
            dedupe_sources = [
                s["selected_source"]
                for s in dedupe_operation.review_manager.settings.dedupe.scripts
                if "curation_full_outlet_dedupe" == s["endpoint"]
            ]
            sources_missing_in_dedupe = [
                x for x in available_sources if x not in dedupe_sources
            ]
            if len(sources_missing_in_dedupe) > 0:
                dedupe_operation.review_manager.logger.warning(
                    f"{colors.ORANGE}Sources missing in "
                    "dedupe.scripts.curation_full_outlet_dedupe: "
                    f"{','.join(sources_missing_in_dedupe)}{colors.END}"
                )
                if "y" == input("Add sources [y,n]?"):
                    for source_missing_in_dedupe in sources_missing_in_dedupe:
                        penultimate_position = (
                            len(dedupe_operation.review_manager.settings.dedupe.scripts)
                            - 1
                        )
                        dedupe_script_to_add = {
                            "endpoint": "curation_full_outlet_dedupe",
                            "selected_source": source_missing_in_dedupe,
                        }
                        dedupe_operation.review_manager.settings.dedupe.scripts.insert(
                            penultimate_position, dedupe_script_to_add
                        )
                        dedupe_operation.review_manager.save_settings()
                        dedupe_operation.review_manager.logger.info(
                            f"{colors.GREEN}Added {source_missing_in_dedupe} "
                            f"to dedupe.scripts{colors.END}"
                        )

        # TODO : create a search/retrieval script that retrieves
        # records based on linked attributes (see cml_assistant)

        source_records = [
            r
            for r in records.values()
            if r["colrev_status"] == colrev.record.RecordState.md_prepared
            and self.settings.selected_source.replace("search/", "")
            in r["colrev_origin"]
        ]

        toc_items = self.__get_toc_items(records_list=source_records)

        if first_source:

            dedupe_operation.review_manager.logger.info(
                f"Starting with records from {self.settings.selected_source}"
                " (setting to md_processed as the initial records)"
            )

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
                    and self.settings.selected_source.replace("search/", "")
                    in r["colrev_origin"]
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

                    if "y" == input(
                        "No existing records (md_processed*) found."
                        "All records unique? Set to md_processed [y]? "
                    ):
                        for source_record_dict in source_records:
                            if all(
                                source_record_dict.get(k, "NA") == v
                                for k, v in toc_item.items()
                            ):
                                source_record_dict[
                                    "colrev_status"
                                ] = colrev.record.RecordState.md_processed
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
                    script_call="colrev dedupe",
                    saved_args={},
                )
            else:
                dedupe_operation.review_manager.logger.info(
                    f"{colors.GREEN}No duplicates found{colors.END}"
                )

            return

        decision_list: list[dict] = []
        # decision_list =[{'ID1': ID1, 'ID2': ID2, 'decision': 'duplicate'}]

        dedupe_operation.review_manager.logger.info(
            "Identify duplicates between "
            f"curated_records and {self.settings.selected_source} (within toc_items)"
        )

        pdf_source = False
        relevant_source = [
            s
            for s in dedupe_operation.review_manager.settings.sources
            if str(s.filename) == self.settings.selected_source
        ]
        if len(relevant_source) > 0:
            pdf_source = "pdfs_dir" == relevant_source[0].source_name

        if not pdf_source:
            dedupe_operation.review_manager.logger.info(
                "Processing as a non-pdf source (matching exact colrev_ids)"
            )

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
                    and self.settings.selected_source.replace("search/", "")
                    not in r["colrev_origin"]
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

        else:
            dedupe_operation.review_manager.logger.info("Processing as a pdf source")

            pdf_prep_operation = (
                dedupe_operation.review_manager.get_pdf_prep_operation()
            )
            pdf_metadata_validation = (
                colrev.ops.built_in.pdf_prep.metadata_valiation.PDFMetadataValidation(
                    pdf_prep_operation=pdf_prep_operation,
                    settings={"name": "dedupe_pdf_md_validation"},
                )
            )

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
                    and self.settings.selected_source.replace("search/", "")
                    not in r["colrev_origin"]
                ]
                pdf_same_toc_records = [
                    r
                    for r in source_records
                    if all(r.get(k, "NA") == v for k, v in toc_item.items())
                ]

                references = pd.DataFrame.from_dict(
                    processed_same_toc_records + pdf_same_toc_records
                )

                nr_entries = references.shape[0]
                if nr_entries == 0:
                    continue
                similarity_array = np.zeros([nr_entries, nr_entries])

                # Note : min_similarity only means that the PDF will be considered
                # for validates_based_on_metadata(...), which is the acutal test!
                min_similarity = 0.7
                similarity_array, tuples_to_process = self.__calculate_similarities(
                    similarity_array=similarity_array,
                    references=references,
                    min_similarity=min_similarity,
                )

                curated_record_ids = [r["ID"] for r in processed_same_toc_records]
                pdf_record_ids = [r["ID"] for r in pdf_same_toc_records]
                for tuple_to_process in tuples_to_process:
                    rec1 = records[tuple_to_process[0]]
                    rec2 = records[tuple_to_process[1]]

                    # Note : Focus on merges between
                    # curated_records and pdf_same_toc_records
                    # Note : this should also ensure that pdf groups are not merged
                    # until a corresponding curated record group is available.
                    if (
                        rec1["ID"] in curated_record_ids
                        and rec2["ID"] in curated_record_ids
                    ):
                        continue
                    if rec1["ID"] in pdf_record_ids and rec2["ID"] in pdf_record_ids:
                        continue

                    if "file" in rec2:
                        updated_record = rec1.copy()
                        updated_record["file"] = rec2["file"]
                    elif "file" in rec1:
                        updated_record = rec2.copy()
                        updated_record["file"] = rec1["file"]
                    else:  # None of the records is curated
                        continue

                    record = colrev.record.Record(data=updated_record)
                    validation_info = (
                        pdf_metadata_validation.validates_based_on_metadata(
                            review_manager=dedupe_operation.review_manager,
                            record=record,
                        )
                    )

                    overlapping_colrev_ids = colrev.record.Record(
                        data=rec1
                    ).has_overlapping_colrev_id(record=colrev.record.Record(data=rec2))
                    if validation_info["validates"] or overlapping_colrev_ids:

                        # Note : make sure that we merge into the CURATED record
                        if "file" in rec1:
                            if tuple_to_process[0] not in [
                                x["ID1"] for x in decision_list
                            ]:
                                decision_list.append(
                                    {
                                        "ID1": tuple_to_process[0],
                                        "ID2": tuple_to_process[1],
                                        "decision": "duplicate",
                                    }
                                )
                        else:
                            if tuple_to_process[1] not in [
                                x["ID1"] for x in decision_list
                            ]:
                                decision_list.append(
                                    {
                                        "ID1": tuple_to_process[1],
                                        "ID2": tuple_to_process[0],
                                        "decision": "duplicate",
                                    }
                                )

        # Note : dedupe.apply_merges reloads the records and
        # thereby discards previous changes
        if len(decision_list) > 0:
            dedupe_operation.review_manager.logger.info(
                f"{colors.GREEN}Duplicates identified{colors.END}"
            )
            print(decision_list)
            dedupe_operation.apply_merges(results=decision_list)

            dedupe_operation.review_manager.dataset.add_record_changes()

            dedupe_operation.review_manager.create_commit(
                msg="Merge duplicate records",
                script_call="colrev dedupe",
                saved_args={},
            )
        else:
            dedupe_operation.review_manager.logger.info(
                f"{colors.GREEN}No merge-candidates identified between sets{colors.END}"
            )


if __name__ == "__main__":
    pass
