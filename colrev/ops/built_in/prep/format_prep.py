#! /usr/bin/env python
"""Formatting as a prep operation"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search_sources
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class FormatPrep(JsonSchemaMixin):
    """Prepares records by formatting fields"""

    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = "check with the developer"
    always_apply_changes = False

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare the record by formatting fields"""

        # pylint: disable=too-many-branches
        if "author" in record.data and "UNKNOWN" != record.data.get(
            "author", "UNKNOWN"
        ):
            # DBLP appends identifiers to non-unique authors
            record.update_field(
                key="author",
                value=str(re.sub(r"[0-9]{4}", "", record.data["author"])),
                source="FormatPrep",
                keep_source_if_equal=True,
            )

            # fix name format
            if (1 == len(record.data["author"].split(" ")[0])) or (
                ", " not in record.data["author"]
            ):
                record.update_field(
                    key="author",
                    value=colrev.record.PrepRecord.format_author_field(
                        input_string=record.data["author"]
                    ),
                    source="FormatPrep",
                    keep_source_if_equal=True,
                )

        if "title" in record.data and "UNKNOWN" != record.data.get("title", "UNKNOWN"):
            record.update_field(
                key="title",
                value=re.sub(r"\s+", " ", record.data["title"]).rstrip("."),
                source="FormatPrep",
                keep_source_if_equal=True,
            )
            if "UNKNOWN" != record.data["title"]:
                record.format_if_mostly_upper(key="title")

        if "booktitle" in record.data and "UNKNOWN" != record.data.get(
            "booktitle", "UNKNOWN"
        ):
            if "UNKNOWN" != record.data["booktitle"]:
                record.format_if_mostly_upper(key="booktitle", case="title")

                stripped_btitle = re.sub(r"\d{4}", "", record.data["booktitle"])
                stripped_btitle = re.sub(r"\d{1,2}th", "", stripped_btitle)
                stripped_btitle = re.sub(r"\d{1,2}nd", "", stripped_btitle)
                stripped_btitle = re.sub(r"\d{1,2}rd", "", stripped_btitle)
                stripped_btitle = re.sub(r"\d{1,2}st", "", stripped_btitle)
                stripped_btitle = re.sub(r"\([A-Z]{3,6}\)", "", stripped_btitle)
                stripped_btitle = stripped_btitle.replace(
                    "Proceedings of the", ""
                ).replace("Proceedings", "")
                stripped_btitle = stripped_btitle.lstrip().rstrip()
                record.update_field(
                    key="booktitle",
                    value=stripped_btitle,
                    source="FormatPrep",
                    keep_source_if_equal=True,
                )

        if "date" in record.data and "year" not in record.data:
            year = re.search(r"\d{4}", record.data["date"])
            if year:
                record.update_field(
                    key="year",
                    value=year.group(0),
                    source="FormatPrep",
                    keep_source_if_equal=True,
                )

        if "journal" in record.data and "UNKNOWN" != record.data.get(
            "journal", "UNKNOWN"
        ):
            if len(record.data["journal"]) > 10 and "UNKNOWN" != record.data["journal"]:
                record.format_if_mostly_upper(key="journal", case="title")

        if "pages" in record.data and "UNKNOWN" != record.data.get("pages", "UNKNOWN"):
            if "N.PAG" == record.data.get("pages", ""):
                record.remove_field(key="pages")
            else:
                record.unify_pages_field()
                if (
                    not re.match(r"^\d*$", record.data["pages"])
                    and not re.match(r"^\d*--\d*$", record.data["pages"])
                    and not re.match(r"^[xivXIV]*--[xivXIV]*$", record.data["pages"])
                ):
                    prep_operation.review_manager.report_logger.info(
                        f' {record.data["ID"]}:'.ljust(prep_operation.pad, " ")
                        + f'Unusual pages: {record.data["pages"]}'
                    )

        if "language" in record.data:
            # gh_issue https://github.com/geritwagner/colrev/issues/64
            # use https://pypi.org/project/langcodes/
            record.update_field(
                key="language",
                value=record.data["language"]
                .replace("English", "eng")
                .replace("ENG", "eng"),
                source="FormatPrep",
                keep_source_if_equal=True,
            )

        if "doi" in record.data:
            record.update_field(
                key="doi",
                value=record.data["doi"].replace("http://dx.doi.org/", "").upper(),
                source="FormatPrep",
                keep_source_if_equal=True,
            )

        if "number" not in record.data and "issue" in record.data:
            record.update_field(
                key="number",
                value=record.data["issue"],
                source="FormatPrep",
                keep_source_if_equal=True,
            )
            record.remove_field(key="issue")

        if "volume" in record.data and "UNKNOWN" != record.data.get(
            "volume", "UNKNOWN"
        ):
            record.update_field(
                key="volume",
                value=record.data["volume"].replace("Volume ", ""),
                source="FormatPrep",
                keep_source_if_equal=True,
            )

        if "url" in record.data and "fulltext" in record.data:
            if record.data["url"] == record.data["fulltext"]:
                record.remove_field(key="fulltext")

        return record


if __name__ == "__main__":
    pass
