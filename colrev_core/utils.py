#! /usr/bin/env python
import re
import unicodedata

import pandas as pd
from thefuzz import fuzz


def rmdiacritics(char: str) -> str:
    """
    Return the base character of char, by "removing" any
    diacritics like accents or curls and strokes and the like.
    """
    desc = unicodedata.name(char)
    cutoff = desc.find(" WITH ")
    if cutoff != -1:
        desc = desc[:cutoff]
        try:
            char = unicodedata.lookup(desc)
        except KeyError:
            pass  # removing "WITH ..." produced an invalid name
    return char


def remove_accents(input_str: str) -> str:
    try:
        nfkd_form = unicodedata.normalize("NFKD", input_str)
        wo_ac_list = [
            rmdiacritics(c) for c in nfkd_form if not unicodedata.combining(c)
        ]
        wo_ac = "".join(wo_ac_list)
    except ValueError:
        wo_ac = input_str
        pass
    return wo_ac


def format_authors_string(authors: str) -> str:
    authors = str(authors).lower()
    authors_string = ""
    authors = remove_accents(authors)

    # abbreviate first names
    # "Webster, Jane" -> "Webster, J"
    # also remove all special characters and do not include separators (and)
    for author in authors.split(" and "):
        if "," in author:
            last_names = [
                word[0] for word in author.split(",")[1].split(" ") if len(word) > 0
            ]
            authors_string = (
                authors_string + author.split(",")[0] + " " + " ".join(last_names) + " "
            )
        else:
            authors_string = authors_string + author + " "
    authors_string = re.sub(r"[^A-Za-z0-9, ]+", "", authors_string.rstrip())
    return authors_string


def get_record_similarity(record_a: dict, record_b: dict) -> float:
    if "title" not in record_a:
        record_a["title"] = ""
    if "author" not in record_a:
        record_a["author"] = ""
    if "year" not in record_a:
        record_a["year"] = ""
    if "journal" not in record_a:
        record_a["journal"] = ""
    if "volume" not in record_a:
        record_a["volume"] = ""
    if "number" not in record_a:
        record_a["number"] = ""
    if "pages" not in record_a:
        record_a["pages"] = ""
    if "booktitle" not in record_a:
        record_a["booktitle"] = ""
    if "title" not in record_b:
        record_b["title"] = ""
    if "author" not in record_b:
        record_b["author"] = ""
    if "year" not in record_b:
        record_b["year"] = ""
    if "journal" not in record_b:
        record_b["journal"] = ""
    if "volume" not in record_b:
        record_b["volume"] = ""
    if "number" not in record_b:
        record_b["number"] = ""
    if "pages" not in record_b:
        record_b["pages"] = ""
    if "booktitle" not in record_b:
        record_b["booktitle"] = ""

    if "container_title" not in record_a:
        record_a["container_title"] = (
            record_a.get("journal", "")
            + record_a.get("booktitle", "")
            + record_a.get("series", "")
        )

    if "container_title" not in record_b:
        record_b["container_title"] = (
            record_b.get("journal", "")
            + record_b.get("booktitle", "")
            + record_b.get("series", "")
        )

    df_a = pd.DataFrame.from_dict([record_a])
    df_b = pd.DataFrame.from_dict([record_b])

    return get_similarity(df_a.iloc[0], df_b.iloc[0])


def get_similarity(df_a: pd.DataFrame, df_b: pd.DataFrame) -> float:
    details = get_similarity_detailed(df_a, df_b)
    return details["score"]


def get_similarity_detailed(df_a: pd.DataFrame, df_b: pd.DataFrame) -> dict:

    author_similarity = fuzz.ratio(df_a["author"], df_b["author"]) / 100

    title_similarity = fuzz.ratio(df_a["title"].lower(), df_b["title"].lower()) / 100

    # partial ratio (catching 2010-10 or 2001-2002)
    year_similarity = fuzz.ratio(df_a["year"], df_b["year"]) / 100

    outlet_similarity = (
        fuzz.ratio(df_a["container_title"], df_b["container_title"]) / 100
    )

    if str(df_a["journal"]) != "nan":
        # Note: for journals papers, we expect more details
        if df_a["volume"] == df_b["volume"]:
            volume_similarity = 1
        else:
            volume_similarity = 0
        if df_a["number"] == df_b["number"]:
            number_similarity = 1
        else:
            number_similarity = 0

        # page similarity is not considered at the moment.
        #
        # sometimes, only the first page is provided.
        # if str(df_a["pages"]) == "nan" or str(df_b["pages"]) == "nan":
        #     pages_similarity = 1
        # else:
        #     if df_a["pages"] == df_b["pages"]:
        #         pages_similarity = 1
        #     else:
        #         if df_a["pages"].split("-")[0] == df_b["pages"].split("-")[0]:
        #             pages_similarity = 1
        #         else:
        #            pages_similarity = 0

        # Put more weithe on other fields if the title is very common
        # ie., non-distinctive
        # The list is based on a large export of distinct papers, tabulated
        # according to titles and sorted by frequency
        if [df_a["title"], df_b["title"]] in [
            ["editorial", "editorial"],
            ["editorial introduction", "editorial introduction"],
            ["editorial notes", "editorial notes"],
            ["editor's comments", "editor's comments"],
            ["book reviews", "book reviews"],
            ["editorial note", "editorial note"],
            ["reviewer ackowledgment", "reviewer ackowledgment"],
        ]:
            weights = [0.175, 0, 0.175, 0.175, 0.275, 0.2]
        else:
            weights = [0.2, 0.25, 0.13, 0.2, 0.12, 0.1]

        sim_names = [
            "authors",
            "title",
            "year",
            "outlet",
            "volume",
            "number",
        ]
        similarities = [
            author_similarity,
            title_similarity,
            year_similarity,
            outlet_similarity,
            volume_similarity,
            number_similarity,
        ]

    else:

        weights = [0.15, 0.75, 0.05, 0.05]
        sim_names = [
            "author",
            "title",
            "year",
            "outlet",
        ]
        similarities = [
            author_similarity,
            title_similarity,
            year_similarity,
            outlet_similarity,
        ]

    weighted_average = sum(
        similarities[g] * weights[g] for g in range(len(similarities))
    )

    details = (
        "["
        + ",".join([sim_names[g] for g in range(len(similarities))])
        + "]"
        + "*weights_vecor^T = "
        + "["
        + ",".join([str(similarities[g]) for g in range(len(similarities))])
        + "]*"
        + "["
        + ",".join([str(weights[g]) for g in range(len(similarities))])
        + "]^T"
    )
    similarity_score = round(weighted_average, 4)

    return {"score": similarity_score, "details": details}


if __name__ == "__main__":
    pass
