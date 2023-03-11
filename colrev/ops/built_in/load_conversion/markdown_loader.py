#! /usr/bin/env python
"""Load conversion of reference sections (bibliographies) in md-documents based on GROBID"""
from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass

import requests
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.load

# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.LoadConversionPackageEndpointInterface
)
@dataclass
class MarkdownLoader(JsonSchemaMixin):

    """Loads reference strings from text (md) files (based on GROBID)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    ci_supported: bool = False

    supported_extensions = ["md"]

    def __init__(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        settings: dict,
    ):
        self.settings = self.settings_class.load_settings(data=settings)

    def load(
        self, load_operation: colrev.ops.load.Load, source: colrev.settings.SearchSource
    ) -> dict:
        """Load records from the source"""

        load_operation.review_manager.logger.info(
            "Running GROBID to parse structured reference data"
        )

        grobid_service = load_operation.review_manager.get_grobid_service()

        grobid_service.check_grobid_availability()
        with open(source.filename, encoding="utf8") as file:
            if source.filename.suffix == ".md":
                references = [line.rstrip() for line in file if "#" not in line[:2]]
            else:
                references = [line.rstrip() for line in file]

        data = ""
        ind = 0
        for ref in references:
            options = {}
            options["consolidateCitations"] = "0"
            options["citations"] = ref
            ret = requests.post(
                grobid_service.GROBID_URL + "/api/processCitation",
                data=options,
                headers={"Accept": "application/x-bibtex"},
                timeout=30,
            )
            ind += 1
            data = data + "\n" + ret.text.replace("{-1,", "{" + str(ind) + ",")

        records = load_operation.review_manager.dataset.load_records_dict(load_str=data)

        endpoint_dict = load_operation.package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            selected_packages=[asdict(source)],
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
