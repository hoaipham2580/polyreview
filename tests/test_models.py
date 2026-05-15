"""Unit tests for Severity / Finding / ReviewReport models."""

from __future__ import annotations

import pytest

from polyreview.models import Finding, ReviewReport, Severity


def test_severity_ranking() -> None:
    assert Severity.HIGH.rank > Severity.MED.rank > Severity.LOW.rank


def test_finding_rejects_empty_file() -> None:
    with pytest.raises(ValueError):
        Finding(
            agent="security",
            severity=Severity.HIGH,
            file="   ",
            line=1,
            message="x",
        )


def test_overall_severity_picks_highest() -> None:
    r = ReviewReport(
        findings=[
            Finding(agent="a", severity=Severity.LOW, file="x", line=1, message="m"),
            Finding(agent="b", severity=Severity.HIGH, file="x", line=2, message="m"),
        ]
    )
    assert r.overall_severity is Severity.HIGH


def test_overall_severity_low_when_empty() -> None:
    assert ReviewReport().overall_severity is Severity.LOW


def test_by_agent_filters() -> None:
    r = ReviewReport(
        findings=[
            Finding(agent="security", severity=Severity.LOW, file="x", line=1, message="m"),
            Finding(agent="logic", severity=Severity.LOW, file="x", line=1, message="m"),
        ]
    )
    assert len(r.by_agent("security")) == 1
    assert len(r.by_agent("logic")) == 1
