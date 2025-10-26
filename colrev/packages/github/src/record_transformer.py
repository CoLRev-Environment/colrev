#! /usr/bin/env python
"""Utility to transform github repositories into records"""
from __future__ import annotations

import re
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Dict

from github import Github
from github.GithubException import GithubException
from github.GithubException import UnknownObjectException

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


def _set_issue_counts(record_dict: dict, repo: Github.Repository.Repository) -> None:
    try:
        open_ = repo.get_issues(state="open").totalCount
        closed = repo.get_issues(state="closed").totalCount
        record_dict[Fields.GITHUB_ISSUE_COUNT_OPEN] = open_
        record_dict[Fields.GITHUB_ISSUE_COUNT_CLOSED] = closed
        record_dict[Fields.GITHUB_ISSUE_COUNT_TOTAL] = open_ + closed
    except GithubException:
        record_dict[Fields.GITHUB_ISSUE_COUNT_OPEN] = 0
        record_dict[Fields.GITHUB_ISSUE_COUNT_CLOSED] = 0
        record_dict[Fields.GITHUB_ISSUE_COUNT_TOTAL] = 0


def _set_stars_watch_forks(
    record_dict: dict, repo: Github.Repository.Repository
) -> None:
    try:
        record_dict[Fields.GITHUB_STAR_COUNT] = (
            getattr(repo, "stargazers_count", 0) or 0
        )
    except GithubException:
        record_dict[Fields.GITHUB_STAR_COUNT] = 0
    try:
        record_dict[Fields.GITHUB_WATCHER_COUNT] = (
            getattr(repo, "subscribers_count", 0) or 0
        )
    except GithubException:
        record_dict[Fields.GITHUB_WATCHER_COUNT] = 0
    try:
        record_dict[Fields.GITHUB_FORK_COUNT] = getattr(repo, "forks_count", 0) or 0
    except GithubException:
        record_dict[Fields.GITHUB_FORK_COUNT] = 0


def _set_archive_status(record_dict: dict, repo: Github.Repository.Repository) -> None:
    try:
        is_archived = bool(getattr(repo, "archived", False))
        record_dict[Fields.GITHUB_REPO_IS_ARCHIVED] = is_archived
        if is_archived:
            pushed_at = getattr(repo, "pushed_at", None)
            if pushed_at:
                record_dict[Fields.GITHUB_REPO_IS_ARCHIVED_DATE] = pushed_at.strftime(
                    "%Y-%m-%d"
                )
    except GithubException:
        record_dict[Fields.GITHUB_REPO_IS_ARCHIVED] = False


def _set_last_commit_date(
    record_dict: dict, repo: Github.Repository.Repository
) -> None:
    try:
        c = repo.get_commits()[0]
        dt = c.commit.author.date
        record_dict[Fields.GITHUB_COMMIT_LAST_DATE] = dt.strftime("%Y-%m-%d")
    except (GithubException, IndexError):
        pass


def _set_latest_release_date(
    record_dict: dict, repo: Github.Repository.Repository
) -> None:
    try:
        rel = repo.get_latest_release()
        if rel and getattr(rel, "published_at", None):
            record_dict[Fields.GITHUB_LATEST_RELEASE_DATE] = rel.published_at.strftime(
                "%Y-%m-%d"
            )
    except (UnknownObjectException, GithubException):
        pass


def _calc_language_percentages(repo: Github.Repository.Repository) -> Dict[str, float]:
    try:
        lang_bytes = repo.get_languages()
        total = sum(lang_bytes.values()) or 0
        if total == 0:
            return {}
        return {k: round((v / total) * 100.0, 2) for k, v in lang_bytes.items()}
    except GithubException:
        return {}


def _set_languages_pct(record_dict: dict, repo: Github.Repository.Repository) -> None:
    lang_pct = _calc_language_percentages(repo)
    if lang_pct:
        record_dict[Fields.GITHUB_LANGUAGES_PCT] = lang_pct


def _set_branch_statuses(record_dict: dict, repo: Github.Repository.Repository) -> None:
    try:
        branches = list(repo.get_branches())
    except GithubException:
        return

    active = stale = 0
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=90)

    for br in branches:
        try:
            sha = br.commit.sha
            commit = repo.get_commit(sha)
            dt = commit.commit.author.date
            if dt >= threshold:
                active += 1
            else:
                stale += 1
        except GithubException:
            stale += 1

    record_dict[Fields.GITHUB_BRANCH_COUNT_ACTIVE] = active
    record_dict[Fields.GITHUB_BRANCH_COUNT_STALE] = stale
    record_dict[Fields.GITHUB_BRANCH_COUNT_ALL] = active + stale


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
        pass
    return record_dict


def repo_to_record(
    *, repo: Github.Repository.Repository
) -> colrev.record.record.Record:
    """Convert a GitHub repository to a record"""

    record_dict = {
        Fields.ENTRYTYPE: "software",
        Fields.TITLE: repo.name,
        Fields.AUTHOR: _get_contributors(repo),
        Fields.YEAR: repo.updated_at.strftime("%Y"),
        Fields.DATE: repo.updated_at.strftime("%Y/%m/%d"),
        Fields.URL: repo.html_url,
        Fields.ABSTRACT: repo.description,
        Fields.GITHUB_LANGUAGE: repo.language,
        # Basic info triplet
        Fields.GITHUB_BASIC_INFO_OWNER: repo.owner.login,
        Fields.GITHUB_BASIC_INFO_REPO: repo.name,
        Fields.GITHUB_BASIC_INFO_URL: repo.html_url,
    }

    _set_license(record_dict, repo)
    _set_nr_contributors(record_dict, repo)
    _set_nr_commits(record_dict, repo)
    _set_issue_counts(record_dict, repo)
    _set_stars_watch_forks(record_dict, repo)
    _set_archive_status(record_dict, repo)
    _set_last_commit_date(record_dict, repo)
    _set_latest_release_date(record_dict, repo)
    _set_languages_pct(record_dict, repo)
    _set_branch_statuses(record_dict, repo)

    # Use data from CITATION.cff file (if available)
    _update_record_based_on_citation_cff(record_dict, repo)

    record_dict = {k: v for k, v in record_dict.items() if v not in (None, "", [], {})}
    return colrev.record.record.Record(data=record_dict)
