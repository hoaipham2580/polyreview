"""Property-based tests for DiffParser & Finding deduplication.

We assert structural invariants the parser must always satisfy, no matter
what randomly-generated diff we feed it. This catches regressions that
hand-written examples typically miss.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from polyreview.diff import DiffParser
from polyreview.models import Finding, Severity

# Build a syntactically valid hunk from random ints + lines.
_safe_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\n\r"),
    min_size=0,
    max_size=40,
)


@st.composite
def random_diff(draw: st.DrawFn) -> str:
    n_files = draw(st.integers(min_value=1, max_value=3))
    parts: list[str] = []
    for i in range(n_files):
        fname = f"src/f{i}.py"
        added_lines = draw(st.lists(_safe_text, min_size=0, max_size=4))
        removed_lines = draw(st.lists(_safe_text, min_size=0, max_size=4))
        if not added_lines and not removed_lines:
            removed_lines = ["pass"]
        old_len = max(1, len(removed_lines))
        new_len = max(1, len(added_lines))
        parts.append(f"diff --git a/{fname} b/{fname}")
        parts.append(f"--- a/{fname}")
        parts.append(f"+++ b/{fname}")
        parts.append(f"@@ -1,{old_len} +1,{new_len} @@")
        parts.extend(f"-{line}" for line in removed_lines)
        parts.extend(f"+{line}" for line in added_lines)
    return "\n".join(parts) + "\n"


@given(random_diff())
@settings(max_examples=80, deadline=None)
def test_parser_never_raises(diff_text: str) -> None:
    """The parser must be total: any input → list[DiffChunk]."""
    chunks = DiffParser().parse(diff_text)
    assert isinstance(chunks, list)


@given(random_diff())
@settings(max_examples=80, deadline=None)
def test_each_chunk_has_at_least_one_change(diff_text: str) -> None:
    for c in DiffParser().parse(diff_text):
        assert c.added or c.removed


@given(random_diff())
@settings(max_examples=80, deadline=None)
def test_added_lines_have_monotonic_line_numbers(diff_text: str) -> None:
    for c in DiffParser().parse(diff_text):
        nums = [n for n, _ in c.added]
        assert nums == sorted(nums)


# ---- Finding.key() de-duplication property -----------------------------

_finding = st.builds(
    Finding,
    agent=st.sampled_from(["security", "performance", "style", "logic"]),
    severity=st.sampled_from(list(Severity)),
    file=st.sampled_from(["a.py", "b.py", "c.py"]),
    line=st.integers(min_value=0, max_value=200),
    message=st.text(
        alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\n\r"),
        min_size=1,
        max_size=80,
    ),
)


@given(st.lists(_finding, min_size=0, max_size=20))
@settings(max_examples=80, deadline=None)
def test_dedup_by_key_is_idempotent(items: list[Finding]) -> None:
    seen: set = set()
    out: list[Finding] = []
    for f in items:
        k = f.key()
        if k in seen:
            continue
        seen.add(k)
        out.append(f)
    # Property: dedup again yields the same list.
    seen2: set = set()
    out2: list[Finding] = []
    for f in out:
        k = f.key()
        if k in seen2:
            continue
        seen2.add(k)
        out2.append(f)
    assert [f.key() for f in out] == [f.key() for f in out2]
