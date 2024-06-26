#! /usr/bin/env python
"""Utility to transform github repositories into records"""
from __future__ import annotations

import re

from github import Github

import colrev.record.record
import colrev.record.record_prep
from colrev.constants import Fields

# Github-specific constants
GITHUB_VERSION = "colrev.github.version"
GITHUB_LICENSE = "colrev.github.license"
GITHUB_LANGUAGE = "colrev.github.language"


def get_title(*, repo: Github.Repository.Repository, citation_data: str) -> str:
    """Get repository title"""
    if citation_data:
        title = re.search(r"^\s*title:\s*(.+)\s*$", citation_data, re.M)
        if title:
            return title.group(1).strip().replace('"', "")
    return repo.name


def get_authors(*, repo: Github.Repository.Repository, citation_data: str) -> str:
    """Get repository authors"""
    if citation_data:
        authors = re.findall(
            r'- family-names:\s*"(.+)"\s*\n\s*given-names:\s*"(.+)"',
            citation_data,
            re.M,
        )
        return colrev.record.record_prep.PrepRecord.format_author_field(
            " and ".join([a[1].strip() + " " + a[0].strip() for a in authors])
        )
    try:
        return " and ".join(
            [c.login for c in repo.get_contributors() if not c.login.endswith("[bot]")]
        )
    except Exception:
        return ""


def get_url(*, repo: Github.Repository.Repository, citation_data: str) -> str:
    """Get repository URL"""
    if citation_data:
        url = re.search(r"^\s*url:\s*(.+)\s*$", citation_data, re.M)
        if url:
            return url.group(1).strip().replace('"', "")
    return repo.html_url


def get_release_date(*, repo: Github.Repository.Repository, citation_data: str) -> str:
    """Get release date"""
    if citation_data:
        release_date = re.search(r"^\s*date-released:\s*(.+)\s*$", citation_data, re.M)
        if release_date:
            return release_date.group(1).strip()
    return repo.created_at.strftime("%Y/%m/%d")


def get_version(*, repo: Github.Repository.Repository, citation_data: str) -> str:
    """Get current software version"""
    if citation_data:
        version = re.search(r"^\s*version:\s*(.+)\s*$", citation_data, re.M)
        if version:
            return version.group(1).strip()
    return ""


def repo_to_record(
    *, repo: Github.Repository.Repository
) -> colrev.record.record.Record:
    """Convert a GitHub repository to a record"""
    try:  # If available, use data from CITATION.cff file
        content = repo.get_contents("CITATION.cff")
        citation_data = content.decoded_content.decode("utf-8")
    except Exception:
        citation_data = ""

    data = {Fields.ENTRYTYPE: "software"}

    data[Fields.TITLE] = get_title(repo=repo, citation_data=citation_data)

    authors = get_authors(repo=repo, citation_data=citation_data)
    if authors:
        data[Fields.AUTHOR] = authors

    data[Fields.URL] = get_url(repo=repo, citation_data=citation_data)

    data[Fields.DATE] = get_release_date(repo=repo, citation_data=citation_data)

    data[Fields.YEAR] = data[Fields.DATE][:4]

    data[Fields.ABSTRACT] = repo.description

    data[GITHUB_LANGUAGE] = repo.language

    try:
        data[GITHUB_LICENSE] = repo.get_license().license.name
    except Exception:
        pass

    version = get_version(repo=repo, citation_data=citation_data)
    if version:
        data[GITHUB_VERSION] = version

    return colrev.record.record.Record(data=data)
