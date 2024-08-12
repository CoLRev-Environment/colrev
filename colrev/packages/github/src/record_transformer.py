#! /usr/bin/env python
"""Utility to transform github repositories into records"""
from __future__ import annotations

import re

from github import Github
from github.GithubException import GithubException

import colrev.record.record
import colrev.record.record_prep
from colrev.constants import Fields


def _set_title(*, record_dict: dict, citation_data: str) -> None:
    """Set repository title"""
    title = re.search(r"^\s*title:\s*(.+)\s*$", citation_data, re.M)
    if title:
        record_dict[Fields.TITLE] = title.group(1).strip().replace('"', "")


def _set_authors(*, record_dict: dict, citation_data: str) -> None:
    """Set repository authors"""
    authors = re.findall(
        r'- family-names:\s*"(.+)"\s*\n\s*given-names:\s*"(.+)"',
        citation_data,
        re.M,
    )
    record_dict[Fields.AUTHOR] = (
        colrev.record.record_prep.PrepRecord.format_author_field(
            " and ".join([a[1].strip() + " " + a[0].strip() for a in authors])
        )
    )


def _set_url(*, record_dict: dict, citation_data: str) -> None:
    """Set repository URL"""
    url = re.search(r"^\s*url:\s*(.+)\s*$", citation_data, re.M)
    if url:
        record_dict[Fields.URL] = url.group(1).strip().replace('"', "")


def _set_year_and_release_date(*, record_dict: dict, citation_data: str) -> None:
    """Set release date"""
    release_date = re.search(r"^\s*date-released:\s*(.+)\s*$", citation_data, re.M)
    if release_date:
        record_dict[Fields.DATE] = release_date.group(1).strip()
        record_dict[Fields.YEAR] = record_dict[Fields.DATE][:4]


def _set_version(record_dict: dict, citation_data: str) -> None:
    """Set current software version"""
    version = re.search(r"^\s*version:\s*(.+)\s*$", citation_data, re.M)
    if version:
        record_dict[Fields.GITHUB_VERSION] = version.group(1).strip()


def _get_contributors(repo: Github.Repository.Repository) -> str:
    return " and ".join(
        [c.login for c in repo.get_contributors() if not c.login.endswith("[bot]")]
    )


def _set_license(record_dict: dict, repo: Github.Repository.Repository) -> None:
    try:
        record_dict[Fields.GITHUB_LICENSE] = repo.get_license().license.name
    except GithubException:
        pass


def _set_nr_contributors(record_dict: dict, repo: Github.Repository.Repository) -> None:
    record_dict[Fields.GITHUB_NR_CONTRIBUTORS] = 0  # empty repository
    try:
        record_dict[Fields.GITHUB_NR_CONTRIBUTORS] = repo.get_contributors().totalCount
    except GithubException:
        pass


def _set_nr_commits(record_dict: dict, repo: Github.Repository.Repository) -> None:
    record_dict[Fields.GITHUB_NR_COMMITS] = 0  # empty repository
    try:
        record_dict[Fields.GITHUB_NR_COMMITS] = repo.get_commits().totalCount
    except GithubException:
        pass


def _update_record_based_on_citation_cff(
    record_dict: dict, repo: Github.Repository.Repository
) -> dict:
    try:
        content = repo.get_contents("CITATION.cff")
        citation_data = content.decoded_content.decode("utf-8")

        _set_title(record_dict=record_dict, citation_data=citation_data)
        _set_authors(record_dict=record_dict, citation_data=citation_data)
        _set_year_and_release_date(record_dict=record_dict, citation_data=citation_data)
        _set_version(record_dict, citation_data)
        _set_url(record_dict=record_dict, citation_data=citation_data)

    except GithubException:
        record_dict = {}
    return record_dict


def repo_to_record(
    *, repo: Github.Repository.Repository
) -> colrev.record.record.Record:
    """Convert a GitHub repository to a record"""

    # Set default values
    record_dict = {
        Fields.ENTRYTYPE: "software",
        Fields.TITLE: repo.name,
        Fields.AUTHOR: _get_contributors(repo),
        Fields.YEAR: repo.updated_at.strftime("%Y"),
        Fields.DATE: repo.updated_at.strftime("%Y/%m/%d"),
        Fields.URL: repo.html_url,
        Fields.ABSTRACT: repo.description,
        Fields.GITHUB_LANGUAGE: repo.language,
    }

    _set_license(record_dict, repo)
    _set_nr_contributors(record_dict, repo)
    _set_nr_commits(record_dict, repo)

    # Use data from CITATION.cff file (if available)
    _update_record_based_on_citation_cff(record_dict, repo)

    record_dict = {k: v for k, v in record_dict.items() if v}

    return colrev.record.record.Record(data=record_dict)
