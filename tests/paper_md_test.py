from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from typing import cast

from bibliography_io import load_raw
from bibliography_io import write
import pytest

import colrev.env.utils
from colrev.record.record_utils import index_records_by_id
from colrev.packages.paper_md.src.paper_md import PaperMarkdown


def test_append_to_non_sample_references_uses_bibliography_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    non_sample_references = tmp_path / "non_sample_references.bib"
    write(
        {
            "existing": {
                "ID": "existing",
                "ENTRYTYPE": "article",
                "title": "Existing reference",
            }
        },
        path=non_sample_references,
        primary=True,
    )
    changes: list[Path] = []
    paper = cast(Any, object.__new__(PaperMarkdown))
    paper.non_sample_references = non_sample_references
    paper.logger = logging.getLogger(__name__)
    paper.review_manager = SimpleNamespace(
        dataset=SimpleNamespace(git_repo=SimpleNamespace(add_changes=changes.append))
    )
    package_bibtex = """@article{existing,
  title = {Duplicate reference}
}

@article{added,
  title = {New reference}
}
"""
    monkeypatch.setattr(
        colrev.env.utils,
        "get_package_file_content",
        lambda *, module, filename: package_bibtex.encode("utf-8"),
    )

    paper._append_to_non_sample_references(
        module="test.module", filepath=Path("references.bib")
    )

    records = index_records_by_id(load_raw(non_sample_references))
    assert set(records) == {"existing", "added"}
    assert records["existing"]["title"] == "Existing reference"
    assert records["added"]["title"] == "New reference"
    for record in records.values():
        assert "colrev_origin" not in record
        assert "colrev_masterdata_provenance" not in record
        assert "colrev_data_provenance" not in record
    assert changes == [Path("data/data") / PaperMarkdown.NON_SAMPLE_REFERENCES_RELATIVE]


def test_copy_references_bib_uses_bibliography_io(tmp_path: Path) -> None:
    sample_references = tmp_path / "sample_references.bib"
    changes: list[Path] = []
    source_records = {
        "sample": {
            "ID": "sample",
            "ENTRYTYPE": "article",
            "title": "Sample reference",
            "colrev_origin": ["source.bib/sample"],
            "colrev_masterdata_provenance": {
                "title": {"source": "provider", "note": "verified"}
            },
            "custom.field": "value",
        }
    }
    paper = cast(Any, object.__new__(PaperMarkdown))
    paper.sample_references = sample_references
    paper.review_manager = SimpleNamespace(
        dataset=SimpleNamespace(
            load_records_dict=lambda: source_records,
            git_repo=SimpleNamespace(add_changes=changes.append),
        )
    )

    paper._copy_references_bib()

    records = index_records_by_id(load_raw(sample_references))
    assert "colrev_origin" not in records["sample"]
    assert "colrev_masterdata_provenance" not in records["sample"]
    assert "colrev_data_provenance" not in records["sample"]
    assert records["sample"]["custom_field"] == "value"
    assert changes == [sample_references]
