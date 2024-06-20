import logging
import os
from pathlib import Path

import pytest

import colrev.review_manager
import colrev.settings
from colrev.constants import SearchType


def test_load_md(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the load utils for md files"""

    # only supports md
    with pytest.raises(NotImplementedError):
        os.makedirs("data/search", exist_ok=True)
        Path("data/search/table.ptvc").touch()
        try:
            colrev.loader.load_utils.load(
                filename=Path("data/search/table.ptvc"),
            )
        finally:
            Path("data/search/table.ptvc").unlink()

    # file must exist
    with pytest.raises(FileNotFoundError):
        colrev.loader.load_utils.load(
            filename=Path("non-existent.md"),
            logger=logging.getLogger(__name__),
            empty_if_file_not_exists=False,
        )

    if base_repo_review_manager.in_ci_environment():
        return

    search_source = colrev.settings.SearchSource(
        endpoint="colrev.unknown_source",
        filename=Path("data/search/md_data.md"),
        search_type=SearchType.OTHER,
        search_parameters={},
        comment="",
    )

    helpers.retrieve_test_file(
        source=Path("2_loader/data/md_data.md"),
        target=Path("data/search/md_data.md"),
    )

    records = colrev.loader.load_utils.load(
        filename=search_source.filename,
        logger=logging.getLogger(__name__),
    )

    assert records["1"]["ID"] == "1"
    assert records["1"]["ENTRYTYPE"] == "article"
    assert (
        records["1"]["title"]
        == "Systematic reviews: work that needs to be done and not to be done"
    )
    assert records["1"]["journal"] == "Journal of Evidence-Based Medicine"
    assert records["1"]["year"] == "2013"
    assert records["1"]["pages"] == "232--235"
    assert records["1"]["volume"] == "6"
    assert records["1"]["number"] == "4"
    assert records["1"]["author"] == "Adams, C and Polzmacher, S and Wolff, A"

    assert records["2"]["ID"] == "2"
    assert records["2"]["ENTRYTYPE"] == "article"
    assert (
        records["2"]["title"]
        == "Architecture of Sysperanto: a model-based ontology of the is field"
    )
    assert (
        records["2"]["journal"]
        == "Communications of the Association for Information Systems"
    )
    assert records["2"]["year"] == "2005"
    assert records["2"]["pages"] == "1--40"
    assert records["2"]["volume"] == "15"
    assert records["2"]["number"] == "1"
    assert records["2"]["author"] == "Alter, S"

    assert records["3"]["ID"] == "3"
    assert records["3"]["ENTRYTYPE"] == "article"
    assert (
        records["3"]["title"]
        == "Generating research questions through problematization"
    )
    assert records["3"]["journal"] == "Academy of Management Review"
    assert records["3"]["year"] == "2011"
    assert records["3"]["pages"] == "247--271"
    assert records["3"]["volume"] == "36"
    assert records["3"]["number"] == "2"
    assert records["3"]["author"] == "Alvesson, M and Sandberg, J"

    assert records["4"]["ID"] == "4"
    assert records["4"]["ENTRYTYPE"] == "article"
    assert (
        records["4"]["title"]
        == "Vision for SLR tooling infrastructure: prioritizing value-added requirements"
    )
    assert records["4"]["journal"] == "Information and Software Technology"
    assert records["4"]["year"] == "2017"
    assert records["4"]["pages"] == "72--81"
    assert records["4"]["volume"] == "91"
    assert records["4"]["author"] == "Al-Zubidy, A and Carver, J and Hale, D"

    assert records["5"]["ID"] == "5"
    assert records["5"]["ENTRYTYPE"] == "inproceedings"
    assert records["5"]["title"] == "Brainwash: a data system for feature engineering"
    assert (
        records["5"]["booktitle"]
        == "Proceedings of the biennial conference on innovative data systems research"
    )
    assert records["5"]["year"] == "2013"
    assert records["5"]["address"] == "Asilomar, CA"
    assert records["5"]["author"] == "Anderson, M and Antenucci, D and Bittorf, V"

    assert records["6"]["ID"] == "6"
    assert records["6"]["ENTRYTYPE"] == "article"
    assert (
        records["6"]["title"]
        == "Big data, big insights? Advancing service innovation and design with machine learning"
    )
    assert records["6"]["journal"] == "Journal of Service Research"
    assert records["6"]["year"] == "2017"
    assert records["6"]["pages"] == "17--39"
    assert records["6"]["volume"] == "21"
    assert records["6"]["number"] == "1"
    assert records["6"]["author"] == "Antons, D and Breidbach, C"

    nr_records = colrev.loader.load_utils.get_nr_records(Path("data/search/md_data.md"))
    assert 6 == nr_records
