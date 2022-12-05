#!/usr/bin/env python


def test_add_colrev_ids() -> None:
    import colrev.record

    v1 = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_data_provenance": {},
        "colrev_masterdata_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": "orig1",
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
        "colrev_data_provenance": {},
        "colrev_masterdata_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": "orig1",
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
    R1.add_colrev_ids(records=[v1, v2])
    assert [
        "colrev_id1:|a|mis-quarterly|45|1|2020|rai|editorial",
        "colrev_id1:|a|misq|45|1|2020|rai|editorial",
    ] == R1.data["colrev_id"]


def test_provenance() -> None:

    import colrev.record

    v1 = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_data_provenance": {},
        "colrev_masterdata_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": "orig1",
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
        "url": "www.test.com",
    }
    R1 = colrev.record.Record(data=v1)
    R1.add_data_provenance(key="url", source="manual", note="test")
    assert R1.data["colrev_data_provenance"]["url"]["source"] == "manual"
    assert R1.data["colrev_data_provenance"]["url"]["note"] == "test"

    R1.add_data_provenance_note(key="url", note="1")
    assert R1.data["colrev_data_provenance"]["url"]["note"] == "test,1"

    assert R1.get_field_provenance(key="url") == ["manual", "test,1"]

    R1.add_masterdata_provenance(key="author", source="manual", note="test")
    assert R1.data["colrev_masterdata_provenance"]["author"]["note"] == "test"
    assert R1.data["colrev_masterdata_provenance"]["author"]["source"] == "manual"

    R1.add_masterdata_provenance_note(key="author", note="check")
    assert R1.data["colrev_masterdata_provenance"]["author"]["note"] == "test,check"


def test_defects() -> None:

    import colrev.record

    v1 = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_data_provenance": {},
        "colrev_masterdata_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": "orig1",
        "year": "2020",
        "title": "EDITORIAL",
        "author": "RAI",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
        "url": "www.test.com",
    }
    R1 = colrev.record.Record(data=v1)
    assert set(R1.get_quality_defects()) == {"title", "author"}
    assert R1.has_quality_defects()
    review_manager = colrev.review_manager.ReviewManager()
    R1.import_provenance(review_manager=review_manager)
    assert R1.data == {
        "ENTRYTYPE": "article",
        "ID": "R1",
        "author": "RAI",
        "journal": "MIS Quarterly",
        "number": "1",
        "pages": "1--3",
        "title": "EDITORIAL",
        "volume": "45",
        "year": "2020",
        "colrev_data_provenance": {"url": {"note": "", "source": "orig1"}},
        "colrev_masterdata_provenance": {
            "author": {"note": "quality_defect", "source": "orig1"},
            "journal": {"note": "", "source": "orig1"},
            "number": {"note": "", "source": "orig1"},
            "pages": {"note": "", "source": "orig1"},
            "title": {"note": "quality_defect", "source": "orig1"},
            "volume": {"note": "", "source": "orig1"},
            "year": {"note": "", "source": "orig1"},
        },
        "colrev_origin": "orig1",
        "colrev_status": colrev.record.RecordState.md_prepared,
        "url": "www.test.com",
    }


def test_merge() -> None:
    import colrev.record

    R1 = colrev.record.Record(
        data={
            "ID": "R1",
            "colrev_data_provenance": {},
            "colrev_masterdata_provenance": {
                "volume": {"source": "source-1", "note": ""}
            },
            "colrev_status": colrev.record.RecordState.md_prepared,
            "colrev_origin": "orig1",
            "title": "EDITORIAL",
            "author": "Rai, Arun",
            "journal": "MIS Quarterly",
            "volume": "45",
            "pages": "1--3",
        }
    )
    R2 = colrev.record.Record(
        data={
            "ID": "R2",
            "colrev_data_provenance": {},
            "colrev_masterdata_provenance": {
                "volume": {"source": "source-1", "note": ""},
                "number": {"source": "source-1", "note": ""},
            },
            "colrev_status": colrev.record.RecordState.md_prepared,
            "colrev_origin": "orig2",
            "title": "Editorial",
            "author": "ARUN RAI",
            "journal": "MISQ",
            "volume": "45",
            "number": "4",
            "pages": "1--3",
        }
    )

    R1.merge(merging_record=R2, default_source="test")
    print(R1)

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

    import colrev.env.local_index

    LOCAL_INDEX = colrev.env.local_index.LocalIndex()

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

    # Different curated repos -> no duplicate
    assert "no" == LOCAL_INDEX.is_duplicate(
        record1_colrev_id=[
            "colrev_id1:|a|mis-quarterly|26|4|2002|jasperson-carte-saunders-butler-croes-zheng|power-and-information-technology-research-a-metatriangulation-review"
        ],
        record2_colrev_id=[
            "colrev_id1:|a|information-systems-research|15|2|2004|fichman|real-options-and-it-platform-adoption-implications-for-theory-and-practice"
        ],
    )


def test_parse_bib() -> None:
    import colrev.record

    R1 = colrev.record.Record(
        data={
            "ID": "R1",
            "colrev_data_provenance": {"url": {"source": "manual", "note": "testing"}},
            "colrev_masterdata_provenance": {
                "volume": {"source": "source-1", "note": ""}
            },
            "colrev_status": colrev.record.RecordState.md_prepared,
            "colrev_origin": "orig1",
            "title": "EDITORIAL",
            "author": "Rai, Arun",
            "journal": "MIS Quarterly",
            "volume": "45",
            "pages": "1--3",
            "url": "www.test.com",
        }
    )
    expected = {
        "ID": "R1",
        "colrev_data_provenance": "url:manual;testing;",
        "colrev_masterdata_provenance": "volume:source-1;;",
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": "orig1",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "pages": "1--3",
        "url": "www.test.com",
    }

    result = R1.get_data(stringify=True)
    assert expected == result
