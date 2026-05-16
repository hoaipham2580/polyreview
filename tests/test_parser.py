"""Regression tests for `_parse_findings`.

Each case here is an actual response shape we observed in the cached
DeepSeek-V4-Flash run, distilled into a minimal example.
"""

from __future__ import annotations

import pytest

from polyreview.agents import _parse_findings
from polyreview.models import Severity


def test_clean_json_array_parses() -> None:
    raw = """[
      {"severity": "HIGH", "file": "a.py", "line": 1, "message": "bad"}
    ]"""
    out = _parse_findings(raw, agent="security")
    assert len(out) == 1
    assert out[0].severity is Severity.HIGH


@pytest.mark.parametrize(
    "alias,expected",
    [
        ("HIGH", Severity.HIGH),
        ("CRITICAL", Severity.HIGH),
        ("error", Severity.HIGH),
        ("Severe", Severity.HIGH),
        ("MEDIUM", Severity.MED),  # the real DeepSeek case
        ("Moderate", Severity.MED),
        ("warn", Severity.MED),
        ("LOW", Severity.LOW),
        ("info", Severity.LOW),
        ("totally-bogus-string", Severity.LOW),
    ],
)
def test_severity_aliases_recognised(alias: str, expected: Severity) -> None:
    raw = '[{"severity": "' + alias + '", "file": "a.py", "line": 1, "message": "x"}]'
    out = _parse_findings(raw, agent="security")
    assert out and out[0].severity is expected


def test_double_array_concatenated() -> None:
    """DeepSeek occasionally emits ``[]\\n\\n[ {...} ]``."""
    raw = '[]\n\n[{"severity": "MEDIUM", "file": "a.py", "line": 2, "message": "x"}]'
    out = _parse_findings(raw, agent="logic")
    assert len(out) == 1
    assert out[0].severity is Severity.MED


def test_prose_wrapped_json_array() -> None:
    """Real model: 'Here is what I found: [ {...} ]. Hope that helps!'"""
    raw = (
        "Here is what I found:\n"
        '[{"severity": "HIGH", "file": "auth.py", "line": 5, "message": "weak hash"}]\n'
        "Hope that helps!"
    )
    out = _parse_findings(raw, agent="security")
    assert len(out) == 1
    assert out[0].file == "auth.py"


def test_prose_only_response_yields_no_findings() -> None:
    """The synthesizer output style: pure prose with no JSON at all."""
    raw = "总体结论:存在 SQL 注入漏洞,需立即修复。"
    assert _parse_findings(raw, agent="security") == []


def test_empty_string_response() -> None:
    assert _parse_findings("", agent="security") == []
    assert _parse_findings("   \n  ", agent="security") == []


def test_code_fence_with_language_tag() -> None:
    raw = "```json\n" '[{"severity": "HIGH", "file": "x.py", "line": 1, "message": "bad"}]\n' "```"
    out = _parse_findings(raw, agent="security")
    assert len(out) == 1


def test_string_line_number_extracted() -> None:
    """Some models return ``"line": "L42"`` or ``"line 42"``."""
    raw = '[{"severity": "HIGH", "file": "x.py", "line": "L42", "message": "bad"}]'
    out = _parse_findings(raw, agent="security")
    assert out and out[0].line == 42


def test_missing_message_drops_finding() -> None:
    """Pydantic would reject empty message; we filter pre-emptively."""
    raw = '[{"severity": "HIGH", "file": "x.py", "line": 1, "message": ""}]'
    assert _parse_findings(raw, agent="security") == []


def test_object_at_top_level_treated_as_single_finding() -> None:
    raw = '{"severity": "HIGH", "file": "x.py", "line": 1, "message": "bad"}'
    out = _parse_findings(raw, agent="security")
    assert len(out) == 1
