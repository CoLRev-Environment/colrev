#! /usr/bin/env python
"""ENLIT"""
from pathlib import Path

import pandas as pd
from bib_dedupe.bib_dedupe import block
from bib_dedupe.bib_dedupe import cluster
from bib_dedupe.bib_dedupe import match
from bib_dedupe.bib_dedupe import prep
from bib_dedupe.merge import merge

import colrev.env.tei_parser
import colrev.exceptions as colrev_exceptions
import colrev.ops.check
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import RecordState
from colrev.review_manager import ReviewManager


def _extract_references_from_records(
    review_manager: ReviewManager,
    records: dict,
) -> pd.DataFrame:
    """Extract references from records."""
    review_manager.logger.info("Extracting references...")
    refs_list = []
    for record in records.values():
        if Fields.FILE not in record:
            continue

        try:
            tei = colrev.env.tei_parser.TEIParser(
                pdf_path=Path(record[Fields.FILE]),
                tei_path=Path(
                    record[Fields.FILE]
                    .replace(".pdf", ".tei.xml")
                    .replace("/pdfs", "/.tei")
                ),
            )
            refs = tei.get_references(add_intext_citation_count=True)
            for ref in refs:
                ref[Fields.ID] = record["ID"] + "_" + ref[Fields.ID]

            refs_list.extend(refs)
            col = Colors.GREEN
            if len(refs) == 0:
                col = Colors.RED
            elif len(refs) < 10:
                col = Colors.ORANGE
            review_manager.logger.info(
                f" extracted {col}{str(len(refs)).rjust(4)}{Colors.END} references from {record[Fields.FILE]}"
            )
        except FileNotFoundError:
            review_manager.logger.warning(
                f"Could not find TEI file for {record[Fields.FILE]}: "
                "Please check the TEI file or the PDF."
            )
            continue
        except colrev_exceptions.TEIException:
            review_manager.logger.warning(
                f"Could not extract references from {record[Fields.FILE]}: "
                "Please check the TEI file or the PDF."
            )
            continue

    # Create a DataFrame from the flattened list of references
    df_all_references = pd.DataFrame(refs_list)
    df_all_references["nr_references"] = 1
    return df_all_references


def _load_included_records(review_manager: ReviewManager) -> pd.DataFrame:
    colrev.ops.check.CheckOperation(review_manager)
    records = review_manager.dataset.load_records_dict()

    records = {
        key: {
            k: v
            for k, v in record.items()
            if k not in [Fields.MD_PROV, Fields.D_PROV, Fields.ORIGIN]
        }
        for key, record in records.items()
        if record[Fields.STATUS]
        in [RecordState.rev_included, RecordState.rev_synthesized]
    }

    review_manager.logger.info(
        f"Loaded {len(records)} records (rev_included or rev_synthesized)."
    )
    return records


def main() -> None:
    """Main function to run the ENLIT script."""

    review_manager = ReviewManager()
    review_manager.logger.info("Start ENLIT")

    records = _load_included_records(review_manager=review_manager)

    # TODO : create a generic extract_citation_network() method in tei-utils?
    df_all_references = _extract_references_from_records(
        review_manager=review_manager,
        records=records,
    )

    def merge_into_list(values: list) -> str:
        """Concatenate all values into a single string, separated by commas."""
        merged_string = ",".join(
            str(value) for value in values if isinstance(value, str) and value != ""
        )
        return merged_string

    def sum_nr_references(values: list) -> int:
        """Sum all integers in a list."""
        return sum([int(value) for value in values if value != ""])

    records_df = prep(df_all_references, verbosity_level=0)
    deduplication_pairs = block(records_df, verbosity_level=0)
    matched_df = match(deduplication_pairs, verbosity_level=0)
    duplicate_id_sets = cluster(matched_df, verbosity_level=0)
    df_all_references = merge(
        df_all_references,
        duplicate_id_sets=duplicate_id_sets,
        merge_functions={
            Fields.NR_INTEXT_CITATIONS: merge_into_list,
            "nr_references": sum_nr_references,
        },
    )
    df_all_references["in_sample"] = False

    # df_all_references.to_csv("export.csv", index=False)

    df_records = pd.DataFrame.from_dict(records, orient="index")
    df_records["in_sample"] = True
    # drop colrev.data_provenance and colrev.master_data_provenance
    df_records = df_records.drop(
        columns=[Fields.MD_PROV, Fields.D_PROV], errors="ignore"
    )

    df_all_references = pd.concat([df_all_references, df_records], ignore_index=True)

    def select_original_id(values: list) -> str:
        """Select the original ID from the list of values."""
        for value in values:
            if isinstance(value, str) and "_b" not in value:
                return value
        return values[0] if values else ""

    def in_sample(values: list) -> bool:
        return any(str(v).lower() == "true" for v in values)

    # df_all_references.to_csv("export_before.csv", index=False, encoding="utf-8-sig")

    pre_duplication_size = df_all_references.shape[0]
    review_manager.logger.info(
        f"Citation network: {Colors.GREEN}{pre_duplication_size} references{Colors.END}"
    )
    review_manager.logger.info("Start deduplication...")

    records_df = prep(df_all_references, verbosity_level=0)
    deduplication_pairs = block(records_df, verbosity_level=0)
    matched_df = match(deduplication_pairs, verbosity_level=0)
    duplicate_id_sets = cluster(matched_df, verbosity_level=0)

    df_all_references = merge(
        df_all_references,
        duplicate_id_sets=duplicate_id_sets,
        merge_functions={
            # TODO : the ID-merging introduces problems...
            Fields.ID: select_original_id,
            Fields.NR_INTEXT_CITATIONS: merge_into_list,
            "nr_references": sum_nr_references,
            "in_sample": in_sample,
        },
    )

    df_all_references["in_sample"] = (
        df_all_references["in_sample"]
        .astype(str)
        .str.lower()
        .map({"true": True, "false": False})
    )

    df_all_references["nr_references"] = pd.to_numeric(
        df_all_references["nr_references"], errors="coerce"
    )
    df_all_references["nr_references"] = (
        df_all_references["nr_references"].fillna(0).astype(int)
    )

    # Print statistics: size before and after selection
    after_duplication_size = df_all_references.shape[0]
    nr_duplicates = pre_duplication_size - after_duplication_size
    review_manager.logger.info(
        f"Remove {Colors.RED}{str(nr_duplicates).rjust(6)} duplicates{Colors.END}:"
        f"    {Colors.GREEN}{str(after_duplication_size).rjust(6)} references{Colors.END}"
    )

    # Filter to keep only rows where nr_references > 0
    df_all_references = df_all_references[df_all_references["nr_references"] > 0]
    nr_cited = df_all_references.shape[0]
    non_cited_references = after_duplication_size - nr_cited
    review_manager.logger.info(
        f"Remove {Colors.RED}{str(non_cited_references).rjust(6)} non-cited{Colors.END}:"
        f"     {Colors.GREEN}{str(nr_cited).rjust(6)} references{Colors.END}"
    )

    df_all_references = df_all_references[df_all_references["in_sample"]]
    nr_in_sample = df_all_references.shape[0]
    out_of_sample_difference = nr_cited - nr_in_sample
    review_manager.logger.info(
        f"Remove {Colors.RED}{str(out_of_sample_difference).rjust(6)} "
        f"out-of-sample{Colors.END}: {Colors.GREEN}{str(nr_in_sample).rjust(6)} "
        f"references{Colors.END}"
    )

    # df_all_references.to_csv("export_2.csv", index=False, encoding="utf-8-sig")

    # Replace all whitespace-only strings with empty string, then NaN
    df_cleaned = df_all_references.replace(r"^\s*$", pd.NA, regex=True)

    # Drop columns where all values are missing (NaN or empty after replacement)
    df_all_references = df_cleaned.dropna(axis=1, how="all")

    # Ensure only existing columns are selected
    preferred_cols = ["nr_references", "nr_intext_citations"]
    existing_preferred_cols = [
        col for col in preferred_cols if col in df_all_references.columns
    ]

    # Put preferred columns first, then the rest
    cols = existing_preferred_cols + [
        col for col in df_all_references.columns if col not in existing_preferred_cols
    ]
    df_all_references = df_all_references[cols]

    # sort by nr_references
    df_all_references = df_all_references.sort_values(
        by="nr_references", ascending=False
    )

    # save to csv
    review_manager.logger.info(
        f"Saving list to {Colors.GREEN}enlit_references.csv{Colors.END}"
    )
    df_all_references.to_csv("enlit_references.csv", index=False, encoding="utf-8-sig")
