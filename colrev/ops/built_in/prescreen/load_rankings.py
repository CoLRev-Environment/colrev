import csv


def __load_ais_ranking() -> dict[str]:
    """loads ais rankings"""
    ais_ranking = {}
    with open("rankings_index.csv", encoding="cp850") as ranking_csv:
        data = csv.reader(ranking_csv, delimiter=",")
        ais_ranking = {rows[0]: rows[1] for rows in data}
    return ais_ranking


def __load_vhb_ranking() -> dict[str]:
    """loads vhb rankings"""
    vhb_ranking = {}
    with open("rankings_index.csv", encoding="cp850") as ranking_csv:
        data = csv.reader(ranking_csv, delimiter=",")
        vhb_ranking = {rows[2]: rows[3] for rows in data}
    return vhb_ranking


def __load_ft50_ranking() -> dict[str]:
    """loads ft50 rankings"""
    ft50_ranking = {}
    with open("rankings_index.csv", encoding="cp850") as ranking_csv:
        data = csv.reader(ranking_csv, delimiter=",")
        ft50_ranking = {rows[4]: rows[5] for rows in data}
    return ft50_ranking


def __load_predatory_journals_beall() -> dict[str]:
    """loads Beall's predatory journals"""
    predatory_journals_beall = {}
    with open("rankings_index.csv", encoding="cp850") as ranking_csv:
        data = csv.reader(ranking_csv, delimiter=",")
        predatory_journals_beall = {rows[6]: rows[7] for rows in data}
    return predatory_journals_beall
