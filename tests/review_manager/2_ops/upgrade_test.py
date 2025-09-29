#!/usr/bin/env python
"""Test the colrev upgrade"""
import colrev.ops.upgrade


def test_colrev_version() -> None:
    """Test the colrev version"""

    v1 = colrev.ops.upgrade.CoLRevVersion("0.10.0")
    v2 = colrev.ops.upgrade.CoLRevVersion("0.10.1")
    assert v1 <= v2

    v1 = colrev.ops.upgrade.CoLRevVersion("0.9.3")
    v2 = colrev.ops.upgrade.CoLRevVersion("0.8.4")
    assert v1 > v2
    assert v1 >= v2
    assert v2 <= v1
    assert not v2 >= v1
