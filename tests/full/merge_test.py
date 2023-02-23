#!/usr/bin/env python
import colrev.review_manager


def test_merge(mocker) -> None:
    import colrev.record
    import colrev.env.local_index

    mocker.patch("colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git", return_value=("Gerit Wagner", "gerit.wagner@uni-bamberg.de"))

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


    LOCAL_INDEX = colrev.env.local_index.LocalIndex()
    mocker.patch("colrev.env.local_index.LocalIndex.is_duplicate", return_value="unknown")

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
