#!/usr/bin/env python
from pathlib import Path

import pytest

import colrev.exceptions as colrev_exceptions
import colrev.record


@pytest.fixture(scope="module")
def script_loc(request) -> Path:  # type: ignore
    """Return the directory of the currently running test script"""

    return Path(request.fspath).parent


@pytest.fixture
def record_with_pdf() -> colrev.record.Record:
    return colrev.record.Record(
        data={
            "ID": "WagnerLukyanenkoParEtAl2022",
            "ENTRYTYPE": "article",
            "file": Path("data/WagnerLukyanenkoParEtAl2022.pdf"),
        }
    )


v1 = {
    "ID": "R1",
    "ENTRYTYPE": "article",
    "colrev_masterdata_provenance": {
        "year": {"source": "import.bib/id_0001", "note": ""},
        "title": {"source": "import.bib/id_0001", "note": ""},
        "author": {"source": "import.bib/id_0001", "note": ""},
        "journal": {"source": "import.bib/id_0001", "note": ""},
        "volume": {"source": "import.bib/id_0001", "note": ""},
        "number": {"source": "import.bib/id_0001", "note": ""},
        "pages": {"source": "import.bib/id_0001", "note": ""},
    },
    "colrev_data_provenance": {},
    "colrev_status": colrev.record.RecordState.md_prepared,
    "colrev_origin": ["import.bib/id_0001"],
    "year": "2020",
    "title": "EDITORIAL",
    "author": "Rai, Arun",
    "journal": "MIS Quarterly",
    "volume": "45",
    "number": "1",
    "pages": "1--3",
}
v2 = {
    "ID": "R1",
    "ENTRYTYPE": "article",
    "colrev_masterdata_provenance": {
        "year": {"source": "import.bib/id_0001", "note": ""},
        "title": {"source": "import.bib/id_0001", "note": ""},
        "author": {"source": "import.bib/id_0001", "note": ""},
        "journal": {"source": "import.bib/id_0001", "note": ""},
        "volume": {"source": "import.bib/id_0001", "note": ""},
        "number": {"source": "import.bib/id_0001", "note": ""},
        "pages": {"source": "import.bib/id_0001", "note": ""},
    },
    "colrev_data_provenance": {},
    "colrev_status": colrev.record.RecordState.md_prepared,
    "colrev_origin": ["import.bib/id_0001"],
    "year": "2020",
    "title": "EDITORIAL",
    "author": "Rai, A",
    "journal": "MISQ",
    "volume": "45",
    "number": "1",
    "pages": "1--3",
}

R1 = colrev.record.Record(data=v1)
R2 = colrev.record.Record(data=v2)

WagnerLukyanenkoParEtAl2022_pdf_content = """Debates and Perspectives Paper

Artiﬁcial intelligence and the conduct of
literature reviews

Gerit Wagner, Roman Lukyanenko and Guy Par ´e 

Journal of Information Technology
2022, Vol. 37(2) 209–226
© Association for Information
Technology Trust 2021

Article reuse guidelines:
sagepub.com/journals-permissions
DOI: 10.1177/02683962211048201
Journals.sagepub.com/jinf

Abstract
Artiﬁcial intelligence (AI) is beginning to transform traditional research practices in many areas. In this context, literature
reviews stand out because they operate on large and rapidly growing volumes of documents, that is, partially structured
(meta)data, and pervade almost every type of paper published in information systems research or related social science
disciplines. To familiarize researchers with some of the recent trends in this area, we outline how AI can expedite individual
steps of the literature review process. Considering that the use of AI in this context is in an early stage of development, we
propose a comprehensive research agenda for AI-based literature reviews (AILRs) in our ﬁeld. With this agenda, we would
like to encourage design science research and a broader constructive discourse on shaping the future of AILRs in research.

Keywords
Artiﬁcial
automation, literature review

intelligence, machine learning, natural

language processing, research data management, data infrastructure,

Introduction
The potential of artiﬁcial intelligence (AI) to augment and
partially automate research has sparked vivid debates in
many scientiﬁc disciplines, including the health sciences
(Adams et al., 2013; Tsafnat et al., 2014), biology (King
et al., 2009), and management (Johnson et al., 2019). In
particular, the concept of automated science is raising in-
triguing questions related to the future of research in dis-
ciplines that require “high-level abstract thinking, intricate
knowledge of methodologies and epistemology, and per-
suasive writing capabilities” (Johnson et al., 2019: 292).
These debates resonate with scholars in Information Sys-
tems (IS), who ponder which role AI and automation can
play in theory development (Tremblay et al., 2018) and in
combining data-driven and theory-driven research (Maass
et al., 2018). With this commentary, we join the discussion
which has been resumed recently by Johnson et al. (2019) in
the business disciplines. The authors observe that across this
multi-disciplinary discourse, two dominant narratives have
emerged. The ﬁrst narrative adopts a provocative and vi-
sionary perspective to present its audience with a choice
between accepting or rejecting future research practices in
which AI plays a dominant role. The second narrative
acknowledges that a gradual adoption of AI-based research
tools has already begun and aims at engaging its readers in a
constructive debate on how to leverage AI-based tools for

the beneﬁt of the research ﬁeld and its stakeholders. In this
paper, our position resonates more with the latter per-
spective, which is focused on the mid-term instead of the
long-term, and well-positioned to advance the discourse
with less speculative and more actionable discussions of the
speciﬁc research processes that are more amenable appli-
cations of AI and those processes that rely more on the
human ingenuity of researchers.

In this essay, we focus on the use of AI-based tools in the
conduct of literature reviews. Advancing knowledge in this
area is particularly promising since (1) standalone review
projects require substantial efforts over months and years
(Larsen et al., 2019), (2) the volume of reviews published in
IS journals has been rising steadily (Schryen et al., 2020),
and (3) literature reviews involve tasks that fall on a
spectrum between the mechanical and the creative . At the
same time, the process of reviewing literature is mostly
conducted manually with sample sizes threatening to exceed
the cognitive limits of human processing capacities. This

Department of Information Technologies, HEC Montr´eal, Montr´eal,
Qu´ebec, Canada

Corresponding author:
Guy Par´e, Research Chair in Digital Health, HEC Montr´eal, 3000, chemin
de la C ˆote-Sainte-Catherin Montr´eal, Qu´ebec H3T 2A7, Canada.
Email: guy.pare@hec.ca"""


def test_eq() -> None:
    assert R1 == R1
    assert R1 != R2


def test_copy() -> None:
    R1_cop = R1.copy()
    assert R1 == R1_cop


def test_update_field() -> None:
    R2_mod = R2.copy()

    # Test append_edit=True / identifying_field
    R2_mod.update_field(
        key="journal", value="Mis Quarterly", source="test", append_edit=True
    )
    expected = "import.bib/id_0001|test"
    actual = R2_mod.data["colrev_masterdata_provenance"]["journal"]["source"]
    assert expected == actual

    # Test append_edit=True / non-identifying_field
    R2_mod.update_field(
        key="non_identifying_field", value="nfi_value", source="import.bib/id_0001"
    )
    R2_mod.update_field(
        key="non_identifying_field", value="changed", source="test", append_edit=True
    )
    expected = "import.bib/id_0001|test"
    actual = R2_mod.data["colrev_data_provenance"]["non_identifying_field"]["source"]
    assert expected == actual

    # Test append_edit=True (without key in *provenance) / identifying field
    del R2_mod.data["colrev_masterdata_provenance"]["journal"]
    R2_mod.update_field(
        key="journal", value="Mis Quarterly", source="test", append_edit=True
    )
    expected = "original|test"
    actual = R2_mod.data["colrev_masterdata_provenance"]["journal"]["source"]
    assert expected == actual

    # Test append_edit=True (without key in *provenance) / non-identifying field
    del R2_mod.data["colrev_data_provenance"]["non_identifying_field"]
    R2_mod.update_field(key="non_identifying_field", value="nfi_value", source="test")
    expected = "original|test"
    actual = R2_mod.data["colrev_data_provenance"]["non_identifying_field"]["source"]
    assert expected == actual


def test_rename_field() -> None:
    R2_mod = R2.copy()

    # Identifying field
    R2_mod.rename_field(key="journal", new_key="booktitle")
    expected = "import.bib/id_0001|rename-from:journal"
    actual = R2_mod.data["colrev_masterdata_provenance"]["booktitle"]["source"]
    assert expected == actual
    assert "journal" not in R2_mod.data
    assert "journal" not in R2_mod.data["colrev_masterdata_provenance"]

    # Non-identifying field
    R2_mod.update_field(
        key="link", value="https://www.test.org", source="import.bib/id_0001"
    )
    R2_mod.rename_field(key="link", new_key="url")
    expected = "import.bib/id_0001|rename-from:link"
    actual = R2_mod.data["colrev_data_provenance"]["url"]["source"]
    assert expected == actual
    assert "link" not in R2_mod.data
    assert "link" not in R2_mod.data["colrev_data_provenance"]


def test_remove_field() -> None:
    R2_mod = R2.copy()
    del R2_mod.data["colrev_masterdata_provenance"]["number"]
    R2_mod.remove_field(key="number", not_missing_note=True, source="test")
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "test", "note": "not_missing"},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, A",
        "journal": "MISQ",
        "volume": "45",
        "pages": "1--3",
    }

    actual = R2_mod.data
    print(actual)
    assert expected == actual


def test_masterdata_is_complete() -> None:
    R1_mod = R1.copy()

    R1_mod.remove_field(key="number", not_missing_note=True, source="test")
    assert R1_mod.masterdata_is_complete()

    R1_mod.data["colrev_masterdata_provenance"]["number"]["note"] = "missing"
    assert not R1_mod.masterdata_is_complete()

    R1_mod.data["colrev_masterdata_provenance"] = {
        "CURATED": {"source": ":https...", "note": ""}
    }
    assert R1_mod.masterdata_is_complete()


def test_diff() -> None:
    R2_mod = R2.copy()
    R2_mod.remove_field(key="pages")
    # keep_source_if_equal
    R2_mod.update_field(
        key="journal", value="MISQ", source="test", keep_source_if_equal=True
    )

    R2_mod.update_field(key="non_identifying_field", value="nfi_value", source="test")
    R2_mod.update_field(key="booktitle", value="ICIS", source="test")
    R2_mod.update_field(key="publisher", value="Elsevier", source="test")
    print(R1.get_diff(other_record=R2_mod))
    expected = [
        (
            "add",
            "",
            [
                ("booktitle", {"source": "test", "note": ""}),
                ("publisher", {"source": "test", "note": ""}),
            ],
        ),
        ("remove", "", [("pages", {"source": "import.bib/id_0001", "note": ""})]),
        ("change", "author", ("Rai, Arun", "Rai, A")),
        ("change", "journal", ("MIS Quarterly", "MISQ")),
        ("add", "", [("booktitle", "ICIS"), ("publisher", "Elsevier")]),
        ("remove", "", [("pages", "1--3")]),
    ]
    actual = R1.get_diff(other_record=R2_mod)
    assert expected == actual

    print(R1.get_diff(other_record=R2_mod, identifying_fields_only=False))
    expected = [
        (
            "add",
            "colrev_masterdata_provenance",
            [
                ("booktitle", {"source": "test", "note": ""}),
                ("publisher", {"source": "test", "note": ""}),
            ],
        ),
        (
            "remove",
            "colrev_masterdata_provenance",
            [("pages", {"source": "import.bib/id_0001", "note": ""})],
        ),
        (
            "add",
            "colrev_data_provenance",
            [("non_identifying_field", {"source": "test", "note": ""})],
        ),
        ("change", "author", ("Rai, Arun", "Rai, A")),
        ("change", "journal", ("MIS Quarterly", "MISQ")),
        (
            "add",
            "",
            [
                ("non_identifying_field", "nfi_value"),
                ("booktitle", "ICIS"),
                ("publisher", "Elsevier"),
            ],
        ),
        ("remove", "", [("pages", "1--3")]),
    ]
    actual = R1.get_diff(other_record=R2_mod, identifying_fields_only=False)
    assert expected == actual


def test_change_entrytype_inproceedings() -> None:
    R1_mod = R1.copy()
    R1_mod.data["volume"] = "UNKNOWN"
    R1_mod.data["number"] = "UNKNOWN"
    R1_mod.data["title"] = "Editorial"
    R1_mod.update_field(
        key="publisher",
        value="Elsevier",
        source="import.bib/id_0001",
        note="inconsistent with entrytype",
    )
    R1_mod.change_entrytype(new_entrytype="inproceedings")
    print(R1_mod.data)
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "inproceedings",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
            "publisher": {"source": "import.bib/id_0001", "note": ""},
            "booktitle": {
                "source": "import.bib/id_0001|rename-from:journal",
                "note": "",
            },
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "booktitle": "MIS Quarterly",
        "year": "2020",
        "title": "Editorial",
        "author": "Rai, Arun",
        "pages": "1--3",
        "publisher": "Elsevier",
    }
    actual = R1_mod.data
    assert expected == actual

    with pytest.raises(
        colrev.exceptions.MissingRecordQualityRuleSpecification,
    ):
        R1_mod.change_entrytype(new_entrytype="dialoge")

    # assert "" == R1_mod.data


def test_get_inconsistencies() -> None:
    R1_mod = R1.copy()
    R1_mod.data["ENTRYTYPE"] = "phdthesis"
    R1_mod.data["author"] = "Author, Name and Other, Author"
    expected = {"volume", "number", "journal", "author"}
    actual = R1_mod.get_inconsistencies()
    assert expected == actual

    assert R1_mod.has_inconsistent_fields()


def test_change_entrytype_article() -> None:
    input = {
        "ID": "R1",
        "ENTRYTYPE": "inproceedings",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
            "publisher": {"source": "import.bib/id_0001", "note": ""},
            "booktitle": {
                "source": "import.bib/id_0001",
                "note": "",
            },
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "booktitle": "MIS Quarterly",
        "year": "2020",
        "title": "Editorial",
        "author": "Rai, Arun",
        "pages": "1--3",
        "publisher": "Elsevier",
    }
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
            "publisher": {"source": "import.bib/id_0001", "note": ""},
            "journal": {
                "source": "import.bib/id_0001|rename-from:booktitle",
                "note": "",
            },
            "volume": {"source": "generic_field_requirements", "note": "missing"},
            "number": {"source": "generic_field_requirements", "note": "missing"},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_needs_manual_preparation,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "Editorial",
        "author": "Rai, Arun",
        "pages": "1--3",
        "publisher": "Elsevier",
        "journal": "MIS Quarterly",
        "volume": "UNKNOWN",
        "number": "UNKNOWN",
    }
    REC = colrev.record.Record(data=input)
    REC.change_entrytype(new_entrytype="article")
    actual = REC.data
    assert expected == actual


def test_add_provenance_all() -> None:
    R1_mod = R1.copy()
    del R1_mod.data["colrev_masterdata_provenance"]
    R1_mod.add_provenance_all(source="import.bib/id_0001")
    print(R1_mod.data)
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_data_provenance": {
            "ID": {"source": "import.bib/id_0001", "note": ""},
            "colrev_origin": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
    }
    actual = R1_mod.data
    assert expected == actual


def test_format_bib_style() -> None:
    expected = "Rai, Arun (2020) EDITORIAL. MIS Quarterly, (45) 1"
    actual = R1.format_bib_style()
    assert expected == actual


def test_shares_origins() -> None:
    assert R1.shares_origins(other_record=R2)


def test_set_status() -> None:
    R1_mod = R1.copy()
    R1_mod.data["author"] = "UNKNOWN"
    R1_mod.set_status(target_state=colrev.record.RecordState.md_prepared)
    expected = colrev.record.RecordState.md_needs_manual_preparation
    actual = R1_mod.data["colrev_status"]
    assert expected == actual


def test_get_value() -> None:
    expected = "Rai, Arun"
    actual = R1.get_value(key="author")
    assert expected == actual

    expected = "Rai, Arun"
    actual = R1.get_value(key="author", default="custom_file")
    assert expected == actual

    expected = "custom_file"
    actual = R1.get_value(key="file", default="custom_file")
    assert expected == actual


def test_create_colrev_id() -> None:
    # Test type: phdthesis
    R1_mod = R1.copy()
    R1_mod.data["ENTRYTYPE"] = "phdthesis"
    R1_mod.data["school"] = "University of Minnesota"
    R1_mod.data["colrev_id"] = R1_mod.create_colrev_id()
    expected = ["colrev_id1:|phdthesis|university-of-minnesota|2020|rai|editorial"]
    actual = R1_mod.get_colrev_id()
    assert expected == actual

    # Test type: techreport
    R1_mod = R1.copy()
    R1_mod.data["ENTRYTYPE"] = "techreport"
    R1_mod.data["institution"] = "University of Minnesota"
    R1_mod.data["colrev_id"] = R1_mod.create_colrev_id()
    expected = ["colrev_id1:|techreport|university-of-minnesota|2020|rai|editorial"]
    actual = R1_mod.get_colrev_id()
    assert expected == actual

    # Test type: inproceedings
    R1_mod = R1.copy()
    R1_mod.data["ENTRYTYPE"] = "inproceedings"
    R1_mod.data["booktitle"] = "International Conference on Information Systems"
    R1_mod.data["colrev_id"] = R1_mod.create_colrev_id()
    expected = [
        "colrev_id1:|p|international-conference-on-information-systems|2020|rai|editorial"
    ]
    actual = R1_mod.get_colrev_id()
    assert expected == actual

    # Test type: article
    R1_mod = R1.copy()
    R1_mod.data["ENTRYTYPE"] = "article"
    R1_mod.data["journal"] = "Journal of Management Information Systems"
    R1_mod.data["colrev_id"] = R1_mod.create_colrev_id()
    expected = [
        "colrev_id1:|a|journal-of-management-information-systems|45|1|2020|rai|editorial"
    ]
    actual = R1_mod.get_colrev_id()
    assert expected == actual

    # Test type: article
    R1_mod = R1.copy()
    R1_mod.data["ENTRYTYPE"] = "monogr"
    R1_mod.data["series"] = "Lecture notes in cs"
    R1_mod.data["colrev_id"] = R1_mod.create_colrev_id()
    expected = ["colrev_id1:|monogr|lecture-notes-in-cs|2020|rai|editorial"]
    actual = R1_mod.get_colrev_id()
    assert expected == actual

    # Test type: article
    R1_mod = R1.copy()
    R1_mod.data["ENTRYTYPE"] = "online"
    R1_mod.data["url"] = "www.loc.de/subpage.html"
    R1_mod.data["colrev_id"] = R1_mod.create_colrev_id()
    expected = ["colrev_id1:|online|wwwlocde-subpagehtml|2020|rai|editorial"]
    actual = R1_mod.get_colrev_id()
    assert expected == actual


def test_get_colrev_id() -> None:
    R1_mod = R1.copy()
    R1_mod.data["colrev_id"] = R1_mod.create_colrev_id()
    expected = ["colrev_id1:|a|mis-quarterly|45|1|2020|rai|editorial"]
    actual = R1_mod.get_colrev_id()
    assert expected == actual


def test_add_colrev_ids() -> None:
    expected = "colrev_id1:|a|mis-quarterly|45|1|2020|rai|editorial"
    actual = R1.create_colrev_id()
    assert expected == actual

    expected = "colrev_id1:|a|misq|45|1|2020|rai|editorial"
    actual = R2.create_colrev_id()
    assert expected == actual


def test_has_overlapping_colrev_id() -> None:
    R1_mod = R1.copy()
    R1_mod.data["colrev_id"] = R1_mod.create_colrev_id()

    R2_mod = R1.copy()
    R2_mod.data["colrev_id"] = R2_mod.create_colrev_id()

    assert R2_mod.has_overlapping_colrev_id(record=R1_mod)

    R2_mod.data["colrev_id"] = []
    assert not R2_mod.has_overlapping_colrev_id(record=R1_mod)


def test_provenance() -> None:
    R1_mod = R1.copy()

    R1_mod.add_data_provenance(key="url", source="manual", note="test")
    expected = "manual"
    actual = R1_mod.data["colrev_data_provenance"]["url"]["source"]
    assert expected == actual

    expected = "test"
    actual = R1_mod.data["colrev_data_provenance"]["url"]["note"]
    assert expected == actual

    R1_mod.add_data_provenance_note(key="url", note="1")
    expected = "test,1"
    actual = R1_mod.data["colrev_data_provenance"]["url"]["note"]
    assert expected == actual

    expected = {"source": "manual", "note": "test,1"}  # type: ignore
    actual = R1_mod.get_field_provenance(key="url")
    assert expected == actual

    R1_mod.add_masterdata_provenance(key="author", source="manual", note="test")
    expected = "test"
    actual = R1_mod.data["colrev_masterdata_provenance"]["author"]["note"]
    assert expected == actual

    actual = R1_mod.data["colrev_masterdata_provenance"]["author"]["source"]
    expected = "manual"
    assert expected == actual

    R1_mod.add_masterdata_provenance_note(key="author", note="check")
    expected = "test,check"
    actual = R1_mod.data["colrev_masterdata_provenance"]["author"]["note"]
    assert expected == actual


def test_set_masterdata_complete() -> None:
    # field=UNKNOWN and no not_missing note
    R1_mod = R1.copy()
    R1_mod.data["number"] = "UNKNOWN"
    R1_mod.data["volume"] = "UNKNOWN"
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "test", "note": "not_missing"},
            "number": {"source": "test", "note": "not_missing"},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "pages": "1--3",
    }
    R1_mod.set_masterdata_complete(source="test")
    actual = R1_mod.data
    print(R1_mod.data)
    assert expected == actual

    # missing fields and no colrev_masterdata_provenance
    R1_mod = R1.copy()
    del R1_mod.data["volume"]
    del R1_mod.data["number"]
    del R1_mod.data["colrev_masterdata_provenance"]["number"]
    del R1_mod.data["colrev_masterdata_provenance"]["volume"]
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "test", "note": "not_missing"},
            "number": {"source": "test", "note": "not_missing"},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "pages": "1--3",
    }
    R1_mod.set_masterdata_complete(source="test")
    actual = R1_mod.data
    print(R1_mod.data)
    assert expected == actual

    # misleading "missing" note
    R1_mod = R1.copy()
    R1_mod.data["colrev_masterdata_provenance"]["volume"]["note"] = "missing"
    R1_mod.data["colrev_masterdata_provenance"]["number"]["note"] = "missing"
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }

    R1_mod.set_masterdata_complete(source="test")
    actual = R1_mod.data
    print(R1_mod.data)
    assert expected == actual

    R1_mod.data["colrev_masterdata_provenance"] = {
        "CURATED": {"source": ":https...", "note": ""}
    }
    R1_mod.set_masterdata_complete(source="test")
    del R1_mod.data["colrev_masterdata_provenance"]
    R1_mod.set_masterdata_complete(source="test")


def test_set_masterdata_consistent() -> None:
    R1_mod = R1.copy()
    R1_mod.data["colrev_masterdata_provenance"]["journal"][
        "note"
    ] = "inconsistent with ENTRYTYPE"
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }
    R1_mod.set_masterdata_consistent()
    actual = R1_mod.data
    print(actual)
    assert expected == actual

    R1_mod = R1.copy()
    del R1_mod.data["colrev_masterdata_provenance"]
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {},
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }
    R1_mod.set_masterdata_consistent()
    actual = R1_mod.data
    print(actual)
    assert expected == actual


def test_set_fields_complete() -> None:
    R1_mod = R1.copy()
    R1_mod.data["colrev_masterdata_provenance"]["number"]["note"] = "incomplete"
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }

    R1_mod.set_fields_complete()
    actual = R1_mod.data
    print(actual)
    assert expected == actual


def test_get_missing_fields() -> None:
    R1_mod = R1.copy()
    R1_mod.data["ENTRYTYPE"] = "dialogue"

    with pytest.raises(
        colrev.exceptions.MissingRecordQualityRuleSpecification,
    ):
        R1_mod.get_missing_fields()


def test_reset_pdf_provenance_notes() -> None:
    # defects
    R1_mod = R1.copy()
    R1_mod.data["colrev_data_provenance"]["file"] = {
        "source": "test",
        "note": "defects",
    }
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {
            "file": {"source": "test", "note": ""},
        },
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }
    R1_mod.reset_pdf_provenance_notes()
    actual = R1_mod.data
    assert expected == actual

    # missing provenance
    R1_mod = R1.copy()
    del R1_mod.data["colrev_data_provenance"]
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {"file": {"source": "ORIGINAL", "note": ""}},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }
    R1_mod.reset_pdf_provenance_notes()
    actual = R1_mod.data
    assert expected == actual

    # file missing in missing provenance
    R1_mod = R1.copy()
    # del R1_mod.data["colrev_data_provenance"]["file"]
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {
            "file": {"source": "NA", "note": ""},
        },
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }
    R1_mod.reset_pdf_provenance_notes()
    actual = R1_mod.data
    print(actual)
    assert expected == actual


def test_cleanup_pdf_processing_fields() -> None:
    R1_mod = R1.copy()
    R1_mod.data["text_from_pdf"] = "This is the full text inserted from the PDF...."
    R1_mod.data["pages_in_file"] = "12"

    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }
    R1_mod.cleanup_pdf_processing_fields()
    actual = R1_mod.data
    print(actual)
    assert expected == actual


def test_get_tei_filename() -> None:
    R1_mod = R1.copy()
    R1_mod.data["file"] = "data/pdfs/Rai2020.pdf"
    expected = Path("data/.tei/Rai2020.tei.xml")
    actual = R1_mod.get_tei_filename()
    assert expected == actual


def test_get_record_similarity() -> None:
    expected = 0.854
    actual = colrev.record.Record.get_record_similarity(record_a=R1, record_b=R2)
    assert expected == actual


def test_get_incomplete_fields() -> None:
    R1_mod = R1.copy()
    R1_mod.data["title"] = "Editoria…"
    expected = {"title"}
    actual = R1_mod.get_incomplete_fields()
    assert expected == actual

    R1_mod.data["author"] = "Rai, Arun et al."
    expected = {"title", "author"}
    actual = R1_mod.get_incomplete_fields()
    assert expected == actual

    assert R1_mod.has_incomplete_fields()


def test_merge_select_non_all_caps() -> None:
    # Select title-case (not all-caps title) and full author name
    R1 = colrev.record.Record(data=v1)
    R2 = colrev.record.Record(data=v2)

    R1_mod = R1.copy()
    R2_mod = R2.copy()
    print(R1_mod)
    print(R2_mod)
    R1_mod.data["title"] = "Editorial"
    R2_mod.data["colrev_origin"] = ["import.bib/id_0002"]
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001", "import.bib/id_0002"],
        "year": "2020",
        "title": "Editorial",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }

    R1_mod.merge(merging_record=R2_mod, default_source="test")
    actual = R1_mod.data
    assert expected == actual


def test_merge_except_errata() -> None:
    # Mismatching part suffixes
    R1_mod = R1.copy()
    R2_mod = R2.copy()
    R1_mod.data["title"] = "Editorial - Part 1"
    R2_mod.data["title"] = "Editorial - Part 2"
    with pytest.raises(
        colrev.exceptions.InvalidMerge,
    ):
        R2_mod.merge(merging_record=R1_mod, default_source="test")

    # Mismatching erratum (a-b)
    R1_mod = R1.copy()
    R2_mod = R2.copy()
    R2_mod.data["title"] = "Erratum - Editorial"
    with pytest.raises(
        colrev.exceptions.InvalidMerge,
    ):
        R1_mod.merge(merging_record=R2_mod, default_source="test")

    # Mismatching erratum (b-a)
    R1_mod = R1.copy()
    R2_mod = R2.copy()
    R1_mod.data["title"] = "Erratum - Editorial"
    with pytest.raises(
        colrev.exceptions.InvalidMerge,
    ):
        R2_mod.merge(merging_record=R1_mod, default_source="test")

    # Mismatching commentary
    R1_mod = R1.copy()
    R2_mod = R2.copy()
    R1_mod.data["title"] = "Editorial - a commentary to the other paper"
    with pytest.raises(
        colrev.exceptions.InvalidMerge,
    ):
        R2_mod.merge(merging_record=R1_mod, default_source="test")


def test_merge_local_index(mocker) -> None:  # type: ignore
    import colrev.record
    import colrev.env.local_index

    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Gerit Wagner", "gerit.wagner@uni-bamberg.de"),
    )

    R1_mod = colrev.record.Record(
        data={
            "ID": "R1",
            "colrev_data_provenance": {},
            "colrev_masterdata_provenance": {
                "volume": {"source": "source-1", "note": ""}
            },
            "colrev_status": colrev.record.RecordState.md_prepared,
            "colrev_origin": ["orig1"],
            "title": "EDITORIAL",
            "author": "Rai, Arun",
            "journal": "MIS Quarterly",
            "volume": "45",
            "pages": "1--3",
        }
    )
    R2_mod = colrev.record.Record(
        data={
            "ID": "R2",
            "colrev_data_provenance": {},
            "colrev_masterdata_provenance": {
                "volume": {"source": "source-1", "note": ""},
                "number": {"source": "source-1", "note": ""},
            },
            "colrev_status": colrev.record.RecordState.md_prepared,
            "colrev_origin": ["orig2"],
            "title": "Editorial",
            "author": "ARUN RAI",
            "journal": "MISQ",
            "volume": "45",
            "number": "4",
            "pages": "1--3",
        }
    )

    R1_mod.merge(merging_record=R2, default_source="test")
    print(R1_mod)

    # from colrev.env import LocalIndex

    # LOCAL_INDEX = LocalIndex()
    # record = {
    #     "ID": "StandingStandingLove2010",
    #     "ENTRYTYPE": "article",
    #     "colrev_origin": "lr_db.bib/Standing2010",
    #     "colrev_status": RecordState.rev_synthesized,
    #     "colrev_id": "colrev_id1:|a|decision-support-systems|49|1|2010|standing-standing-love|a-review-of-research-on-e-marketplaces-1997-2008;",
    #     "colrev_pdf_id": "cpid1:ffffffffffffffffc3f00fffc2000023c2000023c0000003ffffdfffc0005fffc007ffffffffffffffffffffc1e00003c1e00003cfe00003ffe00003ffe00003ffffffffe7ffffffe3dd8003c0008003c0008003c0008003c0008003c0008003c0008003c0008003c0018003ffff8003e7ff8003e1ffffffffffffffffffffff",
    #     "exclusion_criteria": "NA",
    #     "file": "/home/gerit/ownCloud/data/journals/DSS/49_1/A-review-of-research-on-e-marketplaces-1997-2008_2010.pdf",
    #     "doi": "10.1016/J.DSS.2009.12.008",
    #     "author": "Standing, Susan and Standing, Craig and Love, Peter E. D",
    #     "journal": "Decision Support Systems",
    #     "title": "A review of research on e-marketplaces 1997–2008",
    #     "year": "2010",
    #     "volume": "49",
    #     "number": "1",
    #     "pages": "41--51",
    #     "literature_review": "yes",
    #     "metadata_source_repository_paths": "/home/gerit/ownCloud/data/AI Research/Literature Reviews/LRDatabase/wip/lrs_target_variable",
    # }

    # LOCAL_INDEX.index_record(record=record)

    # DEDUPE test:

    LOCAL_INDEX = colrev.env.local_index.LocalIndex()
    mocker.patch(
        "colrev.env.local_index.LocalIndex.is_duplicate", return_value="unknown"
    )

    # short cids / empty lists
    assert "unknown" == LOCAL_INDEX.is_duplicate(
        record1_colrev_id=[], record2_colrev_id=[]
    )
    assert "unknown" == LOCAL_INDEX.is_duplicate(
        record1_colrev_id=["short"], record2_colrev_id=["short"]
    )

    # Same repo and overlapping colrev_ids -> duplicate
    # assert "yes" == LOCAL_INDEX.is_duplicate(
    #     record1_colrev_id=[
    #         "colrev_id1:|a|mis-quarterly|26|4|2002|jasperson-carte-saunders-butler-croes-zheng|power-and-information-technology-research-a-metatriangulation-review"
    #     ],
    #     record2_colrev_id=[
    #         "colrev_id1:|a|mis-quarterly|26|4|2002|jasperson-carte-saunders-butler-croes-zheng|review-power-and-information-technology-research-a-metatriangulation-review"
    #     ],
    # )

    mocker.patch("colrev.env.local_index.LocalIndex.is_duplicate", return_value="no")

    # Different curated repos -> no duplicate
    assert "no" == LOCAL_INDEX.is_duplicate(
        record1_colrev_id=[
            "colrev_id1:|a|mis-quarterly|26|4|2002|jasperson-carte-saunders-butler-croes-zheng|power-and-information-technology-research-a-metatriangulation-review"
        ],
        record2_colrev_id=[
            "colrev_id1:|a|information-systems-research|15|2|2004|fichman|real-options-and-it-platform-adoption-implications-for-theory-and-practice"
        ],
    )


def test_get_quality_defects() -> None:
    v_t = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_data_provenance": {},
        "colrev_masterdata_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "Editorial",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
        "url": "www.test.com",
    }

    author_defects = [
        "RAI",  # all-caps
        "Rai, Arun and B",  # incomplete part
        "Rai, Phd, Arun",  # additional title
        "Rai, Arun; Straub, Detmar",  # incorrect delimiter
        "Mathiassen, Lars and jonsson, katrin and Holmstrom, Jonny",  # author without capital letters
        "University, Villanova and Sipior, Janice",  # University in author field
    ]
    for author_defect in author_defects:
        v_t["author"] = author_defect
        R1_mod = colrev.record.Record(data=v_t)
        expected = {"author"}
        actual = set(R1_mod.get_quality_defects())
        assert expected == actual
        assert R1_mod.has_quality_defects()

    non_author_defects = ["Mourato, Inês and Dias, Álvaro and Pereira, Leandro"]
    for non_author_defect in non_author_defects:
        v_t["author"] = non_author_defect
        R1_mod = colrev.record.Record(data=v_t)
        expected = set()
        actual = set(R1_mod.get_quality_defects())
        assert expected == actual
        assert not R1_mod.has_quality_defects()

    v_t["author"] = "Rai, Arun"

    title_defects = ["EDITORIAL"]  # all-caps
    for title_defect in title_defects:
        v_t["title"] = title_defect
        R1_mod = colrev.record.Record(data=v_t)
        expected = {"title"}
        actual = set(R1_mod.get_quality_defects())
        assert expected == actual
        assert R1_mod.has_quality_defects()


def test_apply_restrictions() -> None:
    input = {"ENTRYTYPE": "phdthesis"}
    R_test = colrev.record.Record(data=input)
    restrictions = {
        "ENTRYTYPE": "article",
        "journal": "MISQ",
        "booktitle": "ICIS",
        "volume": True,
        "number": True,
    }
    R_test.apply_restrictions(restrictions=restrictions)
    expected = {
        "ENTRYTYPE": "article",
        "colrev_status": colrev.record.RecordState.md_needs_manual_preparation,
        "colrev_masterdata_provenance": {
            "author": {
                "source": "colrev_curation.masterdata_restrictions",
                "note": "missing",
            },
            "title": {
                "source": "colrev_curation.masterdata_restrictions",
                "note": "missing",
            },
            "year": {
                "source": "colrev_curation.masterdata_restrictions",
                "note": "missing",
            },
            "volume": {
                "source": "colrev_curation.masterdata_restrictions",
                "note": "missing",
            },
            "number": {
                "source": "colrev_curation.masterdata_restrictions",
                "note": "missing",
            },
        },
        "journal": "MISQ",
        "booktitle": "ICIS",
    }
    actual = R_test.data
    assert expected == actual


def test_get_container_title() -> None:
    R1_mod = R1.copy()

    # article
    expected = "MIS Quarterly"
    actual = R1_mod.get_container_title()
    assert expected == actual

    R1_mod.data["ENTRYTYPE"] = "inproceedings"
    R1_mod.data["booktitle"] = "ICIS"
    expected = "ICIS"
    actual = R1_mod.get_container_title()
    assert expected == actual

    R1_mod.data["ENTRYTYPE"] = "book"
    R1_mod.data["title"] = "Momo"
    expected = "Momo"
    actual = R1_mod.get_container_title()
    assert expected == actual

    R1_mod.data["ENTRYTYPE"] = "inbook"
    R1_mod.data["booktitle"] = "Book title a"
    expected = "Book title a"
    actual = R1_mod.get_container_title()
    assert expected == actual


def test_complete_provenance() -> None:
    R1_mod = R1.copy()
    del R1_mod.data["colrev_masterdata_provenance"]
    del R1_mod.data["colrev_data_provenance"]
    R1_mod.update_field(key="url", value="www.test.eu", source="asdf")

    R1_mod.complete_provenance(source_info="test")
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_data_provenance": {"url": {"source": "test", "note": ""}},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
        "url": "www.test.eu",
        "colrev_masterdata_provenance": {
            "year": {"source": "test", "note": ""},
            "title": {"source": "test", "note": ""},
            "author": {"source": "test", "note": ""},
            "journal": {"source": "test", "note": ""},
            "volume": {"source": "test", "note": ""},
            "number": {"source": "test", "note": ""},
            "pages": {"source": "test", "note": ""},
        },
    }
    actual = R1_mod.data
    assert expected == actual


def test_get_toc_key() -> None:
    expected = "mis-quarterly|45|1"
    actual = R1.get_toc_key()
    assert expected == actual

    input = {
        "ENTRYTYPE": "inproceedings",
        "booktitle": "International Conference on Information Systems",
        "year": "2012",
    }
    expected = "international-conference-on-information-systems|2012"
    actual = colrev.record.Record(data=input).get_toc_key()
    assert expected == actual

    input = {
        "ENTRYTYPE": "phdthesis",
        "ID": "test",
        "title": "Thesis on asteroids",
        "year": "2012",
    }
    with pytest.raises(
        colrev_exceptions.NotTOCIdentifiableException,
        match="ENTRYTYPE .* not toc-identifiable",
    ):
        colrev.record.Record(data=input).get_toc_key()


def test_print_citation_format() -> None:
    R1.print_citation_format()


def test_print_diff_pair() -> None:
    colrev.record.Record.print_diff_pair(
        record_pair=[R1.data, R2.data], keys=["title", "journal", "booktitle"]
    )


def test_prescreen_exclude() -> None:
    R1_mod = R1.copy()
    R1_mod.data["colrev_status"] = colrev.record.RecordState.rev_synthesized
    R1_mod.data["number"] = "UNKNOWN"
    R1_mod.data["volume"] = "UNKNOWN"

    R1_mod.prescreen_exclude(reason="retracted", print_warning=True)
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.rev_prescreen_excluded,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "pages": "1--3",
        "prescreen_exclusion": "retracted",
    }

    actual = R1_mod.data
    print(actual)
    assert expected == actual


def test_parse_bib() -> None:
    R1_mod = R1.copy()
    R1_mod.data["colrev_origin"] = "import.bib/id_0001;md_crossref.bib/01;"
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": "year:import.bib/id_0001;;\n                                    title:import.bib/id_0001;;\n                                    author:import.bib/id_0001;;\n                                    journal:import.bib/id_0001;;\n                                    volume:import.bib/id_0001;;\n                                    number:import.bib/id_0001;;\n                                    pages:import.bib/id_0001;;",
        "colrev_data_provenance": "",
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": "import.bib/id_0001;\n                                    md_crossref.bib/01;",
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }
    print(type(R1_mod.data["colrev_origin"]))
    actual = R1_mod.get_data(stringify=True)
    assert expected == actual


def test_print_prescreen_record(capfd) -> None:  # type: ignore
    R1_mod = R1.copy()
    expected = "  ID: R1 (article)\n  \x1b[92mEDITORIAL\x1b[0m\n  Rai, Arun\n  MIS Quarterly (2020) 45(1)\n"

    R1_mod.print_prescreen_record()
    actual, err = capfd.readouterr()
    assert expected == actual


def test_print_pdf_prep_man(capfd) -> None:  # type: ignore
    R2_mod = R2.copy()
    R2_mod.data["abstract"] = "This paper focuses on ..."
    R2_mod.data["url"] = "www.gs.eu"
    R2_mod.data["colrev_data_provenance"]["file"] = {
        "note": "nr_pages_not_matching,title_not_in_first_pages,author_not_in_first_pages"
    }

    expected = """\x1b[91mRai, A\x1b[0m\n\x1b[91mEDITORIAL\x1b[0m\nMISQ (2020) 45(1), \x1b[91mpp.1--3\x1b[0m\n\nAbstract: This paper focuses on ...\n\n\nurl: www.gs.eu\n\n"""

    R2_mod.print_pdf_prep_man()
    actual, err = capfd.readouterr()
    assert expected == actual


@pytest.mark.parametrize(
    "input, expected",
    [
        ("Tom Smith", "Smith, Tom"),
        (
            "Garza, JL and Wu, ZH and Singh, M and Cherniack, MG.",
            "Garza, JL and Wu, ZH and Singh, M and Cherniack, MG.",
        ),
    ],
)
def test_format_author_field(input: str, expected: str) -> None:
    actual = colrev.record.PrepRecord.format_author_field(input_string=input)
    assert expected == actual


def test_extract_text_by_page(
    script_loc: Path, record_with_pdf: colrev.record.Record
) -> None:
    record_with_pdf
    expected = WagnerLukyanenkoParEtAl2022_pdf_content
    actual = record_with_pdf.extract_text_by_page(
        pages=[0], project_path=script_loc.parent
    )
    actual = actual.rstrip()
    assert expected == actual


def test_set_pages_in_pdf(
    script_loc: Path, record_with_pdf: colrev.record.Record
) -> None:
    expected = 18
    record_with_pdf.set_pages_in_pdf(project_path=script_loc.parent)
    actual = record_with_pdf.data["pages_in_file"]
    assert expected == actual


def test_set_text_from_pdf(
    script_loc: Path, record_with_pdf: colrev.record.Record
) -> None:
    record_with_pdf
    expected = WagnerLukyanenkoParEtAl2022_pdf_content
    record_with_pdf.set_text_from_pdf(project_path=script_loc.parent)
    actual = record_with_pdf.data["text_from_pdf"]
    actual = actual[0:4234]
    assert expected == actual


def test_get_retrieval_similarity() -> None:
    expected = 0.934
    actual = colrev.record.PrepRecord.get_retrieval_similarity(
        record_original=R1, retrieved_record_original=R2
    )
    assert expected == actual


def test_format_if_mostly_upper() -> None:
    prep_rec = R1.copy_prep_rec()

    prep_rec.format_if_mostly_upper(key="year")

    prep_rec.data["title"] = "ALL CAPS TITLE"
    prep_rec.data["colrev_masterdata_provenance"]["title"]["note"] = "quality_defect"
    prep_rec.format_if_mostly_upper(key="title")
    expected = "All caps title"
    actual = prep_rec.data["title"]
    assert expected == actual

    prep_rec.data["title"] = "ALL CAPS TITLE"
    prep_rec.format_if_mostly_upper(key="title", case="title")
    expected = "All Caps Title"
    actual = prep_rec.data["title"]
    assert expected == actual


def test_rename_fields_based_on_mapping() -> None:
    prep_rec = R1.copy_prep_rec()

    prep_rec.rename_fields_based_on_mapping(mapping={"Number": "issue"})
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
            "issue": {"source": "import.bib/id_0001|rename-from:number", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "pages": "1--3",
        "issue": "1",
    }

    actual = prep_rec.data
    assert expected == actual


def test_unify_pages_field() -> None:
    prep_rec = R1.copy_prep_rec()
    prep_rec.data["pages"] = "1-2"
    prep_rec.unify_pages_field()
    expected = "1--2"
    actual = prep_rec.data["pages"]
    assert expected == actual

    del prep_rec.data["pages"]
    prep_rec.unify_pages_field()

    prep_rec.data["pages"] = ["1", "2"]
    prep_rec.unify_pages_field()


def test_preparation_save_condition() -> None:
    prep_rec = R1.copy_prep_rec()
    prep_rec.data["colrev_status"] = colrev.record.RecordState.md_imported
    prep_rec.data["colrev_masterdata_provenance"]["title"][
        "note"
    ] = "disagreement with test"
    expected = True
    actual = prep_rec.preparation_save_condition()
    assert expected == actual

    prep_rec.data["colrev_masterdata_provenance"]["title"]["note"] = "record_not_in_toc"
    expected = True
    actual = prep_rec.preparation_save_condition()
    assert expected == actual


def test_preparation_break_condition() -> None:
    prep_rec = R1.copy_prep_rec()
    prep_rec.data["colrev_masterdata_provenance"]["title"][
        "note"
    ] = "disagreement with website"
    expected = True
    actual = prep_rec.preparation_break_condition()
    assert expected == actual

    prep_rec = R1.copy_prep_rec()
    prep_rec.data["colrev_status"] = colrev.record.RecordState.rev_prescreen_excluded
    expected = True
    actual = prep_rec.preparation_break_condition()
    assert expected == actual


def test_update_metadata_status() -> None:
    # Retracted (crossmark)
    R1_mod = R1.copy_prep_rec()
    R1_mod.data["crossmark"] = "True"
    R1_mod.update_metadata_status()
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.rev_prescreen_excluded,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
        "prescreen_exclusion": "retracted",
    }
    actual = R1_mod.data
    assert expected == actual

    # Curated
    R1_mod = R1.copy_prep_rec()
    R1_mod.data["colrev_masterdata_provenance"] = {
        "CURATED": {"source": "http...", "note": ""}
    }
    R1_mod.data["title"] = "Editorial"
    R1_mod.update_metadata_status()
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "CURATED": {"source": "http...", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "Editorial",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }
    actual = R1_mod.data
    assert expected == actual

    # Quality defect
    R1_mod = R1.copy_prep_rec()
    R1_mod.data["author"] = "Rai, Arun, ARUN"
    R1_mod.update_metadata_status()
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_needs_manual_preparation,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun, ARUN",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }
    actual = R1_mod.data
    assert expected == actual
