#! /usr/bin/env python
"""Load conversion of bib files using pybtex"""
from __future__ import annotations

import os
import re
import typing
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.load

# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument


@zope.interface.implementer(
    colrev.env.package_manager.LoadConversionPackageEndpointInterface
)
@dataclass
class BibPybtexLoader(JsonSchemaMixin):

    """Loads BibTeX files (based on pybtex)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    supported_extensions = ["bib"]

    ci_supported: bool = True

    def __init__(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def __general_load_fixes(self, records: dict) -> dict:
        return records

    def __apply_file_fixes(
        self, *, load_operation: colrev.ops.load.Load, filename: Path
    ) -> None:
        # pylint: disable=duplicate-code

        # Errors to fix before pybtex loading:
        # - set_incremental_ids (otherwise, not all records will be loaded)
        # - fix_keys (keys containing white spaces)
        record_ids: typing.List[str] = []
        with open(filename, "r+b") as file:
            seekpos = file.tell()
            line = file.readline()
            while line:
                if b"@" in line[:3]:
                    current_id = line[line.find(b"{") + 1 : line.rfind(b",")]
                    current_id_str = current_id.decode("utf-8").lstrip().rstrip()

                    if current_id_str in record_ids:
                        next_id = load_operation.review_manager.dataset.generate_next_unique_id(
                            temp_id=current_id_str, existing_ids=record_ids
                        )
                        load_operation.review_manager.logger.info(
                            f"Fix duplicate ID: {current_id_str} >> {next_id}"
                        )

                        replacement_line = (
                            line.decode("utf-8")
                            .replace(current_id.decode("utf-8"), next_id)
                            .encode("utf-8")
                        )

                        line = file.readline()
                        remaining = line + file.read()
                        file.seek(seekpos)
                        file.write(replacement_line)
                        seekpos = file.tell()
                        file.flush()
                        os.fsync(file)
                        file.write(remaining)
                        file.truncate()  # if the replacement is shorter...
                        file.seek(seekpos)

                        record_ids.append(next_id)

                    else:
                        record_ids.append(current_id_str)
                if re.match(
                    r"^\s*[a-zA-Z0-9]+\s+[a-zA-Z0-9]+\s*\=", line.decode("utf-8")
                ):
                    replacement_line = re.sub(
                        r"(^\s*)([a-zA-Z0-9]+)\s+([a-zA-Z0-9]+)(\s*\=)",
                        r"\1\2_\3\4",
                        line.decode("utf-8"),
                    ).encode("utf-8")
                    load_operation.review_manager.logger.info(
                        f"Fix invalid key: \n{line.decode('utf-8')}"
                        f"{replacement_line.decode('utf-8')}"
                    )
                    line = file.readline()
                    remaining = line + file.read()
                    file.seek(seekpos)
                    file.write(replacement_line)
                    seekpos = file.tell()
                    file.flush()
                    os.fsync(file)
                    file.write(remaining)
                    file.truncate()  # if the replacement is shorter...
                    file.seek(seekpos)

                seekpos = file.tell()
                line = file.readline()

    def load(
        self, load_operation: colrev.ops.load.Load, source: colrev.settings.SearchSource
    ) -> dict:
        """Load records from the source"""
        records = {}
        if source.filename.is_file():
            self.__apply_file_fixes(
                load_operation=load_operation, filename=source.filename
            )

            with open(source.filename, encoding="utf8") as bibtex_file:
                records = load_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )
        records = self.__general_load_fixes(records)

        endpoint_dict = load_operation.package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            selected_packages=[source.get_dict()],
            operation=load_operation,
            ignore_not_available=False,
        )
        endpoint = endpoint_dict[source.endpoint]

        records = endpoint.load_fixes(  # type: ignore
            load_operation, source=source, records=records
        )

        return records


if __name__ == "__main__":
    pass
