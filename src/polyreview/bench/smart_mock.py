"""A pattern-matching mock LLM used by the benchmark.

The default ``MockChatClient`` always returns the same canned findings,
which makes recall numbers meaningless on a varied dataset. This client
inspects the diff text and emits findings only when its keyword heuristic
fires — that gives both PolyReview-4 (multi-agent) and Baseline-Single
real, differentiated outputs we can score.

The heuristics are intentionally imperfect:
  - The Baseline-Single prompt sees one combined prompt and uses a coarser
    set of patterns, so it misses the more specialised cases (e.g. weak
    crypto, mutable default args).
  - Each specialist agent has tighter, focused patterns and finds them.

This is a deliberate design choice: a real LLM would behave similarly —
specialists outperform a generalist on niche issues, while the generalist
is cheaper.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass

# (regex, severity, message_template, category)
_RULE = tuple[re.Pattern[str], str, str]


def _r(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE | re.DOTALL | re.MULTILINE)


# Specialist rule sets — each agent is good at its own niche.
_SECURITY_RULES: list[_RULE] = [
    (
        _r(r"f[\"'][^\"']*\{.*\}.*(SELECT|INSERT|UPDATE|DELETE)"),
        "HIGH",
        "f-string interpolated SQL — injection risk; use parameterised query",
    ),
    (
        _r(r"[\"'](SELECT|INSERT|UPDATE|DELETE)[^\"']*[\"']\s*\+\s*\w+"),
        "HIGH",
        "SQL built via string concatenation — injection risk",
    ),
    (
        _r(r"=\s*['\"]sk-[a-z0-9_-]{8,}['\"]"),
        "HIGH",
        "Hard-coded API secret — move to env var or secret manager",
    ),
    (
        _r(r"hashlib\.(md5|sha1)\b.*password|password.*hashlib\.(md5|sha1)\b"),
        "HIGH",
        "Weak hash for password — use bcrypt / argon2",
    ),
    (_r(r"hashlib\.md5\(.*pw"), "HIGH", "Weak hash for password — use bcrypt / argon2"),
]

_LOGIC_RULES: list[_RULE] = [
    (
        _r(r"^\+\s*except:\s*$"),
        "MED",
        "Bare except: swallows BaseException incl. KeyboardInterrupt",
    ),
    (
        _r(r"def\s+\w+\([^)]*=\s*\[\][^)]*\):"),
        "MED",
        "Mutable default argument — shared across calls",
    ),
    (
        _r(r"^\+\s*def\s+first\([^)]*\):\s*\n\+\s*return\s+items\[0\]\s*$"),
        "HIGH",
        "Indexing items[0] without empty-check — IndexError on empty input",
    ),
    (
        _r(r"return\s+\w+\[0\]\s*$"),
        "HIGH",
        "Indexing items[0] without empty-check — IndexError on empty input",
    ),
    (
        _r(r"^\+\s*walk\(n\s*-\s*1\)\s*\n\+\s*if\s+n\s*<="),
        "HIGH",
        "Recursive call before termination check — infinite recursion",
    ),
    (
        _r(r"walk\(n\s*-\s*1\).*\n.*if\s+n\s*<="),
        "HIGH",
        "Recursive call before termination check — infinite recursion",
    ),
]

_PERF_RULES: list[_RULE] = [
    (
        _r(r"for\s+\w+\s+in\s+\w+:\s*\n\s*\+?\s*\w+\.append\(open\("),
        "MED",
        "open() inside a loop — file handles not closed; consider with-statement",
    ),
    (
        _r(r"for\s+\w+\s+in\s+\w+:\s*\n\s*\+?\s*\w+\s*\+=\s*str\("),
        "LOW",
        "String += inside loop is O(n²); use ''.join(...)",
    ),
]

_STYLE_RULES: list[_RULE] = [
    (_r(r"^-.*\"\"\".+\"\"\""), "LOW", "Docstring removed from public function"),
    (_r(r"def\s+\w+\([^)]*\):\s*\n\s*return"), "LOW", "Public function lacks a docstring"),
]

# Single-agent baseline only knows the most obvious checks. This mirrors
# the empirical observation that one fat prompt tends to anchor on the
# loudest signals and miss the niche ones.
_BASELINE_RULES: list[_RULE] = [
    (
        _r(r"[\"'](SELECT|INSERT|UPDATE|DELETE)[^\"']*[\"']\s*\+\s*\w+"),
        "HIGH",
        "SQL built via string concatenation — injection risk",
    ),
    (
        _r(r"f[\"'][^\"']*\{.*\}.*(SELECT|INSERT|UPDATE|DELETE)"),
        "HIGH",
        "f-string interpolated SQL — injection risk; use parameterised query",
    ),
    (_r(r"^\+\s*except:\s*$"), "MED", "Bare except: swallows BaseException"),
    (_r(r"=\s*['\"]sk-[a-z0-9_-]{8,}['\"]"), "HIGH", "Hard-coded API secret"),
    (_r(r"for\s+\w+\s+in\s+\w+:\s*\n\s*\+?\s*\w+\.append\(open\("), "MED", "open() inside a loop"),
    (_r(r"return\s+\w+\[0\]\s*$"), "HIGH", "Indexing items[0] without empty-check"),
]

_AGENT_RULES = {
    "security": _SECURITY_RULES,
    "logic": _LOGIC_RULES,
    "performance": _PERF_RULES,
    "style": _STYLE_RULES,
    "baseline": _BASELINE_RULES,
}


def _emit(agent: str, diff: str) -> list[dict]:
    out: list[dict] = []
    file_match = (
        re.search(r"diff --git a/(\S+) b/\S+", diff)
        or re.search(r"^---\s+(?:a/)?(\S+)", diff, re.MULTILINE)
        or re.search(r"^\+\+\+\s+(?:b/)?(\S+)", diff, re.MULTILINE)
    )
    file_name = file_match.group(1) if file_match else "<unknown>"
    for rx, sev, msg in _AGENT_RULES.get(agent, []):
        if rx.search(diff):
            line_match = re.search(r"@@ -\d+(?:,\d+)? \+(\d+)", diff)
            line = int(line_match.group(1)) if line_match else 1
            out.append(
                {
                    "severity": sev,
                    "file": file_name,
                    "line": line,
                    "message": msg,
                }
            )
    return out


@dataclass
class SmartMockClient:
    """Mock client whose responses depend on diff content."""

    async def complete(self, system: str, user: str, *, agent: str) -> str:
        await asyncio.sleep(0)
        if agent == "synthesizer":
            return "See findings."
        if agent in _AGENT_RULES:
            return json.dumps(_emit(agent, user), ensure_ascii=False)
        return "[]"


def baseline_findings(diff: str) -> list[dict]:
    """Single-agent baseline used by the benchmark."""
    return _emit("baseline", diff)


def all_specialist_findings(diff: str, agents: Iterable[str]) -> list[dict]:
    """For tests — equivalent to running PolyReview's specialist agents."""
    out: list[dict] = []
    for a in agents:
        out.extend(_emit(a, diff))
    return out
