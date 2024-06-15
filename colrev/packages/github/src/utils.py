#! /usr/bin/env python
"""Utility to transform github repositories into records"""
from __future__ import annotations

import re

import colrev.record.record
import colrev.record.record_prep
from colrev.constants import Fields
from colrev.constants import FieldValues

from github import Github

def get_citation_data(*, citation_data: str) -> dict:
    """TODO: get citation data from cff file"""
    pass


def repo_to_record(*, repo: Github.Repository.Repository) -> colrev.record.record.Record:
    """Convert a GitHub repository to a record dict"""
    try: #If available, use data from CITATION.cff file
        content = repo.get_contents("CITATION.cff")
        citation_data = content.decoded_content.decode('utf-8')
        record_dict = GitHubSearchSource.get_citation_data(citation_data=citation_data)
    except:
        record_dict = {
            Fields.ENTRYTYPE: "software",
            Fields.TITLE: repo.name,
            Fields.URL: repo.html_url,
            Fields.AUTHOR: ", ".join([contributor.login for contributor in repo.get_contributors() if not contributor.login.endswith("[bot]")]),
            Fields.YEAR: str(repo.created_at.year),
            Fields.ABSTRACT: repo.description,
            Fields.LANGUAGE: repo.language,
            Fields.FILE: repo.html_url + "/blob/main/README.md" if repo.get_readme() else None
            #Fields.LICENSE?: license_info.spdx_id if repo.license else None
        }

    return colrev.record.record.Record(data=record_dict)