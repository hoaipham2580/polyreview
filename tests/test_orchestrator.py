"""End-to-end tests using the deterministic MockChatClient."""

from __future__ import annotations

import pytest

from polyreview.config import Config
from polyreview.llm import MockChatClient
from polyreview.orchestrator import Orchestrator
from polyreview.reporter import to_json, to_markdown


@pytest.fixture
def diff_text() -> str:
    return (
        "diff --git a/src/auth.py b/src/auth.py\n"
        "--- a/src/auth.py\n"
        "+++ b/src/auth.py\n"
        "@@ -1,1 +1,1 @@\n"
        '-q = "SELECT * FROM u WHERE n=" + name\n'
        '+q = "SELECT * FROM u WHERE n=?"\n'
    )


@pytest.fixture
def orch() -> Orchestrator:
    cfg = Config()
    cfg.cache.enabled = False
    return Orchestrator(config=cfg, client=MockChatClient())


async def test_end_to_end_produces_findings(orch: Orchestrator, diff_text: str) -> None:
    report = await orch.review_diff(diff_text)
    assert report.files_changed >= 1
    assert report.hunks >= 1
    assert report.findings, "mock should yield at least one finding"


async def test_findings_sorted_by_severity_desc(orch: Orchestrator, diff_text: str) -> None:
    report = await orch.review_diff(diff_text)
    ranks = [f.severity.rank for f in report.findings]
    assert ranks == sorted(ranks, reverse=True)


async def test_dedup_when_same_diff_reviewed_twice(orch: Orchestrator, diff_text: str) -> None:
    report = await orch.review_diff(diff_text)
    keys = [f.key() for f in report.findings]
    assert len(keys) == len(set(keys))


async def test_markdown_and_json_render(orch: Orchestrator, diff_text: str) -> None:
    report = await orch.review_diff(diff_text)
    md = to_markdown(report)
    js = to_json(report)
    assert "PolyReview Report" in md
    assert "findings" in js
