"""Unit tests for the diff parser."""

from __future__ import annotations

from polyreview.diff import DiffParser

EXAMPLE = """\
diff --git a/src/auth.py b/src/auth.py
index 1111111..2222222 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -40,3 +40,4 @@ def login(name, pw):
     conn = db()
-    q = "SELECT * FROM u WHERE n='" + name + "'"
+    q = "SELECT * FROM u WHERE n=?"
+    return conn.execute(q, (name,)).fetchone()
diff --git a/src/api.py b/src/api.py
index 3333333..4444444 100644
--- a/src/api.py
+++ b/src/api.py
@@ -16,2 +16,3 @@ def first(items):
-    return items[0]
+    if not items:
+        raise ValueError("empty")
"""


def test_parses_two_files() -> None:
    chunks = DiffParser().parse(EXAMPLE)
    files = sorted({c.file for c in chunks})
    assert files == ["src/api.py", "src/auth.py"]


def test_added_and_removed_lines_classified() -> None:
    chunks = DiffParser().parse(EXAMPLE)
    auth = next(c for c in chunks if c.file == "src/auth.py")
    assert len(auth.removed) == 1
    assert len(auth.added) == 2
    assert "SELECT" in auth.removed[0][1]


def test_empty_input_returns_empty_list() -> None:
    assert DiffParser().parse("") == []


def test_render_round_trip_contains_markers() -> None:
    chunks = DiffParser().parse(EXAMPLE)
    rendered = chunks[0].render()
    assert "+" in rendered
    assert "-" in rendered
