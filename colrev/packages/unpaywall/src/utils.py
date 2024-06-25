#! /usr/bin/env python
"""Utils for Unpaywall"""
import typing

import colrev.review_manager
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields

UNPAYWALL_EMAIL_PATH = "packages.pdf_get.colrev.unpaywall.email"

ENTRYTYPE_MAPPING = {
    "journal-article": ENTRYTYPES.ARTICLE,
    "book": ENTRYTYPES.BOOK,
    "proceedings-article": ENTRYTYPES.INPROCEEDINGS,
    "book-chapter": ENTRYTYPES.INBOOK,
    "conference": ENTRYTYPES.CONFERENCE,
    "dissertation": ENTRYTYPES.PHDTHESIS,
    "report": ENTRYTYPES.TECHREPORT,
    "other": ENTRYTYPES.MISC,
    "book-section": ENTRYTYPES.INBOOK,
    "monograph": ENTRYTYPES.THESIS,
    "report-component": ENTRYTYPES.TECHREPORT,
    "peer-review": ENTRYTYPES.MISC,
    "book-track": ENTRYTYPES.INCOLLECTION,
    "book-part": ENTRYTYPES.INBOOK,
    "journal-volume": ENTRYTYPES.ARTICLE,
    "book-set": ENTRYTYPES.MISC,
    "reference-entry": ENTRYTYPES.MISC,
    "journal": ENTRYTYPES.MISC,
    "component": ENTRYTYPES.MISC,
    "proceedings-series": ENTRYTYPES.PROCEEDINGS,
    "report-series": ENTRYTYPES.TECHREPORT,
    "proceedings": ENTRYTYPES.PROCEEDINGS,
    "database": ENTRYTYPES.MISC,
    "standard": ENTRYTYPES.MISC,
    "reference-book": ENTRYTYPES.BOOK,
    "posted-content": ENTRYTYPES.MISC,
    "journal-issue": ENTRYTYPES.MISC,
    "grant": ENTRYTYPES.MISC,
    "dataset": ENTRYTYPES.MISC,
    "book-series": ENTRYTYPES.BOOK,
    "edited-book": ENTRYTYPES.BOOK,
}


def get_email(review_manager: colrev.review_manager.ReviewManager) -> str:
    """Get user's name and email,

    if user have specified an email in registry, that will be returned
    otherwise it will return the email used in git
    """
    env_man = review_manager.environment_manager
    env_mail = env_man.get_settings_by_key(UNPAYWALL_EMAIL_PATH)
    _, email = env_man.get_name_mail_from_git()
    email = env_mail or email
    return email


def _get_authors(*, article: dict) -> typing.List[str]:
    authors = []
    z_authors = article.get("z_authors", [])
    if z_authors:
        for author in z_authors:
            given_name = author.get("given", "")
            family_name = author.get("family", "")
            authors.append(f"{family_name}, {given_name}")
    return authors


def _get_affiliation(*, article: dict) -> typing.List[str]:
    affiliations = set()
    z_authors = article.get("z_authors", "")
    if z_authors:
        for person in z_authors:
            person_affiliation = person.get("affiliation", [])
            if person_affiliation:
                affiliations.add(person_affiliation[0]["name"])

    return list(affiliations)


def _create_record(article: dict) -> colrev.record.record.Record:
    doi = article.get("doi", "").upper()
    record_dict = {Fields.ID: doi}

    entrytype = ENTRYTYPE_MAPPING.get(article.get("genre", "other"), ENTRYTYPES.MISC)
    record_dict[Fields.ENTRYTYPE] = entrytype

    record_dict[Fields.AUTHOR] = " and ".join(_get_authors(article=article))
    record_dict[Fields.TITLE] = article.get("title", "")
    record_dict[Fields.YEAR] = article.get("year", "")
    record_dict[Fields.DOI] = doi

    if entrytype == ENTRYTYPES.ARTICLE:
        record_dict[Fields.JOURNAL] = article.get("journal_name", "")
    elif entrytype == ENTRYTYPES.BOOK:
        record_dict[Fields.PUBLISHER] = article.get("publisher", "")
    elif entrytype == ENTRYTYPES.INPROCEEDINGS:
        record_dict[Fields.BOOKTITLE] = article.get("journal_name", "")
    elif entrytype == ENTRYTYPES.INBOOK:
        record_dict[Fields.BOOKTITLE] = article.get("journal_name", "")
        record_dict[Fields.PUBLISHER] = article.get("publisher", "")
    elif entrytype == ENTRYTYPES.CONFERENCE:
        record_dict[Fields.BOOKTITLE] = article.get("journal_name", "")
    elif entrytype == ENTRYTYPES.PHDTHESIS:
        record_dict[Fields.SCHOOL] = ",".join(_get_affiliation(article=article))
    elif entrytype == ENTRYTYPES.TECHREPORT:
        record_dict[Fields.INSTITUTION] = ",".join(_get_affiliation(article=article))
    elif entrytype == ENTRYTYPES.INCOLLECTION:
        record_dict[Fields.BOOKTITLE] = article.get("journal_name", "")
        record_dict[Fields.PUBLISHER] = article.get("publisher", "")

    bestoa = article.get("best_oa_location", "")
    if bestoa:
        record_dict[Fields.URL] = bestoa.get("url_for_landing_page", "")
        record_dict[Fields.FULLTEXT] = bestoa.get("url_for_pdf", "")

    final_record_dict = {key: value for key, value in record_dict.items() if value}

    record = colrev.record.record.Record(final_record_dict)

    return record
