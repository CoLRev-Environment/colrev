#! /usr/bin/env python
"""Consolidation of metadata based on GitHub REST API as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record
from colrev.constants import Fields


# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.package_manager.interfaces.PrepInterface)
@dataclass
class GithubMetadataPrep(JsonSchemaMixin):
    """Prepares records based on GitHub metadata"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings