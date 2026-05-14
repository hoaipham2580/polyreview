"""Unified diff parser.

Intentionally hand-written (rather than relying on `unidiff`) so we can keep
the parser deterministic and exercise it with property-based tests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_FILE_HDR_RE = re.compile(r"^diff --git a/(?P<a>.+?) b/(?P<b>.+?)$")
_HUNK_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_len>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_len>\d+))? @@"
)


@dataclass
class DiffChunk:
    """One hunk of changes inside one file."""

    file: str
    old_start: int
    new_start: int
    added: list[tuple[int, str]] = field(default_factory=list)  # (line_no, text)
    removed: list[tuple[int, str]] = field(default_factory=list)
    context: list[tuple[int, str]] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.added and not self.removed

    def render(self) -> str:
        """Reconstruct the chunk roughly as a unified-diff snippet."""
        parts = [f"--- {self.file}"]
        parts += [f"-{txt}" for _, txt in self.removed]
        parts += [f"+{txt}" for _, txt in self.added]
        return "\n".join(parts)


class DiffParser:
    """Parse a unified diff into a list of ``DiffChunk`` objects."""

    def parse(self, diff_text: str) -> list[DiffChunk]:
        chunks: list[DiffChunk] = []
        if not diff_text:
            return chunks

        current_file: str | None = None
        current: DiffChunk | None = None
        new_lineno = 0
        old_lineno = 0

        for raw in diff_text.splitlines():
            if not raw:
                continue

            file_match = _FILE_HDR_RE.match(raw)
            if file_match:
                if current and not current.is_empty:
                    chunks.append(current)
                current_file = file_match.group("b")
                current = None
                continue

            if raw.startswith(("+++", "---", "index ", "new file", "deleted file")):
                continue

            hunk_match = _HUNK_RE.match(raw)
            if hunk_match:
                if current and not current.is_empty:
                    chunks.append(current)
                current = DiffChunk(
                    file=current_file or "<unknown>",
                    old_start=int(hunk_match.group("old_start")),
                    new_start=int(hunk_match.group("new_start")),
                )
                old_lineno = current.old_start
                new_lineno = current.new_start
                continue

            if current is None:
                continue

            if raw.startswith("+"):
                current.added.append((new_lineno, raw[1:]))
                new_lineno += 1
            elif raw.startswith("-"):
                current.removed.append((old_lineno, raw[1:]))
                old_lineno += 1
            elif raw.startswith(" "):
                current.context.append((new_lineno, raw[1:]))
                new_lineno += 1
                old_lineno += 1

        if current and not current.is_empty:
            chunks.append(current)

        return chunks
